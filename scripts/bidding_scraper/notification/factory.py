# coding=utf-8
"""通知工厂类"""

from typing import List, Dict

from .base import BaseNotifier
from .feishu import FeishuNotifier
from .wechat import WechatNotifier
from .dingtalk import DingtalkNotifier
from ..models import BidItem
from ..logger import get_logger

logger = get_logger(__name__)


class NotifierFactory:
    """
    通知工厂类
    
    根据配置创建并管理多个通知器
    """
    
    # 支持的通知类型
    NOTIFIER_TYPES = {
        "feishu": FeishuNotifier,
        "wechat": WechatNotifier,
        "dingtalk": DingtalkNotifier,
    }
    
    def __init__(self, notification_config: dict):
        """
        初始化通知工厂
        
        Args:
            notification_config: 通知配置
        """
        self.notifiers: List[BaseNotifier] = []
        self._init_notifiers(notification_config)
    
    def _init_notifiers(self, notification_config: dict):
        """初始化所有通知器"""
        for notifier_type, notifier_class in self.NOTIFIER_TYPES.items():
            config = notification_config.get(notifier_type, {})
            if config.get("enabled", False):
                try:
                    notifier = notifier_class(config)
                    self.notifiers.append(notifier)
                    logger.info(f"[通知工厂] 已启用 {notifier_type} 通知")
                except Exception as e:
                    logger.error(f"[通知工厂] 初始化 {notifier_type} 通知失败: {e}")
    
    def send_all(self, items: List[BidItem]) -> Dict[str, bool]:
        """
        向所有启用的通知渠道发送消息
        
        Args:
            items: 招标信息列表
            
        Returns:
            各通知渠道的发送结果
        """
        if not items:
            logger.info("[通知工厂] 没有新的招标信息，跳过通知")
            return {}
        
        results = {}
        for notifier in self.notifiers:
            notifier_name = notifier.__class__.__name__.replace("Notifier", "").lower()
            try:
                success = notifier.send(items)
                results[notifier_name] = success
            except Exception as e:
                logger.error(f"[通知工厂] {notifier_name} 发送失败: {e}")
                results[notifier_name] = False
        
        return results
    
    def send_text_all(self, text: str) -> Dict[str, bool]:
        """
        向所有启用的通知渠道发送纯文本消息（用于无数据时的通知）

        Args:
            text: 要发送的文本内容

        Returns:
            各通知渠道的发送结果
        """
        results = {}
        for notifier in self.notifiers:
            notifier_name = notifier.__class__.__name__.replace("Notifier", "").lower()
            try:
                success = notifier.send_text(text)
                results[notifier_name] = success
            except Exception as e:
                logger.error(f"[通知工厂] {notifier_name} 文本发送失败: {e}")
                results[notifier_name] = False

        return results

    def get_enabled_notifiers(self) -> List[str]:
        """获取已启用的通知渠道列表"""
        return [
            notifier.__class__.__name__.replace("Notifier", "").lower()
            for notifier in self.notifiers
        ]
