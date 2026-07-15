# coding=utf-8
"""日志管理模块"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .config import Config


class Logger:
    """日志管理类"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str = "bidding_scraper") -> logging.Logger:
        """获取日志记录器"""
        if name in cls._loggers:
            return cls._loggers[name]
        
        config = Config.get_instance()
        
        # 创建logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, config.get("logging.level", "INFO")))
        
        # 避免重复添加handler
        if logger.handlers:
            cls._loggers[name] = logger
            return logger
        
        # 控制台handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)
        
        # 文件handler（可选）
        log_file = config.get("logging.file")
        if log_file:
            # 使用项目根目录作为基础路径
            project_root = Path(__file__).parent.parent.parent
            log_path = project_root / log_file
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            max_size = config.get_int("logging.max_size", 10) * 1024 * 1024  # MB to bytes
            backup_count = config.get_int("logging.backup_count", 5)
            
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger


def get_logger(name: str = "bidding_scraper") -> logging.Logger:
    """获取日志记录器的便捷函数"""
    return Logger.get_logger(name)
