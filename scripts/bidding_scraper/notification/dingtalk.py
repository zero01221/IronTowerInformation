# coding=utf-8
"""钉钉通知器"""

import requests
from typing import List

from .base import BaseNotifier
from ..models import BidItem
from ..logger import get_logger

logger = get_logger(__name__)


class DingtalkNotifier(BaseNotifier):
    """
    钉钉通知器
    
    配置示例（在 config/bidding_scraper.yaml 中）：
    
    notification:
      dingtalk:
        enabled: true
        # Webhook 地址 - 在钉钉群聊中添加自定义机器人后获取
        # 获取方式：
        # 1. 打开钉钉群聊
        # 2. 点击群设置 -> 智能群助手 -> 添加机器人
        # 3. 选择"自定义"机器人
        # 4. 设置安全设置（建议选择"加签"或"自定义关键词"）
        # 5. 复制 Webhook 地址
        webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=your-access-token"
        
        # 如果安全设置选择了"加签"，需要填写密钥
        # secret: "SEC..."
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("webhook_url", "")
        self.secret = config.get("secret", "")
    
    def send(self, items: List[BidItem]) -> bool:
        """
        发送钉钉通知
        
        Args:
            items: 招标信息列表
            
        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug("[钉钉通知] 未启用，跳过")
            return True
        
        if not self.webhook_url:
            logger.error("[钉钉通知] Webhook URL 未配置")
            return False
        
        if not items:
            logger.info("[钉钉通知] 没有新的招标信息，跳过通知")
            return True
        
        message = self.format_message(items)
        
        # 钉钉消息格式
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        
        # 如果配置了密钥，需要加签
        url = self.webhook_url
        if self.secret:
            import time
            import hashlib
            import hmac
            import base64
            from urllib.parse import quote_plus
            
            timestamp = str(round(time.time() * 1000))
            secret_enc = self.secret.encode('utf-8')
            string_to_sign = f'{timestamp}\n{self.secret}'
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = quote_plus(base64.b64encode(hmac_code))
            url = f"{self.webhook_url}&timestamp={timestamp}&sign={sign}"
        
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    logger.info(f"[钉钉通知] 发送成功，共 {len(items)} 条信息")
                    return True
                else:
                    logger.error(f"[钉钉通知] 发送失败: {result.get('errmsg')}")
                    return False
            else:
                logger.error(f"[钉钉通知] HTTP 错误: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"[钉钉通知] 发送异常: {e}")
            return False
