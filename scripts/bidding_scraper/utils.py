# coding=utf-8
"""工具函数模块"""

import random
import re
import time
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)


def get_random_user_agent() -> str:
    """获取随机User-Agent"""
    config = Config.get_instance()
    user_agents = config.get_user_agents()
    if not user_agents:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ]
    return random.choice(user_agents)


def make_headers(referer: str = "") -> dict:
    """生成请求头"""
    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
    reraise=True
)
def fetch_page(
    url: str,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
    method: str = "GET",
    headers: Optional[dict] = None,
    referer: str = "",
    timeout: int = 30,
    encoding: Optional[str] = None,
    proxies: Optional[dict] = None,
    raw: bool = False,
    session: Optional[requests.Session] = None,
):
    """
    获取页面内容，支持自动重试

    Args:
        url: 请求URL
        params: GET参数
        data: POST数据
        method: 请求方法（GET/POST）
        headers: 自定义请求头，会与默认请求头合并
        referer: Referer头
        timeout: 超时时间
        encoding: 强制编码
        proxies: 代理配置，None或空字典则禁用代理
        raw: 是否返回原始文本（True返回str，False返回BeautifulSoup）
        session: 可选的 requests.Session 对象，用于保持Cookie会话

    Returns:
        BeautifulSoup对象或原始文本字符串，失败返回None
    """
    config = Config.get_instance()
    timeout = timeout or config.get_int("request.timeout", 30)

    # 构建请求头：默认头 + 自定义头（自定义头优先）
    req_headers = make_headers(referer)
    if headers:
        req_headers.update(headers)

    # 处理代理：None或空字典则禁用代理
    req_proxies = proxies if proxies else {'http': None, 'https': None}

    try:
        # 使用 session（如果提供）以保持 Cookie 连续性
        requester = session if session else requests
        if method.upper() == "POST":
            resp = requester.post(url, data=data, headers=req_headers, timeout=timeout, proxies=req_proxies)
        else:
            resp = requester.get(url, params=params, headers=req_headers, timeout=timeout, proxies=req_proxies)

        resp.raise_for_status()

        if encoding:
            resp.encoding = encoding
        elif resp.apparent_encoding:
            resp.encoding = resp.apparent_encoding

        if raw:
            return resp.text

        return BeautifulSoup(resp.text, "html.parser")

    except requests.exceptions.Timeout:
        logger.warning(f"请求超时: {url}")
        raise
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP错误 {e.response.status_code}: {url}")
        raise
    except Exception as e:
        logger.error(f"请求失败 {url}: {e}")
        raise


def create_session(
    proxy_url: str = "",
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (500, 502, 503, 504),
) -> requests.Session:
    """
    创建一个带有重试适配器和浏览器级默认头的 requests.Session

    用于需要 Cookie 持久化的爬虫（如需要先访问搜索页获取 CSRF Token）。

    Args:
        proxy_url: 代理 URL（如 "http://proxy:8080"），空字符串表示不使用代理
        retries: 重试次数
        backoff_factor: 退避因子（重试间隔 = backoff_factor * (2^(retry-1)) 秒）
        status_forcelist: 需要重试的 HTTP 状态码

    Returns:
        配置好的 requests.Session 实例
    """
    session = requests.Session()

    # 配置重试适配器
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 设置浏览器级默认头
    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
    })

    # 配置代理（优先级低于 fetch_page 的 proxies 参数）
    if proxy_url:
        session.proxies = {"http": proxy_url, "https": proxy_url}
    else:
        # 从环境变量/配置读取
        from .config import Config
        config = Config.get_instance()
        proxies = config.get_proxies()
        if proxies:
            session.proxies = proxies

    return session


def random_delay(min_seconds: float = 1, max_seconds: float = 3):
    """随机延迟"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def extract_date(text: str) -> Optional[str]:
    """从文本中提取日期（YYYY-MM-DD格式）"""
    # 匹配 YYYY-MM-DD 格式
    patterns = [
        r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
        r"(\d{4}\.\d{1,2}\.\d{1,2})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            # 标准化日期格式
            date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-").replace(".", "-")
            # 补零
            parts = date_str.split("-")
            if len(parts) == 3:
                try:
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                    return f"{year:04d}-{month:02d}-{day:02d}"
                except ValueError:
                    continue
    
    return None


def clean_text(text: str) -> str:
    """清理文本内容"""
    if not text:
        return ""
    # 移除多余空白
    text = re.sub(r"\s+", " ", text)
    # 移除特殊字符
    text = text.replace("\u3000", " ")  # 全角空格
    return text.strip()


def contains_any(text: str, keywords: List[str]) -> bool:
    """检查文本是否包含任一关键词"""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def extract_region(text: str, region_keywords: List[str]) -> Optional[str]:
    """从文本中提取地区信息"""
    if not text:
        return None
    
    for kw in region_keywords:
        if kw in text:
            return kw
    
    return None


def truncate_text(text: str, max_length: int = 200) -> str:
    """截断文本"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length] + "..."
