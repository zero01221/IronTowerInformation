# coding=utf-8
"""企业微信通知器"""

import requests
from typing import List

from .base import BaseNotifier
from ..models import BidItem
from ..logger import get_logger

logger = get_logger(__name__)


class WechatNotifier(BaseNotifier):
    """
    企业微信通知器
    
    配置示例（在 config/bidding_scraper.yaml 中）：
    
    notification:
      wechat:
        enabled: true
        # Webhook 地址 - 在企业微信群聊中添加机器人后获取
        # 获取方式：
        # 1. 打开企业微信群聊
        # 2. 点击群设置 -> 群机器人 -> 添加机器人
        # 3. 复制 Webhook 地址
        webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your-webhook-key"
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("webhook_url", "")
    
    def send(self, items: List[BidItem]) -> bool:
        """
        发送企业微信通知
        
        Args:
            items: 招标信息列表
            
        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug("[企业微信通知] 未启用，跳过")
            return True
        
        if not self.webhook_url:
            logger.error("[企业微信通知] Webhook URL 未配置")
            return False
        
        if not items:
            logger.info("[企业微信通知] 没有新的招标信息，跳过通知")
            return True
        
        message = self.format_message(items)
        
        # 企业微信消息格式
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
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
                if result.get("errcode") == 0:
                    logger.info(f"[企业微信通知] 发送成功，共 {len(items)} 条信息")
                    return True
                else:
                    logger.error(f"[企业微信通知] 发送失败: {result.get('errmsg')}")
                    return False
            else:
                logger.error(f"[企业微信通知] HTTP 错误: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[企业微信通知] 发送异常: {e}")
            return False
