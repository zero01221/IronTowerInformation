<div align="center">

# 铁塔招标信息推送

**自动监控全国/区域铁塔招标信息，实时推送到你的手机/邮箱**

[![GitHub Stars](https://img.shields.io/github/stars/zero01221/IronTowerInformation?style=flat-square&logo=github&color=yellow)](https://github.com/zero01221/IronTowerInformation/stargazers)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg?style=flat-square)](LICENSE)

</div>

---

## 🙏 致谢

本项目基于 [TrendRadar](https://github.com/sansan0/TrendRadar) 项目进行二次开发和定制，特别感谢原作者 [@sansan0](https://github.com/sansan0) 的开源精神和杰出工作。

TrendRadar 是一个功能强大的 AI 驱动的舆情与热点监控工具，为本项目的实现提供了坚实的基础。

🔗 原项目地址：[https://github.com/sansan0/TrendRadar](https://github.com/sansan0/TrendRadar)

---

## 🎯 核心功能

| 功能             | 说明                                       |
| ---------------- | ------------------------------------------ |
| **招标信息抓取** | 定时抓取铁塔招标信息（中国铁塔、运营商等） |
| **关键词筛选**   | 自定义关注的关键词，只推送你关心的内容     |
| **多渠道推送**   | 支持飞书、企业微信、钉钉、Telegram、邮件等 |
| **去重推送**     | 已推送过的招标信息不再重复推送             |
| **日期过滤**     | 只推送最近 N 天内的招标信息                |

---

## 📡 数据源

| 数据源 | 网址 | 说明 |
|--------|------|------|
| 中国政府采购网 | www.ccgp.gov.cn | 政府采购信息 |
| 云南省政府采购网 | www.ccgp-yunnan.gov.cn | 云南省政府采购信息 |
| 中国招标投标公共服务平台 | www.cebpubservice.com | 国家级招标平台 |
| 中国铁塔在线商务平台 | www.tower.com.cn | 网络不可达 |
| 中国铁塔电子采购平台 | ebid.chinatowercom.cn | ES检索服务有时后端故障 |
| 通信工程建设项目招标投标管理信息平台 | txzbqy.miit.gov.cn | 公开REST API端点待逆向，当前需要配置 search_url |

---

##  快速开始

### 1. 获取项目代码

点击右上角 **Use this template** → 创建你自己的仓库

### 2. 配置推送渠道（选一个即可）

进入仓库 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

#### 飞书机器人（推荐）

| Name                 | Secret                      |
| -------------------- | --------------------------- |
| `FEISHU_WEBHOOK` | 你的飞书机器人 Webhook 地址 |

**获取 Webhook 地址：**
1. 打开飞书群 → 群设置 → 群机器人
2. 添加机器人 → 复制 Webhook 地址
3. 格式：`https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx`

#### 企业微信机器人

| Name                 | Secret                            |
| -------------------- | --------------------------------- |
| `WEWORK_WEBHOOK_URL` | 你的企业微信群机器人 Webhook 地址 |

#### 钉钉机器人

| Name                   | Secret                      |
| ---------------------- | --------------------------- |
| `DINGTALK_WEBHOOK_URL` | 你的钉钉机器人 Webhook 地址 |

### 3. 修改关键词（可选）

编辑 `config/bidding_scraper.yaml`，设置你关心的招标关键词：

```yaml
keywords:
  core:
    - 铁塔
    - 塔桅
    - 桅杆
    - 发射塔
    - 广播电视发射台
    # ... 更多关键词
```

### 4. 配置定时推送

GitHub Actions 已配置好每天早上 8:00（北京时间）自动运行。

如需修改推送时间，编辑 `.github/workflows/daily-crawl.yml`：

```yaml
on:
  schedule:
    # 每天 UTC 0:00 (北京时间 8:00)
    - cron: '0 0 * * *'
```

---


## 💻 本地运行

### 环境要求

- Python 3.12+
- uv（包管理器）

### 安装依赖

```bash
# 使用 uv 安装
uv sync

# 或使用 pip
pip install -r requirements.txt
pip install beautifulsoup4
```

### 运行爬虫

```bash
# 运行爬虫并生成 RSS
python -m scripts.bidding_scraper

# 只打印结果，不写文件
python -m scripts.bidding_scraper --dry-run

# 指定输出文件
python -m scripts.bidding_scraper --output output/bidding_feed.xml
```

### 查看统计

```bash
# 查看数据库统计信息
python -m scripts.bidding_scraper --stats
```

---

## ⏰ 定时任务配置

### 配置通知渠道

编辑 `config/bidding_scraper.yaml`，配置你要使用的通知渠道：

```yaml
notification:
  # 飞书通知
  feishu:
    enabled: true
    webhook_url: "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-id"
  
  # 企业微信通知
  wechat:
    enabled: true
    webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your-key"
  
  # 钉钉通知
  dingtalk:
    enabled: true
    webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=your-token"
```

详细配置说明请查看配置文件中的注释。

### Linux/Mac 定时任务

使用 cron 配置定时任务：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天早上8点执行）
0 8 * * * /path/to/IronTowerInformation/scripts/run_scheduler.sh >> /path/to/IronTowerInformation/output/scheduler.log 2>&1
```

### Windows 定时任务

1. 打开"任务计划程序"
2. 创建基本任务
3. 配置：
   - **名称**：招标信息爬虫
   - **触发器**：每天 8:00
   - **操作**：启动程序
   - **程序**：`python`
   - **参数**：`-m scripts.bidding_scraper`
   - **起始于**：项目根目录路径

或者使用批处理文件：
- **程序**：选择 `scripts/run_scheduler.bat`
- **起始于**：项目根目录路径

---

## 📁 项目结构

```
IronTowerInformation/
├── config/
│   ├── bidding_scraper.yaml    # 爬虫配置
│   └── config.yaml             # TrendRadar 配置
├── scripts/
│   ├── bidding_scraper/        # 招标爬虫模块
│   │   ├── crawlers/           # 各数据源爬虫
│   │   ├── main.py             # 主入口
│   │   ├── config.py           # 配置管理
│   │   ├── filters.py          # 过滤逻辑
│   │   ├── database.py         # 数据库
│   │   └── logger.py           # 日志
│   ── notify_feishu.py        # 飞书通知脚本
├── output/                     # 输出目录
│   ├── bidding_feed.xml        # RSS 文件
│   └── bidding_scraper.log     # 日志文件
├── .github/workflows/
│   └── daily-crawl.yml         # GitHub Actions 定时任务
└── README.md
```

---

## 🔧 配置说明

### bidding_scraper.yaml

```yaml
# 数据源配置
sources:
  chinatowercom:
    enabled: true
    max_age_days: 15          # 只抓取最近 15 天的信息
  tower_com_cn:
    enabled: true
    max_age_days: 15
  # ... 其他数据源

# 关键词配置
keywords:
  core:                       # 核心关键词（必须匹配）
    - 铁塔
    - 塔桅
    - 发射塔
  region:                     # 地区关键词
    - 云南
    - 昆明
    # ...

# 推送配置
push:
  schedule:
    time: "08:00"             # 推送时间（北京时间）
  feishu:
    enabled: true
    webhook: ""               # 留空则从环境变量读取

### 数据源配置

编辑 `config/bidding_scraper.yaml`：

```yaml
sources:
  yfbzb:
    enabled: true           # 是否启用
    keywords:               # 搜索关键词
      - 铁塔
      - 塔桅
  
  ccgp:
    enabled: true           # 中国政府采购网
  
  ynggzy:
    enabled: true           # 云南省公共资源交易中心
```

### 日期过滤

默认只抓取最近 15 天的信息，可在配置文件中修改：

```yaml
filter:
  # 只保留最近 N 天的数据
  days_limit: 15
```

### 请求配置

```yaml
request:
  timeout: 30               # 请求超时时间（秒）
  retry_attempts: 3         # 重试次数
  delay_between_requests: 8 # 请求间隔（秒）
```

---

## 📝 更新日志

### 2026-07-14
- 重构爬虫模块，支持 6 个数据源
- 增加日期过滤功能（默认 15 天）
- 扩展关键词：广播电视、发射台、发射塔、维护/维修等
- 优化飞书消息格式（超链接 + 时间）
- 修复本地日志文件不更新问题
- 清理无关代码（热榜平台配置）
### v2.1.0 (2026-07-12)

- ✨ 添加日期过滤功能，默认只抓取最近 15 天的信息
- ✨ 添加通知模块，支持飞书、企业微信、钉钉推送
- ✨ 添加定时任务脚本
- 🐛 修复云南省公共资源交易中心 API 返回类型错误
- 🐛 优化乙方宝爬虫策略，避免触发反爬虫

### v2.0.0 (2026-07-12)

- 🎉 架构重构，模块化设计
- ✨ 添加 SQLite 数据库存储历史记录
- ✨ 添加错误重试机制
- ✨ 添加日志系统
- ✨ 添加健康检查功能

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

GPL-3.0 License

