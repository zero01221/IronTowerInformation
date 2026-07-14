# coding=utf-8
"""爬虫基类模块"""

import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional

from .config import Config
from .filters import BidFilter, RegionFilter
from .logger import get_logger
from .models import BidItem, SourceStatus
from .utils import fetch_page, random_delay

logger = get_logger(__name__)


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(self, source_name: str, source_config: dict):
        """
        初始化爬虫
        
        Args:
            source_name: 数据源名称
            source_config: 数据源配置
        """
        self.source_name = source_name
        self.config = source_config
        self.status = SourceStatus(name=source_name)
        self.bid_filter = BidFilter()
        self.region_filter = RegionFilter()
        
        # 请求配置
        app_config = Config.get_instance()
        self.timeout = app_config.get_int("request.timeout", 30)
        self.delay_between_requests = app_config.get_int("request.delay_between_requests", 5)
        
        # 日期过滤配置：只保留最近N天的信息（可在配置文件中修改）
        self.days_limit = source_config.get("days_limit", app_config.get_int("filter.days_limit", 15))
    
    @abstractmethod
    def fetch(self) -> List[BidItem]:
        """
        抓取招标信息
        
        Returns:
            招标信息列表
        """
        pass
    
    @property
    def display_name(self) -> str:
        """获取显示名称"""
        return self.config.get("name", self.source_name)
    
    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self.config.get("enabled", True)
    
    def is_healthy(self) -> bool:
        """检查是否健康"""
        return self.status.healthy
    
    def filter_items(
        self,
        items: List[BidItem],
        require_yunnan: bool = True,
    ) -> List[BidItem]:
        """过滤招标信息"""
        return self.bid_filter.filter_items(items, require_yunnan)
    
    def filter_by_region(self, items: List[BidItem]) -> List[BidItem]:
        """按地区过滤"""
        return self.region_filter.filter_items(items)
    
    def filter_by_date(self, items: List[BidItem]) -> List[BidItem]:
        """
        按日期过滤，只保留最近N天的信息
        
        Args:
            items: 招标信息列表
            
        Returns:
            过滤后的招标信息列表
        """
        cutoff_date = datetime.now() - timedelta(days=self.days_limit)
        filtered = []
        
        for item in items:
            try:
                # 解析日期（格式：YYYY-MM-DD）
                item_date = datetime.strptime(item.date, "%Y-%m-%d")
                if item_date >= cutoff_date:
                    filtered.append(item)
                else:
                    logger.debug(f"[{self.display_name}] 过滤旧信息: {item.title[:30]}... ({item.date})")
            except (ValueError, TypeError) as e:
                # 日期解析失败，保留该条目
                logger.warning(f"[{self.display_name}] 日期解析失败: {item.date}, 保留该条目")
                filtered.append(item)
        
        logger.info(f"[{self.display_name}] 日期过滤: {len(items)} -> {len(filtered)} 条（最近{self.days_limit}天）")
        return filtered
    
    def delay(self, min_seconds: float = None, max_seconds: float = None):
        """请求间延迟"""
        if min_seconds is None:
            min_seconds = self.delay_between_requests * 0.5
        if max_seconds is None:
            max_seconds = self.delay_between_requests * 1.5
        random_delay(min_seconds, max_seconds)
    
    def get_random_user_agent(self) -> str:
        """获取随机User-Agent"""
        config = Config.get_instance()
        user_agents = config.get_user_agents()
        return random.choice(user_agents)
    
    def record_success(self, items: List[BidItem]):
        """记录成功"""
        self.status.record_success(len(items))
        logger.info(f"[{self.display_name}] 成功获取 {len(items)} 条招标信息")
    
    def record_failure(self, error: str = ""):
        """记录失败"""
        self.status.record_failure()
        if error:
            logger.warning(f"[{self.display_name}] 抓取失败: {error}")
        else:
            logger.warning(f"[{self.display_name}] 抓取失败")
    
    def run(self) -> List[BidItem]:
        """
        运行爬虫
        
        Returns:
            招标信息列表
        """
        if not self.is_enabled():
            logger.info(f"[{self.display_name}] 已禁用，跳过")
            return []
        
        if not self.is_healthy():
            logger.warning(f"[{self.display_name}] 不健康，跳过")
            return []
        
        try:
            logger.info(f"[{self.display_name}] 开始抓取")
            items = self.fetch()
            self.record_success(items)
            return items
        except Exception as e:
            self.record_failure(str(e))
            return []


class CrawlerManager:
    """爬虫管理器"""
    
    def __init__(self):
        """初始化爬虫管理器"""
        self.crawlers: List[BaseCrawler] = []
        self.config = Config.get_instance()
    
    def register(self, crawler: BaseCrawler):
        """注册爬虫"""
        self.crawlers.append(crawler)
        logger.debug(f"注册爬虫: {crawler.display_name}")
    
    def run_all(self) -> List[BidItem]:
        """运行所有爬虫"""
        all_items = []
        
        for i, crawler in enumerate(self.crawlers):
            if i > 0:
                # 数据源间延迟
                delay = self.config.get_int("request.delay_between_sources", 15)
                logger.info(f"等待 {delay} 秒后继续...")
                time.sleep(delay)
            
            items = crawler.run()
            all_items.extend(items)
        
        return all_items
    
    def get_status(self) -> List[dict]:
        """获取所有爬虫状态"""
        return [crawler.status.to_dict() for crawler in self.crawlers]
    
    def health_check(self) -> bool:
        """健康检查"""
        healthy_count = sum(1 for c in self.crawlers if c.is_healthy())
        total_count = len(self.crawlers)
        
        logger.info(f"健康检查: {healthy_count}/{total_count} 个数据源健康")
        return healthy_count > 0
