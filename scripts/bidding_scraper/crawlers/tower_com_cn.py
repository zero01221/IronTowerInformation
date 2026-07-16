"""中国铁塔在线商务平台爬虫"""

from datetime import datetime
from typing import List, Optional
from ..models import BidItem
from ..base_crawler import BaseCrawler
from ..utils import fetch_page, logger


class TowerComCnCrawler(BaseCrawler):
    """中国铁塔在线商务平台 (www.tower.com.cn)"""

    name = "中国铁塔在线商务平台"
    base_url = "https://www.tower.com.cn"
    search_url = "https://www.tower.com.cn/bidding/biddingList"

    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("tower_com_cn", source_config)
        self.keywords = self.config.get("keywords", ["铁塔"])

    def _get_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.tower.com.cn/bidding/biddingList",
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
            # 构建URL
            url = f"{self.search_url}?keyword={keyword}&page=1"

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
            list_items = soup.select("div.bidding-list ul li") or soup.select("div.list-item")

            for item_el in list_items:
                item = self._parse_item(item_el)
                if item:
                    items.append(item)

        except Exception as e:
            logger.error(f"[{self.name}] 请求失败: {e}")

        return items

    def _parse_item(self, item_el) -> Optional[BidItem]:
        """解析单个列表项"""
        try:
            title_el = item_el.select_one("a.title") or item_el.select_one("h3 a")
            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = href if href.startswith("http") else f"{self.base_url}{href}"

            # 获取日期
            date_el = item_el.select_one("span.date") or item_el.select_one("time")
            date_str = date_el.get_text(strip=True) if date_el else datetime.now().strftime("%Y-%m-%d")

            # 获取描述
            desc_el = item_el.select_one("div.desc") or item_el.select_one("p")
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
