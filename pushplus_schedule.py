import json
import os
import requests
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议在 GitHub Secrets 中设置 PUSHPLUS_TOKEN 和 WEATHER_API_KEY
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# ================== 2. 逻辑处理函数 ==================

def get_current_week(start_date_str):
    """根据学期开始日期计算当前是第几周 (周一为一周开始)"""
    # 将字符串转为 date 对象
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    # 【修复点】使用 timedelta 处理日期减法，回退到开学那周的周一
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    # 计算今天距离开学周周一的天数
    days_diff = (date.today() - start_monday).days
    return (days_diff // 7) + 1

def is_this_week(week_str, current_week):
    """核心逻辑：判断当前周是否有课"""
    # 处理 "1-18单周"
    if '单周' in week_str:
        if current_week % 2 == 0: return False
        week_str = week_str.replace('单周', '')
    # 处理 "1-18双周"
    elif '双周' in week_str:
        if current_week % 2 != 0: return False
        week_str = week_str.replace('双周', '')
    
    # 清理中文字符
    clean_str = week_str.replace('周', '')
    
    # 处理范围型 "1-18"
    if '-' in clean_str:
        try:
            start, end = map(int, clean_str.split('-'))
            return start <= current_week <= end
        except: return True
    
    # 处理列表型 "2,4,6,8"
    if ',' in clean_str:
        try:
            weeks = [int(w.strip()) for w in clean_str.split(',')]
            return current_week in weeks
        except: return True
    
    return True

# ================== 3. 核心运行逻辑 ==================

def main():
    # 读取课程表文件
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"错误：读取配置文件失败 - {e}")
        return

    # 获取当前时间和周数
    curr_week = get_current_week(data["semester_info"]["start_date"])
    weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    today_weekday = weekday_map[date.today().isoweekday() - 1]
    
    # 筛选今日课程
    today_courses = []
    for c in data["courses"]:
        if c["day"] == today_weekday and is_this_week(c["weeks"], curr_week):
            today_courses.append(c)
    
    # 按时间排序
    today_courses.sort(key=lambda x: x.get("time", "00:00"))

    # 获取天气（如果 API 出错则降级）
    weather_info = "N/A"
    temp_now = "--"
    if WEATHER_API_KEY:
        try:
            w_url = f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}"
            w_res = requests.get(w_url, timeout=10).json()
            if w_res.get("error_code") == 0:
                real = w_res["result"]["realtime"]
                temp_now = real['temperature']
                weather_info = f"{real['info']} · {CITY_NAME}"
        except: pass

    # ================== 4. 构建 HTML 模板 ==================
    colors = ["#4834d4", "#ff4757", "#2e86de", "#ffa502", "#2ed573"]
    course_items_html = ""
    
    for i, c in enumerate(today_courses):
        color = colors[i % len(colors)]
        course_items_html += f"""
        <div style="border-left:4px solid {color}; padding:12px; margin-bottom:12px; background:#f9f9f9; border-radius:0 10px 10px 0;">
            <div style="font-weight:bold; font-size:15px; color:#2d3436;">{c.get('name')} 
                <span style="float:right; color:{color}; font-size:12px;">{c.get('session')}</span>
            </div>
            <div style="font-size:13px; color:#636e72; margin-top:5px;">
                🕒 {c.get('time','').split('-')[0]} | 📍 {c.get('location')} | 👨‍🏫 {c.get('teacher')}
            </div>
        </div>"""

    if not today_courses:
        course_items_html = '<p style="text-align:center; color:#999; padding:30px;">🎉 今天没有课程，享受生活吧！</p>'

    full_html = f"""
    <div style="max-width:400px; margin:0 auto; background:#fff; border-radius:24px; overflow:hidden; font-family:sans-serif; border:1px solid #eee; color:#2d3436;">
        <div style="background:linear-gradient(135deg, #4834d4, #686de0); padding:20px; color:#fff; position:relative;">
            <div style="font-size:12px; opacity:0.8;">第 {curr_week} 周 · {today_weekday}</div>
            <h2 style="margin:5px 0 0 0; font-size:20px;">今日课表 ({len(today_courses)})</h2>
            <div style="position:absolute; right:20px; bottom:15px; text-align:right;">
                <b style="font-size:22px;">{temp_now}°C</b><br>
                <small style="opacity:0.9;">{weather_info}</small>
            </div>
        </div>
        <div style="padding:15px;">{course_items_html}</div>
        <div style="text-align:center; padding-bottom:15px; font-size:11px; color:#ccc;">✨ 祝你学习愉快</div>
    </div>
    """

    # ================== 5. 执行推送 ==================
    if PUSHPLUS_TOKEN:
        post_data = {
            "token": PUSHPLUS_TOKEN,
            "title": f"📅 {today_weekday}课表 (第{curr_week}周)",
            "content": full_html,
            "template": "html"
        }
        try:
            res = requests.post("http://www.pushplus.plus/send", json=post_data, timeout=15)
            print(f"推送响应: {res.json()}")
        except Exception as e:
            print(f"推送网络错误: {e}")
    else:
        print("未配置 PUSHPLUS_TOKEN，跳过推送。")

if __name__ == "__main__":
    main()
