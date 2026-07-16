"""云南省政府采购网爬虫"""

from datetime import datetime
from typing import List, Optional
from ..models import BidItem
from ..base_crawler import BaseCrawler
from ..utils import fetch_page, logger


class CcgpYunnanCrawler(BaseCrawler):
    """云南省政府采购网 (www.ccgpyunnan.gov.cn)"""

    name = "云南省政府采购网"
    base_url = "http://www.ccgpyunnan.gov.cn"
    list_url = "http://www.ccgpyunnan.gov.cn/page/procurement/procurementList.html"

    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("ccgp_yunnan", source_config)
        self.keywords = self.config.get("keywords", ["铁塔"])

    def _get_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "http://www.ccgpyunnan.gov.cn/page/procurement/procurementList.html",
        }

    def _get_search_keywords(self) -> List[str]:
        return self.keywords

    def _get_max_pages(self) -> int:
        return 3

    def _get_page_delay(self) -> int:
        return 3

    def fetch(self) -> List[BidItem]:
        """获取招标信息"""
        all_items = []

        for keyword in self.keywords:
            logger.info(f"[{self.display_name}] 搜索关键词: {keyword}")
            items = self._fetch_keyword(keyword)
            all_items.extend(items)
            self.delay()

        return all_items

    def _fetch_keyword(self, keyword: str) -> List[BidItem]:
        """获取指定关键词的招标信息"""
        items = []

        try:
            # 云南省政府采购网可能没有搜索API，直接抓取列表页
            url = f"{self.list_url}"

            html = fetch_page(
                url,
                headers=self._get_headers(),
                proxies=self.proxies,
                timeout=15,
            )

            if not html:
                return items

            # 解析HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            # 查找招标信息列表（需要根据实际页面结构调整选择器）
            list_items = soup.select("div.list-box ul li") or soup.select("div.procurement-list li")

            for item_el in list_items:
                item = self._parse_item(item_el, keyword)
                if item:
                    items.append(item)

        except Exception as e:
            logger.error(f"[{self.name}] 请求失败: {e}")

        return items

    def _parse_item(self, item_el, keyword: str) -> Optional[BidItem]:
        """解析单个列表项"""
        try:
            title_el = item_el.select_one("a") or item_el.select_one("h3")
            if not title_el:
                return None

            title = title_el.get_text(strip=True)

            # 检查是否包含关键词
            if keyword not in title:
                return None

            href = title_el.get("href", "")
            url = href if href.startswith("http") else f"{self.base_url}{href}"

            # 获取日期
            date_el = item_el.select_one("span.date") or item_el.select_one("time")
            date_str = date_el.get_text(strip=True) if date_el else datetime.now().strftime("%Y-%m-%d")

            # 获取描述
            desc_el = item_el.select_one("p") or item_el.select_one("div.desc")
            description = desc_el.get_text(strip=True) if desc_el else ""

            return BidItem(
                title=title,
                url=url,
                date=date_str,
                source=self.name,
                description=description,
            )
        except Exception as e:
            logger.error(f"[{self.name}] 解析项失败: {e}")
            return None
