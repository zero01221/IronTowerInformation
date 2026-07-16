# coding=utf-8
"""中国政府采购网爬虫"""

import time
from typing import List, Optional

from bs4 import BeautifulSoup

from ..base_crawler import BaseCrawler
from ..logger import get_logger
from ..models import BidItem
from ..utils import fetch_page, extract_date, clean_text, get_random_user_agent

logger = get_logger(__name__)

# CCGP 反爬关键词检测
_ANTI_SCRAPING_KEYWORDS = ["您的访问过于频繁", "频繁访问", "请稍后再试"]


class CcgpCrawler(BaseCrawler):
    """中国政府采购网爬虫

    注意: search.ccgp.gov.cn 有严格的反爬机制，同一个IP短时间内频繁
    请求会触发封锁。因此需要:
    1. 关键词之间增加较长延迟（15-30秒）
    2. 检测反爬页面并自动等待恢复
    3. 使用会话Cookie保持请求连续性
    """

    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("ccgp", source_config)
        # 优先使用HTTPS（政府网站已全面升级）
        self.search_url = self.config.get("search_url", "https://search.ccgp.gov.cn/bxsearch")
        self.display_zone = self.config.get("display_zone", "云南")
        self.zone_id = self.config.get("zone_id", "53")
        self.keywords = self.config.get("keywords", ["铁塔"])
        # CCGP需要更长的请求间隔以避免反爬
        self._ccgp_min_delay = self.config.get("min_delay", 15)
        self._ccgp_max_delay = self.config.get("max_delay", 30)
        self._max_retries_on_block = 3

    def fetch(self) -> List[BidItem]:
        """抓取招标信息"""
        all_items = []

        for keyword in self.keywords:
            logger.info(f"[{self.display_name}] 搜索关键词: {keyword}, 地区: {self.display_zone}(zoneId={self.zone_id})")
            items = self._search_keyword(keyword)
            all_items.extend(items)
            # CCGP需要较长延迟防止反爬（15-30秒）
            delay = self._ccgp_min_delay + (self._ccgp_max_delay - self._ccgp_min_delay) * (0.5 + 0.5 * hash(keyword) % 100 / 100.0)
            logger.debug(f"[{self.display_name}] 等待 {delay:.1f} 秒后继续...")
            time.sleep(delay)

        # 去重
        seen_ids = set()
        unique_items = []
        for item in all_items:
            if item.item_id not in seen_ids:
                seen_ids.add(item.item_id)
                unique_items.append(item)

        return unique_items

    def _is_anti_scraping_page(self, soup: BeautifulSoup) -> bool:
        """检测是否为反爬拦截页面"""
        if not soup:
            return False
        text = soup.get_text()
        for keyword in _ANTI_SCRAPING_KEYWORDS:
            if keyword in text:
                return True
        # 也检查是否有搜索结果列表（如果没有且页面很小，可能是拦截页）
        if not soup.select("ul.vT-srch-result-list-bid li") and not soup.select("ul.vT-srch-result-list li"):
            # 如果页面内容很少（<500字符），很可能是拦截页
            if len(text) < 500 and "政府采购" not in text[:200]:
                return True
        return False

    def _search_keyword(self, keyword: str) -> List[BidItem]:
        """搜索单个关键词（带反爬处理）"""
        params = {
            "searchtype": 1,
            "page_index": 1,
            "bidSort": 0,
            "buyerName": "",
            "projectId": "",
            "pinMu": 0,
            "bidType": 1,
            "dbselect": "bidx",
            "kw": keyword,
            "timeType": 2,
            "displayZone": self.display_zone,
            "zoneId": self.zone_id,
            "pppStatus": 0,
            "agentName": "",
        }

        # 使用随机UA降低被封概率
        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
        }

        for attempt in range(self._max_retries_on_block):
            try:
                soup = fetch_page(
                    self.search_url,
                    params=params,
                    headers=headers,
                    referer="https://www.ccgp.gov.cn/",
                    timeout=self.timeout,
                    proxies=self.proxies,
                )

                if not soup:
                    logger.info(f"  找到 0 个搜索结果（请求失败）")
                    return []

                # 检测反爬页面
                if self._is_anti_scraping_page(soup):
                    if attempt < self._max_retries_on_block - 1:
                        wait_time = 30 * (attempt + 1)
                        logger.warning(f"  触发反爬机制，等待 {wait_time} 秒后重试 (第{attempt+1}次)...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"  反爬机制持续拦截，已放弃关键词: {keyword}")
                        return []

                items = self._parse_page(soup)
                logger.info(f"  找到 {len(items)} 个搜索结果")
                return items

            except Exception as e:
                logger.error(f"[{self.display_name}] 搜索失败({keyword}): {e}")
                if attempt < self._max_retries_on_block - 1:
                    time.sleep(10)
                else:
                    return []

        return []
    
    def _parse_page(self, soup: BeautifulSoup) -> List[BidItem]:
        """解析页面"""
        items = []
        
        # 查找搜索结果列表
        results = soup.select("ul.vT-srch-result-list-bid li")
        if not results:
            results = soup.select("ul.vT-srch-result-list li")
        
        for result in results:
            item = self._parse_result(result)
            if item:
                items.append(item)
        
        return items
    
    def _parse_result(self, result) -> Optional[BidItem]:
        """解析单个结果"""
        try:
            a_tag = result.find("a")
            if not a_tag:
                return None
            
            title = a_tag.get_text(strip=True)
            url = a_tag.get("href", "")
            
            # 提取日期
            date_str = ""
            span = result.find("span")
            if span:
                date_str = span.get_text(strip=True)
            date = extract_date(date_str) or extract_date(result.get_text()) or ""
            
            # 提取摘要
            desc = ""
            desc_p = result.find("p")
            if desc_p:
                desc = clean_text(desc_p.get_text(strip=True))
            
            return BidItem(
                title=title,
                url=url,
                original_url=url,
                date=date,
                source=self.display_name,
                description=desc,
            )
        
        except Exception as e:
            logger.debug(f"解析结果失败: {e}")
            return None
