# coding=utf-8
"""
招标信息爬虫 - 生成 RSS feed
爬取多个招标网站，过滤云南铁塔相关招标公告，输出标准 RSS XML

修复说明：
1. should_include() 现在正确使用关键词过滤（核心词 + 地区+行业组合）
2. 中国政府采购网改用搜索 API，按关键词精准检索
3. 中国采购与招标网修正 CSS 选择器（ul.as-pager-body）
4. 移除已失效的中国招标投标公共服务平台（API 返回 HTML 而非 JSON）
5. 云南省公共资源交易中心 API 结果现在会经过关键词过滤

用法：
    python scripts/bidding_scraper.py
    python scripts/bidding_scraper.py --output output/bidding_feed.xml
    python scripts/bidding_scraper.py --dry-run   # 只打印结果，不写文件
"""

import argparse
import hashlib
import random
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

import requests

# 修复 Windows GBK 终端 print 乱码：强制 stdout 使用 utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────
# 过滤关键词配置（分组）
# ─────────────────────────────────────────────────────────────

# 核心关键词 —— 标题或描述必须包含其中至少一个，或者满足「地区 + 行业」组合
CORE_KEYWORDS = [
    # 铁塔直接相关
    "铁塔", "钢管塔", "角钢塔", "格构式铁塔",
    "通信铁塔", "输电铁塔", "电力铁塔", "广播电视塔",
    "塔材", "塔架", "塔身", "塔基", "塔桅",
    "铁塔制造", "铁塔加工", "铁塔生产", "铁塔安装",
    "铁塔工程", "铁塔项目", "铁塔供货",
    "中国铁塔", "铁塔公司",
    "5G铁塔", "基站铁塔",
    "线路铁塔",
    # 塔桅相关（广播电视塔、通信塔等）
    "塔桅", "桅杆", "发射塔", "转播塔",
]

# 地区关键词
REGION_KEYWORDS = [
    "云南", "昆明", "大理", "丽江", "西双版纳", "曲靖",
    "玉溪", "保山", "昭通", "楚雄", "红河", "文山",
    "普洱", "临沧", "德宏", "怒江", "迪庆",
    "滇中", "滇西", "滇东", "滇南", "滇北",
]

# 行业关键词（与地区关键词组合使用）
INDUSTRY_KEYWORDS = [
    # 电力工程
    "输电线路", "输变电", "变电站", "换流站",
    "电力工程", "电网工程", "电力建设",
    "国家电网", "南方电网", "云南电网", "云南电力",
    "特高压", "超高压", "高压线路",
    "电力铁塔",
    # 通信基础设施
    "通信工程", "基站建设", "5G建设",
    "通信设备采购",
    # 钢结构
    "钢结构", "钢构件", "热镀锌", "防腐处理",
    "角钢", "钢管", "型钢",
    "钢结构工程", "钢结构制作", "钢结构安装",
]

# 保留兼容：合并所有白名单词（供外部引用）
INCLUDE_KEYWORDS = CORE_KEYWORDS + REGION_KEYWORDS + INDUSTRY_KEYWORDS

# 包含以下词则排除（中标公告、非招标内容）
EXCLUDE_KEYWORDS = [
    "中标公告", "中标结果", "成交公告", "成交结果",
    "中标候选人公示", "中标候选人",
    "招聘", "求职", "人才", "岗位",
    "拍卖", "出让", "转让",
]

# ─────────────────────────────────────────────────────────────
# User-Agent 池
# ─────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def make_headers(referer: str = "") -> dict:
    headers = {
        "User-Agent": random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        # 不设置 Accept-Encoding，让 requests 自动处理解压
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────

@dataclass
class BiddingItem:
    title: str
    url: str
    pub_date: str          # RFC 2822 格式，用于 RSS
    pub_date_raw: str      # 原始日期字符串，用于显示
    source: str            # 来源网站名称
    description: str = ""

    @property
    def guid(self) -> str:
        return hashlib.md5(self.url.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# 网站爬虫配置
# ─────────────────────────────────────────────────────────────

@dataclass
class SiteConfig:
    name: str
    url: str
    # 多组选择器，按优先级尝试，第一组命中即用
    list_selectors: List[str]       # 列表容器选择器
    item_selectors: List[str]       # 单条目选择器（在容器内）
    title_selectors: List[str]      # 标题选择器（在条目内）
    link_selectors: List[str]       # 链接选择器（在条目内，取 href）
    date_selectors: List[str]       # 日期选择器（在条目内）
    desc_selectors: List[str] = field(default_factory=list)  # 描述选择器（在条目内）
    base_url: str = ""              # 相对链接补全用
    encoding: str = "utf-8"
    extra_params: Dict = field(default_factory=dict)


SITES: List[SiteConfig] = [
    SiteConfig(
        # chinabidding.com 搜索结果页：POST /search/proj.htm?fullText=铁塔
        # HTML: <ul class="as-pager-body"><li><a class="as-pager-item" href="/bidDetail/xxx">
        #         <h5 class="as-p-tit"><span class="txt" title="完整标题">...</span>
        #             <span class="time">发布时间：2026-05-11</span></h5>
        #       </a></li></ul>
        name="中国采购与招标网",
        url="https://www.chinabidding.com/search/proj.htm",
        base_url="https://www.chinabidding.com",
        list_selectors=["ul.as-pager-body"],
        item_selectors=["li"],
        title_selectors=["h5 span.txt", "h5.as-p-tit"],
        link_selectors=["a.as-pager-item"],
        date_selectors=["span.time"],
        desc_selectors=["p.as-p-desc", "div.as-p-desc", "span.as-p-desc", "p"],  # 描述选择器
        encoding="utf-8",
        extra_params={"post_data": {"fullText": "铁塔", "poClass": "BidNotice"}},  # 只搜索铁塔，后续过滤云南
    ),
]


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

def fetch_page(url: str, referer: str = "", timeout: int = 20, encoding: str = "utf-8",
               post_data: Optional[Dict] = None,
               params: Optional[Dict] = None) -> Optional[BeautifulSoup]:
    """抓取页面，返回 BeautifulSoup 对象，失败返回 None。post_data 非空时使用 POST。"""
    try:
        if post_data:
            resp = requests.post(
                url,
                data=post_data,
                headers=make_headers(referer),
                timeout=timeout,
                allow_redirects=True,
                proxies={"http": None, "https": None},
            )
        else:
            resp = requests.get(
                url,
                params=params,
                headers=make_headers(referer),
                timeout=timeout,
                allow_redirects=True,
                proxies={"http": None, "https": None},  # 禁用系统代理
            )
        resp.raise_for_status()
        # 优先使用配置编码，避免 apparent_encoding 误判（如 GBK 页面被误判为 utf-8）
        resp.encoding = encoding
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"  [错误] 请求失败 {url}: {e}")
        return None


def normalize_url(href: str, base_url: str) -> str:
    """补全相对链接"""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base_url.rstrip("/") + href
    return base_url.rstrip("/") + "/" + href


def parse_date(date_str: str) -> str:
    """
    将各种日期格式转为 RFC 2822（RSS 标准格式）
    支持：2024-05-10、2024/05/10、2024年05月10日 等
    """
    if not date_str:
        return formatdate(usegmt=True)

    date_str = date_str.strip()
    # 提取数字日期部分（支持 2024-05-10、2024/05/10、2024年05月10日、20240510 等）
    match = re.search(r"(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})", date_str)
    if not match:
        # 尝试 YYYYMMDD 紧凑格式（如 URL 中的 t20260512_）
        m2 = re.search(r"(\d{4})(\d{2})(\d{2})", date_str)
        if m2:
            match = m2
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            dt = datetime(y, m, d, 8, 0, 0, tzinfo=timezone(timedelta(hours=8)))
            return formatdate(dt.timestamp(), usegmt=False)
        except ValueError:
            pass
    return formatdate(usegmt=True)


def contains_keyword(text: str, keywords: List[str]) -> bool:
    return any(kw in text for kw in keywords)


def fetch_detail_content(url: str, timeout: int = 15) -> str:
    """
    获取招标详情页的正文内容，用于提取地区信息。
    返回提取的文本内容，失败返回空字符串。
    """
    if not url or not url.startswith("http"):
        return ""
    
    try:
        resp = requests.get(
            url,
            headers=make_headers(),
            timeout=timeout,
            allow_redirects=True,
            proxies={"http": None, "https": None},
        )
        resp.raise_for_status()
        # 尝试多种编码
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 移除脚本和样式
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()
        
        # 尝试常见的内容容器选择器
        content_selectors = [
            "div.content", "div.detail-content", "div.article-content",
            "div.main-content", "div#content", "div.container",
            "article", "main", "div.text", "div.description",
        ]
        
        content_text = ""
        for selector in content_selectors:
            content_el = soup.select_one(selector)
            if content_el:
                content_text = content_el.get_text(separator=" ", strip=True)
                break
        
        # 如果没找到特定容器，获取 body 文本
        if not content_text:
            body = soup.find("body")
            if body:
                content_text = body.get_text(separator=" ", strip=True)
        
        # 限制长度，避免过长
        return content_text[:5000] if content_text else ""
        
    except Exception as e:
        print(f"  [警告] 获取详情页失败 {url}: {e}")
        return ""


def extract_region_from_content(content: str) -> str:
    """
    从正文内容中提取地区信息。
    返回找到的地区关键词，未找到返回空字符串。
    """
    if not content:
        return ""
    
    # 常见的地区信息模式
    patterns = [
        r"项目所在地区[：:]\s*([^\n,，。]+)",
        r"所在地区[：:]\s*([^\n,，。]+)",
        r"地区[：:]\s*([^\n,，。]+)",
        r"建设地点[：:]\s*([^\n,，。]+)",
        r"项目地点[：:]\s*([^\n,，。]+)",
        r"工程地点[：:]\s*([^\n,，。]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            location = match.group(1).strip()
            # 检查是否包含云南相关关键词
            for kw in REGION_KEYWORDS:
                if kw in location:
                    return kw
    
    # 直接检查内容中是否包含地区关键词
    for kw in REGION_KEYWORDS:
        if kw in content:
            return kw
    
    return ""


def should_include_with_detail(title: str, url: str, description: str = "", 
                               require_yunnan: bool = True, 
                               fetch_detail: bool = True) -> Tuple[bool, str]:
    """
    判断标题是否应该保留，支持访问详情页提取地区信息。
    
    返回：(是否保留, 提取到的地区信息)
    
    过滤逻辑：
      1. 标题必须非空且长度 >= 5
      2. 标题或描述必须匹配至少一个核心关键词（铁塔相关）
      3. 如果 require_yunnan=True，检查标题/描述/正文中的地区信息
      4. 不能匹配任何排除关键词
    """
    if not title or len(title) < 5:
        return False, ""

    # 合并标题和描述用于检查
    full_text = title + " " + description

    # 黑名单排除（只检查标题）
    if contains_keyword(title, EXCLUDE_KEYWORDS):
        return False, ""

    # 必须有核心关键词（铁塔相关）- 检查标题和描述
    has_core_keyword = contains_keyword(full_text, CORE_KEYWORDS)
    if not has_core_keyword:
        # 如果没有核心关键词，检查地区+行业组合
        has_region = contains_keyword(full_text, REGION_KEYWORDS)
        has_industry = contains_keyword(full_text, INDUSTRY_KEYWORDS)
        if not (has_region and has_industry):
            return False, ""

    # 地区过滤
    if require_yunnan:
        # 先检查标题和描述中是否有地区信息
        if contains_keyword(full_text, REGION_KEYWORDS):
            return True, "标题/描述中包含地区"
        
        # 如果标题/描述中没有地区信息，且允许访问详情页
        if fetch_detail and url:
            print(f"    [正文检查] 标题无地区信息，获取详情页...")
            detail_content = fetch_detail_content(url)
            if detail_content:
                region = extract_region_from_content(detail_content)
                if region:
                    print(f"    [正文检查] 从正文中提取到地区: {region}")
                    return True, region
                else:
                    print(f"    [正文检查] 正文中未找到云南地区信息")
        
        # 没有找到地区信息，排除
        return False, ""

    return True, ""


def should_include(title: str, description: str = "", require_yunnan: bool = True) -> bool:
    """
    判断标题是否应该保留。
    过滤逻辑：
      1. 标题必须非空且长度 >= 5
      2. 标题或描述必须匹配至少一个核心关键词（铁塔相关）
      3. 如果 require_yunnan=True，标题或描述必须包含云南地区关键词
      4. 不能匹配任何排除关键词
    
    参数：
      title: 标题文本
      description: 描述/详情文本（可选，用于检查地区信息）
      require_yunnan: 是否强制要求云南地区
    """
    if not title or len(title) < 5:
        return False

    # 合并标题和描述用于检查
    full_text = title + " " + description

    # 黑名单排除（只检查标题）
    if contains_keyword(title, EXCLUDE_KEYWORDS):
        return False

    # 必须有核心关键词（铁塔相关）- 检查标题和描述
    if not contains_keyword(full_text, CORE_KEYWORDS):
        # 如果没有核心关键词，检查地区+行业组合
        has_region = contains_keyword(full_text, REGION_KEYWORDS)
        has_industry = contains_keyword(full_text, INDUSTRY_KEYWORDS)
        if not (has_region and has_industry):
            return False

    # 地区过滤：必须包含云南相关关键词 - 检查标题和描述
    if require_yunnan:
        if not contains_keyword(full_text, REGION_KEYWORDS):
            return False

    return True


def extract_text(element) -> str:
    """提取元素文本，清理空白和无效替换字符"""
    if element is None:
        return ""
    text = re.sub(r"\s+", " ", element.get_text()).strip()
    # 去除 GBK 解码失败产生的替换字符
    return text.replace("", "")


# ─────────────────────────────────────────────────────────────
# 核心解析逻辑
# ─────────────────────────────────────────────────────────────

def try_selectors(soup_or_element, selectors: List[str]):
    """按优先级尝试多个选择器，返回第一个命中的结果列表"""
    for sel in selectors:
        try:
            results = soup_or_element.select(sel)
            if results:
                return results
        except Exception:
            continue
    return []


def parse_site(site: SiteConfig, enable_detail_check: bool = False) -> List[BiddingItem]:
    """
    爬取单个网站，返回过滤后的招标条目
    
    参数：
      site: 网站配置
      enable_detail_check: 是否启用详情页正文检查（用于标题无地区信息时检查正文）
    """
    print(f"\n[{site.name}] 开始抓取: {site.url}")
    post_data = site.extra_params.get("post_data") if site.extra_params else None
    soup = fetch_page(site.url, encoding=site.encoding, post_data=post_data)
    if not soup:
        return []

    items = []

    # 尝试找到列表容器
    containers = try_selectors(soup, site.list_selectors)
    if not containers:
        # 降级：直接在整个页面找条目
        print(f"  [警告] 未找到列表容器，尝试全页面解析")
        containers = [soup]

    for container in containers[:1]:  # 只取第一个容器
        raw_items = try_selectors(container, site.item_selectors)
        if not raw_items:
            raw_items = try_selectors(soup, site.item_selectors)

        print(f"  找到 {len(raw_items)} 个原始条目")

        for raw in raw_items:
            # 提取标题
            title_els = try_selectors(raw, site.title_selectors)
            if not title_els:
                continue
            title = extract_text(title_els[0])
            if not title:
                continue

            # 清理标题中的标签前缀（如 [招标公告]）
            title = re.sub(r"^\[.*?\]", "", title).strip()

            # 提取描述/摘要（用于地区检查）
            desc_els = try_selectors(raw, site.desc_selectors) if hasattr(site, 'desc_selectors') else []
            desc = extract_text(desc_els[0]) if desc_els else ""
            
            # 提取链接（需要在过滤前提取，用于详情页检查）
            link_els = try_selectors(raw, site.link_selectors)
            href = ""
            if link_els:
                href = link_els[0].get("href", "")
            if not href:
                # 尝试从标题元素本身取链接
                href = title_els[0].get("href", "") if title_els[0].name == "a" else ""
            if not href:
                # 尝试从 li 的父 a 元素取链接（chinabidding 结构）
                parent_a = raw.find_parent("a") or raw.find("a")
                if parent_a:
                    href = parent_a.get("href", "")
            url = normalize_url(href, site.base_url) if href else site.url

            # 过滤
            if enable_detail_check:
                # 启用详情页检查：对于标题无地区信息的条目，访问详情页检查正文
                included, region_info = should_include_with_detail(title, url, desc, require_yunnan=True, fetch_detail=True)
                if not included:
                    continue
                # 如果从详情页提取到地区信息，添加到描述中
                if region_info and region_info not in desc:
                    desc = f"{desc} [正文地区:{region_info}]".strip()
            else:
                # 普通过滤：不访问详情页
                if not should_include(title, desc):
                    continue

            # 提取日期：先找 span，找不到则从 URL 中提取（如 t20260512_ 格式）
            date_els = try_selectors(raw, site.date_selectors)
            date_raw = extract_text(date_els[0]) if date_els else ""
            if not date_raw:
                # 从 href 中提取 YYYYMMDD
                m = re.search(r"(\d{4})(\d{2})(\d{2})", href)
                date_raw = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}" if m else ""
            # 清理日期文本中的前缀（如 "发布时间："）
            date_raw = re.sub(r"^[^0-9]*", "", date_raw)
            pub_date = parse_date(date_raw)

            # 构建描述
            if not desc:
                desc = f"来源：{site.name} 发布时间：{date_raw or '未知'}"
            else:
                desc = f"来源：{site.name} {desc}"

            items.append(BiddingItem(
                title=title,
                url=url,
                pub_date=pub_date,
                pub_date_raw=date_raw or "未知日期",
                source=site.name,
                description=desc,
            ))

    print(f"  过滤后保留 {len(items)} 条招标信息")
    return items


# ─────────────────────────────────────────────────────────────
# 中国政府采购网 搜索 API 专用爬取
# ─────────────────────────────────────────────────────────────

CCGP_SEARCH_URL = "http://search.ccgp.gov.cn/bxsearch"


def fetch_ccgp_search(keyword: str, start_time: str = "", end_time: str = "",
                      page_index: int = 1, display_zone: str = "云南", zone_id: str = "53") -> List[BiddingItem]:
    """
    通过中国政府采购网搜索 API 获取招标公告。
    搜索地址: http://search.ccgp.gov.cn/bxsearch
    
    参数：
      keyword: 搜索关键词
      start_time: 开始时间，格式 YYYY:MM:DD
      end_time: 结束时间，格式 YYYY:MM:DD
      page_index: 页码
      display_zone: 地区名称，如"云南"
      zone_id: 地区 ID，云南省为 53
    """
    from datetime import datetime as dt
    if not end_time:
        end_time = dt.now().strftime("%Y:%m:%d")
    if not start_time:
        start_time = (dt.now() - timedelta(days=7)).strftime("%Y:%m:%d")

    params = {
        "searchtype": 1,
        "page_index": page_index,
        "bidSort": 0,
        "buyerName": "",
        "projectId": "",
        "pinMu": 0,
        "bidType": 1,  # 1=招标公告
        "dbselect": "bidx",
        "kw": keyword,
        "start_time": start_time,
        "end_time": end_time,
        "timeType": 2,
        "displayZone": display_zone,  # 地区名称
        "zoneId": zone_id,            # 地区 ID（云南省=53）
        "pppStatus": 0,
        "agentName": "",
    }

    zone_info = f"{display_zone}(zoneId={zone_id})" if display_zone else "全国"
    print(f"\n[中国政府采购网] 搜索关键词: {keyword}, 地区: {zone_info}")
    soup = fetch_page(CCGP_SEARCH_URL, params=params,
                      referer="http://www.ccgp.gov.cn/")
    if not soup:
        return []

    items = []

    # 搜索结果列表
    result_items = soup.select("ul.vT-srch-result-list-bid li")
    if not result_items:
        result_items = soup.select("ul.vT-srch-result-list li")

    print(f"  找到 {len(result_items)} 个搜索结果")

    for li in result_items:
        a_tag = li.find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        if not title:
            continue

        # 清理标题
        title = re.sub(r"^\[.*?\]", "", title).strip()

        # 提取描述/摘要（用于地区检查）
        desc_tag = li.select_one("p") or li.select_one("span.desc") or li.select_one("div.desc")
        desc = extract_text(desc_tag) if desc_tag else ""

        # 过滤：由于已通过 URL 参数限制地区为云南，这里不再强制要求地区关键词
        # require_yunnan=False 表示不强制要求地区关键词（网站已做地区过滤）
        if not should_include(title, desc, require_yunnan=False):
            continue

        href = a_tag.get("href", "")
        url = normalize_url(href, "http://www.ccgp.gov.cn")

        # 提取日期
        date_span = li.select_one("span.date") or li.select_one("span")
        date_raw = ""
        if date_span:
            date_raw = extract_text(date_span)
            # 提取日期部分
            m = re.search(r"(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})", date_raw)
            if m:
                date_raw = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
            else:
                date_raw = ""

        pub_date = parse_date(date_raw)

        # 构建描述
        if not desc:
            desc = f"来源：中国政府采购网 发布时间：{date_raw or '未知'}"
        else:
            desc = f"来源：中国政府采购网 {desc}"

        items.append(BiddingItem(
            title=title,
            url=url,
            pub_date=pub_date,
            pub_date_raw=date_raw or "未知日期",
            source="中国政府采购网",
            description=desc,
        ))

    print(f"  过滤后保留 {len(items)} 条招标信息")
    return items


def fetch_ccgp() -> List[BiddingItem]:
    """爬取中国政府采购网，使用多个关键词搜索"""
    all_items: List[BiddingItem] = []
    # 搜索关键词：铁塔相关（后续通过 should_include 过滤云南地区）
    keywords = [
        "铁塔",
        "中国铁塔",
        "通信铁塔",
        "塔桅",
    ]

    for i, kw in enumerate(keywords):
        if i > 0:
            time.sleep(random.randint(3, 6))
        try:
            items = fetch_ccgp_search(kw)
            all_items.extend(items)
        except Exception as e:
            print(f"  [错误] 中国政府采购网搜索 '{kw}' 失败: {e}")

    # 去重（按 URL）
    seen_urls = set()
    unique_items = []
    for item in all_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique_items.append(item)

    return unique_items


# ─────────────────────────────────────────────────────────────
# RSS 生成
# ─────────────────────────────────────────────────────────────

RSS_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>云南铁塔制造招标信息</title>
    <link>https://github.com</link>
    <description>聚合云南地区铁塔制造相关招标公告，来源：中国政府采购网、云南省公共资源交易中心、中国采购与招标网、乙方宝</description>
    <language>zh-cn</language>
    <lastBuildDate>{build_date}</lastBuildDate>
    <ttl>1440</ttl>
{items}
  </channel>
</rss>"""

ITEM_TEMPLATE = """\
    <item>
      <title>{title}</title>
      <link>{url}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{description}</description>
      <source url="{source_url}">{source}</source>
    </item>"""


def build_rss(items: List[BiddingItem]) -> str:
    item_xmls = []
    for item in items:
        item_xmls.append(ITEM_TEMPLATE.format(
            title=escape(item.title),
            url=escape(item.url),
            guid=item.guid,
            pub_date=item.pub_date,
            description=escape(item.description),
            source=escape(item.source),
            source_url=escape(item.url),
        ))
    return RSS_TEMPLATE.format(
        build_date=formatdate(usegmt=True),
        items="\n".join(item_xmls),
    )


# ─────────────────────────────────────────────────────────────
# 云南省公共资源交易中心 专用 API 爬取
# ─────────────────────────────────────────────────────────────

YNGGZY_API = "https://ggzy.yn.gov.cn/ynggfwpt-home-api/jyzyCenter/jyInfo/gcjs/getZbggList"
YNGGZY_DETAIL_BASE = "https://ggzy.yn.gov.cn/tradeHall/tradeDetail"

# 工程建设各类型接口（zfcg 接口不存在，只保留 gcjs）
YNGGZY_TRADE_TYPES = [
    ("gcjs", "工程建设"),
]


def fetch_ynggzy_api(trade_type: str, page: int = 1, page_size: int = 20) -> List[BiddingItem]:
    """调用云南省公共资源交易中心 JSON API
    
    注意：该网站本身全是云南省的信息，因此只需匹配铁塔关键词，无需再检查地区
    """
    api_url = f"https://ggzy.yn.gov.cn/ynggfwpt-home-api/jyzyCenter/jyInfo/{trade_type}/getZbggList"
    payload = {
        "pageNum": page,
        "pageSize": page_size,
        "bulletintype": "1",   # 1=招标公告
    }
    headers = {
        "User-Agent": random_ua(),
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://ggzy.yn.gov.cn/",
        "Origin": "https://ggzy.yn.gov.cn",
    }
    items = []
    try:
        resp = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=20,
            proxies={"http": None, "https": None},
        )
        resp.raise_for_status()
        data = resp.json()

        # 响应结构：{"code":"1","value":{"list":[...]}} 或其他变体
        rows = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = (
                data.get("value", {}).get("list", [])
                or data.get("value", {}).get("rows", [])
                or data.get("data", {}).get("list", [])
                or data.get("data", {}).get("rows", [])
                or data.get("rows", [])
                or data.get("list", [])
                or []
            )

        print(f"  [云南公共资源] {trade_type} 获取 {len(rows)} 条")

        for row in rows:
            title = row.get("bulletinname", "").strip()
            if not title:
                continue

            # 提取地区信息作为描述（仅用于展示，不用于过滤）
            area = row.get("jyptid", "") or row.get("areaName", "")
            desc = f"地区：{area}"

            # 关键词过滤：该网站本身全是云南省信息，只需匹配铁塔关键词，无需检查地区
            # require_yunnan=False 表示不强制要求地区关键词
            if not should_include(title, desc, require_yunnan=False):
                continue

            guid = row.get("guid", "")
            trade_t = row.get("tradeType", trade_type)
            detail_url = f"{YNGGZY_DETAIL_BASE}?guid={guid}&tradeType={trade_t}" if guid else YNGGZY_API

            date_raw = row.get("bulletinissuetime", "") or row.get("createTime", "")
            pub_date = parse_date(date_raw)

            # 构建完整描述
            desc = f"来源：云南省公共资源交易中心 地区：{area} 发布时间：{date_raw}"

            items.append(BiddingItem(
                title=title,
                url=detail_url,
                pub_date=pub_date,
                pub_date_raw=date_raw or "未知日期",
                source="云南省公共资源交易中心",
                description=desc,
            ))

    except Exception as e:
        print(f"  [云南公共资源] {trade_type} 请求失败: {e}")

    return items


def fetch_ynggzy() -> List[BiddingItem]:
    """爬取云南省公共资源交易中心所有类型招标公告"""
    print(f"\n[云南省公共资源交易中心] 开始抓取 API")
    all_items: List[BiddingItem] = []
    for trade_type, type_name in YNGGZY_TRADE_TYPES:
        items = fetch_ynggzy_api(trade_type)
        all_items.extend(items)
        if len(YNGGZY_TRADE_TYPES) > 1:
            time.sleep(random.randint(3, 8))
    print(f"  过滤后保留 {len(all_items)} 条招标信息")
    return all_items


# ─────────────────────────────────────────────────────────────
# 全国招标采购信息平台（乙方宝）爬取
# ─────────────────────────────────────────────────────────────

YFBZB_SEARCH_URL = "https://www.yfbzb.com/search/invitedBidSearch"
# 云南省的 provinceId（需要通过实际请求确认）
YFBZB_YUNNAN_PROVINCE_ID = "2358"  # 暂定，可能需要调整


def fetch_yfbzb_search(keyword: str, province_id: str = "", page_no: int = 1, page_size: int = 20) -> List[BiddingItem]:
    """
    通过乙方宝搜索 API 获取招标公告。
    
    参数：
      keyword: 搜索关键词
      province_id: 省份 ID（为空则全国）
      page_no: 页码
      page_size: 每页大小
    """
    params = {
        "defaultSearch": "true",
        "keyword": keyword,
        "pageNo": page_no,
        "pageSize": page_size,
    }
    if province_id:
        params["provinceId"] = province_id

    province_info = f"省份ID={province_id}" if province_id else "全国"
    print(f"\n[乙方宝] 搜索关键词: {keyword}, 地区: {province_info}")
    
    soup = fetch_page(YFBZB_SEARCH_URL, params=params,
                      referer="https://www.yfbzb.com/")
    if not soup:
        return []

    items = []

    # 乙方宝搜索结果在表格中
    table = soup.select_one("table")
    if not table:
        print("  [警告] 未找到表格")
        return []
    
    rows = table.select("tbody tr")
    print(f"  找到 {len(rows)} 个搜索结果")

    for row in rows:
        # 提取标题和链接
        title_td = row.select_one("td:first-child")
        if not title_td:
            continue
        
        a_tag = title_td.find("a")
        if not a_tag:
            continue

        title = a_tag.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        # 清理标题
        title = re.sub(r"^\[.*?\]", "", title).strip()

        # 提取地区（第3列）
        area_td = row.select_one("td:nth-child(3)")
        area = area_td.get_text(strip=True) if area_td else ""
        
        # 提取描述（包含地区信息）
        desc = f"地区：{area}" if area else ""

        # 过滤：检查标题和地区
        # 如果指定了省份ID，网站已经做了地区过滤，只需检查铁塔关键词
        # 如果没有指定省份ID，需要检查地区是否包含云南
        if province_id:
            # 网站已做地区过滤，只需匹配铁塔关键词
            if not should_include(title, desc, require_yunnan=False):
                continue
        else:
            # 需要检查地区是否包含云南
            # 由于乙方宝是全国性网站，需要检查地区信息
            if not should_include(title, desc, require_yunnan=True):
                continue

        href = a_tag.get("href", "")
        url = normalize_url(href, "https://www.yfbzb.com")

        # 提取日期（第4列）
        date_td = row.select_one("td:nth-child(4)")
        date_raw = ""
        if date_td:
            date_raw = date_td.get_text(strip=True)
            # 提取日期部分
            m = re.search(r"(\d{4})[.\-/年](\d{1,2})[.\-/月](\d{1,2})", date_raw)
            if m:
                date_raw = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
            else:
                date_raw = ""

        pub_date = parse_date(date_raw)

        # 构建描述
        desc = f"来源：乙方宝 地区：{area} 发布时间：{date_raw or '未知'}"

        items.append(BiddingItem(
            title=title,
            url=url,
            pub_date=pub_date,
            pub_date_raw=date_raw or "未知日期",
            source="乙方宝",
            description=desc,
        ))

    print(f"  过滤后保留 {len(items)} 条招标信息")
    return items


def fetch_yfbzb() -> List[BiddingItem]:
    """爬取乙方宝，使用关键词搜索
    
    搜索策略：
    - 使用"铁塔"搜索：覆盖大部分铁塔相关项目
    - 使用"塔桅"搜索：覆盖广播电视塔桅等项目（如"兰坪县广播电视无线发射台塔桅检修"）
    - 过滤时通过 CORE_KEYWORDS 和 REGION_KEYWORDS 确保结果相关
    """
    all_items: List[BiddingItem] = []
    # 搜索关键词：铁塔 + 塔桅（覆盖更多场景）
    keywords = ["铁塔", "塔桅"]

    for i, kw in enumerate(keywords):
        if i > 0:
            time.sleep(random.randint(3, 6))
        try:
            # 不限制省份ID，搜索全国数据，然后在过滤时检查地区
            items = fetch_yfbzb_search(kw, province_id="", page_no=1)
            all_items.extend(items)
        except Exception as e:
            print(f"  [错误] 乙方宝搜索 '{kw}' 失败: {e}")

    # 去重（按 URL）
    seen_urls = set()
    unique_items = []
    for item in all_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique_items.append(item)

    return unique_items


# ─────────────────────────────────────────────────────────────
# 云南招标网（bidcenter）爬取
# ─────────────────────────────────────────────────────────────

YUNNAN_BIDCENTER_URL = "https://yn.bidcenter.com.cn/zhaobiao/zbkeyw-19388-0-0-90.html"


def fetch_yunnan_bidcenter() -> List[BiddingItem]:
    """
    爬取云南招标网（bidcenter）的铁塔招标信息。
    该网站专门聚合云南地区的招标信息，数据丰富。
    """
    print(f"\n[云南招标网] 开始抓取")
    soup = fetch_page(YUNNAN_BIDCENTER_URL, referer="https://yn.bidcenter.com.cn/")
    if not soup:
        return []

    items = []
    
    # 查找所有招标条目（链接格式：diqucontent-xxx-1.html）
    links = soup.select('a[href*="diqucontent-"]')
    print(f"  找到 {len(links)} 个链接")
    
    for link in links:
        title = link.get_text(strip=True)
        href = link.get("href", "")
        
        if not title or not href:
            continue
        
        # 补全 URL
        if href.startswith("/"):
            url = f"https://yn.bidcenter.com.cn{href}"
        elif href.startswith("http"):
            url = href
        else:
            url = f"https://yn.bidcenter.com.cn/{href}"
        
        # 提取日期信息（从父元素或相邻文本中）
        date_raw = ""
        parent = link.parent
        if parent:
            text = parent.get_text()
            # 匹配日期格式：2026-07-09丨招标公告丨云南
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
            if date_match:
                date_raw = date_match.group(1)
        
        # 关键词过滤：该网站本身全是云南省信息，只需匹配铁塔关键词
        if not should_include(title, "", require_yunnan=False):
            continue
        
        pub_date = parse_date(date_raw)
        desc = f"来源：云南招标网 发布时间：{date_raw}"
        
        items.append(BiddingItem(
            title=title,
            url=url,
            pub_date=pub_date,
            pub_date_raw=date_raw or "未知日期",
            source="云南招标网",
            description=desc,
        ))
    
    print(f"  过滤后保留 {len(items)} 条招标信息")
    return items


# ─────────────────────────────────────────────────────────────
# 中国铁塔电子采购平台爬取
# ─────────────────────────────────────────────────────────────

TOWER_EBID_URL = "https://ebid.chinatowercom.cn/zgtt/gggs/003001/list.html"
TOWER_EBID_API = "https://ebid.chinatowercom.cn/zgtt/gggs/003001/list.html"


def fetch_tower_ebid() -> List[BiddingItem]:
    """
    爬取中国铁塔电子采购平台的招标信息。
    这是铁塔公司官方采购平台，信息最权威、最全面。
    """
    print(f"\n[中国铁塔电子采购平台] 开始抓取")
    
    # 尝试通过 API 获取数据
    headers = {
        "User-Agent": random_ua(),
        "Accept": "application/json, text/html, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://ebid.chinatowercom.cn/",
        "Origin": "https://ebid.chinatowercom.cn",
    }
    
    items = []
    
    # 尝试多种可能的 API 端点
    api_urls = [
        "https://ebid.chinatowercom.cn/zgtt/gggs/003001/list.html",
        "https://ebid.chinatowercom.cn/zgtt/portal/notice/list",
    ]
    
    for api_url in api_urls:
        try:
            resp = requests.get(api_url, headers=headers, timeout=20, 
                              proxies={"http": None, "https": None})
            
            # 尝试解析为 JSON
            try:
                data = resp.json()
                rows = data.get("data", {}).get("list", []) or data.get("list", []) or []
                
                for row in rows:
                    title = row.get("title", "").strip()
                    if not title:
                        continue
                    
                    # 检查是否包含云南相关信息
                    area = row.get("area", "") or row.get("province", "")
                    if "云南" not in area and "云" not in area:
                        # 检查标题中是否有云南相关
                        if not any(kw in title for kw in ["云南", "昆明", "大理", "丽江", "西双版纳", "曲靖", "玉溪", "保山", "昭通", "楚雄", "红河", "文山", "普洱", "临沧", "德宏", "怒江", "迪庆"]):
                            continue
                    
                    # 关键词过滤
                    if not should_include(title, area, require_yunnan=False):
                        continue
                    
                    notice_id = row.get("id", "") or row.get("noticeId", "")
                    url = f"https://ebid.chinatowercom.cn/zgtt/gggs/003001/{notice_id}.html" if notice_id else api_url
                    
                    date_raw = row.get("publishTime", "") or row.get("createTime", "")
                    pub_date = parse_date(date_raw)
                    
                    desc = f"来源：中国铁塔电子采购平台 地区：{area} 发布时间：{date_raw}"
                    
                    items.append(BiddingItem(
                        title=title,
                        url=url,
                        pub_date=pub_date,
                        pub_date_raw=date_raw or "未知日期",
                        source="中国铁塔电子采购平台",
                        description=desc,
                    ))
                
                if items:
                    break
                    
            except (ValueError, KeyError):
                # 不是 JSON，尝试解析 HTML
                resp.encoding = 'utf-8'
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 查找公告列表
                links = soup.select('a[href*="/zgtt/gggs/"]')
                for link in links:
                    title = link.get_text(strip=True)
                    href = link.get("href", "")
                    
                    if not title or len(title) < 10:
                        continue
                    
                    # 检查是否包含云南相关信息
                    if not any(kw in title for kw in ["云南", "昆明", "大理", "丽江", "西双版纳", "曲靖", "玉溪", "保山", "昭通", "楚雄", "红河", "文山", "普洱", "临沧", "德宏", "怒江", "迪庆"]):
                        continue
                    
                    # 关键词过滤
                    if not should_include(title, "", require_yunnan=False):
                        continue
                    
                    if href.startswith("/"):
                        url = f"https://ebid.chinatowercom.cn{href}"
                    elif href.startswith("http"):
                        url = href
                    else:
                        url = f"https://ebid.chinatowercom.cn/{href}"
                    
                    pub_date = parse_date("")
                    desc = f"来源：中国铁塔电子采购平台"
                    
                    items.append(BiddingItem(
                        title=title,
                        url=url,
                        pub_date=pub_date,
                        pub_date_raw="未知日期",
                        source="中国铁塔电子采购平台",
                        description=desc,
                    ))
                
                if items:
                    break
                    
        except Exception as e:
            print(f"  [警告] {api_url} 请求失败: {e}")
            continue
    
    print(f"  过滤后保留 {len(items)} 条招标信息")
    return items


# ─────────────────────────────────────────────────────────────
# 中国电力招标采购网爬取
# ─────────────────────────────────────────────────────────────

DLZTB_URL = "http://m.dlztb.com"


def fetch_dlztb() -> List[BiddingItem]:
    """
    爬取中国电力招标采购网的铁塔相关招标信息。
    """
    print(f"\n[中国电力招标采购网] 开始抓取")
    
    # 搜索铁塔关键词 - 使用移动端搜索接口
    search_url = f"{DLZTB_URL}/search/index.html"
    params = {"keyword": "铁塔 云南"}
    
    soup = fetch_page(search_url, params=params, referer=DLZTB_URL)
    if not soup:
        # 尝试直接访问招标信息列表页
        list_url = f"{DLZTB_URL}/zbxx/"
        soup = fetch_page(list_url, referer=DLZTB_URL)
        if not soup:
            return []
    
    items = []
    
    # 查找搜索结果列表
    links = soup.select('a[href*="/view/"], a[href*="/zbxx/"]')
    print(f"  找到 {len(links)} 个链接")
    
    for link in links:
        title = link.get_text(strip=True)
        href = link.get("href", "")
        
        if not title or not href or len(title) < 10:
            continue
        
        # 检查是否包含云南相关信息
        if not any(kw in title for kw in ["云南", "昆明", "大理", "丽江", "西双版纳", "曲靖", "玉溪", "保山", "昭通", "楚雄", "红河", "文山", "普洱", "临沧", "德宏", "怒江", "迪庆"]):
            continue
        
        # 关键词过滤
        if not should_include(title, "", require_yunnan=False):
            continue
        
        if href.startswith("/"):
            url = f"http://m.dlztb.com{href}"
        elif href.startswith("http"):
            url = href
        else:
            url = f"http://m.dlztb.com/{href}"
        
        pub_date = parse_date("")
        desc = f"来源：中国电力招标采购网"
        
        items.append(BiddingItem(
            title=title,
            url=url,
            pub_date=pub_date,
            pub_date_raw="未知日期",
            source="中国电力招标采购网",
            description=desc,
        ))
    
    print(f"  过滤后保留 {len(items)} 条招标信息")
    return items


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="招标信息爬虫，生成 RSS feed")
    parser.add_argument("--output", default="output/bidding_feed.xml", help="输出文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印结果，不写文件")
    parser.add_argument("--interval", type=int, default=15, help="请求间隔秒数（默认15）")
    args = parser.parse_args()

    all_items: List[BiddingItem] = []

    # 1. 爬取中国政府采购网（搜索 API）
    try:
        ccgp_items = fetch_ccgp()
        all_items.extend(ccgp_items)
    except Exception as e:
        print(f"[错误] 中国政府采购网爬取异常: {e}")

    # 2. 爬取普通 HTML 网站（chinabidding 等）
    for i, site in enumerate(SITES):
        if i > 0:
            wait = args.interval + random.randint(0, 10)
            print(f"\n等待 {wait} 秒后继续...")
            time.sleep(wait)
        try:
            items = parse_site(site)
            all_items.extend(items)
        except Exception as e:
            print(f"  [错误] {site.name} 爬取异常: {e}")

    # 3. 爬取云南省公共资源交易中心（专用 API）
    wait = args.interval + random.randint(0, 10)
    print(f"\n等待 {wait} 秒后继续...")
    time.sleep(wait)
    try:
        yn_items = fetch_ynggzy()
        all_items.extend(yn_items)
    except Exception as e:
        print(f"  [错误] 云南省公共资源交易中心爬取异常: {e}")

    # 4. 爬取全国招标采购信息平台（乙方宝）
    wait = args.interval + random.randint(0, 10)
    print(f"\n等待 {wait} 秒后继续...")
    time.sleep(wait)
    try:
        yfbzb_items = fetch_yfbzb()
        all_items.extend(yfbzb_items)
    except Exception as e:
        print(f"  [错误] 乙方宝爬取异常: {e}")

    # 5. 爬取云南招标网（bidcenter）- 需要人机验证，暂时禁用
    # wait = args.interval + random.randint(0, 10)
    # print(f"\n等待 {wait} 秒后继续...")
    # time.sleep(wait)
    # try:
    #     bidcenter_items = fetch_yunnan_bidcenter()
    #     all_items.extend(bidcenter_items)
    # except Exception as e:
    #     print(f"  [错误] 云南招标网爬取异常: {e}")

    # 6. 爬取中国铁塔电子采购平台 - 需要登录，暂时禁用
    # wait = args.interval + random.randint(0, 10)
    # print(f"\n等待 {wait} 秒后继续...")
    # time.sleep(wait)
    # try:
    #     tower_items = fetch_tower_ebid()
    #     all_items.extend(tower_items)
    # except Exception as e:
    #     print(f"  [错误] 中国铁塔电子采购平台爬取异常: {e}")

    # 7. 爬取中国电力招标采购网 - 搜索接口变化，暂时禁用
    # wait = args.interval + random.randint(0, 10)
    # print(f"\n等待 {wait} 秒后继续...")
    # time.sleep(wait)
    # try:
    #     dlztb_items = fetch_dlztb()
    #     all_items.extend(dlztb_items)
    # except Exception as e:
    #     print(f"  [错误] 中国电力招标采购网爬取异常: {e}")

    # 全局去重（按 URL）
    seen_urls = set()
    unique_items = []
    for item in all_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique_items.append(item)
    all_items = unique_items

    print(f"\n{'='*50}")
    print(f"共收集到 {len(all_items)} 条招标信息")

    if not all_items:
        print("未找到任何匹配的招标信息，请检查网站结构是否变化")
        return

    # 按日期排序（最新在前）
    all_items.sort(key=lambda x: x.pub_date, reverse=True)

    # 按日期分组
    from collections import defaultdict
    items_by_date = defaultdict(list)
    for item in all_items:
        items_by_date[item.pub_date_raw].append(item)

    # 打印摘要（按日期分组，输出招标名称和网址）
    print(f"\n{'='*50}")
    print(f"共收集到 {len(all_items)} 条招标信息")
    print(f"{'='*50}")
    
    for date, items in sorted(items_by_date.items(), reverse=True):
        print(f"\n【{date}】共 {len(items)} 条")
        for item in items:
            print(f"  {item.title[:70]}")
            print(f"    {item.url}")

    rss_content = build_rss(all_items)

    if args.dry_run:
        return

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rss_content, encoding="utf-8")
    print(f"\nRSS 文件已写入: {output_path}")


if __name__ == "__main__":
    main()
