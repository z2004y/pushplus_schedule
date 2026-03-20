import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 邮件配置
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = "smtp.qq.com"  
SMTP_PORT = 465

# 节假日 API
HOLIDAY_API_URL = "https://raw.githubusercontent.com/lanceliao/china-holiday-calender/master/holidayAPI.json"

# ================== 2. 核心推送函数 ==================

def send_email(title, html_content):
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        print("邮件环境变量配置不全，已跳过邮件发送。")
        return

    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
    if not receivers: return

    message = MIMEText(html_content, 'html', 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    message['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
    
    if len(receivers) == 1:
        message['To'] = receivers[0]
    else:
        message['To'] = Header("课表订阅用户", "utf-8").encode()

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASS)
            server.sendmail(EMAIL_SENDER, receivers, message.as_string())
        print(f"邮件已群发至 {len(receivers)} 个邮箱。")
    except Exception as e:
        print(f"邮件推送失败: {e}")

# ================== 3. 核心逻辑处理 ==================

def get_holiday_status():
    try:
        res = requests.get(HOLIDAY_API_URL, timeout=10).json()
        today = date.today()
        year_data = res.get("Years", {}).get(str(today.year), [])
        for holiday in year_data:
            start = datetime.strptime(holiday["StartDate"], "%Y-%m-%d").date()
            end = datetime.strptime(holiday["EndDate"], "%Y-%m-%d").date()
            if start <= today <= end: return True, holiday["Name"]
            if today.strftime("%Y-%m-%d") in holiday.get("CompDays", []): return False, f"{holiday['Name']}补班"
        return (today.weekday() >= 5), "周末"
    except: return (date.today().weekday() >= 5), "普通周末"

def get_current_week(start_date_str):
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    return ((date.today() - start_monday).days // 7) + 1

def is_course_this_week(week_str, current_week):
    clean_str = week_str.replace('周', '').strip()
    for interval in clean_str.split(','):
        if '-' in interval:
            try:
                s, e = map(int, interval.split('-'))
                if s <= current_week <= e: return True
            except: continue
        else:
            try:
                if int(interval) == current_week: return True
            except: continue
    return False

# ================== 4. 主流程 ==================

def main():
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("未找到 timetable.json 文件。")
        return

    today = date.today()
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 期末判定逻辑
    is_final_period = curr_week >= 17 
    end_date = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    days_to_end = (end_date - today).days
    countdown_text = f"距离学期结束还有 {days_to_end} 天" if days_to_end > 0 else "学期已结束"
    is_off_day, holiday_tag = get_holiday_status()

    # 获取天气
    temp_range, weather_info = "N/A", "未知"
    if WEATHER_API_KEY:
        try:
            w_res = requests.get(f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}", timeout=5).json()
            if w_res.get("error_code") == 0:
                temp_range = w_res["result"]["future"][0]["temperature"]
                weather_info = w_res["result"]["future"][0]['weather']
        except: pass

    # 筛选课程
    today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # UI 变量定义 (修复 NameError)
    header_gradient = "linear-gradient(135deg, #ff4757, #ff6b81)" if is_final_period else "linear-gradient(135deg, #5352ed, #70a1ff)"
    title_prefix = "🔥 期末周提醒" if is_final_period else "📚 今日课表"
    
    # 颜色适配方案 (透明背景)
    card_bg = "rgba(255, 255, 255, 0.95)" 
    text_main = "#2f3542"
    text_sub = "#747d8c"

    course_cards = ""
    if is_off_day and not today_courses:
        main_body_html = f"<div style='padding: 50px 20px; text-align: center;'><h4 style='color: {text_main};'>{holiday_tag}休息日</h4></div>"
    else:
        colors = [("#5352ed", "rgba(83, 82, 237, 0.1)"), ("#2ed573", "rgba(46, 213, 115, 0.1)"), ("#ffa502", "rgba(255, 165, 2, 0.1)")]
        for i, c in enumerate(today_courses):
            m_c = "#ff4757" if is_final_period else colors[i % len(colors)][0]
            b_c = "rgba(255, 71, 87, 0.1)" if is_final_period else colors[i % len(colors)][1]
            course_cards += f"""
            <div style='margin-bottom: 15px; background: {card_bg}; border-radius: 12px; border-left: 5px solid {m_c}; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                    <b style='font-size: 17px; color: {text_main};'>{c['name']}</b>
                    <span style='font-size: 11px; background: {b_c}; color: {m_c}; padding: 3px 8px; border-radius: 5px;'>{c['session']}</span>
                </div>
                <div style='color: {text_sub}; font-size: 13px; line-height: 1.8;'>
                    <div style='display: inline-block; width: 48%; min-width: 140px;'>🕒 {c['time']}</div>
                    <div style='display: inline-block; width: 48%; min-width: 140px;'>📍 {c['location']}</div>
                    <div style='display: inline-block; width: 48%; min-width: 140px;'>👨‍🏫 {c['teacher']}</div>
                    <div style='display: inline-block; width: 48%; min-width: 140px; color: {m_c}; font-weight: bold;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards = f"<p style='text-align: center; color: {text_sub}; padding: 40px;'>今天没课，记得温习功课哦！</p>"
        main_body_html = f"<div style='padding: 15px;'>{course_cards}</div>"

    # 最终 HTML (包含 Meta 标签适配夜间模式)
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="color-scheme" content="light dark">
        <meta name="supported-color-schemes" content="light dark">
        <style>
            :root {{ color-scheme: light dark; supported-color-schemes: light dark; }}
            @media (prefers-color-scheme: dark) {{
                .container {{ background: transparent !important; }}
                .text-main {{ color: #ffffff !important; }}
                .text-sub {{ color: #aeaeb2 !important; }}
                .footer-text {{ color: #636366 !important; }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 0; background: transparent;">
        <div class="container" style='max-width: 600px; margin: 0 auto; background: transparent; font-family: -apple-system, system-ui, sans-serif;'>
            <div style='background: {header_gradient}; padding: 35px 25px; color: white; border-radius: 20px 20px 0 0;'>
                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    <tr>
                        <td align="left">
                            <h2 style='margin: 0; font-size: 22px;'>{title_prefix}</h2>
                            <p style='margin: 5px 0 0; opacity: 0.8; font-size: 13px;'>第 {curr_week} 周 · {weekday_cn}</p>
                        </td>
                        <td align="right" style="vertical-align: bottom;">
                            <div style='font-size: 18px; font-weight: bold;'>{temp_range}</div>
                            <div style='font-size: 12px; opacity: 0.8;'>{CITY_NAME} / {weather_info}</div>
                        </td>
                    </tr>
                </table>
            </div>
            <div style="background: rgba(255,255,255,0.05); border-radius: 0 0 20px 20px; overflow: hidden; padding-bottom: 10px;">
                {main_body_html}
                <div style='text-align: center; padding: 15px; border-top: 1px solid rgba(128,128,128,0.1); color: #8e8e93; font-size: 12px;' class="footer-text">
                    — {countdown_text} —
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    # 发送推送
    push_title = f"{'🔥' if is_final_period else '📅'} {weekday_cn}课表({len(today_courses)}门)"
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": push_title, "content": full_html, "template": "html"}, timeout=10)
        except: pass
    send_email(push_title, full_html)

if __name__ == "__main__":
    main()
