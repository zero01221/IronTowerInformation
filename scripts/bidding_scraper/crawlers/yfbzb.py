# coding=utf-8
"""乙方宝爬虫"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..base_crawler import BaseCrawler
from ..logger import get_logger
from ..models import BidItem
from ..utils import fetch_page, extract_date, clean_text

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
    
    def fetch(self) -> List[BidItem]:
        """抓取招标信息"""
        all_items = []
        
        for keyword in self.keywords:
            logger.info(f"[{self.display_name}] 搜索关键词: {keyword}")
            items = self._search_keyword(keyword)
            all_items.extend(items)
            self.delay()
        
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
            page_items = self._fetch_page(keyword, page_no)
            if not page_items:
                break
            items.extend(page_items)
            self.delay(1, 3)
        
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
            soup = fetch_page(
                self.search_url,
                params=params,
                referer=self.base_url,
                timeout=self.timeout,
            )
            
            if not soup:
                return []
            
            return self._parse_page(soup)
        
        except Exception as e:
            logger.error(f"[{self.display_name}] 获取页面失败: {e}")
            return []
    
    def _parse_page(self, soup: BeautifulSoup) -> List[BidItem]:
        """解析页面"""
        items = []
        
        # 查找表格
        table = soup.select_one("table")
        if not table:
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
                    # 提取完整的千里马链接
                    return href
            
            return ""
        
        except Exception as e:
            logger.debug(f"获取原始链接失败: {e}")
            return ""
