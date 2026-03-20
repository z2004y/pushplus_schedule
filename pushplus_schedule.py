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
EMAIL_PASS = os.getenv("EMAIL_PASS")  # 注意：此处应填写SMTP授权码
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = "smtp.qq.com"  
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
    # 1. 加载本地数据
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("❌ 未找到 timetable.json")
        return

    # 2. 基础计算
    today = date.today()
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    is_final_period = curr_week >= 17 
    end_date = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    days_to_end = (end_date - today).days
    countdown_text = f"距离学期结束还有 {max(0, days_to_end)} 天"
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

    # 4. 筛选课程
    today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # 5. UI 渲染逻辑
    header_gradient = "linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%)" if is_final_period else "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"
    
    course_cards_html = ""
    # 调色盘
    accents = [
        {"bg": "rgba(30, 144, 255, 0.08)", "text": "#1E90FF"},
        {"bg": "rgba(255, 71, 87, 0.08)", "text": "#FF4757"},
        {"bg": "rgba(46, 213, 115, 0.08)", "text": "#2ED573"},
        {"bg": "rgba(255, 165, 2, 0.08)", "text": "#FFA502"}
    ]

    if is_off_day and not today_courses:
        main_body_html = f"""
        <div style='padding: 60px 20px; text-align: center;'>
            <div style='font-size: 50px; margin-bottom: 15px;'>☕</div>
            <div style='font-size: 18px; color: #1A1C1D; font-weight: 700;'>{holiday_tag}休息日</div>
            <div style='font-size: 13px; color: #747D8C; margin-top: 8px;'>今日无课，尽情享受悠闲时光</div>
        </div>"""
    else:
        for i, c in enumerate(today_courses):
            style = accents[i % len(accents)]
            c_bg = "rgba(235, 77, 75, 0.1)" if is_final_period else style["bg"]
            c_text = "#eb4d4b" if is_final_period else style["text"]
            border_line = f'<div style="position:absolute; left:0; top:0; bottom:0; width:4px; background:{c_text};"></div>' if is_final_period else ""

            course_cards_html += f"""
            <div style="background:#FFFFFF; border-radius:20px; padding:18px; margin-bottom:15px; border:1px solid #E6EBF1; box-shadow:0 8px 16px rgba(0,0,0,0.04); position:relative; overflow:hidden;">
                {border_line}
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <b style="font-size:18px; color:#1A1C1D;">{c['name']}</b>
                    <span style="font-size:11px; padding:3px 8px; border-radius:8px; background:#F1F3F5; color:#57606F; font-weight:bold;">{c['session']}</span>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                    <div style="font-size:13px; padding:8px 10px; border-radius:10px; background:{c_bg}; color:{c_text}; font-weight:600;">🕒 {c['time']}</div>
                    <div style="font-size:13px; padding:8px 10px; border-radius:10px; background:rgba(46,213,115,0.08); color:#2ED573;">📍 {c['location']}</div>
                    <div style="font-size:13px; color:#747D8C; padding:2px 10px;">👨‍🏫 {c['teacher']}</div>
                    <div style="font-size:13px; color:{c_text}; padding:2px 10px;">🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        
        if not today_courses:
            course_cards_html = "<div style='text-align:center; color:#747D8C; padding:50px 0; font-size:14px;'>📖 今日无课，自习也是种进步</div>"
        main_body_html = f"<div style='padding:15px;'>{course_cards_html}</div>"

    # 6. HTML 最终拼接
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0; padding:15px; background-color:#F6F8FA; font-family:-apple-system,sans-serif;">
        <div style="max-width:460px; margin:0 auto; background:#FFFFFF; border-radius:28px; overflow:hidden; box-shadow:0 15px 35px rgba(0,0,0,0.08);">
            <div style="background:{header_gradient}; padding:40px 25px; color:#FFFFFF;">
                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    <tr>
                        <td>
                            <h2 style="margin:0; font-size:26px; font-weight:800; letter-spacing:-0.5px;">{'🔥 期末作战' if is_final_period else '📅 今日行程'}</h2>
                            <div style="margin-top:6px; font-size:14px; opacity:0.9;">Week {curr_week} · {weekday_cn} · {today.strftime('%m月%d日')}</div>
                        </td>
                        <td align="right">
                            <div style="font-size:20px; font-weight:300;">{temp_range}</div>
                            <div style="font-size:11px; font-weight:700; opacity:0.8;">{weather_info} @ {CITY_NAME}</div>
                        </td>
                    </tr>
                </table>
            </div>
            {main_body_html}
            <div style="text-align:center; padding:25px; border-top:1px solid #F1F3F5;">
                <div style="color:#A4B0BE; font-size:11px; font-weight:bold; letter-spacing:2px;">— SEMESTER COUNTDOWN —</div>
                <div style="color:#747D8C; font-size:12px; margin-top:8px; font-weight:500;">{countdown_text}</div>
            </div>
            <div style="text-align:center; padding-bottom:20px; font-size:10px; color:#CED6E0;">Smart Campus Assist · 祝你考试必过</div>
        </div>
    </body>
    </html>
    """

    # 7. 推送
    p_title = f"{'🔥' if is_final_period else '📅'} {weekday_cn}课表 | {len(today_courses)}门"
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", 
                          json={"token": PUSHPLUS_TOKEN, "title": p_title, "content": full_html, "template": "html"}, 
                          timeout=10)
        except: pass
    send_email(p_title, full_html)

if __name__ == "__main__":
    main()
