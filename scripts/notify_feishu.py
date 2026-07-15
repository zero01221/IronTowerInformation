# coding=utf-8
"""飞书机器人通知脚本"""

import json
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.bidding_scraper.database import Database


def send_feishu_notification(webhook_url: str, items: list):
    """发送飞书通知"""
    if not webhook_url:
        print("未配置飞书 Webhook，跳过通知")
        return
    
    if not items:
        print("没有新的招标信息，跳过通知")
        return
    
    # 构建消息内容
    title = f"📢 云南铁塔招标信息 - 今日新增 {len(items)} 条"
    
    # 构建消息体
    content = f"**{title}**\n\n"
    
    for i, item in enumerate(items[:20], 1):  # 最多显示 20 条
        date = item.get('date', '未知')
        source = item.get('source', '未知')
        title_text = item.get('title', '未知')
        url = item.get('url', '')
        
        # 飞书 Markdown 格式：标题作为超链接
        if url:
            content += f"**{i}.** [{title_text}]({url})\n"
        else:
            content += f"**{i}.** {title_text}\n"
        
        content += f"    {date} | 📰 {source}\n"
        content += "\n"
    
    if len(items) > 20:
        content += f"\n...还有 {len(items) - 20} 条，请查看完整报告\n"
    
    # 飞书消息格式
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": content
                }
            ]
        }
    }
    
    # 发送请求
    import requests
    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        resp.raise_for_status()
        print(f"飞书通知发送成功：{len(items)} 条信息")
    except Exception as e:
        print(f"飞书通知发送失败：{e}")


def main():
    """主函数"""
    webhook_url = os.environ.get("FEISHU_WEBHOOK", "")
    
    if not webhook_url:
        print("未配置 FEISHU_WEBHOOK 环境变量")
        sys.exit(1)
    
    # 从数据库获取今日新增项目
    db = Database()
    today_items = db.get_today_items()
    
    print(f"今日新增 {len(today_items)} 条招标信息")
    
    # 发送通知
    send_feishu_notification(webhook_url, today_items)


if __name__ == "__main__":
    main()
