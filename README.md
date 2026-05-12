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
| **多渠道推送**   | 支持企业微信、飞书、钉钉、Telegram、邮件等 |
| **去重推送**     | 已推送过的招标信息不再重复推送             |
| **网页报告**     | 生成 HTML 报告，可在浏览器查看完整信息     |

---

## 🚀 快速开始

### 1. 获取项目代码

点击右上角 **Use this template** → 创建你自己的仓库

### 2. 配置推送渠道（选一个即可）

进入仓库 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

#### 企业微信机器人（推荐，最简单）

| Name                 | Secret                            |
| -------------------- | --------------------------------- |
| `WEWORK_WEBHOOK_URL` | 你的企业微信群机器人 Webhook 地址 |

#### 飞书机器人

| Name                 | Secret                      |
| -------------------- | --------------------------- |
| `FEISHU_WEBHOOK_URL` | 你的飞书机器人 Webhook 地址 |

#### 钉钉机器人

| Name                   | Secret                      |
| ---------------------- | --------------------------- |
| `DINGTALK_WEBHOOK_URL` | 你的钉钉机器人 Webhook 地址 |

#### 邮件推送

| Name             | Secret                       |
| ---------------- | ---------------------------- |
| `EMAIL_FROM`     | 发件人邮箱                   |
| `EMAIL_PASSWORD` | 邮箱密码/授权码              |
| `EMAIL_TO`       | 收件人邮箱（多个用逗号分隔） |

### 3. 修改关键词（可选）

编辑 `config/frequency_words.txt`，设置你关心的招标关键词：

```txt
# 示例：关注塔类业务和室分项目
铁塔
基站
塔类
室分
5G基站
通信杆
美化塔
```
