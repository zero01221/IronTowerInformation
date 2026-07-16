# coding=utf-8
"""通知基类"""

from abc import ABC, abstractmethod
from typing import List

from ..models import BidItem
from ..logger import get_logger

logger = get_logger(__name__)


class BaseNotifier(ABC):
    """通知基类"""
    
    def __init__(self, config: dict):
        """
        初始化通知器
        
        Args:
            config: 通知配置
        """
        self.config = config
        self.enabled = config.get("enabled", False)
    
    @abstractmethod
    def send(self, items: List[BidItem]) -> bool:
        """
        发送通知

        Args:
            items: 招标信息列表

        Returns:
            是否发送成功
        """
        pass

    def send_text(self, text: str) -> bool:
        """
        发送纯文本消息（用于无数据时的通知，如"今天没有新消息"）

        Args:
            text: 要发送的文本内容

        Returns:
            是否发送成功
        """
        if not self.enabled:
            return True
        return False
    
    def format_message(self, items: List[BidItem]) -> str:
        """
        格式化消息内容
        
        Args:
            items: 招标信息列表
            
        Returns:
            格式化后的消息内容
        """
        if not items:
            return "暂无新的招标信息"
        
        lines = [f"📢 发现 {len(items)} 条新的招标信息：\n"]
        
        # 按日期分组
        date_groups = {}
        for item in items:
            date = item.date
            if date not in date_groups:
                date_groups[date] = []
            date_groups[date].append(item)
        
        # 按日期排序（最新的在前）
        sorted_dates = sorted(date_groups.keys(), reverse=True)
        
        for date in sorted_dates:
            date_items = date_groups[date]
            lines.append(f"\n【{date}】共 {len(date_items)} 条")
            
            for item in date_items:
                lines.append(f"• {item.title}")
                lines.append(f"  🔗 {item.url}")
        
        return "\n".join(lines)
    
    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self.enabled
