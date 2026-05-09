import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议通过环境变量设置，也可直接填入引号内
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 邮件配置
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")      # 授权码
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

# ================== 2. 逻辑处理函数 ==================

def get_holiday_status():
    """
    获取节假日详情
    返回: (is_off_day, status_text, is_makeup, target_weekday)
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    # 周几映射表
    week_map = {"Monday": "周一", "Tuesday": "周二", "Wednesday": "周三", 
                "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"}
    
    try:
        # 使用 timor.tech API 获取当日法定状态
        url = f"https://timor.tech/api/holiday/info/{today_str}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        if res.get("code") == 0:
            h_type = res["type"]["type"] # 0工作日, 1周末, 2节日, 3调休
            h_name = res["holiday"]["name"] if res.get("holiday") else ""
            
            # 逻辑：只要 type 是 0，就必须上课/上班
            if h_type == 0:
                # 如果是周六日(5,6)且 type=0，明确为补班
                is_makeup = today.weekday() >= 5
                target = None
                if is_makeup and res.get("holiday"):
                    target = week_map.get(res["holiday"].get("target"))
                return False, (f"{h_name}补班" if is_makeup else "工作日"), is_makeup, target
            else:
                # 1, 2, 3 均为休息
                return True, (h_name or "周末休息"), False, None
    except:
        pass

    # 保底逻辑
    is_weekend = today.weekday() >= 5
    return is_weekend, ("周末" if is_weekend else "工作日"), False, None

def is_course_this_week(week_str, current_week):
    """解析周数，支持 1-16, 1,3,5, 2-10(单/双)"""
    is_even = current_week % 2 == 0
    if "单" in week_str and is_even: return False
    if "双" in week_str and not is_even: return False
    
    clean = week_str.replace('周','').replace('(单)','').replace('(双)','').replace('单','').replace('双','').strip()
    for part in clean.split(','):
        if '-' in part:
            try:
                s, e = map(int, part.split('-'))
                if s <= current_week <= e: return True
            except: continue
        elif part.strip():
            try:
                if int(part) == current_week: return True
            except: continue
    return False

def send_email(title, html_content):
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]): return
    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
    message = MIMEText(html_content, 'html', 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    message['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
    message['To'] = receivers[0] if len(receivers) == 1 else Header("课表订阅用户", "utf-8").encode()
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASS)
            server.sendmail(EMAIL_SENDER, receivers, message.as_string())
    except Exception as e: print(f"邮件失败: {e}")

# ================== 3. 主程序流程 ==================

def main():
    # 1. 加载配置
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        print("未找到 timetable.json"); return

    # 2. 时间与周数计算
    today = date.today()
    start_dt = datetime.strptime(config["semester_info"]["start_date"], "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    curr_week = ((today - start_monday).days // 7) + 1
    
    natural_weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    is_off_day, status_text, is_makeup, target_weekday = get_holiday_status()

    # 3. 确定查询哪一天的课表 (如果是补班，优先按映射日期查)
    query_day = target_weekday if (is_makeup and target_weekday) else natural_weekday

    # 4. 获取天气
    temp, weather = "N/A", "未知"
    if WEATHER_API_KEY:
        try:
            w_res = requests.get(f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}", timeout=5).json()
            if w_res.get("error_code") == 0:
                temp = w_res["result"]["future"][0]["temperature"]
                weather = w_res["result"]["future"][0]['weather']
        except: pass

    # 5. 筛选课程
    today_courses = [c for c in config["courses"] if c["day"] == query_day and is_course_this_week(c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # 6. 构造 UI 渲染
    # 主题色：红色(补班警告), 绿色(放假愉快), 蓝色(普通工作日)
    theme_color = "#d63031" if is_makeup else ("#27ae60" if is_off_day else "#0984e3")
    title_label = "🚨 补班上课提醒" if is_makeup else ("🏖️ 放假休息" if is_off_day else "📚 今日课表")
    
    course_cards = ""
    if is_off_day:
        course_cards = f"""
        <div style='padding: 40px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h3 style='color: #2f3542;'>{status_text}</h3>
            <p style='color: #747d8c; font-size: 14px;'>今天放假，好好休息吧！</p>
        </div>"""
    else:
        # 如果是补班日，增加顶部提示
        if is_makeup:
            course_cards += f"""
            <div style='background: #fff5f5; border: 1px solid #fab1a0; padding: 12px; border-radius: 10px; margin-bottom: 15px; color: #c0392b; font-size: 13px;'>
                <b>调休说明：</b>今天是{status_text}，按自然星期是{natural_weekday}，现为您显示<b>{query_day}</b>的课程。
            </div>"""
        
        for c in today_courses:
            course_cards += f"""
            <div style='margin-bottom: 12px; background: #fff; border-radius: 12px; border-left: 5px solid {theme_color}; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>
                <div style='font-weight: bold; color: #2d3436; font-size: 16px;'>{c['name']}</div>
                <div style='margin-top: 8px; font-size: 13px; color: #636e72; display: grid; grid-template-columns: 1fr 1fr; gap: 5px;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div>
                    <div>👨‍🏫 {c['teacher']}</div><div style='color: {theme_color}; font-weight: bold;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        
        if not today_courses:
            course_cards += f"<p style='text-align:center; padding:30px; color:#b2bec3;'>{query_day}暂无课程安排</p>"

    # 7. 完整 HTML 模板
    full_html = f"""
    <div style='max-width: 420px; margin: 0 auto; background: #f5f6fa; border-radius: 20px; overflow: hidden; font-family: sans-serif; border: 1px solid #dcdde1;'>
        <div style='background: {theme_color}; padding: 25px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h3 style='margin: 0; font-size: 20px;'>{title_label}</h3>
                    <p style='margin: 5px 0 0; opacity: 0.9; font-size: 12px;'>第 {curr_week} 周 · {natural_weekday} ({status_text})</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 18px; font-weight: bold;'>{temp}</div>
                    <div style='font-size: 12px;'>{CITY_NAME}·{weather}</div>
                </div>
            </div>
        </div>
        <div style='padding: 15px;'>{course_cards}</div>
        <div style='text-align: center; padding: 15px 0; border-top: 1px solid #eee; margin: 0 15px; color: #ced6e0; font-size: 10px;'>智能推送服务 · 祝学习顺利</div>
    </div>"""

    # 8. 发送推送
    final_title = f"{title_label} | {len(today_courses)}门课"
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", 
                          json={"token": PUSHPLUS_TOKEN, "title": final_title, "content": full_html, "template": "html"})
        except: pass
    send_email(final_title, full_html)

if __name__ == "__main__":
    main()
