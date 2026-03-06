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
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") # 支持 "a@qq.com,b@163.com" 格式
SMTP_SERVER = "smtp.qq.com"  # QQ邮箱使用 smtp.qq.com，网易使用 smtp.163.com
SMTP_PORT = 465

# 节假日 API
HOLIDAY_API_URL = "https://raw.githubusercontent.com/lanceliao/china-holiday-calender/master/holidayAPI.json"

# ================== 2. 核心推送函数 ==================

def send_email(title, html_content):
    """支持群发且保护隐私的邮件推送"""
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        print("邮件环境变量配置不全，已跳过邮件发送。")
        return

    # 解析收件人列表
    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
    if not receivers:
        return

    message = MIMEText(html_content, 'html', 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    message['From'] = Header(f"课表助手 <{EMAIL_SENDER}>", 'utf-8')
    
    # 群发隐私处理：多人时隐藏具体名单
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
    """识别节假日/补班逻辑"""
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

# ================== 4. 主流程 ==================

def main():
    # 1. 加载本地 timetable.json
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("未找到 timetable.json 文件，请检查。")
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

    # 3. 获取天气 (提取 future 温度范围)
    temp_range, weather_info = "N/A", "未知"
    if WEATHER_API_KEY:
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=5).json()
            if w_res.get("error_code") == 0:
                # 关键修改：获取当日最高/最低温范围
                temp_range = w_res["result"]["future"][0]["temperature"]
                weather_info = w_res["result"]["future"][0]['weather']
        except Exception as e:
            print(f"天气接口调用失败: {e}")

    # 4. 筛选今日课程
    today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))
    course_count = len(today_courses)

    # 5. UI 渲染逻辑
    header_bg = "linear-gradient(135deg, #ff4757, #ff6b81)" if is_final_period else "linear-gradient(135deg, #4834d4, #686de0)"
    title_prefix = "🔥 期末周提醒" if is_final_period else "📚 今日课表"
    
    course_cards = ""
    if is_off_day and not today_courses:
        main_body_html = f"""
        <div style='padding: 40px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h4 style='color: #2f3542; margin: 10px 0;'>{holiday_tag}休息日</h4>
        </div>"""
    else:
        colors = [("#ff4757", "#ffeeee"), ("#2e86de", "#e1f0ff"), ("#ffa502", "#fff4e1"), ("#2ed573", "#e7fbf0")]
        for i, c in enumerate(today_courses):
            m_color = "#ff4757" if is_final_period else colors[i % len(colors)][0]
            b_color = "#fff5f5" if is_final_period else colors[i % len(colors)][1]
            course_cards += f"""
            <div style='margin-bottom: 15px; background: #fff; border-radius: 15px; border-left: 6px solid {m_color}; padding: 18px; box-shadow: 0 4px 10px rgba(0,0,0,0.03);'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 17px; font-weight: bold; color: #2f3542;'>{c['name']}</span>
                    <span style='font-size: 11px; background: {b_color}; color: {m_color}; padding: 2px 8px; border-radius: 6px;'>{c['session']}</span>
                </div>
                <div style='margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px; color: #747d8c;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div><div>👨‍🏫 {c['teacher']}</div>
                    <div style='color: {m_color}; font-weight: 500;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards = "<p style='text-align: center; color: #747d8c; padding: 30px;'>今天没课，记得温习功课哦！</p>"
        main_body_html = f"<div style='padding: 15px 20px;'>{course_cards}</div>"

    full_html = f"""
    <div style='max-width: 450px; margin: 0 auto; background: #f1f2f6; border-radius: 25px; overflow: hidden; font-family: -apple-system, sans-serif;'>
        <div style='background: {header_bg}; padding: 30px 25px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
                <div>
                    <h2 style='margin: 0; font-size: 22px;'>{title_prefix}</h2>
                    <p style='margin: 5px 0 0; opacity: 0.8; font-size: 13px;'>第 {curr_week} 周 · {weekday_cn}</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 20px; font-weight: bold;'>{temp_range}</div>
                    <div style='font-size: 12px; opacity: 0.9;'>{CITY_NAME} / {weather_info}</div>
                </div>
            </div>
        </div>
        {main_body_html}
        <div style='text-align: center; padding: 15px 0; border-top: 1px solid #e1e4e8; margin: 0 20px;'>
            <span style='color: #a4b0be; font-size: 12px;'>— {countdown_text} —</span>
        </div>
        <div style='text-align: center; padding-bottom: 20px; color: #ced6e0; font-size: 11px;'>自动提醒服务 · 祝你考试必过</div>
    </div>"""

    # 6. 发送推送
    push_title = f"{'🔥' if is_final_period else '📅'} {weekday_cn}课表({course_count}门)"
    
    # 微信推送 (PushPlus)
    if PUSHPLUS_TOKEN:
        try:
            push_data = {"token": PUSHPLUS_TOKEN, "title": push_title, "content": full_html, "template": "html", "topic": "721683736"}
            requests.post("http://www.pushplus.plus/send", json=push_data, timeout=10)
        except: pass

    # 邮件推送 (群发/单发)
    send_email(push_title, full_html)

if __name__ == "__main__":
    main()
