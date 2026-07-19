# coding=utf-8
"""乙方宝爬虫

乙方宝 (yfbzb.com) 是一个招标信息聚合平台，聚合了全国各地的招标信息。
搜索接口返回 HTML 表格，需要解析 <table> 结构。

注意: 该网站有反爬机制（HTTP 468），需要:
1. 使用 Session 先访问首页建立 Cookie
2. 添加浏览器级请求头
3. 关键词和页面间增加随机延迟
"""

import re
import requests
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..base_crawler import BaseCrawler
from ..logger import get_logger
from ..models import BidItem
from ..utils import fetch_page, extract_date, clean_text, get_random_user_agent

logger = get_logger(__name__)


class YfbzbCrawler(BaseCrawler):
    """乙方宝爬虫"""

    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("yfbzb", source_config)
        self.base_url = self.config.get("base_url", "https://www.yfbzb.com")
        self.search_url = self.config.get("search_url", "https://www.yfbzb.com/search/invitedBidSearch")
        self.keywords = self.config.get("keywords", ["铁塔", "塔桅"])
        self.max_pages = self.config.get("max_pages", 2)
        # 日期过滤：只保留最近N天的信息（可在配置文件中修改）
        self.days_limit = self.config.get("days_limit", 15)
        # Session 和预热状态
        self._session: Optional[requests.Session] = None
        self._session_warmed: bool = False

    def _warm_session(self):
        """
        预热 Session：访问首页建立 Cookie

        防止 HTTP 468（疑似 Cloudflare/CDN 反爬）：
        - 先访问首页获取必要的 Cookie
        - 设置完整的浏览器请求头
        """
        if self._session_warmed:
            return

        logger.info(f"[{self.display_name}] 预热会话（访问首页建立Cookie）...")
        try:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Upgrade-Insecure-Requests": "1",
            })
            if self.proxies:
                self._session.proxies = self.proxies

            resp = self._session.get(self.base_url, timeout=self.timeout)
            resp.raise_for_status()
            cookies = list(self._session.cookies)
            logger.info(f"[{self.display_name}] 首页 HTTP {resp.status_code}, "
                        f"获取 {len(cookies)} 个Cookie")

            self._session_warmed = True
        except Exception as e:
            logger.warning(f"[{self.display_name}] 预热失败: {e}，将使用无状态请求")
            self._session_warmed = True  # 标记已尝试

    def fetch(self) -> List[BidItem]:
        """抓取招标信息"""
        self._warm_session()

        all_items = []

        for i, keyword in enumerate(self.keywords):
            if i > 0:
                # 关键词间随机延迟，避免触发反爬
                self.delay(3, 7)

            logger.info(f"[{self.display_name}] 搜索关键词: {keyword}")
            items = self._search_keyword(keyword)
            all_items.extend(items)

        # 去重
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.item_id not in seen_ids:
                seen_ids.add(item.item_id)
                unique_items.append(item)

        # 过滤云南地区
        filtered_items = self.filter_by_region(unique_items)

        # 日期过滤：只保留最近N天的信息
        filtered_items = self.filter_by_date(filtered_items)

        return filtered_items

    def _search_keyword(self, keyword: str) -> List[BidItem]:
        """搜索单个关键词"""
        items = []

        for page_no in range(1, self.max_pages + 1):
            if page_no > 1:
                self.delay(2, 5)  # 翻页延迟

            page_items = self._fetch_page(keyword, page_no)
            if not page_items:
                break
            items.extend(page_items)

        return items

    def _fetch_page(self, keyword: str, page_no: int) -> List[BidItem]:
        """获取单页数据"""
        params = {
            "defaultSearch": "true",
            "keyword": keyword,
            "pageNo": page_no,
            "pageSize": 20,
        }

        try:
            # 使用 Session 或回退到无状态 fetch_page
            if self._session:
                url = f"{self.search_url}?{urlencode(params)}"
                resp = self._session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
            else:
                soup = fetch_page(
                    self.search_url,
                    params=params,
                    referer=self.base_url,
                    timeout=self.timeout,
                )

            if not soup:
                return []

            return self._parse_page(soup)

        except requests.exceptions.HTTPError as e:
            logger.warning(f"[{self.display_name}] HTTP错误 {e.response.status_code}: {self.search_url}")
            return []
        except Exception as e:
            logger.error(f"[{self.display_name}] 获取页面失败: {e}")
            return []

    def _parse_page(self, soup: BeautifulSoup) -> List[BidItem]:
        """解析页面"""
        items = []

        # 查找表格
        table = soup.select_one("table")
        if not table:
            logger.debug(f"[{self.display_name}] 未找到表格，可能页面结构已变化")
            return items

        rows = table.select("tbody tr")
        if not rows:
            return items

        for row in rows:
            item = self._parse_row(row)
            if item:
                items.append(item)

        return items

    def _parse_row(self, row) -> Optional[BidItem]:
        """解析单行数据"""
        try:
            cells = row.select("td")
            if len(cells) < 3:
                return None

            # 标题和链接
            title_cell = cells[0]
            a_tag = title_cell.find("a")
            if not a_tag:
                return None

            title = a_tag.get_text(strip=True)
            href = a_tag.get("href", "")
            if href and not href.startswith("http"):
                href = f"{self.base_url}{href}"

            # 地区
            area_cell = cells[2] if len(cells) > 2 else None
            area = area_cell.get_text(strip=True) if area_cell else ""

            # 日期
            date_cell = cells[3] if len(cells) > 3 else None
            date_str = date_cell.get_text(strip=True) if date_cell else ""
            date = extract_date(date_str) or ""

            # 获取详情页的原始链接（可选，默认关闭以避免触发反爬虫）
            fetch_detail = self.config.get("fetch_detail", False)
            if fetch_detail and href:
                original_url = self._get_original_url(href)
            else:
                original_url = ""

            return BidItem(
                title=title,
                url=original_url or href,
                original_url=original_url,
                date=date,
                source=self.display_name,
                description=area,
            )

        except Exception as e:
            logger.debug(f"解析行失败: {e}")
            return None

    def _get_original_url(self, detail_url: str) -> str:
        """从详情页获取原始发布平台链接（千里马）"""
        try:
            if self._session:
                resp = self._session.get(detail_url, timeout=self.timeout)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
            else:
                soup = fetch_page(
                    detail_url,
                    referer=self.base_url,
                    timeout=self.timeout,
                )

            if not soup:
                return ""

            # 查找千里马链接
            for a in soup.select("a"):
                href = a.get("href", "")
                if "qianlima.com" in href:
                    return href

            return ""

        except Exception as e:
            logger.debug(f"获取原始链接失败: {e}")
            return ""
