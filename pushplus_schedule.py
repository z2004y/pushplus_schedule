import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议在 GitHub Actions Secrets 中配置，或直接在此修改
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 邮件配置
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")      # 授权码/应用密码
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

# ================== 2. 调试与逻辑工具 ==================

def debug_log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DEBUG: {msg}")

def get_holiday_status():
    """
    根据 API 数字精准识别：
    type 0 (工作日) & type 3 (调休补班) -> 必须上课
    type 1 (普通周末) & type 2 (法定节假日) -> 放假休息
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    week_map = {"Monday": "周一", "Tuesday": "周二", "Wednesday": "周三", 
                "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"}
    
    try:
        # 使用 timor.tech API
        url = f"https://timor.tech/api/holiday/info/{today_str}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        debug_log(f"API 响应内容: {res}")
        
        if res.get("code") == 0:
            h_type = res["type"]["type"]  # 获取数字类型
            h_name = res["type"]["name"]  # 获取名称
            
            # --- 核心判定逻辑 ---
            # 0 和 3 都属于需要上班/上课的日子
            if h_type in [0, 3]:
                # 补班定义：API说是工作模式(0,3) 且 实际是周六日(5,6)
                is_makeup = today.weekday() >= 5
                
                target = None
                if res.get("holiday") and res["holiday"].get("target"):
                    target = week_map.get(res["holiday"].get("target"))
                
                debug_log(f"结果判定: 【上课模式】 类型={h_type}, 名称={h_name}, 补班={is_makeup}, 映射={target}")
                return False, h_name, is_makeup, target
            else:
                # 1 和 2 属于休息模式
                debug_log(f"结果判定: 【放假模式】 类型={h_type}, 名称={h_name}")
                return True, h_name, False, None
    except Exception as e:
        debug_log(f"节假日API异常: {e}")

    # 保底：仅根据周六日判断
    is_weekend = today.weekday() >= 5
    return is_weekend, ("周末" if is_weekend else "工作日"), False, None

def is_course_this_week(course_name, week_str, current_week):
    """解析周数并支持单双周筛选"""
    is_even = current_week % 2 == 0
    # 单双周关键字过滤
    if "单" in week_str and is_even:
        debug_log(f"  [-] {course_name}: 单周课，今日第{current_week}周(双)，跳过")
        return False
    if "双" in week_str and not is_even:
        debug_log(f"  [-] {course_name}: 双周课，今日第{current_week}周(单)，跳过")
        return False
    
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

    # 2. 基础时间计算
    today = date.today()
    start_dt = datetime.strptime(config["semester_info"]["start_date"], "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    curr_week = ((today - start_monday).days // 7) + 1
    natural_weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    debug_log(f"当前学期第 {curr_week} 周，今日 {natural_weekday}")

    # 3. 节假日与补班映射
    is_off_day, status_text, is_makeup, target_weekday = get_holiday_status()

    # 逻辑映射：如果是补班且API指定了调休目标（如补周一），则查询周一的课
    query_day = target_weekday if (is_makeup and target_weekday) else natural_weekday
    debug_log(f"决策: 状态={status_text}, 补班={is_makeup}, 映射目标={target_weekday}, 最终查课日期={query_day}")

    # 4. 获取天气
    temp, weather = "N/A", "未知"
    if WEATHER_API_KEY:
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=5).json()
            if w_res.get("error_code") == 0:
                temp = w_res["result"]["future"][0]["temperature"]
                weather = w_res["result"]["future"][0]['weather']
        except: debug_log("天气接口调用失败")

    # 5. 筛选课程
    today_courses = [c for c in config["courses"] if c["day"] == query_day and is_course_this_week(c['name'], c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # 6. UI 主题判定
    # 优先级：补班(红) > 有课(蓝) > 放假(绿)
    if is_makeup:
        theme_color = "#d63031" # 红色
        title_label = "🚨 补班上课提醒"
    elif len(today_courses) > 0:
        theme_color = "#0984e3" # 蓝色
        title_label = "📚 今日课表"
    elif is_off_day:
        theme_color = "#27ae60" # 绿色
        title_label = "🏖️ 放假休息"
    else:
        theme_color = "#0984e3"
        title_label = "📚 今日课表"

    # 7. 构造 HTML 卡片
    course_cards = ""
    # 只有确定是放假且确实没课时，才展示“放假好好休息”
    if is_off_day and len(today_courses) == 0:
        course_cards = f"""
        <div style='padding: 40px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h3 style='color: #2d3436;'>{status_text}</h3>
            <p style='color: #636e72; font-size: 14px;'>今天放假，好好休息吧！</p>
        </div>"""
    else:
        if is_makeup:
            course_cards += f"<div style='background:#fff5f5; border:1px solid #fab1a0; padding:12px; border-radius:10px; margin-bottom:15px; color:#c0392b; font-size:13px;'><b>调休说明：</b>今天是{status_text}。正在按<b>{query_day}</b>的课表显示。</div>"
        
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
            course_cards += f"<p style='text-align:center; padding:30px; color:#b2bec3;'>{status_text}，但{query_day}暂无课程</p>"

    # 完整 HTML 模板
    full_html = f"""
    <div style='max-width: 420px; margin: 0 auto; background: #f5f6fa; border-radius: 20px; overflow: hidden; font-family: sans-serif; border: 1px solid #dcdde1;'>
        <div style='background: {theme_color}; padding: 25px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h3 style='margin: 0; font-size: 18px;'>{title_label}</h3>
                    <p style='margin: 5px 0 0; opacity: 0.9; font-size: 12px;'>第 {curr_week} 周 · {natural_weekday} ({status_text})</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 16px; font-weight: bold;'>{temp}</div>
                    <div style='font-size: 11px;'>{CITY_NAME}·{weather}</div>
                </div>
            </div>
        </div>
        <div style='padding: 15px;'>{course_cards}</div>
        <div style='text-align: center; padding: 15px 0; color: #ced6e0; font-size: 10px;'>自动提醒服务 · 祝学习愉快</div>
    </div>"""

    # 8. 执行发送
    final_title = f"{title_label} | {len(today_courses)}门课"
    
    # PushPlus 发送
    if PUSHPLUS_TOKEN:
        try:
            requests.post("http://www.pushplus.plus/send", 
                          json={"token": PUSHPLUS_TOKEN, "title": final_title, "content": full_html, "template": "html"})
            debug_log("PushPlus 推送成功")
        except: pass

    # Email 发送
    if all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        try:
            receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
            msg = MIMEText(full_html, 'html', 'utf-8')
            msg['Subject'] = Header(final_title, 'utf-8')
            msg['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL_SENDER, EMAIL_PASS)
                server.sendmail(EMAIL_SENDER, receivers, msg.as_string())
            debug_log("邮件推送成功")
        except Exception as e:
            debug_log(f"邮件发送失败: {e}")

    debug_log("=== 任务运行结束 ===")

if __name__ == "__main__":
    main()
