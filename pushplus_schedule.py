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

# ================== 2. 核心推送函数 ==================

def send_email(title, html_content):
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        print("邮件环境变量配置不全，已跳过邮件发送。")
        return

    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
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
        print(f"邮件已发送至 {len(receivers)} 个邮箱。")
    except Exception as e:
        print(f"邮件推送失败: {e}")

# ================== 3. 核心逻辑处理 ==================

def get_holiday_status():
    """
    通过专业节假日API获取状态
    返回: (is_off_day, status_text)
    type说明: 0工作日, 1周末, 2节日, 3调休
    """
    today_str = date.today().strftime("%Y-%m-%d")
    try:
        # 使用 timor.tech API，能自动处理区间和调休
        url = f"https://timor.tech/api/holiday/info/{today_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        if res.get("code") == 0:
            h_type = res["type"]["type"]
            h_name = res["holiday"]["name"] if res.get("holiday") else ""
            
            if h_type == 0: # 工作日
                if h_name: return False, f"{h_name}补班"
                return False, "工作日"
            elif h_type == 1: # 周末
                return True, "周末休息"
            elif h_type == 2: # 节日
                return True, h_name
            elif h_type == 3: # 调休放假
                return True, f"{h_name}调休"
    except Exception as e:
        print(f"节假日接口异常: {e}")
    
    # 保底方案
    is_weekend = date.today().weekday() >= 5
    return is_weekend, "周末" if is_weekend else "工作日"

def get_current_week(start_date_str):
    """计算当前教学周"""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    days_diff = (date.today() - start_monday).days
    return (days_diff // 7) + 1

def is_course_this_week(week_str, current_week):
    """解析周数字符串逻辑，支持 '1-16周', '1,3,5', '单周/双周'"""
    # 预处理字符串
    clean_str = week_str.replace('周', '').strip()
    is_even = current_week % 2 == 0 # 是否双周
    
    # 针对 (单), (双) 这种格式的处理
    if "单" in clean_str and is_even: return False
    if "双" in clean_str and not is_even: return False
    
    clean_str = clean_str.replace("(单)", "").replace("(双)", "").replace("单", "").replace("双", "")
    
    for interval in clean_str.split(','):
        interval = interval.strip()
        if not interval: continue
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
    # 1. 加载本地配置
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        return

    # 2. 基础时间数据
    today = date.today()
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 状态判定
    is_off_day, holiday_tag = get_holiday_status()
    is_final_period = curr_week >= 17 
    end_date = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    days_to_end = (end_date - today).days
    countdown_text = f"距离学期结束还有 {days_to_end} 天" if days_to_end > 0 else "学期已结束"

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

    # 5. UI 渲染逻辑
    header_bg = "#ff4757" if is_final_period else "#4834d4"
    status_icon = "🏖️" if is_off_day else "📖"
    
    course_cards = ""
    # 逻辑：如果是放假且没课，显示休息界面；如果是补班，即使没课也会显示今日无课
    if is_off_day and not today_courses:
        main_body_html = f"""
        <div style='padding: 40px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h3 style='color: #2f3542; margin: 10px 0;'>{holiday_tag}</h3>
            <p style='color: #747d8c;'>享受你的假期吧！</p>
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
                    <span style='font-size: 11px; background: {b_color}; color: {m_color}; padding: 2px 8px; border-radius: 6px;'>{c.get('session','课程')}</span>
                </div>
                <div style='margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px; color: #747d8c;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div><div>👨‍🏫 {c['teacher']}</div>
                    <div style='color: {m_color}; font-weight: 500;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        
        if not today_courses:
            course_cards = f"<div style='text-align: center; color: #747d8c; padding: 30px;'>今日({holiday_tag})无课安排</div>"
        main_body_html = f"<div style='padding: 15px 20px;'>{course_cards}</div>"

    full_html = f"""
    <div style='max-width: 450px; margin: 0 auto; background: #f1f2f6; border-radius: 25px; overflow: hidden; font-family: -apple-system, sans-serif;'>
        <div style='background: {header_bg}; padding: 30px 25px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
                <div>
                    <h2 style='margin: 0; font-size: 20px;'>{status_icon} {holiday_tag} · {weekday_cn}</h2>
                    <p style='margin: 5px 0 0; opacity: 0.8; font-size: 13px;'>第 {curr_week} 教学周 | {'期末阶段' if is_final_period else '常规阶段'}</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 18px; font-weight: bold;'>{temp_range}</div>
                    <div style='font-size: 12px; opacity: 0.9;'>{CITY_NAME} / {weather_info}</div>
                </div>
            </div>
        </div>
        {main_body_html}
        <div style='text-align: center; padding: 15px 0; border-top: 1px solid #e1e4e8; margin: 0 20px;'>
            <span style='color: #a4b0be; font-size: 12px;'>— {countdown_text} —</span>
        </div>
        <div style='text-align: center; padding-bottom: 20px; color: #ced6e0; font-size: 11px;'>自动提醒服务 · 祝你学习愉快</div>
    </div>"""

    # 6. 发送推送
    push_title = f"{'🔥' if is_final_period else '📅'} {holiday_tag}{weekday_cn}课表({course_count}门)"
    
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", 
                          json={"token": PUSHPLUS_TOKEN, "title": push_title, "content": full_html, "template": "html"}, 
                          timeout=10)
        except: pass

    send_email(push_title, full_html)

if __name__ == "__main__":
    main()
