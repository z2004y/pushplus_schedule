import json
import os
import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 0. 环境初始化 ==================
os.environ['TZ'] = 'Asia/Shanghai'
if hasattr(time, 'tzset'):
    time.tzset()

# ================== 1. 基础配置 ==================
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = os.getenv("CITY_NAME", "兰州")

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = 465

# ================== 2. 核心逻辑函数 ==================

def debug_log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DEBUG: {msg}")

def get_hitokoto():
    """获取一言随机语录"""
    try:
        res = requests.get("https://v1.hitokoto.cn/?c=d&c=i", timeout=5).json()
        return f"{res['hitokoto']} —— 「{res['from']}」"
    except:
        return "每一个不曾起舞的日子，都是对生命的辜负。 —— 尼采"

def get_holiday_status():
    """通过 API 精准识别放假与调休"""
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    week_map = {"Monday": "周一", "Tuesday": "周二", "Wednesday": "周三", 
                "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"}
    try:
        url = f"https://timor.tech/api/holiday/info/{today_str}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        if res.get("code") == 0:
            h_type = res["type"]["type"] 
            h_name = res["type"]["name"]
            if h_type in [0, 3]:
                is_adj = today.weekday() >= 5
                target = week_map.get(res.get("holiday", {}).get("target")) if res.get("holiday") else None
                return False, h_name, is_adj, target
            return True, h_name, False, None
    except: pass
    is_weekend = today.weekday() >= 5
    return is_weekend, ("周末" if is_weekend else "工作日"), False, None

def is_course_this_week(course_name, week_str, current_week):
    """解析周数并支持单双周筛选"""
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

# ================== 3. 主程序 ==================

def main():
    debug_log("=== 启动课表推送助手 ===")
    
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        debug_log(f"读取失败: {e}"); return

    today = date.today()
    start_dt = datetime.strptime(config["semester_info"]["start_date"], "%Y-%m-%d").date()
    end_dt = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    curr_week = ((today - start_monday).days // 7) + 1
    
    total_days = (end_dt - start_dt).days
    elapsed_days = (today - start_dt).days
    progress_percent = max(0, min(100, int((elapsed_days / total_days) * 100))) if total_days > 0 else 0
    natural_weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    is_off_day, status_text, is_adj, target_weekday = get_holiday_status()
    query_day = target_weekday if (is_adj and target_weekday) else natural_weekday
    hitokoto_text = get_hitokoto()

    # 状态与颜色映射
    if is_adj:
        bracket_label, theme_color, header_title = "调休", "#d63031", "🚨 调休上课"
    elif is_off_day:
        bracket_label, theme_color, header_title = "放假", "#27ae60", "🏖️ 放假休息"
    else:
        bracket_label, theme_color, header_title = "上课", "#0984e3", "📚 今日课表"

    # 天气获取
    temp, weather = "N/A", "未知"
    if WEATHER_API_KEY and WEATHER_API_KEY != "你的_聚合天气_KEY":
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=5).json()
            if w_res.get("error_code") == 0:
                f = w_res["result"]["future"][0]
                temp, weather = f["temperature"], f['weather']
        except: pass

    # 筛选与排序
    today_courses = [c for c in config["courses"] if c["day"] == query_day and is_course_this_week(c['name'], c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00").split('-')[0].strip().zfill(5))

    # 推送标题
    if is_off_day and len(today_courses) == 0:
        final_push_title = f"放假休息 | {len(today_courses)}门课"
    elif is_adj:
        final_push_title = f"调休上课 | {len(today_courses)}门课"
    else:
        final_push_title = f"{natural_weekday}课表 | {len(today_courses)}门课"

    # 进度条组件
    mini_bar = f"""
    <div style='margin-top: 2px; display: flex; align-items: center;'>
        <div style='width: 100px; background: rgba(255,255,255,0.3); height: 4px; border-radius: 2px; overflow: hidden;'>
            <div style='width: {progress_percent}%; background: #ffffff; height: 100%; border-radius: 2px;'></div>
        </div>
        <span style='font-size: 10px; color: #ffffff; margin-left: 6px; font-weight: bold; line-height: 1;'>{progress_percent}%</span>
    </div>"""

    # 课程卡片渲染
    course_cards = ""
    if is_off_day and len(today_courses) == 0:
        course_cards = f"<div style='padding: 40px 0; text-align: center;'><div style='font-size: 40px;'>☕</div><h3 style='color: #2d3436; margin: 10px 0 5px;'>{status_text}</h3><p style='color: #636e72; font-size: 13px;'>今天放假，好好休息吧！</p></div>"
    else:
        if is_adj:
            course_cards += f"<div style='background:#fff5f5; border:1px solid #fab1a0; padding:8px; border-radius:8px; margin-bottom:15px; color:#c0392b; font-size:12px; text-align:center;'>调休：按<b>{query_day}</b>课表显示</div>"
        for c in today_courses:
            course_cards += f"""
            <div style='margin-bottom: 12px; background: #fff; border-radius: 12px; border-left: 5px solid {theme_color}; padding: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);'>
                <div style='font-weight: bold; color: #2d3436; font-size: 16px; margin-bottom: 6px;'>{c['name']}</div>
                <div style='font-size: 13px; color: #636e72; display: grid; grid-template-columns: 1fr 1fr; gap: 4px;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div>
                    <div>👨‍🏫 {c['teacher']}</div><div style='color: {theme_color}; font-weight: bold;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards += f"<p style='text-align:center; padding:30px; color:#b2bec3;'>暂无课程</p>"

    # 优化后的 HTML 模板
    full_html = f"""
    <div style='max-width: 420px; margin: 0 auto; background: #f8f9fc; border-radius: 24px; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; border: 1px solid #e1e4e8; box-shadow: 0 8px 24px rgba(0,0,0,0.05);'>
        <!-- Header -->
        <div style='background: {theme_color}; padding: 25px 20px; color: white;'>
            <div style='text-align: center; margin-bottom: 18px;'>
                <h3 style='margin: 0; font-size: 22px; letter-spacing: 0.5px; font-weight: 800;'>{header_title}</h3>
            </div>
            
            <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
                <div style='text-align: left;'>
                    <p style='margin: 0; opacity: 0.95; font-size: 14px; font-weight: 600; line-height: 1;'>
                        第 {curr_week} 周 · {natural_weekday} ({bracket_label})
                    </p>
                    {mini_bar}
                </div>
                
                <div style='text-align: right;'>
                    <div style='font-size: 20px; font-weight: 800; line-height: 1;'>{temp}</div>
                    <div style='font-size: 11px; opacity: 0.85; margin-top: 4px; font-weight: 500; line-height: 1;'>{CITY_NAME} · {weather}</div>
                </div>
            </div>
        </div>
        
        <!-- Content -->
        <div style='padding: 20px;'>
            {course_cards}
            
            <!-- Quote -->
            <div style='margin-top: 15px; padding: 16px; background: #ffffff; border-radius: 16px; border: 1px dashed #d1d9e6;'>
                <div style='font-size: 13px; color: #4a5568; line-height: 1.6; font-style: italic; text-align: center;'>“ {hitokoto_text} ”</div>
            </div>
        </div>
        
        <!-- Footer -->
        <div style='text-align: center; padding: 15px 0; color: #a0aec0; font-size: 11px; background: #f1f4f8; font-weight: 500;'>
            自动推送助手 · 祝你学习愉快 ✨
        </div>
    </div>"""

    # 发送逻辑
    if PUSHPLUS_TOKEN and PUSHPLUS_TOKEN != "你的_PUSHPLUS_TOKEN":
        try: requests.post("http://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": final_push_title, "content": full_html, "template": "html"})
        except: pass
    if all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        try:
            receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
            msg = MIMEText(full_html, 'html', 'utf-8'); msg['Subject'] = Header(final_push_title, 'utf-8')
            msg['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_SENDER, EMAIL_PASS); server.sendmail(EMAIL_SENDER, receivers, msg.as_string())
            debug_log("推送成功")
        except Exception as e: debug_log(f"失败: {e}")

if __name__ == "__main__":
    main()
