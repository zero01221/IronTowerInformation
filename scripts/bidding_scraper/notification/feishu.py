# coding=utf-8
"""飞书通知器"""

import requests
from typing import List

from .base import BaseNotifier
from ..models import BidItem
from ..logger import get_logger

logger = get_logger(__name__)


class FeishuNotifier(BaseNotifier):
    """
    飞书通知器
    
    配置示例（在 config/bidding_scraper.yaml 中）：
    
    notification:
      feishu:
        enabled: true
        # Webhook 地址 - 在飞书群聊中添加自定义机器人后获取
        # 获取方式：
        # 1. 打开飞书群聊
        # 2. 点击群设置 -> 群机器人 -> 添加机器人
        # 3. 选择"自定义机器人"
        # 4. 复制 Webhook 地址
        webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-token"
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("webhook_url", "")
    
    def send(self, items: List[BidItem]) -> bool:
        """
        发送飞书通知
        
        Args:
            items: 招标信息列表
            
        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug("[飞书通知] 未启用，跳过")
            return True
        
        if not self.webhook_url:
            logger.error("[飞书通知] Webhook URL 未配置")
            return False
        
        if not items:
            logger.info("[飞书通知] 没有新的招标信息，跳过通知")
            return True
        
        message = self.format_message(items)
        
        # 飞书消息格式
        payload = {
            "msg_type": "text",
            "content": {
                "text": message
            }
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info(f"[飞书通知] 发送成功，共 {len(items)} 条信息")
                    return True
                else:
                    logger.error(f"[飞书通知] 发送失败: {result.get('msg')}")
                    return False
            else:
                logger.error(f"[飞书通知] HTTP 错误: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[飞书通知] 发送异常: {e}")
            return False

    def send_text(self, text: str) -> bool:
        """
        发送纯文本消息到飞书

        Args:
            text: 要发送的文本内容

        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug("[飞书通知] 未启用，跳过")
            return True

        if not self.webhook_url:
            logger.error("[飞书通知] Webhook URL 未配置")
            return False

        payload = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info(f"[飞书通知] 文本消息发送成功")
                    return True
                else:
                    logger.error(f"[飞书通知] 发送失败: {result.get('msg')}")
                    return False
            else:
                logger.error(f"[飞书通知] HTTP 错误: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"[飞书通知] 发送异常: {e}")
            return False
