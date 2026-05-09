# 📅 pushplus_schedule

**pushplus_schedule** 是一款专为学生设计的智能课表推送系统。它不仅是一个简单的提醒工具，更是一个集成了**实时天气、调休补班映射、期末状态感知**的校园生活助手。



## 🌟 核心亮点

### 🧠 智能调度逻辑 (Holiday Engine 2.0)

*   **补班映射技术**：区别于普通脚本，本系统集成了 `timor.tech` 动态节假日 API。当遇到调休补班（如周日补周一的课）时，脚本会自动抓取目标日期的课表，并以**红色高亮**提醒，彻底杜绝“补班没课”的误报。
*   **数字精准识别**：采用 API 类型码（Type 0/3）双重判定，精准区分法定节假日区间、调休放假与周末补班。
*   **动态教学周计算**：只需设置开学周周一日期，脚本自动计算当前周数，完美支持单双周筛选逻辑。
*   **期末自动预警**：当进入第 17 周或倒计时开启时，界面会自动转为 **“警告红色”** ，并置顶期末状态，营造备考氛围。

### 🎨 极致视觉体验

*   **响应式 HTML 卡片**：适配微信 PushPlus 和各类手机邮件客户端。
*   **语义化配色**：
    *   **蓝色 (Primary)**：普通上课日。
    *   **绿色 (Success)**：法定放假，提示“好好休息”。
    *   **红色 (Danger)**：**调休补班日** 或 **期末周**，高能预警。



## 🛠️ 配置文件说明 (`timetable.json`)

请将文件置于根目录，结构参考如下：

```json
{
  "semester_info": {
    "start_date": "2026-03-02",   // 只要是开学第一周的任意一天即可
    "end_date": "2026-07-10"     // 用于倒计时计算
  },
  "courses": [
    {
      "name": "马克思主义基本原理", 
      "day": "周一",             // 匹配周一至周日
      "weeks": "1-16周(单)",      // 支持: "1-16", "2-10(双)", "1,3,5"
      "time": "08:30-10:10",
      "location": "信远楼-202",
      "teacher": "张教授"
    }
  ]
}
```



## 🚀 部署指引

### 1. 获取 API 密钥

*   **微信推送**: [PushPlus 官网](http://www.pushplus.plus/) 获取 `Token`。
*   **实时天气**: [聚合数据](https://www.juhe.cn/) 申请“天气预报”API。
*   **邮件授权**: 开启邮箱 SMTP 并获取**授权码**（非登录密码）。

### 2. 环境变量 (GitHub Secrets)

| 变量名 | 说明 |
| --- | --- |
| `PUSHPLUS_TOKEN` | PushPlus 令牌 |
| `WEATHER_API_KEY` | 聚合天气 Key |
| `EMAIL_SENDER` | 发信人邮箱 |
| `EMAIL_PASS` | SMTP 授权码 |
| `EMAIL_RECEIVER` | 收信人邮箱 (多个用逗号隔开) |



## 🤖 自动化运行 (GitHub Actions)

本配置已针对 **Node.js 24** 兼容性进行优化，消除了 Actions 弃用警告。

创建 `.github/workflows/main.yml`:

```yaml
name: 📚 Daily Schedule Push

on:
  schedule:
    - cron: '0 23 * * *' # 北京时间每天早上 07:00 运行
  workflow_dispatch:      # 支持手动点击测试

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true # 强制使用 Node 24 消除警告

jobs:
  push-schedule:
    runs-on: ubuntu-latest
    steps:
      - name: 📥 Checkout repository
        uses: actions/checkout@v4

      - name: 🐍 Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: 📦 Install dependencies
        run: pip install requests

      - name: 🕒 Set timezone
        run: sudo timedatectl set-timezone Asia/Shanghai

      - name: 📚 Run Script
        env:
          PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}
          WEATHER_API_KEY: ${{ secrets.WEATHER_API_KEY }}
          EMAIL_SENDER: ${{ secrets.EMAIL_SENDER }}
          EMAIL_PASS: ${{ secrets.EMAIL_PASS }}
          EMAIL_RECEIVER: ${{ secrets.EMAIL_RECEIVER }}
        run: python pushplus_schedule.py # 确保脚本文件名正确
```



## ❓ 常见问题 (FAQ)

**Q: 为什么补班日显示的是周一的课？**
A: 这是本脚本的特性。如果 API 返回今天补周一的课，脚本会自动映射。如果不想自动映射，请在 `get_holiday_status` 函数中关闭 `target_weekday` 的赋值。

**Q: 为什么 Actions 运行日志有 Node.js 的警告？**
A: 只要设置了 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`，虽然仍有提示，但系统已经在使用最新的 Node 24 环境运行，不会影响 2026 年后的使用。

**Q: 城市天气不对？**
A: 请在 `pushplus_schedule.py` 顶部的 `CITY_NAME` 修改为你所在的城市。



## 🤝 参与贡献

欢迎通过 Issue 或 Pull Request 提交功能改进（如对接更多的推送通道或优化 UI）。
