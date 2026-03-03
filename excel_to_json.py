import pandas as pd
import json
import sys
import re
from pathlib import Path


def parse_cell_value(value):
    if pd.isna(value) or value is None:
        return None
    value = str(value).strip()
    if value == '' or value == 'NaN':
        return None
    return value


def extract_courses_from_cell(cell_value):
    if not cell_value:
        return []
    
    cell_str = str(cell_value).strip()
    if not cell_str or cell_str == 'NaN':
        return []
    
    courses = []
    
    lines = [line.strip() for line in cell_str.replace('\r', '\n').split('\n') if line.strip()]
    
    i = 0
    while i < len(lines):
        if len(lines) - i < 5:
            break
        
        course = {
            'name': None,
            'teacher': None,
            'week': None,
            'classroom': None,
            'section': None
        }
        
        course['name'] = lines[i]
        
        teacher_line = lines[i + 1]
        if '(' in teacher_line or '）' in teacher_line:
            if len(lines) > i + 2 and len(lines[i + 2]) <= 4:
                course['teacher'] = lines[i + 2]
                course['week'] = lines[i + 3]
                course['classroom'] = lines[i + 4]
                course['section'] = lines[i + 5] if len(lines) > i + 5 else None
                i += 6
            else:
                course['teacher'] = teacher_line
                course['week'] = lines[i + 2]
                course['classroom'] = lines[i + 3]
                course['section'] = lines[i + 4]
                i += 5
        else:
            course['teacher'] = teacher_line
            course['week'] = lines[i + 2]
            course['classroom'] = lines[i + 3]
            course['section'] = lines[i + 4]
            i += 5
        
        if course['name'] and course['teacher']:
            courses.append(course)
    
    return courses


def parse_time_section(section_str):
    if not section_str:
        return None
    
    section_str = str(section_str).strip()
    
    section_map = {
        '[01-02]节': '08:00-09:50',
        '[03-04]节': '10:10-12:00',
        '[05-06]节': '14:30-16:20',
        '[07-08]节': '16:40-18:30',
        '[09-10]节': '19:30-21:20'
    }
    
    for key, value in section_map.items():
        if key in section_str:
            return value
    
    return None


def format_section(section_str):
    if not section_str:
        return None
    
    section_str = str(section_str).strip()
    
    section_str = section_str.replace('[', '').replace(']', '')
    
    section_str = re.sub(r'0*(\d+)-0*(\d+)', r'\1-\2', section_str)
    
    return section_str


def format_weeks(week_str):
    if not week_str:
        return None
    
    week_str = str(week_str).strip()
    
    week_str = week_str.replace('[周]', '')
    week_str = week_str.replace('单周', '单周')
    week_str = week_str.replace('双周', '双周')
    
    if not week_str.endswith('周'):
        week_str += '周'
    
    return week_str


def clean_teacher_name(teacher_str):
    if not teacher_str:
        return None
    
    teacher_str = str(teacher_str).strip()
    
    teacher_str = re.sub(r'\s*\([^)]*\)', '', teacher_str)
    teacher_str = re.sub(r'\s*\（[^)]*\）', '', teacher_str)
    
    return teacher_str.strip()


def excel_to_timetable(excel_path, output_path=None):
    excel_path = Path(excel_path)
    
    if not excel_path.exists():
        print(f"错误: 文件不存在 - {excel_path}")
        return None
    
    df = pd.read_excel(excel_path)
    
    headers = df.iloc[0].tolist()
    year_info = parse_cell_value(headers[0])
    
    year_term_match = re.search(r'学年学期：(\d{4})-(\d{4})-(\d)', year_info)
    if year_term_match:
        start_year = year_term_match.group(1)
        end_year = year_term_match.group(2)
        term = year_term_match.group(3)
        
        if term == '1':
            semester_name = f"{start_year}-{end_year}秋季学期"
        elif term == '2':
            semester_name = f"{start_year}-{end_year}春季学期"
        else:
            semester_name = f"{start_year}-{end_year}夏季学期"
        
        if term == '1':
            start_date = f"{start_year}-09-01"
            end_date = f"{start_year}-12-31"
        elif term == '2':
            start_date = f"{end_year}-02-01"
            end_date = f"{end_year}-07-31"
        else:
            start_date = f"{end_year}-07-01"
            end_date = f"{end_year}-08-31"
    else:
        semester_name = "未知学期"
        start_date = ""
        end_date = ""
    
    day_map = {
        '星期一': '周一',
        '星期二': '周二',
        '星期三': '周三',
        '星期四': '周四',
        '星期五': '周五',
        '星期六': '周六',
        '星期日': '周日'
    }
    
    courses_list = []
    
    for col_idx in range(1, min(len(df.columns), 8)):
        day_name_cn = day_names[col_idx - 1]
        day_name_short = day_map.get(day_name_cn, day_name_cn)
        
        for row_idx in range(2, min(len(df), 11)):
            cell_value = df.iloc[row_idx, col_idx]
            courses = extract_courses_from_cell(cell_value)
            
            for course in courses:
                formatted_course = {
                    'name': course['name'],
                    'day': day_name_short,
                    'time': parse_time_section(course['section']),
                    'session': format_section(course['section']),
                    'location': course['classroom'],
                    'teacher': clean_teacher_name(course['teacher']),
                    'weeks': format_weeks(course['week'])
                }
                courses_list.append(formatted_course)
    
    timetable = {
        'semester_info': {
            'name': semester_name,
            'start_date': start_date,
            'end_date': end_date
        },
        'courses': courses_list
    }
    
    return timetable


def merge_timetables(timetables):
    merged = {
        'semester_info': {
            'name': '',
            'start_date': '',
            'end_date': ''
        },
        'courses': []
    }
    
    for timetable in timetables:
        if timetable is None:
            continue
        merged['courses'].extend(timetable['courses'])
    
    if timetables:
        merged['semester_info'] = timetables[0]['semester_info']
    
    return merged


def select_files():
    excel_files = sorted(list(Path('.').glob('*.xls')) + list(Path('.').glob('*.xlsx')))
    
    if not excel_files:
        print("未找到Excel文件")
        return None
    
    print("请选择要转换的Excel文件:")
    print("0. 全部转换")
    for i, file in enumerate(excel_files, 1):
        print(f"{i}. {file.name}")
    
    while True:
        try:
            choice = input("\n请输入序号 (0-{}): ".format(len(excel_files))).strip()
            choice = int(choice)
            if 0 <= choice <= len(excel_files):
                return excel_files if choice == 0 else [excel_files[choice - 1]]
            else:
                print("无效输入，请重新输入")
        except ValueError:
            print("无效输入，请输入数字")


def batch_convert(files):
    if not files:
        print("未选择文件")
        return
    
    print(f"\n共选择 {len(files)} 个文件\n")
    
    timetables = []
    for excel_file in files:
        timetable = excel_to_timetable(excel_file)
        if timetable:
            timetables.append(timetable)
            print(f"成功: {excel_file.name} - 提取 {len(timetable['courses'])} 门课程")
    
    if timetables:
        merged_timetable = merge_timetables(timetables)
        
        output_path = Path('timetable.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_timetable, f, ensure_ascii=False, indent=2)
        
        print(f"\n成功: 合并为 timetable.json")
        print(f"共提取 {len(merged_timetable['courses'])} 门课程")


day_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']


if __name__ == '__main__':
    if len(sys.argv) > 1:
        excel_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        timetable = excel_to_timetable(excel_file, output_file)
        if timetable:
            if output_file is None:
                output_path = Path(excel_file).with_suffix('.json')
                output_path = output_path.parent / 'timetable.json'
            else:
                output_path = Path(output_file)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(timetable, f, ensure_ascii=False, indent=2)
            print(f"成功: {Path(excel_file).name} 已转换为 {output_path.name}")
            print(f"共提取 {len(timetable['courses'])} 门课程")
    else:
        selected_files = select_files()
        batch_convert(selected_files)
