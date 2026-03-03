import json
import os
import requests
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议通过环境变量设置，也可直接替换字符串
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 节假日 API 数据源
HOLIDAY_API_URL = "https://raw.githubusercontent.com/lanceliao/china-holiday-calender/master/holidayAPI.json"

# ================== 2. 核心逻辑函数 ==================

def get_holiday_status():
    """解析节假日数据，识别放假与补班"""
    try:
        res = requests.get(HOLIDAY_API_URL, timeout=10).json()
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        year_data = res.get("Years", {}).get(str(today.year), [])
        
        # 优先判断法定节假日
        for holiday in year_data:
            start = datetime.strptime(holiday["StartDate"], "%Y-%m-%d").date()
            end = datetime.strptime(holiday["EndDate"], "%Y-%m-%d").date()
            if start <= today <= end:
                return True, holiday["Name"]
            # 判断是否为补班日
            if today_str in holiday.get("CompDays", []):
                return False, f"{holiday['Name']}补班"
        
        # 普通周末判断
        return (today.weekday() >= 5), "周末"
    except:
        # 网络异常时回退到本地判断
        return (date.today().weekday() >= 5), "普通周末"

def get_current_week(start_date_str):
    """计算当前教学周"""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    # 调整到起始周的周一
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    days_diff = (date.today() - start_monday).days
    return (days_diff // 7) + 1

def is_course_this_week(week_str, current_week):
    """
    解析周数逻辑：
    支持 "3-18周", "3,5,7周", "3-12,17-18周", "3周" 等格式
    """
    clean_str = week_str.replace('周', '').strip()
    # 按逗号分割区间
    intervals = clean_str.split(',')
    for interval in intervals:
        if '-' in interval:
            try:
                start, end = map(int, interval.split('-'))
                if start <= current_week <= end:
                    return True
            except: continue
        else:
            try:
                if int(interval) == current_week:
                    return True
            except: continue
    return False

def main():
    # 1. 加载本地配置文件
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("错误：未找到 timetable.json 文件")
        return

    # 2. 计算时间和周数
    today = date.today()
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today.weekday()]
    
    # 判定是否为最后两周（期末周）
    is_final_period = curr_week >= 17 
    
    # 计算学期结束倒计时
    end_date = datetime.strptime(config["semester_info"]["end_date"], "%Y-%m-%d").date()
    days_to_end = (end_date - today).days
    
    is_off_day, holiday_tag = get_holiday_status()

    # 3. 获取天气数据
    curr_temp, weather_info, temp_range = "N/A", "未知", "--/--"
    if WEATHER_API_KEY:
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=5).json()
            if w_res.get("error_code") == 0:
                curr_temp = w_res["result"]["realtime"]["temperature"]
                today_f = w_res["result"]["future"][0]
                weather_info = today_f['weather']
                temp_range = today_f['temperature'].replace('\\', '')
        except: pass

    # 4. 筛选今日课程
    today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # 5. UI 渲染逻辑
    # 头部配色：期末周使用红色，平时使用紫色
    header_bg = "linear-gradient(135deg, #ff4757, #ff6b81)" if is_final_period else "linear-gradient(135deg, #4834d4, #686de0)"
    title_prefix = "🔥 期末周提醒" if is_final_period else "📚 今日课表"
    
    # 倒计时条
    countdown_text = f"距离学期结束还有 {days_to_end} 天" if days_to_end > 0 else "学期已结束"
    
    main_body_html = ""
    if is_off_day and not today_courses:
        main_body_html = f"""
        <div style='padding: 40px 20px; text-align: center;'>
            <div style='font-size: 50px;'>☕</div>
            <h4 style='color: #2f3542; margin: 10px 0;'>{holiday_tag}休息日</h4>
            <p style='color: #747d8c; font-size: 13px;'>{countdown_text}</p>
        </div>"""
    else:
        # 生成课程卡片
        course_cards = ""
        colors = [("#ff4757", "#ffeeee"), ("#2e86de", "#e1f0ff"), ("#ffa502", "#fff4e1"), ("#2ed573", "#e7fbf0")]
        
        for i, c in enumerate(today_courses):
            # 期末周统一色调增强紧张感，平时使用彩色
            m_color = "#ff4757" if is_final_period else colors[i % len(colors)][0]
            b_color = "#fff5f5" if is_final_period else colors[i % len(colors)][1]
            
            course_cards += f"""
            <div style='margin-bottom: 15px; background: #fff; border-radius: 15px; border-left: 6px solid {m_color}; padding: 18px; box-shadow: 0 4px 10px rgba(0,0,0,0.03);'>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 17px; font-weight: bold; color: #2f3542;'>{c['name']}</span>
                    <span style='font-size: 11px; background: {b_color}; color: {m_color}; padding: 2px 8px; border-radius: 6px;'>{c['session']}</span>
                </div>
                <div style='margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px; color: #747d8c;'>
                    <div>🕒 {c['time']}</div>
                    <div>📍 {c['location']}</div>
                    <div>👨‍🏫 {c['teacher']}</div>
                    <div style='color: {m_color}; font-weight: 500;'>🗓️ {c['weeks']}</div>
                </div>
            </div>"""
        
        if not today_courses:
            course_cards = "<p style='text-align: center; color: #747d8c; padding: 30px;'>今天没课，记得温习功课哦！</p>"
            
        main_body_html = f"""
        <div style='padding: 15px 20px;'>
            <div style='margin-bottom: 15px; font-size: 13px; color: #a4b0be; text-align: center;'>— {countdown_text} —</div>
            {course_cards}
        </div>"""

    # 6. 组装最终 HTML
    full_html = f"""
    <div style='max-width: 450px; margin: 0 auto; background: #f1f2f6; border-radius: 25px; overflow: hidden; font-family: -apple-system, sans-serif;'>
        <div style='background: {header_bg}; padding: 30px 25px; color: white;'>
            <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
                <div>
                    <h2 style='margin: 0; font-size: 22px;'>{title_prefix}</h2>
                    <p style='margin: 5px 0 0; opacity: 0.8; font-size: 13px;'>第 {curr_week} 周 · {weekday_cn}</p>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 26px; font-weight: bold;'>{curr_temp}°C</div>
                    <div style='font-size: 12px; opacity: 0.9;'>{CITY_NAME} / {weather_info}</div>
                </div>
            </div>
        </div>
        {main_body_html}
        <div style='text-align: center; padding: 15px; color: #ced6e0; font-size: 11px;'>自动提醒服务 · 祝你考试必过</div>
    </div>
    """

    # 7. 发送推送
    push_data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"{'🔥' if is_final_period else '📅'} {weekday_cn}课表提醒",
        "content": full_html,
        "template": "html"
    }
    
    response = requests.post("http://www.pushplus.plus/send", json=push_data)
    print(f"推送结果: {response.text}")

if __name__ == "__main__":
    main()
