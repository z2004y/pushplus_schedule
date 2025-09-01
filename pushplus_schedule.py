import json
import os
import requests
from datetime import datetime, date

# PushPlus 配置
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "your_pushplus_token_here")  # 从环境变量获取token
PUSHPLUS_URL = "http://www.pushplus.plus/send"

# 聚合数据天气API配置
WEATHER_API_URL = "http://apis.juhe.cn/simpleWeather/query"
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "your_weather_api_key_here")  # 从环境变量获取天气API key
CITY_NAME = "苏州"  # 可以修改为你所在的城市

def get_weather_info() -> dict:
    """
    获取天气信息。
    """
    if not WEATHER_API_KEY or WEATHER_API_KEY == "your_weather_api_key_here":
        return {"error": "天气API Key未配置"}
    
    try:
        params = {
            'key': WEATHER_API_KEY,
            'city': CITY_NAME,
        }
        
        response = requests.get(WEATHER_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('error_code') == 0:
                return {
                    "success": True,
                    "data": result.get('result', {})
                }
            else:
                return {
                    "error": f"天气API错误: {result.get('reason', '未知错误')}"
                }
        else:
            return {"error": f"天气API请求失败，状态码: {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        return {"error": f"天气API网络请求失败: {e}"}
    except Exception as e:
        return {"error": f"获取天气信息时发生错误: {e}"}

def format_weather_html(weather_data: dict) -> str:
    """
    格式化天气信息为HTML。
    """
    if "error" in weather_data:
        return f"<div style='background-color: #ffebee; padding: 10px; border-radius: 5px; margin: 10px 0;'>" \
               f"<p>🌤️ 天气信息获取失败: {weather_data['error']}</p></div>"
    
    if not weather_data.get("success"):
        return "<div style='background-color: #ffebee; padding: 10px; border-radius: 5px; margin: 10px 0;'>" \
               "<p>🌤️ 天气信息暂时无法获取</p></div>"
    
    data = weather_data.get("data", {})
    city = data.get("city", CITY_NAME)
    realtime = data.get("realtime", {})
    future = data.get("future", [])
    
    # 实时天气
    temperature = realtime.get("temperature", "N/A")
    humidity = realtime.get("humidity", "N/A")
    info = realtime.get("info", "未知")
    wid = realtime.get("wid", {})
    wind_direction = wid.get("dir", "无风向") if isinstance(wid, dict) else "无风向"
    wind_power = wid.get("power", "无风力") if isinstance(wid, dict) else "无风力"
    
    # 今日天气预报
    today_forecast = future[0] if future else {}
    today_temp_range = today_forecast.get("temperature", "N/A")
    today_weather = today_forecast.get("weather", "未知")
    
    # 天气图标映射
    weather_icons = {
        "晴": "☀️", "多云": "⛅", "阴": "☁️", "小雨": "🌦️",
        "中雨": "🌧️", "大雨": "⛈️", "雪": "❄️", "雾": "🌫️"
    }
    
    weather_icon = "🌤️"
    for weather_key, icon in weather_icons.items():
        if weather_key in info or weather_key in today_weather:
            weather_icon = icon
            break
    
    weather_html = f"""
    <div style='background: linear-gradient(135deg, #74b9ff, #0984e3); 
                color: white; padding: 15px; border-radius: 10px; margin: 10px 0;'>
        <h3 style='margin: 0 0 10px 0;'>{weather_icon} {city} 天气</h3>
        <div style='display: flex; justify-content: space-between; flex-wrap: wrap;'>
            <div style='flex: 1; min-width: 200px;'>
                <p><strong>🌡️ 当前温度：</strong>{temperature}°C</p>
                <p><strong>🌈 天气状况：</strong>{info}</p>
                <p><strong>💧 湿度：</strong>{humidity}%</p>
            </div>
            <div style='flex: 1; min-width: 200px;'>
                <p><strong>🌬️ 风向：</strong>{wind_direction}</p>
                <p><strong>💨 风力：</strong>{wind_power}</p>
                <p><strong>📊 今日温度：</strong>{today_temp_range}</p>
            </div>
        </div>
    </div>
    """
    
    return weather_html
    
def get_current_week(start_date_str: str) -> int:
    """
    根据学期开始日期计算当前是第几周。
    学期开始当天算作第一周的第一天。
    """
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"错误：学期开始日期 '{start_date_str}' 格式不正确，应为 YYYY-MM-DD。")
        return 0

    today = date.today()

    if today < start_date:
        return 0

    days_since_start = (today - start_date).days
    current_week = (days_since_start // 7) + 1
    return current_week

def get_daily_schedule(json_file_path: str) -> dict:
    """
    读取课程表JSON文件，返回今天的课程信息。
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"error": f"课程表文件 '{json_file_path}' 未找到"}
    except json.JSONDecodeError:
        return {"error": f"文件 '{json_file_path}' 不是有效的JSON格式"}
    except Exception as e:
        return {"error": f"读取课程表文件时发生错误：{e}"}

    semester_info = data.get("semester_info", {})
    courses = data.get("courses", [])

    semester_name = semester_info.get("name", "未知学期")
    start_date_str = semester_info.get("start_date")
    end_date_str = semester_info.get("end_date")

    if not start_date_str:
        return {"error": "JSON文件中 'semester_info' 下的 'start_date' 未定义"}

    try:
        semester_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        semester_end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else None
    except ValueError as e:
        return {"error": f"学期日期格式不正确：{e}"}

    today = date.today()
    current_week = get_current_week(start_date_str)

    # 日期映射
    day_map = {
        1: "周一", 2: "周二", 3: "周三", 4: "周四",
        5: "周五", 6: "周六", 7: "周日"
    }
    today_day_name = day_map.get(today.isoweekday(), "未知")

    # 检查学期状态
    if today < semester_start_date:
        return {
            "semester_name": semester_name,
            "date": today.strftime('%Y-%m-%d'),
            "day": today_day_name,
            "week": current_week,
            "status": "not_started",
            "message": "学期尚未开始"
        }

    if semester_end_date and today > semester_end_date:
        return {
            "semester_name": semester_name,
            "date": today.strftime('%Y-%m-%d'),
            "day": today_day_name,
            "week": current_week,
            "status": "ended",
            "message": "学期已结束"
        }

    # 获取今天的课程
    daily_courses = []
    for course in courses:
        if course.get("day") == today_day_name:
            weeks_str = course.get("weeks", "").replace("(周)", "").replace("周", "").strip()
            if not weeks_str:
                continue

            active_weeks = []
            for part in weeks_str.split(','):
                part = part.strip()
                if '-' in part:
                    try:
                        start_str, end_str = part.split('-')
                        start, end = int(start_str.strip()), int(end_str.strip())
                        active_weeks.extend(range(start, end + 1))
                    except ValueError:
                        pass
                else:
                    try:
                        active_weeks.append(int(part))
                    except ValueError:
                        pass

            if current_week in active_weeks:
                daily_courses.append(course)

    # 按时间排序
    def get_start_time_key(course_item):
        time_str = course_item.get("time", "23:59-23:59")
        try:
            start_time_part = time_str.split('-')[0].strip()
            return datetime.strptime(start_time_part, '%H:%M').time()
        except (ValueError, IndexError):
            return datetime.strptime("23:59", '%H:%M').time()

    daily_courses.sort(key=get_start_time_key)

    return {
        "semester_name": semester_name,
        "date": today.strftime('%Y-%m-%d'),
        "day": today_day_name,
        "week": current_week,
        "status": "active",
        "courses": daily_courses
    }

def format_schedule_message(schedule_data: dict, weather_data: dict = None) -> tuple:
    """
    格式化课程表消息，返回标题和内容。
    """
    if "error" in schedule_data:
        return "课程表推送错误", schedule_data["error"]

    date_str = schedule_data["date"]
    day_str = schedule_data["day"]
    week_num = schedule_data["week"]
    semester_name = schedule_data["semester_name"]
    
    title = f"📚 今日课程"
    
    content += f"<p><strong>📅 日期：</strong>{date_str} {day_str} 第{week_num}周</p>\n\n"
    
    # 添加天气信息
    if weather_data:
        content += format_weather_html(weather_data)
        content += "\n"

    if schedule_data["status"] == "not_started":
        content += "<p>🎯 学期尚未开始，请耐心等待。</p>"
        return title, content

    if schedule_data["status"] == "ended":
        content += "<p>🎉 学期已结束，祝您假期愉快！</p>"
        return title, content

    courses = schedule_data.get("courses", [])
    
    if not courses:
        content += "<p>🎈 今天没有安排课程，可以好好休息！</p>"
    else:
        content += f"<h3>📖 今日共有 {len(courses)} 门课程：</h3>\n"
        
        for i, course in enumerate(courses, 1):
            content += f"<div style='border-left: 4px solid #4CAF50; padding-left: 15px; margin: 10px 0;'>\n"
            content += f"<h4>📝 {course.get('name', '未知课程')}</h4>\n"
            content += f"<p><strong>⏰ 时间：</strong>{course.get('time', '未知时间')} ({course.get('session', '未知节次')})</p>\n"
            content += f"<p><strong>📍 地点：</strong>{course.get('location', '未知地点')}</p>\n"
            content += f"<p><strong>👨‍🏫 老师：</strong>{course.get('teacher', '未知老师')}</p>\n"
            content += f"<p><strong>📊 教学周：</strong>{course.get('weeks', '未知周数')}</p>\n"
            content += "</div>\n\n"

    content += "<hr>\n<p style='color: #666; font-size: 12px;'>💡 此消息由课程表推送系统自动发送</p>"
    
    return title, content

def send_pushplus_message(token: str, title: str, content: str, template: str = "html") -> bool:
    """
    发送PushPlus消息。
    """
    data = {
        "token": token,
        "title": title,
        "topic": "721683736",
        "content": content,
        "template": template
    }
    
    try:
        response = requests.post(PUSHPLUS_URL, json=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 200:
            print(f"✅ 消息推送成功: {title}")
            return True
        else:
            print(f"❌ 消息推送失败: {result.get('msg', '未知错误')}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 推送消息时发生错误: {e}")
        return False

def main():
    """
    主函数：获取课程表和天气信息并推送。
    """
    # 获取脚本所在目录的timetable.json文件
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "timetable.json")
    
    # 检查token是否设置
    if not PUSHPLUS_TOKEN or PUSHPLUS_TOKEN == "your_pushplus_token_here":
        print("❌ 请先设置您的PushPlus token！")
        print("请在GitHub仓库的Settings > Secrets中添加 PUSHPLUS_TOKEN")
        return

    # 获取课程表数据
    print("📚 正在读取课程表...")
    schedule_data = get_daily_schedule(json_path)
    
    # 获取天气数据
    print("🌤️ 正在获取天气信息...")
    weather_data = get_weather_info()
    
    # 格式化消息
    title, content = format_schedule_message(schedule_data, weather_data)
    
    # 发送推送
    print("📨 正在发送推送...")
    success = send_pushplus_message(PUSHPLUS_TOKEN, title, content)
    
    if success:
        print("🎉 课程表和天气推送完成！")
    else:
        print("💔 推送失败，请检查配置和网络连接。")

if __name__ == "__main__":
    main()
