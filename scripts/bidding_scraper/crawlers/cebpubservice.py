"""中国招标投标公共服务平台爬虫"""

from datetime import datetime
from typing import List, Optional
from ..models import BidItem
from ..base_crawler import BaseCrawler
from ..utils import fetch_page, logger


class CebpubserviceCrawler(BaseCrawler):
    """中国招标投标公共服务平台 (www.cebpubservice.com)"""

    name = "中国招标投标公共服务平台"
    base_url = "https://www.cebpubservice.com"
    search_url = "https://www.cebpubservice.com/ctpsp_iiss/searchbusinesstypebeforedooraction/getSearch.do"

    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("cebpubservice", source_config)
        self.keywords = self.config.get("keywords", ["铁塔"])

    def _get_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.cebpubservice.com/",
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
            # 构建请求参数
            data = {
                "keyword": keyword,
                "pageNum": 1,
                "pageSize": 20,
                "businesstype": "1",  # 招标公告
            }

            html = fetch_page(
                self.search_url,
                method="POST",
                headers=self._get_headers(),
                data=data,
                proxies=self.proxies,
                timeout=15,
            )

            if not html:
                return items

            # 解析JSON响应
            import json
            try:
                resp_data = json.loads(html)
                if resp_data.get("success") and resp_data.get("data"):
                    records = resp_data["data"].get("list", []) or resp_data["data"].get("records", [])
                    for record in records:
                        item = self._parse_record(record)
                        if item:
                            items.append(item)
            except json.JSONDecodeError:
                # 如果返回的是HTML，尝试解析
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                list_items = soup.select("div.search-result li") or soup.select("ul.list li")
                for item_el in list_items:
                    item = self._parse_html_item(item_el)
                    if item:
                        items.append(item)

        except Exception as e:
            logger.error(f"[{self.name}] 请求失败: {e}")

        return items

    def _parse_record(self, record: dict) -> Optional[BidItem]:
        """解析JSON记录"""
        try:
            title = record.get("title", "") or record.get("projectName", "")
            url = record.get("url", "") or record.get("detailUrl", "")
            pub_date = record.get("publishDate", "") or record.get("createTime", "")

            if not title:
                return None

            # 解析日期
            date_obj = None
            if pub_date:
                try:
                    date_obj = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
                except:
                    try:
                        date_obj = datetime.strptime(pub_date, "%Y-%m-%d")
                    except:
                        date_obj = datetime.now()

            return BidItem(
                title=title,
                url=url if url.startswith("http") else f"{self.base_url}{url}",
                date=date_obj.strftime("%Y-%m-%d") if date_obj else datetime.now().strftime("%Y-%m-%d"),
                source=self.name,
                description=record.get("content", "") or record.get("description", ""),
            )
        except Exception as e:
            logger.error(f"[{self.name}] 解析记录失败: {e}")
            return None

    def _parse_html_item(self, item_el) -> Optional[BidItem]:
        """解析HTML列表项"""
        try:
            title_el = item_el.select_one("a") or item_el.select_one("h3")
            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = href if href.startswith("http") else f"{self.base_url}{href}"

            date_el = item_el.select_one("span.date") or item_el.select_one("time")
            date_str = date_el.get_text(strip=True) if date_el else datetime.now().strftime("%Y-%m-%d")

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
            logger.error(f"[{self.name}] 解析HTML项失败: {e}")
            return None
