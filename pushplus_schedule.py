import json
import os
import requests
from datetime import date, datetime, timedelta

# ================== 1. 基础配置 ==================
# 建议在 GitHub Secrets 中配置以下变量，或在此处直接填写
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "你的_PUSHPLUS_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "你的_聚合天气_KEY")
CITY_NAME = "兰州"

# 中国节假日数据源 (ShuYZ 维护)
HOLIDAY_API_URL = "https://raw.githubusercontent.com/lanceliao/china-holiday-calender/master/holidayAPI.json"

# ================== 2. 核心逻辑逻辑 ==================

def get_holiday_status():
    """
    解析 ShuYZ 格式的节假日数据
    返回: (is_off_day, holiday_name)
    is_off_day: True 表示放假（显示休息页），False 表示要上课（含补班）
    """
    try:
        res = requests.get(HOLIDAY_API_URL, timeout=15).json()
        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        year_data = res.get("Years", {}).get(str(today.year), [])

        # 1. 检查是否在法定节假日放假范围内 (StartDate 至 EndDate)
        for holiday in year_data:
            start = datetime.strptime(holiday["StartDate"], "%Y-%m-%d").date()
            end = datetime.strptime(holiday["EndDate"], "%Y-%m-%d").date()
            if start <= today <= end:
                return True, holiday["Name"]

        # 2. 检查是否是补班日 (在 CompDays 列表内)
        for holiday in year_data:
            if today_str in holiday.get("CompDays", []):
                return False, f"{holiday['Name']}补班"

        # 3. 默认逻辑：周六日放假，周一至五上课
        is_weekend = today.weekday() >= 5
        return is_weekend, "周末"
    except Exception as e:
        print(f"节假日API获取失败: {e}")
        # 降级处理：仅按普通周末判断
        return (date.today().weekday() >= 5), "普通周末"

def get_current_week(start_date_str):
    """根据学期开始日期计算当前是第几周"""
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    # 修正日期减法：使用 timedelta
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    days_diff = (date.today() - start_monday).days
    return (days_diff // 7) + 1

def is_course_this_week(week_str, current_week):
    """解析 weeks 字符串判断本周是否有课"""
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
    # 读取课程表配置
    try:
        with open("timetable.json", 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"无法读取 timetable.json: {e}")
        return

    # 获取当前时间和周数
    curr_week = get_current_week(config["semester_info"]["start_date"])
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][date.today().isoweekday()-1]
    
    # 检查节假日/补班状态
    is_off_day, holiday_tag = get_holiday_status()

    # 获取天气数据
    temp_now, weather_text = "--", "数据更新中"
    if WEATHER_API_KEY:
        try:
            w_res = requests.get(f"http://apis.juhe.cn/simpleWeather/query?city={CITY_NAME}&key={WEATHER_API_KEY}", timeout=10).json()
            if w_res.get("error_code") == 0:
                real = w_res["result"]["realtime"]
                temp_now, weather_text = real['temperature'], real['info']
        except: pass

    # 设置 UI 颜色库
    colors = ["#4834d4", "#ff4757", "#2e86de", "#ffa502", "#2ed573"]
    
    # 情况 A：放假模式 (法定节日或普通周末)
    if is_off_day:
        title = f"🏮 {holiday_tag}快乐！今日放假"
        main_content = f"""
        <div style="text-align:center; padding:40px 20px;">
            <div style="font-size:55px; margin-bottom:15px;">☕</div>
            <h3 style="color:#2ed573; margin:0; font-size:20px;">{holiday_tag}休息日</h3>
            <p style="color:#999; font-size:14px; margin-top:10px; line-height:1.6;">
                当前处于假期或周末<br>课表推送自动暂停，放松一下吧！
            </p>
        </div>"""
    
    # 情况 B：上课模式 (含补班日)
    else:
        today_courses = [c for c in config["courses"] if c["day"] == weekday_cn and is_course_this_week(c["weeks"], curr_week)]
        today_courses.sort(key=lambda x: x.get("time", "00:00"))
        
        # 补班日标题特殊提醒
        title = f"📚 {weekday_cn}课表 (第{curr_week}周)"
        if "补班" in holiday_tag:
            title = f"🔁 {holiday_tag}课表推送"

        course_items = ""
        for i, c in enumerate(today_courses):
            color = colors[i % len(colors)]
            course_items += f"""
            <div style="border-left:4px solid {color}; padding:12px; margin-bottom:12px; background:#f9f9f9; border-radius:0 12px 12px 0;">
                <div style="font-weight:bold; font-size:15px; color:#2d3436;">
                    {c['name']} <span style="float:right; color:{color}; font-size:12px;">{c['session']}</span>
                </div>
                <div style="font-size:13px; color:#636e72; margin-top:6px;">
                    🕒 {c['time']} | 📍 {c['location']} | 👨‍🏫 {c['teacher']}
                </div>
            </div>"""
        
        if not today_courses:
            course_items = '<p style="text-align:center; color:#999; padding:40px 0;">🎉 今天没课，自由万岁！</p>'
        
        main_content = f'<div style="padding:15px;">{course_items}</div>'

    # 4. 拼装最终 HTML 模板
    full_html = f"""
    <div style="max-width:420px; margin:0 auto; background:#fff; border-radius:28px; overflow:hidden; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif; border:1px solid #eee; box-shadow:0 4px 15px rgba(0,0,0,0.05);">
        <div style="background:linear-gradient(135deg, #4834d4, #686de0); padding:25px; color:#fff; position:relative;">
            <div style="font-size:13px; opacity:0.85; letter-spacing:1px;">第 {curr_week} 周 · {weekday_cn}</div>
            <h2 style="margin:8px 0 0 0; font-size:22px;">{"今日课程" if not is_off_day else "享受假期"}</h2>
            <div style="position:absolute; right:25px; bottom:20px; text-align:right;">
                <b style="font-size:26px;">{temp_now}°C</b><br>
                <small style="opacity:0.9;">{weather_text}</small>
            </div>
        </div>
        {main_content}
        <div style="text-align:center; padding:0 0 20px 0; font-size:11px; color:#bbb; letter-spacing:1px;">
            ✨ 祝你学习愉快 ✨
        </div>
    </div>"""

    # 5. 执行 PUSHPLUS 推送
    if PUSHPLUS_TOKEN and PUSHPLUS_TOKEN != "你的_PUSHPLUS_TOKEN":
        payload = {
            "token": PUSHPLUS_TOKEN,
            "title": title,
            "content": full_html,
            "template": "html"
        }
        try:
            res = requests.post("http://www.pushplus.plus/send", json=payload, timeout=15)
            print(f"推送结果: {res.json().get('msg')}")
        except Exception as e:
            print(f"推送失败: {e}")
    else:
        print("未检测到有效 Token，跳过推送逻辑。")

if __name__ == "__main__":
    main()
