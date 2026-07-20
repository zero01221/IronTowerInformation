<div align="center">

# 铁塔招标信息推送

**自动监控全国铁塔招标信息，支持 Web 前端检索与飞书推送**

[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg?style=flat-square)](LICENSE)

</div>

---

## 核心功能

| 功能 | 说明 |
|------|------|
| **招标信息抓取** | 定时抓取 3 个数据源的铁塔相关招标/开标/评标/中标信息 |
| **Web 前端** | 本地 Web 页面，支持按地区、公告类型、标题关键字筛选 |
| **飞书推送** | 新增招标信息自动推送到飞书群聊 |
| **日期过滤** | 只抓取最近 7 天的招标信息 |
| **去重存储** | SQLite 存储，已存在的记录不再重复推送 |

---

## 数据源

| 数据源 | 说明 | 状态 |
|--------|------|------|
| 中国招标投标公共服务平台 | 国家级招标平台（4 种公告类型全覆盖） | ✅ |
| 中国铁塔电子采购平台 | 中国铁塔官方采购信息 | ✅ |
| 乙方宝 | 第三方聚合招标平台 | ✅ |

---

## 快速开始

### 环境要求

- Python 3.8+

### 安装

```bash
pip install -r requirements.txt
```

### 运行爬虫

```bash
# 运行爬虫，抓取最近 7 天全国铁塔招标信息
python -m scripts.bidding_scraper.main

# 只打印结果，不写文件
python -m scripts.bidding_scraper.main --dry-run

# 查看数据库统计
python -m scripts.bidding_scraper.main --stats

# 列出最近 N 天的记录
python -m scripts.bidding_scraper.main --list --days 7
```

### 启动 Web 前端

```bash
# 本地服务器（实时数据）
python scripts/serve_web.py
# 浏览器打开 http://localhost:8080

# 生成静态 HTML（可部署到任意静态托管）
python scripts/serve_web.py --output output/index.html
```

在线访问地址：**`https://zero01221.github.io/BiddingInformation`**（每日 8:00 左右自动更新）

支持：
- 🔍 标题关键字搜索
- 🗺️ 省份筛选（下拉框）
- 📋 公告类型筛选（招标公告/开标记录/评标公示/中标公告/采购公告）
- 📅 按日期分组展示

### 飞书通知

编辑 `config/bidding_scraper.yaml`：

```yaml
notification:
  feishu:
    enabled: true
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/your-token"
```

---

## 本地定时任务

### Linux/Mac

```bash
crontab -e
# 每天早上 8 点执行
0 8 * * * cd /path/to/project && python -m scripts.bidding_scraper.main
```

### Windows

使用"任务计划程序"创建每日定时任务：
- **程序**：`python`
- **参数**：`-m scripts.bidding_scraper.main`
- **起始于**：项目根目录

---

## 项目结构

```
IronTowerInformation/
├── config/
│   └── bidding_scraper.yaml       # 爬虫配置（数据源/关键词/通知）
├── scripts/
│   ├── bidding_scraper/            # 爬虫核心模块
│   │   ├── crawlers/               # 各数据源爬虫
│   │   │   ├── cebpubservice.py    # 中国招标投标公共服务平台
│   │   │   ├── chinatowercom.py    # 中国铁塔电子采购平台
│   │   │   └── yfbzb.py            # 乙方宝
│   │   ├── main.py                 # 主入口
│   │   ├── database.py             # SQLite 数据库
│   │   ├── filters.py              # 关键词/日期过滤
│   │   └── notification/           # 飞书/微信/钉钉通知
│   ├── serve_web.py                # Web 前端
│   └── notify_feishu.py            # 飞书通知脚本
├── output/
│   ├── bidding_history.db          # 数据库
│   └── bidding_feed.xml            # RSS 输出
├── requirements.txt
└── pyproject.toml
```

---

## 配置说明

### 关键词

```yaml
keywords:
  core:
    - 铁塔
    - 塔桅
    - 通信铁塔
    - 发射塔
    # ... 更多见配置文件
```

### 日期过滤

```yaml
filter:
  days_limit: 7   # 只抓取最近 7 天
```

### 数据源开关

```yaml
sources:
  cebpubservice:
    enabled: true     # 中国招标投标公共服务平台
  chinatowercom:
    enabled: true     # 中国铁塔电子采购平台
  yfbzb:
    enabled: true     # 乙方宝
```

### 请求配置

```yaml
request:
  timeout: 30                # 请求超时（秒）
  delay_between_requests: 8  # 请求间隔（秒）
  delay_between_sources: 20  # 数据源间延迟（秒）
```

---

## 更新日志

### 2026-07-20
- 🎉 新增 Web 前端，支持地区/类型/关键字筛选
- ✨ 中国招标投标公共服务平台：修复 API 接口，覆盖 4 种公告类型
- 🔧 去除地区限制，改为全国范围抓取
- 🧹 清理 TrendRadar 热点信息相关代码
- 📝 精简项目依赖，仅保留招标爬虫所需

### 2026-07-14
- 重构爬虫模块，支持多数据源
- 增加日期过滤功能
- 扩展关键词：广播电视、发射台、维护/维修等
- 优化飞书消息格式

---

## 许可证

GPL-3.0 License
