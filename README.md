---

# 📅 智能课表推送助手 (PushPlus 版)

一个基于 Python 的自动化工具，能够根据您的课程表（JSON 格式）和中国法定节假日安排，每天早晨通过 **PushPlus** 向您的微信推送精美的今日课表卡片。

---

## ✨ 功能特性

* **智能周数计算**：根据学期开始日期自动计算当前教学周。
* **单双周识别**：完美支持 `1-18周`、`1,3,5周`、`2-16双周` 等多种排课逻辑。
* **节假日感知**：
* **自动避让**：法定节假日及周末自动进入“放假模式”，推送温馨祝福。
* **补班提醒**：自动识别调休补班日，即使是周末也会准时推送课表。


* **实时天气集成**：页眉自动显示当日天气信息（温度、晴雨状态）。
* **精美卡片样式**：适配移动端微信阅读体验，采用响应式 HTML 设计。

---

## 🚀 快速上手

### 1. 准备课程数据

在项目根目录创建 `timetable.json`，格式如下：

```json
{
  "semester_info": {
    "name": "2025-2026春季学期",
    "start_date": "2026-02-20"
  },
  "courses": [
    {
      "name": "高阶英语 I",
      "day": "周一",
      "time": "08:00-09:50",
      "session": "1-2节",
      "location": "A1",
      "teacher": "王老师",
      "weeks": "2,4,6,8,10,12,14,16,18周"
    }
  ]
}

```

### 2. 获取必要 Token

* **PushPlus Token**: 前往 [PushPlus 官网](http://www.pushplus.plus/) 扫码登录，获取您的个人 Token。
* **天气 API Key (可选)**: 前往 [聚合数据](https://www.juhe.cn/) 申请简单天气 API（免费次数足够日常使用）。

---

## 🤖 自动化部署 (GitHub Actions)

无需服务器，利用 GitHub Actions 实现每天定时推送。

### 第一步：设置 Secrets

进入您的 GitHub 仓库：`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`，添加以下变量：

| 名称 | 说明 |
| --- | --- |
| `PUSHPLUS_TOKEN` | 您的 PushPlus 令牌 |
| `WEATHER_API_KEY` | 聚合天气 API Key (可选) |

### 第二步：创建工作流文件

在项目路径 `.github/workflows/` 下创建 `daily_push.yml`：

```yaml
name: Daily Schedule Push

on:
  schedule:
    - cron: '23 23 * * *' # 北京时间每天早上 7:23 推送
  workflow_dispatch:      # 支持手动触发测试

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install requests
      - name: Run push script
        env:
          PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}
          WEATHER_API_KEY: ${{ secrets.WEATHER_API_KEY }}
        run: python pushplus_schedule.py

```

---

## 🛠️ 技术实现说明

1. **数据流**：脚本首先读取本地课程数据，随后通过 REST API 获取最新的节假日和天气信息。
2. **日期处理**：使用 Python 的 `datetime` 和 `timedelta` 模块进行复杂的日期加减运算，确保补班逻辑无误。
3. **HTML 渲染**：内置一套极简的内联 CSS 模板，确保在微信内置浏览器中拥有极佳的显示效果。

---

## 🤝 数据来源

* 节假日数据：[china-holiday-calender](https://github.com/lanceliao/china-holiday-calender)
* 天气数据：[聚合数据 API](https://www.juhe.cn/)

---

## 📝 许可证

本项目采用 [MIT License](https://www.google.com/search?q=LICENSE) 开源。

---
