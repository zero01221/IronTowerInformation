# coding=utf-8
"""招标信息爬虫主入口"""

import argparse
import sys
from pathlib import Path

# 修复 Windows GBK 终端 print 乱码
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .config import Config
from .database import Database
from .logger import get_logger
from .base_crawler import CrawlerManager
from .crawlers import (
    CcgpCrawler,
    CcgpYunnanCrawler,
    CebpubserviceCrawler,
    ChinaTowerComCrawler,
    TowerComCnCrawler,
    MiitTxzbqyCrawler,
)
from .output import OutputFormatter
from .notification import NotifierFactory

logger = get_logger(__name__)


def create_crawler_manager() -> CrawlerManager:
    """创建爬虫管理器"""
    config = Config.get_instance()
    manager = CrawlerManager()
    
    sources = config.get_enabled_sources()
    
    # 注册各数据源爬虫
    if "ccgp" in sources:
        manager.register(CcgpCrawler(sources["ccgp"]))
    
    if "ccgp_yunnan" in sources:
        manager.register(CcgpYunnanCrawler(sources["ccgp_yunnan"]))
    
    if "cebpubservice" in sources:
        manager.register(CebpubserviceCrawler(sources["cebpubservice"]))
    
    if "chinatowercom" in sources:
        manager.register(ChinaTowerComCrawler(sources["chinatowercom"]))
    
    if "tower_com_cn" in sources:
        manager.register(TowerComCnCrawler(sources["tower_com_cn"]))
    
    if "miit_txzbqy" in sources:
        manager.register(MiitTxzbqyCrawler(sources["miit_txzbqy"]))
    
    return manager


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="招标信息爬虫 - 生成 RSS feed")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument("--dry-run", "-n", action="store_true", help="只打印结果，不写文件")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument("--stats", action="store_true", help="显示数据库统计信息")
    
    args = parser.parse_args()
    
    # 加载配置
    Config.load(args.config)
    config = Config.get_instance()
    
    # 初始化数据库
    db = Database()
    
    # 显示统计信息
    if args.stats:
        stats = db.get_stats()
        print("\n数据库统计:")
        print(f"  总记录数: {stats['total']}")
        print(f"  最近7天新增: {stats['recent_week']}")
        print(f"  按来源统计:")
        for source, count in stats['by_source'].items():
            print(f"    {source}: {count}")
        print(f"  数据库路径: {stats['db_path']}")
        return
    
    # 创建爬虫管理器
    manager = create_crawler_manager()
    
    # 健康检查
    if config.get_bool("health_check.enabled", True):
        if not manager.health_check():
            logger.warning("没有健康的数据源")
    
    # 运行所有爬虫
    all_items = manager.run_all()
    
    if not all_items:
        logger.info("未找到任何招标信息")
        return
    
    # 去重（使用数据库）
    existing_ids = db.get_item_ids()
    new_items = [item for item in all_items if item.item_id not in existing_ids]
    
    if new_items:
        # 保存新项目到数据库
        saved_count = db.save_items(new_items)
        logger.info(f"新增 {saved_count} 条招标信息")
        
        # 发送通知
        notification_config = config.get_notification_config()
        if notification_config:
            notifier_factory = NotifierFactory(notification_config)
            enabled_notifiers = notifier_factory.get_enabled_notifiers()
            if enabled_notifiers:
                logger.info(f"发送通知到: {', '.join(enabled_notifiers)}")
                results = notifier_factory.send_all(new_items)
                for notifier_name, success in results.items():
                    status = "成功" if success else "失败"
                    logger.info(f"  {notifier_name}: {status}")
    
    # 获取所有历史记录（用于RSS输出）
    all_history_items = db.get_all_items()
    
    # 输出结果
    formatter = OutputFormatter()
    
    if args.dry_run:
        formatter.print_summary(all_history_items)
    else:
        formatter.save_rss(all_history_items, args.output)
        formatter.print_summary(all_history_items)
    
    # 清理过期数据
    db.cleanup_old_items()
    
    # 显示爬虫状态
    logger.info("\n数据源状态:")
    for status in manager.get_status():
        health = "✓" if status["healthy"] else "✗"
        logger.info(f"  [{health}] {status['name']}: {status['total_items']} 条")


if __name__ == "__main__":
    main()
