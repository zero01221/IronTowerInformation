# coding=utf-8
"""配置管理模块"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class Config:
    """配置管理类"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """加载配置文件"""
        instance = cls()
        
        if config_path is None:
            # 默认配置路径
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "bidding_scraper.yaml"
        
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                instance._config = yaml.safe_load(f) or {}
        else:
            # 使用默认配置
            instance._config = instance._get_default_config()
        
        return instance
    
    @classmethod
    def get_instance(cls) -> "Config":
        """获取配置实例"""
        if cls._instance is None:
            cls.load()
        return cls._instance
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套键"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    def get_list(self, key: str, default: Optional[List] = None) -> List:
        """获取列表配置"""
        value = self.get(key, default or [])
        if isinstance(value, list):
            return value
        return [value] if value else []
    
    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数配置"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔配置"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "yes", "1", "on")
        return bool(value)
    
    def get_sources(self) -> Dict[str, Dict]:
        """获取所有数据源配置"""
        return self.get("sources", {})
    
    def get_enabled_sources(self) -> Dict[str, Dict]:
        """获取已启用的数据源配置"""
        sources = self.get_sources()
        return {
            name: config 
            for name, config in sources.items() 
            if config.get("enabled", True)
        }
    
    def get_core_keywords(self) -> List[str]:
        """获取核心关键词"""
        return self.get_list("keywords.core")
    
    def get_yunnan_keywords(self) -> List[str]:
        """获取云南地区关键词"""
        return self.get_list("keywords.yunnan")
    
    def get_industry_keywords(self) -> List[str]:
        """获取行业关键词"""
        return self.get_list("keywords.industry")
    
    def get_user_agents(self) -> List[str]:
        """获取User-Agent列表"""
        return self.get_list("request.user_agents")
    
    def get_notification_config(self) -> Dict[str, Any]:
        """获取通知配置，支持从环境变量读取Webhook"""
        notification = self.get("notification", {})
        
        # 从环境变量覆盖Webhook URL（优先级更高）
        # 这样可以避免将敏感的Webhook地址提交到仓库
        feishu_env = os.environ.get("FEISHU_WEBHOOK_URL")
        if feishu_env:
            notification.setdefault("feishu", {})["webhook_url"] = feishu_env
        
        wechat_env = os.environ.get("WECHAT_WEBHOOK_URL")
        if wechat_env:
            notification.setdefault("wechat", {})["webhook_url"] = wechat_env
        
        dingtalk_env = os.environ.get("DINGTALK_WEBHOOK_URL")
        if dingtalk_env:
            notification.setdefault("dingtalk", {})["webhook_url"] = dingtalk_env
        
        dingtalk_secret_env = os.environ.get("DINGTALK_SECRET")
        if dingtalk_secret_env:
            notification.setdefault("dingtalk", {})["secret"] = dingtalk_secret_env
        
        return notification
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "keywords": {
                "core": ["铁塔", "塔桅", "通信铁塔", "中国铁塔"],
                "yunnan": ["云南", "昆明", "大理", "丽江", "曲靖", "玉溪", "普洱", "红河", "文山", "西双版纳", "楚雄", "昭通", "保山", "德宏", "怒江", "迪庆", "临沧"],
                "industry": ["通信", "移动", "联通", "电信", "5G", "基站"],
            },
            "sources": {
                "yfbzb": {
                    "enabled": True,
                    "name": "乙方宝",
                    "keywords": ["铁塔", "塔桅"],
                },
            },
            "request": {
                "timeout": 30,
                "retry_attempts": 3,
                "delay_between_requests": 5,
            },
            "database": {
                "path": "output/bidding_history.db",
                "retention_days": 90,
            },
            "output": {
                "rss_file": "output/bidding_feed.xml",
                "max_items": 100,
            },
            "logging": {
                "level": "INFO",
                "file": "output/bidding_scraper.log",
            },
        }
