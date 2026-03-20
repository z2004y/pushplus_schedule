import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议通过环境变量设置，或直接在下方填入字符串
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 邮件配置
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")  # 注意：此处应填写SMTP授权码而非登录密码
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") # 支持 "user1@qq.com,user2@163.com"
SMTP_SERVER = "smtp.qq.com"  # QQ邮箱使用 smtp.qq.com，网易使用 smtp.163.com
SMTP_PORT = 465

# 节假日 API
HOLIDAY_API_URL = "https://raw.githubusercontent.com/lanceliao/china-holiday-calender/master/holidayAPI.json"

# ================== 2. 核心逻辑函数 ==================

def send_email(title, html_content):
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        print("⚠️ 邮件环境变量配置不全，已跳过邮件发送。")
        return

    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
    if not receivers: return

    message = MIMEText(html_content, 'html', 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    message['From'] = f"{Header('智学校园', 'utf-8').encode()} <{EMAIL_SENDER}>"
    
    # 隐私处理：多人接收时隐藏具体名单
    message['To'] = receivers[0] if len(receivers) == 1 else Header("订阅用户", "utf-8").encode()

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASS)
            server.sendmail(EMAIL_SENDER, receivers, message.as_string())
        print(f"✅ 邮件已群发至 {len(receivers)} 个邮箱。")
    except Exception as e:
        print(f"❌ 邮件推送失败: {e}")

def get_holiday_status():
    """获取节假日/补班状态"""
    try:
        res = requests.get(HOLIDAY_API_URL, timeout=10).json()
        today = date.today()
        year_data = res.get("Years", {}).get(str(today.year), [])
        for holiday in year_data:
            start = datetime.strptime(holiday["StartDate"], "%Y-%m-%d").date()
            end = datetime.strptime(holiday["EndDate"], "%Y-%m-%d").date()
            if start <= today <= end: return True, holiday["Name"]
            if today.strftime("%Y-%m-%d") in holiday.get("CompDays", []):
                return False, f"{holiday['Name']}补班"
        return (today.weekday() >= 5), "周末"
    except:
        return (date.today().weekday() >= 5), "普通周末"

def get_current_week(start_date_str):
    """计算当前是第几周"""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    return ((date.today() - start_monday).days // 7) + 1

def is_course_this_week(week_str, current_week):
    """解析周数字符串，如 '1-16周' 或 '3,5,7周'"""
    clean_str = week_str.replace('周', '').strip()
    for interval in clean_str.split(','):
        if '-' in interval:
            try:
                start, end = map(int, interval.split('-'))
                if start <= current_week <= end: return True
            except: continue
        else:
            try:
                if int(interval) == current_week: return True
            except: continue
    return False

# ================== 3. 主执行流程 ==================

def main():
    # 1. 加载本地 timetable.json
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ 未找到 timetable.json，请检查文件路径。")
        return

    # 2. 基础时间计算
    today = date.today()
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 判定学期状态
    is_final_period = curr_week >= 17 
    end_date = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    days_to_end = (end_date - today).days
    countdown_text = f"距离学期结束还有 {max(0, days_to_end)} 天"
    is_off_day, holiday_tag = get_holiday_status()

    # 3. 获取天气 (提取当日数据)
    temp_range, weather_info = "N/A", "未知"
    if WEATHER_API_KEY:
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=5).json()
            if w_res.get("error_code") == 0:
                temp_range = w_res["result"]["future"][0]["temperature"]
                weather_info = w_res["result"]["future"][0]['weather']
        except: pass

    # 4. 筛选今日课程
    today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # 5. UI 渲染 (顶配美化逻辑)
    # 动态配色：正常周为清新蓝，期末周为警示红
    header_gradient = "linear-gradient(135deg, #FF9A9E 0%, #FECFEF 100%)" if is_final_period else "linear-gradient(120deg, #a1c4fd 0%, #c2e9fb 100%)"
    t_main = "#2d3436"  # 莫兰迪深灰
    t_sub = "#636e72"   # 莫兰迪浅灰
    
    course_cards = ""
    if is_off_day and not today_courses:
        main_body_html = f"""
        <div style='padding: 60px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h4 style='color: {t_main}; font-size: 18px; margin: 15px 0 5px;'>{holiday_tag}休息日</h4>
            <p style='color: {t_sub}; font-size: 13px;'>今日无课，愿你享受悠闲时光</p>
        </div>"""
    else:
        # 卡片标签颜色库
        accents = ["#FF7878", "#78E3FF", "#7AFF78", "#FFB178", "#E678FF"]
        for i, c in enumerate(today_courses):
            acc_c = "#eb4d4b" if is_final_period else accents[i % len(accents)]
            course_cards += f"""
            <div style='margin-bottom: 20px; background: rgba(255,255,255,0.7); border-radius: 18px; border: 1px solid rgba(255,255,255,0.2); padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.03);'>
                <div style='display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;'>
                    <b style='font-size: 19px; color: {t_main}; letter-spacing: -0.5px;'>{c['name']}</b>
                    <span style='font-size: 11px; background: rgba(0,0,0,0.04); color: {acc_c}; padding: 3px 8px; border-radius: 6px; font-weight: bold;'>{c['session']}</span>
                </div>
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px; color: {t_sub};'>
                    <div style='background: rgba(0,0,0,0.02); padding: 6px 10px; border-radius: 8px;'>🕒 <b>{c['time']}</b></div>
                    <div style='background: rgba(0,0,0,0.02); padding: 6px 10px; border-radius: 8px;'>📍 {c['location']}</div>
                    <div style='padding: 2px 10px;'>👨‍🏫 {c['teacher']}</div>
                    <div style='padding: 2px 10px; color: {acc_c}; font-weight: 600;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards = f"<div style='text-align: center; color: {t_sub}; padding: 60px 0; font-size: 14px;'>📖 今日无课，正是自习好时光</div>"
        main_body_html = f"<div style='padding: 15px;'>{course_cards}</div>"

# 6. HTML 模板拼接 (亮色模式优化版)
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="color-scheme" content="light">
        <style>
            /* 强制在邮件客户端中使用亮色样式，确保白天显示效果 */
            body {{ 
                margin: 0 !important; 
                padding: 15px !important; 
                background-color: #F6F8FA !important; /* 极淡的底色，衬托卡片 */
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                -webkit-font-smoothing: antialiased;
            }}
            .main-container {{
                max-width: 460px;
                margin: 0 auto;
                background-color: #FFFFFF;
                border-radius: 28px;
                overflow: hidden;
                /* 分层柔和阴影，营造高级感 */
                box-shadow: 0 4px 6px rgba(50, 50, 93, 0.02), 0 10px 20px rgba(0, 0, 0, 0.06);
            }}
            
            /* Header Style */
            .header {{
                background: {header_gradient};
                padding: 40px 25px 30px;
                color: #FFFFFF; /* 强制头部文字为白色 */
                position: relative;
            }}
            .header h2 {{
                margin: 0;
                font-size: 26px;
                font-weight: 800;
                letter-spacing: -0.5px;
                text-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .header-date {{
                margin-top: 6px;
                font-size: 14px;
                opacity: 0.9;
                font-weight: 500;
            }}
            .weather-box {{
                position: absolute;
                right: 25px;
                bottom: 30px;
                text-align: right;
                background: rgba(255,255,255,0.15); /* 微亮的透明块，仅用于装饰天气 */
                padding: 8px 12px;
                border-radius: 12px;
            }}
            
            /* Content Area */
            .content-body {{
                padding: 20px 15px 10px;
                background-color: #FFFFFF;
            }}
            
            /* Course Card Style - 彻底摒弃半透明 */
            .course-card {{
                background-color: #FFFFFF;
                border-radius: 20px;
                padding: 18px;
                margin-bottom: 15px;
                /* 稍微加深一点的阴影，使其在白底上更突出 */
                box-shadow: 0 7px 14px rgba(50, 50, 93, 0.03), 0 3px 6px rgba(0, 0, 0, 0.05);
                border: 1px solid #E6EBF1; /* 添加极细的边框线以定义边界 */
                position: relative;
                overflow: hidden;
            }}
            /* 在期末周添加警示色边条 */
            .final-period-border {{
                position: absolute;
                left: 0;
                top: 0;
                bottom: 0;
                width: 5px;
                background-color: #eb4d4b;
            }}
            
            .course-name {{
                font-size: 19px;
                font-weight: 700;
                color: #1A1C1D; /* 深黑灰色文字，保证清晰度 */
                margin-bottom: 12px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }}
            .session-tag {{
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 8px;
                background-color: #F1F3F5; /* 浅灰底色衬托节次信息 */
                color: #57606F;
                font-weight: bold;
            }}
            
            .info-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }}
            .info-item {{
                font-size: 13px;
                color: #4F5660;
                display: flex;
                align-items: center;
                padding: 6px 10px;
                border-radius: 10px;
            }}
            /* 高亮时间信息 */
            .time-highlight {{
                background-color: rgba(30, 144, 255, 0.08);
                color: #1E90FF;
                font-weight: 600;
            }}
            /* 高亮地点信息 */
            .loc-highlight {{
                background-color: rgba(46, 213, 115, 0.08);
                color: #2ED573;
            }}
            
            /* Footer */
            .footer {{
                text-align: center;
                padding: 20px 25px 30px;
                color: #A4B0BE;
                background-color: #FFFFFF;
                border-top: 1px solid #F1F3F5;
            }}
            .countdown-text {{
                font-size: 12px;
                color: {t_sub};
                margin-top: 8px;
                font-weight: 500;
            }}
        </style>
    </head>
    <body>
        <div class="main-container">
            <div class="header">
                <h2>{'🔥 期末冲刺' if is_final_period else '📅 今日行程'}</h2>
                <div class="header-date">Week {curr_week} · {weekday_cn} · {today.strftime('%m月%d日')}</div>
                <div class="weather-box">
                    <div style="font-size: 20px; font-weight: 300; color:#FFFFFF;">{temp_range}</div>
                    <div style="font-size: 12px; font-weight: 600; opacity: 0.9; color:#FFFFFF;">{weather_info} @ {CITY_NAME}</div>
                </div>
            </div>

            <div class="content-body">
                {course_cards if not (is_off_day and not today_courses) else f"""
                <div style='padding: 60px 20px; text-align: center;'>
                    <div style='font-size: 50px; margin-bottom: 20px;'>☕</div>
                    <div style='font-size: 18px; color: #1A1C1D; font-weight: 700;'>{holiday_tag}休息日</div>
                    <div style='font-size: 13px; color: #747D8C; margin-top: 8px;'>今日无课，尽情享受悠闲时光吧</div>
                </div>
                """}
            </div>

            <div class="footer">
                <div style="font-size: 11px; font-weight: bold; letter-spacing: 2px;">— SEMESTER COUNTDOWN —</div>
                <div class="countdown-text">{countdown_text}</div>
                <div style="margin-top: 20px; font-size: 10px; opacity: 0.7;">Smart Campus Assist · 祝你每天都进步</div>
            </div>
        </div>
    </body>
    </html>
    """

    # 7. 执行推送
    p_title = f"{'🔥' if is_final_period else '📅'} {weekday_cn}课表 | {len(today_courses)}门"
    
    # 微信推送
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", 
                          json={"token": PUSHPLUS_TOKEN, "title": p_title, "content": full_html, "template": "html"}, 
                          timeout=10)
        except: pass
    
    # 邮件推送
    send_email(p_title, full_html)

if __name__ == "__main__":
    main()
