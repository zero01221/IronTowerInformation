# coding=utf-8
"""输出格式化模块"""

from collections import defaultdict
from datetime import datetime
from typing import List
from xml.sax.saxutils import escape

from .config import Config
from .logger import get_logger
from .models import BidItem

logger = get_logger(__name__)


class OutputFormatter:
    """输出格式化类"""
    
    def __init__(self):
        """初始化"""
        self.config = Config.get_instance()
    
    def format_console(self, items: List[BidItem]) -> str:
        """格式化为控制台输出（按日期分类）"""
        if not items:
            return "未找到招标信息"
        
        lines = []
        lines.append("")
        lines.append("=" * 50)
        lines.append(f"共收集到 {len(items)} 条招标信息")
        lines.append("=" * 50)
        lines.append("")
        
        # 按日期分组
        items_by_date = defaultdict(list)
        for item in items:
            items_by_date[item.date or "未知日期"].append(item)
        
        # 按日期降序排列
        sorted_dates = sorted(items_by_date.keys(), reverse=True)
        
        for date in sorted_dates:
            date_items = items_by_date[date]
            lines.append(f"【{date}】共 {len(date_items)} 条")

            for item in date_items:
                lines.append(f"  {item.title}")
                # 优先显示原始链接
                display_url = item.original_url or item.url
                lines.append(f"    {display_url}")
                lines.append(f"    [来源: {item.source}]")

            lines.append("")
        
        return "\n".join(lines)
    
    def format_rss(self, items: List[BidItem]) -> str:
        """格式化为 RSS XML"""
        max_items = self.config.get_int("output.max_items", 100)
        items = items[:max_items]
        
        rss_title = self.config.get("output.rss_title", "招标信息")
        rss_desc = self.config.get("output.rss_description", "招标信息聚合")
        rss_link = self.config.get("output.rss_link", "")
        
        lines = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<rss version="2.0">')
        lines.append('<channel>')
        lines.append(f'<title>{escape(rss_title)}</title>')
        lines.append(f'<description>{escape(rss_desc)}</description>')
        lines.append(f'<link>{escape(rss_link)}</link>')
        lines.append(f'<lastBuildDate>{self._format_rss_date(datetime.now())}</lastBuildDate>')
        
        for item in items:
            lines.append('<item>')
            lines.append(f'<title>{escape(item.title)}</title>')
            # 优先使用原始链接
            display_url = item.original_url or item.url
            lines.append(f'<link>{escape(display_url)}</link>')
            lines.append(f'<description>{escape(item.description)}</description>')
            lines.append(f'<pubDate>{self._format_rss_date(self._parse_date(item.date))}</pubDate>')
            lines.append(f'<guid>{escape(item.item_id)}</guid>')
            lines.append('</item>')
        
        lines.append('</channel>')
        lines.append('</rss>')
        
        return "\n".join(lines)
    
    def _format_rss_date(self, dt: datetime) -> str:
        """格式化 RSS 日期"""
        from email.utils import formatdate
        import time
        return formatdate(time.mktime(dt.timetuple()))
    
    def _parse_date(self, date_str: str) -> datetime:
        """解析日期字符串"""
        if not date_str:
            return datetime.now()
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return datetime.now()
    
    def print_summary(self, items: List[BidItem]):
        """打印摘要到控制台"""
        output = self.format_console(items)
        print(output)
    
    def save_rss(self, items: List[BidItem], output_path: str = None):
        """保存 RSS 文件"""
        if output_path is None:
            output_path = self.config.get("output.rss_file", "output/bidding_feed.xml")
        
        rss_content = self.format_rss(items)
        
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rss_content)
        
        logger.info(f"RSS 文件已写入: {output_path}")
