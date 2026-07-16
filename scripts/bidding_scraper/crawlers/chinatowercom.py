"""中国铁塔电子采购平台爬虫"""

import re
from datetime import datetime
from typing import List, Optional
from ..models import BidItem
from ..base_crawler import BaseCrawler
from ..utils import fetch_page, logger


class ChinaTowerComCrawler(BaseCrawler):
    """中国铁塔电子采购平台 (ebid.chinatowercom.cn)"""

    name = "中国铁塔电子采购平台"
    base_url = "https://ebid.chinatowercom.cn"
    api_url = "https://ebid.chinatowercom.cn/tcpms/tenderee/tendererBiddingInfoController/getTendererBiddingInfoList"

    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("chinatowercom", source_config)
        self.keywords = self.config.get("keywords", ["铁塔"])

    def _get_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://ebid.chinatowercom.cn/tcpms/tenderee/tendererBiddingInfo.html",
            "Origin": "https://ebid.chinatowercom.cn",
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
                "pageNo": 1,
                "pageSize": 20,
                "keyword": keyword,
                "tenderType": "1",  # 招标公告
            }

            html = fetch_page(
                self.api_url,
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
                    records = resp_data["data"].get("records", [])
                    for record in records:
                        item = self._parse_record(record)
                        if item:
                            items.append(item)
            except json.JSONDecodeError:
                logger.warning(f"[{self.name}] JSON解析失败")

        except Exception as e:
            logger.error(f"[{self.name}] 请求失败: {e}")

        return items

    def _parse_record(self, record: dict) -> Optional[BidItem]:
        """解析单条记录"""
        try:
            title = record.get("tenderTitle", "")
            url = record.get("url", "")
            pub_date = record.get("publishDate", "")

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
                description=record.get("tenderContent", ""),
            )
        except Exception as e:
            logger.error(f"[{self.name}] 解析记录失败: {e}")
            return None
