import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议在 GitHub Action 或环境变量中设置，或者直接替换下方字符串
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

# ================== 2. 核心函数 ==================

def send_email(title, html_content):
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        print("邮件配置信息不全，跳过发送。")
        return
    
    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
    message = MIMEText(html_content, 'html', 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    message['From'] = f"{Header('智学校园', 'utf-8').encode()} <{EMAIL_SENDER}>"
    
    if len(receivers) == 1:
        message['To'] = receivers[0]
    else:
        message['To'] = Header("订阅用户", "utf-8").encode()

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASS)
            server.sendmail(EMAIL_SENDER, receivers, message.as_string())
        print(f"邮件已成功群发至 {len(receivers)} 个邮箱。")
    except Exception as e:
        print(f"邮件推送失败: {e}")

def get_holiday_status():
    """识别节假日/补班逻辑"""
    try:
        res = requests.get(HOLIDAY_API_URL, timeout=10).json()
        today = date.today()
        year_data = res.get("Years", {}).get(str(today.year), [])
        for holiday in year_data:
            start = datetime.strptime(holiday["StartDate"], "%Y-%m-%d").date()
            end = datetime.strptime(holiday["EndDate"], "%Y-%m-%d").date()
            if start <= today <= end:
                return True, holiday["Name"]
            if today.strftime("%Y-%m-%d") in holiday.get("CompDays", []):
                return False, f"{holiday['Name']}补班"
        return (today.weekday() >= 5), "周末"
    except:
        return (date.today().weekday() >= 5), "普通周末"

def get_current_week(start_date_str):
    """计算当前教学周"""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    days_diff = (date.today() - start_monday).days
    return (days_diff // 7) + 1

def is_course_this_week(week_str, current_week):
    """解析周数字符串逻辑"""
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

# ================== 3. 主流程 ==================

def main():
    # 1. 加载数据
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("错误: 未找到 timetable.json 文件")
        return

    # 2. 基础时间数据
    today = date.today()
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 期末判定与倒计时
    is_final_period = curr_week >= 17 
    end_date = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    days_to_end = (end_date - today).days
    countdown_text = f"距离学期结束还有 {days_to_end} 天" if days_to_end > 0 else "学期已结束"
    is_off_day, holiday_tag = get_holiday_status()

    # 3. 获取天气
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
    course_count = len(today_courses)

    # 5. UI 渲染逻辑 (美化版)
    header_gradient = "linear-gradient(135deg, #ff4757, #ff6b81)" if is_final_period else "linear-gradient(135deg, #667eea, #764ba2)"
    title_text = "🔥 期末周提醒" if is_final_period else "📅 今日课表"
    
    course_cards = ""
    if is_off_day and not today_courses:
        main_body_html = f"""
        <div style='padding: 60px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h4 style='color: #2f3542; margin: 10px 0;'>{holiday_tag}休息日</h4>
            <p style='color: #a4b0be; font-size: 13px;'>今天没有课程，好好放松一下吧</p>
        </div>"""
    else:
        # 配色方案
        accents = ["#5352ed", "#2ed573", "#ffa502", "#e84393", "#00cec9"]
        for i, c in enumerate(today_courses):
            acc_c = "#ff4757" if is_final_period else accents[i % len(accents)]
            course_cards += f"""
            <div style='margin-bottom: 20px; background: rgba(255,255,255,0.9); border-radius: 16px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border-left: 6px solid {acc_c};'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;'>
                    <span style='font-size: 19px; font-weight: 800; color: #2d3436;'>{c['name']}</span>
                    <span style='font-size: 11px; color: {acc_c}; background: rgba(0,0,0,0.04); padding: 3px 8px; border-radius: 6px; font-weight: bold;'>{c['session']}</span>
                </div>
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px; color: #636e72;'>
                    <div style='background: rgba(0,0,0,0.02); padding: 6px 10px; border-radius: 8px;'>🕒 <b>{c['time']}</b></div>
                    <div style='background: rgba(0,0,0,0.02); padding: 6px 10px; border-radius: 8px;'>📍 {c['location']}</div>
                    <div style='padding: 2px 10px;'>👨‍🏫 {c['teacher']}</div>
                    <div style='padding: 2px 10px; color: {acc_c}; font-weight: 600;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards = "<p style='text-align: center; color: #a4b0be; padding: 40px;'>今天没课，记得温习功课哦！</p>"
        main_body_html = f"<div style='padding: 20px;'>{course_cards}</div>"

    # 6. 组合最终 HTML
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh">
    <head>
        <meta name="color-scheme" content="light dark">
        <style>
            @media (prefers-color-scheme: dark) {{
                .container {{ background: #1c1c1e !important; }}
                .main-card {{ background: rgba(255,255,255,0.05) !important; }}
                h2, .t-main {{ color: #ffffff !important; }}
                .t-sub {{ color: #aeaeb2 !important; }}
            }}
        </style>
    </head>
    <body style="margin: 0; padding: 15px; background: transparent; font-family: -apple-system, sans-serif;">
        <div class="container" style="max-width: 550px; margin: 0 auto; background: #f1f2f6; border-radius: 24px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.1);">
            <div style="background: {header_gradient}; padding: 35px 25px; color: white;">
                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    <tr>
                        <td>
                            <h2 style="margin: 0; font-size: 24px; letter-spacing: 1px;">{title_text}</h2>
                            <p style="margin: 6px 0 0; opacity: 0.8; font-size: 14px;">第 {curr_week} 周 · {weekday_cn} · {today.strftime('%m月%d日')}</p>
                        </td>
                        <td align="right" style="vertical-align: bottom;">
                            <div style="font-size: 20px; font-weight: bold;">{temp_range}</div>
                            <div style="font-size: 12px; opacity: 0.8;">{CITY_NAME} / {weather_info}</div>
                        </td>
                    </tr>
                </table>
            </div>
            <div class="main-card">
                {main_body_html}
                <div style="text-align: center; padding: 15px 0; border-top: 1px solid rgba(0,0,0,0.05); margin: 0 25px;">
                    <span style="color: #a4b0be; font-size: 12px; font-weight: bold; letter-spacing: 1px;">— {countdown_text.upper()} —</span>
                </div>
            </div>
            <div style="text-align: center; padding-bottom: 20px; color: #ced6e0; font-size: 10px; letter-spacing: 1px;">智能校园推送服务</div>
        </div>
    </body>
    </html>
    """

    # 7. 执行推送
    push_title = f"{'🔥' if is_final_period else '📅'} {weekday_cn}课表({course_count}门)"
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": push_title, "content": full_html, "template": "html"}, timeout=10)
        except: pass
    
    send_email(push_title, full_html)

if __name__ == "__main__":
    main()
