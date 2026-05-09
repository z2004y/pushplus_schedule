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

# ================== 2. 逻辑工具函数 ==================

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
    """通过 API 精准识别节假日与调休补班"""
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    week_map = {"Monday": "周一", "Tuesday": "周二", "Wednesday": "周三", 
                "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"}
    try:
        url = f"https://timor.tech/api/holiday/info/{today_str}"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10).json()
        if res.get("code") == 0:
            h_type = res["type"]["type"] 
            h_name = res["type"]["name"]
            if h_type in [0, 3]:
                is_makeup = today.weekday() >= 5
                target = week_map.get(res.get("holiday", {}).get("target")) if res.get("holiday") else None
                return False, h_name, is_makeup, target
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
    
    # 1. 加载本地 JSON
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        debug_log(f"无法读取 timetable.json: {e}"); return

    # 2. 基础时间与【高精度进度】计算
    today = date.today()
    start_dt = datetime.strptime(config["semester_info"]["start_date"], "%Y-%m-%d").date()
    end_dt = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    
    # 计算周数 (以开学周的周一为基准)
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    curr_week = ((today - start_monday).days // 7) + 1
    
    # 计算日期百分比进度
    total_days = (end_dt - start_dt).days
    elapsed_days = (today - start_dt).days
    if elapsed_days < 0:
        progress_percent = 0
    elif elapsed_days > total_days:
        progress_percent = 100
    else:
        progress_percent = int((elapsed_days / total_days) * 100)
    
    natural_weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 3. 状态判定
    is_off_day, status_text, is_makeup, target_weekday = get_holiday_status()
    query_day = target_weekday if (is_makeup and target_weekday) else natural_weekday
    hitokoto_text = get_hitokoto()

    # 4. 获取天气
    temp, weather = "N/A", "未知"
    if WEATHER_API_KEY and WEATHER_API_KEY != "你的_聚合天气_KEY":
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=5).json()
            if w_res.get("error_code") == 0:
                future = w_res["result"]["future"][0]
                temp, weather = future["temperature"], future['weather']
        except: pass

    # 5. 课程筛选与排序
    today_courses = [c for c in config["courses"] if c["day"] == query_day and is_course_this_week(c['name'], c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00").split('-')[0].strip().zfill(5))

    # 6. UI 主题判定
    theme_color = "#d63031" if is_makeup else ("#27ae60" if is_off_day and not today_courses else "#0984e3")
    title_label = "🚨 补班上课" if is_makeup else ("🏖️ 放假休息" if is_off_day and not today_courses else "📚 今日课表")

    # 7. 构造 HTML 卡片
    # --- 优化后的高颜值进度条 ---
    progress_html = f"""
    <div style='margin-bottom: 20px;'>
        <div style='display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 6px;'>
            <span style='font-size: 14px; font-weight: bold; color: #2d3436;'>第 {curr_week} 周进度</span>
            <span style='font-size: 12px; color: {theme_color}; font-weight: bold;'>{progress_percent}%</span>
        </div>
        <div style='background: #e0e6ed; border-radius: 10px; height: 10px; width: 100%; overflow: hidden; box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);'>
            <div style='width: {progress_percent}%; background: {theme_color}; height: 100%; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.2);'></div>
        </div>
        <div style='display: flex; justify-content: space-between; font-size: 10px; color: #a4b0be; margin-top: 4px;'>
            <span>{config["semester_info"]["start_date"]}</span>
            <span>{config["semester_info"]["end_date"]}</span>
        </div>
    </div>
    """

    course_cards = ""
    if is_off_day and len(today_courses) == 0:
        course_cards = f"<div style='padding: 30px; text-align: center;'><div style='font-size: 40px;'>☕</div><h3 style='color: #2d3436;'>{status_text}</h3><p style='color: #636e72; font-size: 13px;'>今天放假，好好休息吧！</p></div>"
    else:
        if is_makeup:
            course_cards += f"<div style='background:#fff5f5; border:1px solid #fab1a0; padding:10px; border-radius:8px; margin-bottom:15px; color:#c0392b; font-size:12px;'><b>调休说明：</b>今天是{status_text}，按<b>{query_day}</b>课表显示。</div>"
        for c in today_courses:
            course_cards += f"""
            <div style='margin-bottom: 12px; background: #fff; border-radius: 12px; border-left: 5px solid {theme_color}; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>
                <div style='font-weight: bold; color: #2d3436; font-size: 16px; margin-bottom: 5px;'>{c['name']}</div>
                <div style='font-size: 13px; color: #636e72; display: grid; grid-template-columns: 1fr 1fr; gap: 5px;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div>
                    <div>👨‍🏫 {c['teacher']}</div><div style='color: {theme_color}; font-weight: bold;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards += f"<p style='text-align:center; padding:20px; color:#b2bec3;'>{status_text}，但{query_day}暂无课程</p>"

    # --- 最终 HTML 结构 ---
    full_html = f"""
    <div style='max-width: 420px; margin: 0 auto; background: #f5f6fa; border-radius: 20px; overflow: hidden; font-family: -apple-system, system-ui, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; border: 1px solid #dcdde1; box-shadow: 0 10px 30px rgba(0,0,0,0.1);'>
        <div style='background: {theme_color}; padding: 25px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h3 style='margin: 0; font-size: 20px; letter-spacing: 1px;'>{title_label}</h3>
                    <p style='margin: 5px 0 0; opacity: 0.9; font-size: 13px;'>
                        <b>第 {curr_week} 周</b> · {natural_weekday} ({status_text})
                    </p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 18px; font-weight: bold;'>{temp}</div>
                    <div style='font-size: 11px; opacity: 0.8;'>{CITY_NAME} · {weather}</div>
                </div>
            </div>
        </div>
        <div style='padding: 20px;'>
            {progress_html}
            {course_cards}
            <div style='margin-top: 15px; padding: 15px; background: #ffffff; border-radius: 12px; border: 1px dashed #ced6e0; position: relative;'>
                <div style='font-size: 13px; color: #57606f; line-height: 1.6; font-style: italic;'>“ {hitokoto_text} ”</div>
            </div>
        </div>
        <div style='text-align: center; padding: 15px 0; color: #a4b0be; font-size: 10px; background: #f1f2f6;'>
            自动提醒助手 · 祝你今天学习愉快 ✨
        </div>
    </div>"""

    # 8. 执行发送
    final_title = f"第{curr_week}周{natural_weekday} | {len(today_courses)}门课"
    if PUSHPLUS_TOKEN and PUSHPLUS_TOKEN != "你的_PUSHPLUS_TOKEN":
        try: requests.post("http://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": final_title, "content": full_html, "template": "html"})
        except: pass
    if all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        try:
            receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
            msg = MIMEText(full_html, 'html', 'utf-8'); msg['Subject'] = Header(final_title, 'utf-8')
            msg['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_SENDER, EMAIL_PASS); server.sendmail(EMAIL_SENDER, receivers, msg.as_string())
            debug_log("推送成功")
        except Exception as e: debug_log(f"失败: {e}")

if __name__ == "__main__":
    main()
