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

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER") 
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

# ================== 2. 调试打印助手 ==================
def debug_log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DEBUG: {msg}")

# ================== 3. 逻辑处理函数 ==================

def get_holiday_status():
    """获取节假日详情，包含深度调试日志"""
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    week_map = {"Monday": "周一", "Tuesday": "周二", "Wednesday": "周三", 
                "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"}
    
    debug_log(f"正在查询日期: {today_str} (自然星期: {['一','二','三','四','五','六','日'][today.weekday()]})")
    
    try:
        url = f"https://timor.tech/api/holiday/info/{today_str}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        debug_log(f"API 响应内容: {res}")
        
        if res.get("code") == 0:
            h_type = res["type"]["type"]  # 0工作日, 1周末, 2节日, 3调休
            h_name = res["holiday"]["name"] if res.get("holiday") else "无名称"
            
            # 判定补班：API返回工作日(0)且自然日是周末
            is_makeup = (h_type == 0 and today.weekday() >= 5)
            target = None
            if is_makeup and res.get("holiday"):
                target = week_map.get(res["holiday"].get("target"))
            
            debug_log(f"解析结果: 类型={h_type}({h_name}), 是否补班={is_makeup}, 映射目标={target}")
            
            if h_type == 0:
                return False, (f"{h_name}补班" if is_makeup else "工作日"), is_makeup, target
            else:
                return True, (h_name or "周末"), False, None
    except Exception as e:
        debug_log(f"API 请求失败: {e}")

    # 保底逻辑
    is_weekend = today.weekday() >= 5
    debug_log(f"使用保底逻辑: 是否周末={is_weekend}")
    return is_weekend, ("周末休息" if is_weekend else "工作日"), False, None

def is_course_this_week(course_name, week_str, current_week):
    """解析周数并打印调试信息"""
    is_even = current_week % 2 == 0
    res = False
    
    # 单双周判定
    if "单" in week_str and is_even:
        debug_log(f"  [-] 课程 {course_name}: 要求单周，当前是第 {current_week} 周(双)，跳过")
        return False
    if "双" in week_str and not is_even:
        debug_log(f"  [-] 课程 {course_name}: 要求双周，当前是第 {current_week} 周(单)，跳过")
        return False
    
    clean = week_str.replace('周','').replace('(单)','').replace('(双)','').replace('单','').replace('双','').strip()
    for part in clean.split(','):
        if '-' in part:
            try:
                s, e = map(int, part.split('-'))
                if s <= current_week <= e: res = True
            except: continue
        elif part.strip():
            try:
                if int(part) == current_week: res = True
            except: continue
    
    if res:
        debug_log(f"  [+] 课程 {course_name}: 周数匹配成功 ({week_str})")
    else:
        debug_log(f"  [-] 课程 {course_name}: 周数不匹配 ({week_str})")
    return res

def send_email(title, html_content):
    if not all([EMAIL_SENDER, EMAIL_PASS, EMAIL_RECEIVER]):
        debug_log("邮件配置缺失，不发送邮件")
        return
    receivers = [r.strip() for r in EMAIL_RECEIVER.split(",") if r.strip()]
    message = MIMEText(html_content, 'html', 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    message['From'] = f"{Header('课表助手', 'utf-8').encode()} <{EMAIL_SENDER}>"
    message['To'] = receivers[0] if len(receivers) == 1 else Header("订阅用户", "utf-8").encode()
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_SENDER, EMAIL_PASS)
            server.sendmail(EMAIL_SENDER, receivers, message.as_string())
        debug_log(f"邮件已群发给 {len(receivers)} 个地址")
    except Exception as e:
        debug_log(f"邮件发送异常: {e}")

# ================== 4. 主程序 ==================

def main():
    debug_log("=== 开始运行课表助手 ===")
    
    # 1. 加载配置
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        debug_log(f"JSON加载失败: {e}"); return

    # 2. 时间计算
    today = date.today()
    start_dt = datetime.strptime(config["semester_info"]["start_date"], "%Y-%m-%d").date()
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    curr_week = ((today - start_monday).days // 7) + 1
    natural_weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    debug_log(f"学期周数计算: 开学周周一={start_monday}, 当前第 {curr_week} 周")

    # 3. 获取节假日状态
    is_off_day, status_text, is_makeup, target_weekday = get_holiday_status()

    # 4. 确定查询哪一天的课表
    query_day = target_weekday if (is_makeup and target_weekday) else natural_weekday
    debug_log(f"查询决策: 今日自然{natural_weekday}, 实际课表查询目标={query_day}")

    # 5. 获取天气
    temp, weather = "N/A", "未知"
    if WEATHER_API_KEY:
        try:
            w_res = requests.get(f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}", timeout=5).json()
            if w_res.get("error_code") == 0:
                temp = w_res["result"]["future"][0]["temperature"]
                weather = w_res["result"]["future"][0]['weather']
                debug_log(f"天气获取成功: {temp}, {weather}")
        except:
            debug_log("天气 API 调用失败")

    # 6. 筛选课程
    debug_log(f"开始筛选 {query_day} 的课程...")
    today_courses = [c for c in config["courses"] if c["day"] == query_day and is_course_this_week(c['name'], c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))
    debug_log(f"今日最终课程总数: {len(today_courses)}")

    # 7. 标题与配色逻辑判定
    if is_makeup:
        theme_color = "#d63031" # 红色
        title_label = "🚨 补班上课提醒"
        debug_log("UI 判定: 补班模式 (红色)")
    elif len(today_courses) > 0:
        theme_color = "#0984e3" # 蓝色
        title_label = "📚 今日课表"
        debug_log("UI 判定: 正常上课模式 (蓝色)")
    elif is_off_day:
        theme_color = "#27ae60" # 绿色
        title_label = "🏖️ 放假休息"
        debug_log("UI 判定: 放假休息模式 (绿色)")
    else:
        theme_color = "#0984e3"
        title_label = "📚 今日课表"
        debug_log("UI 判定: 无课模式 (蓝色)")

    # 8. HTML 构造
    course_cards = ""
    if is_off_day and len(today_courses) == 0:
        course_cards = f"<div style='padding:40px;text-align:center;'>☕ <b>{status_text}</b><br><span style='color:grey;'>今天没课，好好休息</span></div>"
    else:
        if is_makeup:
            course_cards += f"<div style='background:#fff5f5; border:1px solid #fab1a0; padding:10px; border-radius:10px; margin-bottom:15px; color:#c0392b; font-size:12px;'><b>调休说明：</b>今天是{status_text}，显示{query_day}课表</div>"
        
        for c in today_courses:
            course_cards += f"""
            <div style='margin-bottom:12px; background:#fff; border-radius:12px; border-left:5px solid {theme_color}; padding:15px; box-shadow:0 2px 5px rgba(0,0,0,0.05);'>
                <div style='font-weight:bold; color:#2d3436;'>{c['name']}</div>
                <div style='margin-top:8px; font-size:13px; color:#636e72; display:grid; grid-template-columns:1fr 1fr;'>
                    <div>🕒 {c['time']}</div><div>📍 {c['location']}</div>
                    <div>👨‍🏫 {c['teacher']}</div><div style='color:{theme_color}; font-weight:bold;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        if not today_courses:
            course_cards += f"<p style='text-align:center; padding:30px; color:#b2bec3;'>{status_text}，但暂无课程安排</p>"

    full_html = f"""
    <div style='max-width:420px; margin:0 auto; background:#f5f6fa; border-radius:20px; overflow:hidden; border:1px solid #dcdde1;'>
        <div style='background:{theme_color}; padding:25px; color:white;'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <h3 style='margin:0;'>{title_label}</h3>
                    <p style='margin:5px 0 0; opacity:0.9; font-size:12px;'>第 {curr_week} 周 · {natural_weekday} ({status_text})</p>
                </div>
                <div style='text-align:right;'>
                    <div style='font-size:18px; font-weight:bold;'>{temp}</div>
                    <div style='font-size:12px;'>{CITY_NAME}·{weather}</div>
                </div>
            </div>
        </div>
        <div style='padding:15px;'>{course_cards}</div>
    </div>"""

    # 9. 执行发送
    final_title = f"{title_label} | {len(today_courses)}门课"
    if PUSHPLUS_TOKEN:
        try:
            r = requests.post("http://www.pushplus.plus/send", 
                          json={"token": PUSHPLUS_TOKEN, "title": final_title, "content": full_html, "template": "html"})
            debug_log(f"PushPlus 响应: {r.text}")
        except Exception as e:
            debug_log(f"PushPlus 发送失败: {e}")
    
    send_email(final_title, full_html)
    debug_log("=== 程序运行结束 ===")

if __name__ == "__main__":
    main()
