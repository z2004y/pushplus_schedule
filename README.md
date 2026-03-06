# 📅 pushplus_schedule

**pushplus_schedule** 是一款专为学生设计的智能课表推送系统。它不仅是一个简单的提醒工具，更是一个集成了**实时天气、法定节假日调度、期末状态感知**的校园生活助手。

---

## 🌟 核心亮点

### 🧠 智能调度逻辑

* **节假日自适应**：通过集成 `china-holiday-calender` API，脚本能识别“调休补班”和“法定节假日”。如果是法定假日，即便周一有课也会自动提示休息；如果是周末补班，则会准时提醒上课。
* **动态教学周计算**：只需设置开学日期，脚本自动计算当前是第几周，精准匹配单双周或指定周数的课程。
* **期末自动预警**：当进入第 17 周（可自定义）或距离学期结束不足 20 天时，推送界面会自动转为**“燃情红色”**，并置顶期末倒计时，营造备考氛围。

### 🎨 极致视觉体验

* **响应式 HTML 卡片**：针对移动端优化，无论是在微信 PushPlus 还是手机邮件客户端，均有完美的卡片式排版。
* **多色彩课程标识**：不同时段的课程采用循环配色，视觉重心清晰，重点信息（教室、教师）一目了然。

---

## 🛠️ 配置文件说明 (`timetable.json`)

项目核心依赖于 `timetable.json`，请严格遵循以下结构：

```json
{
  "semester_info": {
    "start_date": "2024-02-26",   // 这一周的周一即为第一周
    "end_date": "2024-07-10"     // 用于倒计时计算
  },
  "courses": [
    {
      "name": "高等数学",         // 课程名称
      "day": "周一",             // 周一至周日
      "weeks": "1-16周",         // 支持格式: "1-8,10-16周", "单周", "1,3,5周"
      "time": "08:30-10:05",     // 上课时间
      "location": "教1-202",      // 教室地点
      "teacher": "张教授",        // 任课教师
      "session": "第1-2节"        // 节次标签
    }
  ]
}

```

---

## 🚀 部署指引

### 1. 获取 API 密钥

* **Wechat Push**: 前往 [PushPlus 官网](http://www.pushplus.plus/) 扫码登录，获取 `Token`。
* **Weather**: 前往 [聚合数据](https://www.juhe.cn/) 申请“天气预报”API（免费）。
* **Email**: 开启邮箱 SMTP 服务（如 QQ 邮箱：设置 -> 账号 -> 生成授权码）。

### 2. 环境变量列表

| 变量名 | 说明 | 示例 |
| --- | --- | --- |
| `PUSHPLUS_TOKEN` | 微信推送令牌 | `a1b2c3d4...` |
| `WEATHER_API_KEY` | 聚合天气 KEY | `f9e8d7...` |
| `EMAIL_SENDER` | 发信人邮箱 | `my_bot@qq.com` |
| `EMAIL_PASS` | SMTP 授权码 | `abcdexxxxxxfgh` |
| `EMAIL_RECEIVER` | 收信人邮箱 (支持群发) | `user1@qq.com,user2@163.com` |

---

## 🤖 自动化运行 (GitHub Actions)

建议使用 GitHub Actions 实现每日 0 成本自动推送。在 `.github/workflows/` 下创建 `main.yml`:

```yaml
name: Daily Schedule Push
on:
  schedule:
    - cron: '22 23 * * *' # 北京时间每天早上 7:22 运行
  workflow_dispatch:      # 支持手动触发测试

jobs:
  push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install requests
      - name: Run script
        env:
          PUSHPLUS_TOKEN: ${{ secrets.PUSHPLUS_TOKEN }}
          WEATHER_API_KEY: ${{ secrets.WEATHER_API_KEY }}
          EMAIL_SENDER: ${{ secrets.EMAIL_SENDER }}
          EMAIL_PASS: ${{ secrets.EMAIL_PASS }}
          EMAIL_RECEIVER: ${{ secrets.EMAIL_RECEIVER }}
        run: python main.py

```

---

## ❓ 常见问题 (FAQ)

**Q: 为什么我收到的天气显示 N/A？** A: 请检查聚合天气的 API KEY 是否正确，或者该城市名称是否在聚合数据的覆盖范围内（默认为“兰州”）。

**Q: 如何修改期末周判定的时间？** A: 修改代码中的 `is_final_period = curr_week >= 17` 这一行，将 `17` 改为你学校的实际周数即可。

**Q: 邮件推送失败怎么办？** A: 请确认使用的是 SMTP 授权码而非邮箱登录密码，且 SMTP 服务器地址与端口（默认 465）匹配。

---

## 🤝 贡献与反馈

如果你有更好的 UI 设计思路或功能改进建议，欢迎提交 **Pull Request** 或 **Issue**。
