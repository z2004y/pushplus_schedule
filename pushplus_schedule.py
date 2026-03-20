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
        today_str = today.strftime("%Y-%m-%d")
        year_data = res.get("Years", {}).get(str(today.year), [])
        
        for holiday in year_data:
            start = datetime.strptime(holiday["StartDate"], "%Y-%m-%d").date()
            end = datetime.strptime(holiday["EndDate"], "%Y-%m-%d").date()
            if start <= today <= end:
                return True, holiday["Name"]
            if today_str in holiday.get("CompDays", []):
                return False, f"{holiday['Name']}补班"
        
        return (today.weekday() >= 5), "周末"
    except:
        return (date.today().weekday() >= 5), "普通周末"

def get_current_week(start_date_str):
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    days_diff = (date.today() - start_monday).days
    return (days_diff // 7) + 1

def is_course_this_week(week_str, current_week):
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

# ================== 4. 主流程 ==================

def main():
    # 1. 加载本地数据
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("未找到 timetable.json 文件。")
        return

    # 2. 基础时间数据
    today = date.today()
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
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

    # 5. UI 渲染逻辑 (全端适配版)
    header_bg = "linear-gradient(135deg, #ff4757, #ff6b81)" if is_final_period else "linear-gradient(135deg, #4834d4, #686de0)"
    title_prefix = "🔥 期末周提醒" if is_final_period else "📚 今日课表"
    
    course_cards = ""
    if is_off_day and not today_courses:
        main_body_html = f"<div style='padding: 60px 20px; text-align: center;'><div style='font-size: 50px;'>☕</div><h4 style='color: #2f3542;'>{holiday_tag}休息日</h4></div>"
    else:
        colors = [("#ff4757", "#ffeeee"), ("#2e86de", "#e1f0ff"), ("#ffa502", "#fff4e1"), ("#2ed573", "#e7fbf0")]
        for i, c in enumerate(today_courses):
            m_color = "#ff4757" if is_final_period else colors[i % len(colors)][0]
            b_color = "#fff5f5" if is_final_period else colors[i % len(colors)][1]
            course_cards += f"""
            <div style='margin-bottom: 20px; background: #fff; border-radius: 12px; border-left: 6px solid {m_color}; padding: 20px; border-right: 1px solid #f1f2f6; border-top: 1px solid #f1f2f6; border-bottom: 1px solid #f1f2f6; box-shadow: 0 4px 12px rgba(0,0,0,0.02);'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;'>
                    <span style='font-size: 18px; font-weight: bold; color: #2f3542;'>{c['name']}</span>
                    <span style='font-size: 12px; background: {b_color}; color: {m_color}; padding: 4px 10px; border-radius: 4px; font-weight: bold;'>{c['session']}</span>
                </div>
                <div style='color: #747d8c; font-size: 14px; line-height: 2;'>
                    <div style='display: inline-block; width: 48%; min-width: 140px;'>🕒 {c['time']}</div>
                    <div style='display: inline-block; width: 48%; min-width: 140px;'>📍 {c['location']}</div>
                    <div style='display: inline-block; width: 48%; min-width: 140px;'>👨‍🏫 {c['teacher']}</div>
                    <div style='display: inline-block; width: 48%; min-width: 140px; color: {m_color}; font-weight: bold;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards = "<p style='text-align: center; color: #747d8c; padding: 40px;'>今天没课，记得温习功课哦！</p>"
        main_body_html = f"<div style='padding: 20px;'>{course_cards}</div>"

    full_html = f"""
    <div style='background-color: #f6f8fa; padding: 20px 10px; min-height: 100%;'>
        <div style='max-width: 600px; width: 100%; margin: 0 auto; background: #ffffff; border-radius: 20px; overflow: hidden; font-family: -apple-system, "Helvetica Neue", sans-serif; box-shadow: 0 15px 35px rgba(0,0,0,0.05);'>
            <div style='background: {header_bg}; padding: 35px 30px; color: white;'>
                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    <tr>
                        <td align="left">
                            <h2 style='margin: 0; font-size: 24px; letter-spacing: 1px;'>{title_prefix}</h2>
                            <p style='margin: 8px 0 0; opacity: 0.85; font-size: 14px;'>第 {curr_week} 周 · {weekday_cn} · {today.strftime("%m月%d日")}</p>
                        </td>
                        <td align="right" style="vertical-align: bottom;">
                            <div style='font-size: 20px; font-weight: bold;'>{temp_range}</div>
                            <div style='font-size: 12px; opacity: 0.9;'>{CITY_NAME} / {weather_info}</div>
                        </td>
                    </tr>
                </table>
            </div>
            {main_body_html}
            <div style='text-align: center; padding: 20px 0; border-top: 1px solid #f1f2f6; margin: 0 30px;'>
                <span style='color: #a4b0be; font-size: 13px; font-weight: 500;'>— {countdown_text} —</span>
            </div>
            <div style='text-align: center; padding: 0 20px 25px; color: #ced6e0; font-size: 11px;'>
                自动推送服务 · 祝你考试必过
            </div>
        </div>
    </div>"""

    # 6. 发送推送
    push_title = f"{'🔥' if is_final_period else '📅'} {weekday_cn}课表({course_count}门)"
    if PUSHPLUS_TOKEN:
        try:
            push_data = {"token": PUSHPLUS_TOKEN, "title": push_title, "content": full_html, "template": "html"}
            requests.post("http://www.pushplus.plus/send", json=push_data, timeout=10)
        except: pass
    send_email(push_title, full_html)

if __name__ == "__main__":
    main()
