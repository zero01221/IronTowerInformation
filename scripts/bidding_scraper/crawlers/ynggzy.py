# coding=utf-8
"""云南省公共资源交易中心爬虫"""

from typing import List, Optional

import requests

from ..base_crawler import BaseCrawler
from ..logger import get_logger
from ..models import BidItem
from ..utils import extract_date, clean_text, random_delay

logger = get_logger(__name__)


class YnggzyCrawler(BaseCrawler):
    """云南省公共资源交易中心爬虫"""
    
    def __init__(self, source_config: dict):
        """初始化"""
        super().__init__("ynggzy", source_config)
        self.api_url = self.config.get("api_url", "https://ggzy.yn.gov.cn/ynggfwpt-home-api/jyzyCenter/jyInfo/gcjs/getZbggList")
    
    def fetch(self) -> List[BidItem]:
        """抓取招标信息"""
        all_items = []
        
        # 抓取多个分类的数据
        categories = ["gcjs", "zfcg", "cqjy"]
        category_names = {"gcjs": "工程建设", "zfcg": "政府采购", "cqjy": "产权交易"}
        
        for category in categories:
            logger.info(f"  [{self.display_name}] 抓取分类: {category_names.get(category, category)}")
            items = self._fetch_category(category)
            logger.info(f"  [{self.display_name}] {category} 获取 {len(items)} 条")
            all_items.extend(items)
            random_delay(3, 6)
        
        # 网站本身全是云南省信息，无需检查地区
        filtered_items = self.filter_items(all_items, require_yunnan=False)
        
        return filtered_items
    
    def _fetch_category(self, category: str) -> List[BidItem]:
        """抓取单个分类"""
        api_url = self.api_url.replace("gcjs", category)
        
        payload = {
            "pageNum": 1,
            "pageSize": 20,
            "bulletintype": "1",
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": "https://ggzy.yn.gov.cn/",
        }
        
        try:
            resp = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                proxies=self.proxies,
            )
            data = resp.json()
            
            # 检查返回数据类型
            if isinstance(data, str):
                logger.warning(f"[{self.display_name}] {category} 返回字符串: {data[:100]}")
                return []
            
            if not isinstance(data, dict):
                logger.warning(f"[{self.display_name}] {category} 返回非字典类型: {type(data)}")
                return []
            
            # 安全获取列表数据
            value = data.get("value", {})
            if isinstance(value, str):
                logger.warning(f"[{self.display_name}] {category} value 为字符串: {value[:100]}")
                return []
            
            rows = value.get("list", []) if isinstance(value, dict) else []
            
            items = []
            for row in rows:
                item = self._parse_row(row, category)
                if item:
                    items.append(item)
            
            return items
        
        except Exception as e:
            logger.error(f"[{self.display_name}] 获取 {category} 失败: {e}")
            return []
    
    def _parse_row(self, row: dict, category: str) -> Optional[BidItem]:
        """解析单行数据"""
        try:
            title = row.get("bulletinname", "")
            if not title:
                return None
            
            # 构建详情链接
            bulletin_id = row.get("bulletinid", "")
            url = f"https://ggzy.yn.gov.cn/#/newDetail?category={category}&id={bulletin_id}"
            
            # 提取日期
            date_str = row.get("releasetime", "") or row.get("publishdate", "")
            date = extract_date(date_str) or ""
            
            # 地区信息
            area = row.get("areaname", "") or row.get("districtname", "")
            
            return BidItem(
                title=title,
                url=url,
                original_url=url,
                date=date,
                source=self.display_name,
                description=area,
            )
        
        except Exception as e:
            logger.debug(f"解析行失败: {e}")
            return None
