import json
import os
import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 0. 环境初始化 ==================
# 解决 GitHub Actions (UTC) 时区偏差
os.environ['TZ'] = 'Asia/Shanghai'
if hasattr(time, 'tzset'):
    time.tzset()

# ================== 1. 基础配置 ==================
# 建议在 GitHub Actions Secrets 中配置，或直接在此修改
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = os.getenv("CITY_NAME", "兰州")

# 邮件配置
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.qq.com")
SMTP_PORT = 465

# ================== 2. 核心工具函数 ==================

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
    
    # 1. 加载本地数据
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        debug_log(f"读取失败: {e}"); return

    # 2. 基础时间与高精度进度计算
    today = date.today()
    s_date = datetime.strptime(config["semester_info"]["start_date"], "%Y-%m-%d").date()
    e_date = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    s_monday = s_date - timedelta(days=s_date.weekday())
    curr_week = ((today - s_monday).days // 7) + 1
    
    total_days = (e_date - s_date).days
    elapsed_days = (today - s_date).days
    progress = max(0, min(100, int((elapsed_days / total_days) * 100))) if total_days > 0 else 0
    natural_weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 3. 状态判定与文字映射
    is_off, status_text, is_adj, target_day = get_holiday_status()
    query_day = target_day if (is_adj and target_day) else natural_weekday
    hitokoto = get_hitokoto()

    # 4. UI 颜色与标题定制
    if is_adj:
        label, theme_color, theme_gradient, header_title = "调休", "#FF4B2B", "#FF416C", "🚨 调休上课"
    elif is_off:
        label, theme_color, theme_gradient, header_title = "放假", "#56AB2F", "#A8E063", "🏖️ 放假休息"
    else:
        label, theme_color, theme_gradient, header_title = "上课", "#2193B0", "#6DDCFF", "📚 今日课表"

    # 5. 获取天气
    temp, weather = "N/A", "未知"
    if WEATHER_API_KEY and WEATHER_API_KEY != "你的_聚合天气_KEY":
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=5).json()
            if w_res.get("error_code") == 0:
                f_w = w_res["result"]["future"][0]
                temp, weather = f_w["temperature"], f_w['weather']
        except: pass

    # 6. 筛选与 zfill 排序
    courses = [c for c in config["courses"] if c["day"] == query_day and is_course_this_week(c['name'], c["weeks"], curr_week)]
    courses.sort(key=lambda x: x.get("time", "00:00").split('-')[0].strip().zfill(5))

    # 7. 推送标题逻辑
    if is_off and len(courses) == 0:
        push_title = f"放假休息 | {len(courses)}门课"
    elif is_adj:
        push_title = f"调休上课 | {len(courses)}门课"
    else:
        push_title = f"{natural_weekday}课表 | {len(courses)}门课"

    # 8. 构造 HTML
    # 进度条组件
    mini_bar = f"""
    <div style='margin-top: 2px; display: flex; align-items: center;'>
        <div style='width: 80px; background: rgba(255,255,255,0.3); height: 4px; border-radius: 4px; overflow: hidden;'>
            <div style='width: {progress}%; background: #ffffff; height: 100%;'></div>
        </div>
        <span style='font-size: 10px; color: #ffffff; margin-left: 6px; font-weight: bold; line-height: 1;'>{progress}%</span>
    </div>"""

    # 课程卡片渲染
    course_cards = ""
    if is_off and len(courses) == 0:
        course_cards = f"<div style='padding: 40px 0; text-align: center;'><div style='font-size: 35px;'>☕</div><p style='color: #94a3b8; font-size: 14px; margin-top: 10px;'>今天放假，好好休息吧！</p></div>"
    else:
        if is_adj:
            course_cards += f"<div style='background:rgba(214,48,49,0.05); border:1px solid rgba(214,48,49,0.1); padding:8px; border-radius:10px; margin-bottom:15px; color:#d63031; font-size:12px; text-align:center;'>调休按<b>{query_day}</b>课表显示</div>"
        for c in courses:
            course_cards += f"""
            <div style='margin-bottom: 12px; background: #ffffff; border-radius: 16px; border-left: 4px solid {theme_color}; padding: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); border: 1px solid #f1f5f9;'>
                <div style='font-weight: 800; color: #1e293b; font-size: 16px; margin-bottom: 6px;'>{c['name']}</div>
                <div style='font-size: 13px; color: #64748b; display: grid; grid-template-columns: 1fr 1fr; gap: 4px;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div>
                    <div>👨‍🏫 {c['teacher']}</div><div style='color: {theme_color}; font-weight: bold;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not courses:
            course_cards += f"<p style='text-align:center; padding:30px; color:#94a3b8;'>今日暂无课程安排</p>"

    # 最终 HTML 模板
    full_html = f"""
    <div style='max-width: 400px; margin: 0 auto; background: #ffffff; border-radius: 24px; overflow: hidden; font-family: -apple-system, system-ui, sans-serif; border: 1px solid #f1f5f9; box-shadow: 0 10px 25px rgba(0,0,0,0.05);'>
        <!-- Header: 左右开弓 + 底部对齐 -->
        <div style='background: linear-gradient(135deg, {theme_color}, {theme_gradient}); padding: 20px 22px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
                <!-- 左侧 -->
                <div style='text-align: left;'>
                    <h3 style='margin: 0 0 5px 0; font-size: 19px; letter-spacing: 0.5px; font-weight: 800;'>{header_title}</h3>
                    <p style='margin: 0; opacity: 0.95; font-size: 13px; font-weight: 600; line-height: 1.1;'>
                        第 {curr_week} 周 · {natural_weekday} ({label})
                    </p>
                    {mini_bar}
                </div>
                <!-- 右侧: 强化大字温度 -->
                <div style='text-align: right;'>
                    <div style='font-size: 24px; font-weight: 900; line-height: 1.1;'>{temp}</div>
                    <div style='font-size: 12px; opacity: 0.9; margin-top: 2px; line-height: 1.1; font-weight: 600;'>{CITY_NAME} · {weather}</div>
                </div>
            </div>
        </div>
        
        <!-- 内容 -->
        <div style='padding: 18px;'>
            {course_cards}
            
            <!-- 一言语录 -->
            <div style='margin-top: 8px; padding: 15px; background: #f8fafc; border-radius: 16px; border: 1px solid #f1f5f9;'>
                <div style='font-size: 12px; color: #475569; line-height: 1.6; font-style: italic; text-align: center;'>“ {hitokoto} ”</div>
            </div>
        </div>
        
        <!-- Footer -->
        <div style='text-align: center; padding: 12px 0; color: #94a3b8; font-size: 10px; background: #f8fafc;'>
            自动提醒助手 · 愿你学有所成 ✨
        </div>
    </div>"""

    # 9. 执行发送
    if PUSHPLUS_TOKEN and PUSHPLUS_TOKEN != "你的_PUSHPLUS_TOKEN":
        try: requests.post("http://www.pushplus.plus/send", json={"token": PUSHPLUS_TOKEN, "title": push_title, "content": full_html, "template": "html"})
        except: pass
    if all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        try:
            receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
            msg = MIMEText(full_html, 'html', 'utf-8'); msg['Subject'] = Header(push_title, 'utf-8')
            msg['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_SENDER, EMAIL_PASS); server.sendmail(EMAIL_SENDER, receivers, msg.as_string())
            debug_log("推送成功")
        except Exception as e: debug_log(f"失败: {e}")

if __name__ == "__main__":
    main()
