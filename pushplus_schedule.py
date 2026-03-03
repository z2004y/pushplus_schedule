import json
import os
import requests
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 数据源
HOLIDAY_API_URL = "https://raw.githubusercontent.com/lanceliao/china-holiday-calender/master/holidayAPI.json"

# ================== 2. 逻辑处理函数 ==================

def get_holiday_status():
    """解析节假日数据，识别放假与补班"""
    try:
        res = requests.get(HOLIDAY_API_URL, timeout=15).json()
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        year_data = res.get("Years", {}).get(str(today.year), [])
        for holiday in year_data:
            start = datetime.strptime(holiday["StartDate"], "%Y-%m-%d").date()
            end = datetime.strptime(holiday["EndDate"], "%Y-%m-%d").date()
            if start <= today <= end:
                return True, holiday["Name"]
        for holiday in year_data:
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
    """单双周及范围周数判定"""
    if '单周' in week_str:
        if current_week % 2 == 0: return False
        week_str = week_str.replace('单周', '')
    elif '双周' in week_str:
        if current_week % 2 != 0: return False
        week_str = week_str.replace('双周', '')
    clean_str = week_str.replace('周', '')
    if '-' in clean_str:
        try:
            start, end = map(int, clean_str.split('-'))
            return start <= current_week <= end
        except: return True
    elif ',' in clean_str:
        try:
            weeks = [int(w.strip()) for w in clean_str.split(',')]
            return current_week in weeks
        except: return True
    return True

# ================== 3. 执行主逻辑 ==================

def main():
    # 读取配置
    with open("timetable.json", 'r', encoding='utf-8') as f:
        config = json.load(f)

    curr_week = get_current_week(config["semester_info"]["start_date"])
    week_parity = "单周" if curr_week % 2 != 0 else "双周"
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.today().isoweekday()-1]
    today_date_str = date.today().strftime("%m月%d日")
    
    is_off_day, holiday_tag = get_holiday_status()

    # --- 天气处理 ---
    curr_temp, weather_info, temp_range = "N/A", "未知", "-- / --"
    if WEATHER_API_KEY:
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=10).json()
            if w_res.get("error_code") == 0:
                curr_temp = w_res["result"]["realtime"]["temperature"]
                today_f = w_res["result"]["future"][0]
                weather_info = today_f['weather']
                temp_range = today_f['temperature'].replace('\\', '')
        except: pass

    # --- UI 渲染逻辑 ---
    main_body_html = ""
    colors = [("#ff4757", "#ffeeee"), ("#2e86de", "#e1f0ff"), ("#ffa502", "#fff4e1"), ("#2ed573", "#e7fbf0"), ("#5352ed", "#ececff")]
    
    if is_off_day:
        title = f"🏮 {holiday_tag}快乐"
        main_body_html = f"""
        <div style='padding: 50px 20px; text-align: center;'>
            <div style='font-size: 60px; margin-bottom: 20px;'>☕</div>
            <h4 style='color: #2f3542; margin: 0;'>{holiday_tag}休息日</h4>
            <p style='color: #747d8c; font-size: 14px; margin-top: 10px;'>今天是法定假期或周末，好好放松！</p>
        </div>"""
    else:
        today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
        today_courses.sort(key=lambda x: x.get("time", "00:00"))
        
        title = f"📚 {weekday_cn}课表"
        course_count_html = f"<div style='padding: 25px 25px 10px;'><span style='font-size: 16px; font-weight: bold; color: #2f3542;'>📖 今日共有 {len(today_courses)} 门课程</span></div>"
        
        course_cards = ""
        for i, c in enumerate(today_courses):
            main_color, bg_color = colors[i % len(colors)]
            course_cards += f"""
            <div style='margin-bottom: 15px; background: #fff; border-radius: 20px; border: 1px solid #f1f2f6; border-left: 6px solid {main_color}; box-shadow: 0 4px 12px rgba(0,0,0,0.02);'>
                <div style='padding: 20px;'>
                    <div style='display: flex; justify-content: space-between; align-items: flex-start;'>
                        <h4 style='margin: 0; color: #2f3542; font-size: 17px; line-height: 1.4;'>{c['name']}</h4>
                        <span style='font-size: 11px; background: {bg_color}; color: {main_color}; padding: 2px 8px; border-radius: 6px; white-space: nowrap;'>{c.get('session','')}</span>
                    </div>
                    <div style='margin-top: 12px; display: grid; grid-template-columns: 1.2fr 1fr; gap: 10px; font-size: 13px; color: #747d8c;'>
                        <div>🕒 {c.get('time','')}</div>
                        <div>📍 {c.get('location','')}</div>
                        <div>👨‍🏫 {c.get('teacher','')}</div>
                        <div style='color: {main_color};'>🗓️ {c.get('weeks','')}</div>
                    </div>
                </div>
            </div>"""
        
        if not today_courses:
            course_cards = "<div style='padding: 40px 20px; text-align: center; color: #747d8c;'>🎉 今日无课，自由万岁！</div>"
        
        main_body_html = course_count_html + f"<div style='padding: 10px 20px 30px;'>{course_cards}</div>"

    # --- 组装最终 HTML ---
    full_html = f"""
    <div style='max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 30px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.05); font-family: sans-serif;'>
        <div style='background: linear-gradient(135deg, #4834d4, #686de0); padding: 30px 25px; color: white; position: relative;'>
            <h2 style='margin: 0; font-size: 24px; font-weight: 600;'>今日课表 <span style='font-size: 16px; opacity: 0.8;'>· {weekday_cn}</span></h2>
            <div style='margin-top: 10px; display: flex; gap: 10px;'>
                <span style='background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 12px;'>第 {curr_week} 周 ({week_parity})</span>
                <span style='background: rgba(255,255,255,0.2); padding: 4px 12px; border-radius: 20px; font-size: 12px;'>📅 {today_date_str}</span>
            </div>
            <div style='position: absolute; right: 20px; bottom: 20px; text-align: right;'>
                <div style='font-size: 28px; font-weight: bold;'>{curr_temp}°C</div>
                <div style='font-size: 12px; opacity: 0.9;'>{CITY_NAME} · {weather_info}</div>
                <div style='font-size: 10px; opacity: 0.7;'>{temp_range}</div>
            </div>
        </div>
        {main_body_html}
        <div style='padding: 0 25px 25px; text-align: center; color: #ced6e0; font-size: 11px; letter-spacing: 1px;'>✨ 祝你今天学习愉快 ✨</div>
    </div>
    """

    # --- 发送推送 ---
    requests.post("http://www.pushplus.plus/send", json={
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": full_html,
        "template": "html"
    })

if __name__ == "__main__":
    main()
