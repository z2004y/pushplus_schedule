import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议在 GitHub Actions Secrets 中配置，也可直接填入引号内
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 邮件配置
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")      # 邮箱授权码
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = "smtp.qq.com"               # 如使用网易请改 smtp.163.com
SMTP_PORT = 465

# ================== 2. 核心逻辑处理 ==================

def get_holiday_status():
    """
    识别放假和补班。
    返回: (is_off_day, status_text, is_makeup)
    is_off_day: 是否放假休息
    is_makeup: 是否是周末补班（补班需要上课）
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    try:
        # 使用专业节假日 API (timor.tech)
        url = f"https://timor.tech/api/holiday/info/{today_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        if res.get("code") == 0:
            h_type = res["type"]["type"]      # 0工作日, 1周末, 2节日, 3调休
            h_name = res["holiday"]["name"] if res.get("holiday") else ""
            
            if h_type == 0: # 正常工作日或补班
                # 如果是周六(5)或周日(6)但 type 为 0，则是补班
                if today.weekday() >= 5:
                    return False, f"{h_name}补班日", True
                return False, "工作日", False
            else: # 1, 2, 3 均为放假
                return True, h_name or "周末休息", False
    except Exception as e:
        print(f"节假日API获取异常: {e}")
    
    # API 故障时的保底逻辑
    is_weekend = today.weekday() >= 5
    return is_weekend, ("周末" if is_weekend else "工作日"), False

def is_course_this_week(week_str, current_week):
    """解析周数逻辑，支持 '1-16', '1,3,5', '1-10(单/双)'"""
    is_even = current_week % 2 == 0
    if "单" in week_str and is_even: return False
    if "双" in week_str and not is_even: return False
    
    # 清理字符
    clean_str = week_str.replace('周','').replace('(单)','').replace('(双)','').replace('单','').replace('双','').strip()
    
    for interval in clean_str.split(','):
        if '-' in interval:
            try:
                start, end = map(int, interval.split('-'))
                if start <= current_week <= end: return True
            except: continue
        elif interval.strip():
            try:
                if int(interval) == current_week: return True
            except: continue
    return False

def send_email(title, html_content):
    """邮件发送函数"""
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        return
    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
    message = MIMEText(html_content, 'html', 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    message['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
    message['To'] = receivers[0] if len(receivers) == 1 else Header("学生用户", "utf-8").encode()
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASS)
            server.sendmail(EMAIL_SENDER, receivers, message.as_string())
    except Exception as e:
        print(f"邮件推送失败: {e}")

# ================== 3. 主程序 ==================

def main():
    # 1. 加载配置
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"加载失败: {e}")
        return

    # 2. 计算当前教学周
    today = date.today()
    start_dt = datetime.strptime(config["semester_info"]["start_date"], "%Y-%m-%d").date()
    # 找到开学那周的周一
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    curr_week = ((today - start_monday).days // 7) + 1
    
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    is_off_day, status_text, is_makeup = get_holiday_status()

    # 3. 获取天气
    temp_range, weather_info = "N/A", "未知"
    if WEATHER_API_KEY:
        try:
            w_res = requests.get(f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}", timeout=5).json()
            if w_res.get("error_code") == 0:
                temp_range = w_res["result"]["future"][0]["temperature"]
                weather_info = w_res["result"]["future"][0]['weather']
        except: pass

    # 4. 筛选课程
    today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # 5. UI 渲染渲染
    # 颜色策略：补班=红色，上课=蓝色，放假=绿色
    theme_color = "#eb4d4b" if is_makeup else ("#4834d4" if not is_off_day else "#6ab04c")
    title_prefix = "⚠️ 补班提醒" if is_makeup else ("📚 今日课表" if not is_off_day else "🏖️ 放假休息")
    
    course_cards = ""
    if is_off_day and not today_courses:
        # 纯放假且没课
        course_cards = f"""
        <div style='padding: 40px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h3 style='color: #2f3542;'>{status_text}</h3>
            <p style='color: #747d8c; font-size: 14px;'>今天放假，好好休息</p>
        </div>"""
    elif is_makeup and not today_courses:
        # 补班但自然课表里没课（可能需要上其他日子的课）
        course_cards = f"""
        <div style='margin: 15px; padding: 20px; background: #fffbe6; border: 1px dashed #ffe58f; border-radius: 12px; text-align: center;'>
            <p style='color: #faad14; font-weight: bold; font-size: 16px;'>补班预警</p>
            <p style='color: #855800; font-size: 13px; line-height: 1.6;'>今天是 {status_text}。<br>你的课表在{weekday_cn}没有安排，请核实是否需要按照调休后的教学安排上课！</p>
        </div>"""
    else:
        # 正常展示课程
        for c in today_courses:
            course_cards += f"""
            <div style='margin-bottom: 12px; background: #fff; border-radius: 12px; border-left: 5px solid {theme_color}; padding: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.05);'>
                <div style='font-weight: bold; color: #2f3542; font-size: 16px; margin-bottom: 8px;'>{c['name']}</div>
                <div style='font-size: 13px; color: #747d8c; display: grid; grid-template-columns: 1fr 1fr; gap: 6px;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div>
                    <div>👨‍🏫 {c['teacher']}</div><div style='color: {theme_color}'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards = f"<p style='text-align: center; color: #a4b0be; padding: 30px;'>{weekday_cn}没有课程安排</p>"

    # HTML 整体模板
    full_html = f"""
    <div style='max-width: 450px; margin: 0 auto; background: #f4f7f6; border-radius: 20px; overflow: hidden; font-family: -apple-system, sans-serif; border: 1px solid #e1e4e8;'>
        <div style='background: {theme_color}; padding: 25px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
                <div>
                    <h2 style='margin: 0; font-size: 20px;'>{title_prefix}</h2>
                    <p style='margin: 5px 0 0; opacity: 0.9; font-size: 13px;'>第 {curr_week} 周 · {weekday_cn} ({status_text})</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 18px; font-weight: bold;'>{temp_range}</div>
                    <div style='font-size: 12px; opacity: 0.9;'>{CITY_NAME} / {weather_info}</div>
                </div>
            </div>
        </div>
        <div style='padding: 15px;'>{course_cards}</div>
        <div style='text-align: center; padding: 15px 0; border-top: 1px solid #eee; margin: 0 15px; color: #ced6e0; font-size: 11px;'>
            智能课表助手 · 祝学习愉快
        </div>
    </div>"""

    # 6. 执行发送
    push_title = f"{title_prefix} | {status_text} | {len(today_courses)}门课"
    
    # PushPlus
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", 
                          json={"token": PUSHPLUS_TOKEN, "title": push_title, "content": full_html, "template": "html"})
        except: pass

    # Email
    send_email(push_title, full_html)

if __name__ == "__main__":
    main()
