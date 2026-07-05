## 项目概述

铁塔招标信息推送（IronTowerInformation），基于 [TrendRadar](https://github.com/sansan0/TrendRadar) 二次开发。自动监控全国/区域铁塔招标信息，支持关键词筛选和多渠道推送（企业微信、飞书、钉钉、Telegram、邮件）。

## 技术栈

- **语言**: Python 3.12+
- **包管理**: uv（pyproject.toml + uv.lock）
- **核心依赖**: requests, PyYAML, feedparser, boto3, litellm, fastmcp, json-repair, tenacity
- **构建系统**: hatchling
- **MCP 服务**: fastmcp + websockets（HTTP 模式，端口 3333）

## 目录结构

```
/workspace/projects/
├── trendradar/           # 主包
│   ├── __main__.py       # CLI 主入口（python -m trendradar）
│   ├── context.py        # 应用上下文
│   ├── core/             # 配置加载、分析、调度
│   ├── crawler/          # 数据抓取模块
│   ├── notification/     # 多渠道推送（企微/飞书/钉钉/TG/邮件）
│   ├── report/           # 报告生成
│   ├── storage/          # 数据存储
│   ├── ai/               # AI 分析模块
│   └── utils/            # 工具函数
├── mcp_server/           # MCP 服务端
├── config/               # 配置文件
│   ├── config.yaml       # 主配置
│   ├── frequency_words.txt # 关键词列表
│   ├── timeline.yaml     # 时间线配置
│   └── ai_filter/        # AI 过滤配置
├── scripts/              # 脚本（bidding_scraper.py 招标抓取）
├── output/               # 输出目录
├── docker/               # Docker 配置
├── index.html            # 报告模板（静态 HTML）
├── start-http.sh         # MCP HTTP 服务启动脚本
├── pyproject.toml        # 项目配置
└── requirements.txt      # 依赖清单
```

## 关键入口 / 核心模块

- **CLI 入口**: `python -m trendradar` 或 `trendradar`（安装后）
- **MCP 服务**: `python -m mcp_server.server` 或 `trendradar-mcp`
- **HTTP 模式**: `bash start-http.sh`（端口 3333）
- **招标抓取脚本**: `scripts/bidding_scraper.py`
- **主配置**: `config/config.yaml`

## 运行与预览

- 本项目为后端/CLI 工具，无可预览的 Web 界面
- 运行方式：`uv run python -m trendradar`
- MCP 服务：`uv run python -m mcp_server.server --transport http --host 0.0.0.0 --port 3333`

## 用户偏好与长期约束

- Python 项目必须使用 uv 管理依赖和虚拟环境
- 禁止使用 npm/yarn
- 配置文件位于 config/ 目录

## 常见问题和预防

- 虚拟环境未创建时需先运行 `uv sync`
- MCP HTTP 服务默认端口 3333，注意不要与系统端口冲突
- 推送渠道需在 GitHub Secrets 或环境变量中配置 Webhook/凭据
