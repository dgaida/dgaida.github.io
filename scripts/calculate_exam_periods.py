"""
This script calculates and extrapolates exam periods for TH Köln.
It scrapes lecture times and interdisciplinary project weeks (HIP) from the TH Köln website,
calculates exam blocks based on certain rules (e.g., 2 blocks in winter, 1 in summer),
and extrapolates these periods into the future (up to 4 years).
The results are saved as Markdown, ICS, and PDF files.
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional, Any, Set
import holidays
from dateutil import easter
from icalendar import Calendar, Event as ICalEvent
import os
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

# URL configuration
VORLESUNGSZEITEN_URL = "https://www.th-koeln.de/studium/vorlesungszeiten_357.php"
HIP_URL = "https://www.th-koeln.de/studium/interdisziplinaere-projektwoche_48320.php"

# School holidays NRW
SCHOOL_HOLIDAYS = {
    2024: {
        "Ostern": (date(2024, 3, 25), date(2024, 4, 6)),
        "Sommer": (date(2024, 7, 8), date(2024, 8, 20)),
        "Herbst": (date(2024, 10, 14), date(2024, 10, 26)),
    },
    2025: {
        "Ostern": (date(2025, 4, 14), date(2025, 4, 26)),
        "Sommer": (date(2025, 7, 14), date(2025, 8, 26)),
        "Herbst": (date(2025, 10, 13), date(2025, 10, 25)),
    },
    2026: {
        "Ostern": (date(2026, 3, 30), date(2026, 4, 11)),
        "Sommer": (date(2026, 7, 20), date(2026, 9, 1)),
        "Herbst": (date(2026, 10, 17), date(2026, 10, 31)),
    },
    2027: {
        "Ostern": (date(2027, 3, 22), date(2027, 4, 3)),
        "Sommer": (date(2027, 7, 19), date(2027, 8, 31)),
        "Herbst": (date(2027, 10, 23), date(2027, 11, 6)),
    },
    2028: {
        "Ostern": (date(2028, 4, 10), date(2028, 4, 22)),
        "Sommer": (date(2028, 7, 10), date(2028, 8, 22)),
        "Herbst": (date(2028, 10, 23), date(2028, 11, 4)),
    },
    2029: {
        "Ostern": (date(2029, 3, 26), date(2029, 4, 7)),
        "Sommer": (date(2029, 7, 2), date(2029, 8, 14)),
        "Herbst": (date(2029, 10, 15), date(2029, 10, 27)),
    },
    2030: {
        "Ostern": (date(2030, 4, 15), date(2030, 4, 27)),
        "Sommer": (date(2030, 6, 24), date(2030, 8, 6)),
        "Herbst": (date(2030, 10, 14), date(2030, 10, 26)),
    }
}

def parse_date(date_str: str, default_year: Optional[int] = None) -> Optional[date]:
    """Parses a date string into a date object.

    Args:
        date_str: The date string to parse (e.g., 'dd.mm.yyyy' or 'dd.mm.').
        default_year: The year to use if the date string doesn't contain one.

    Returns:
        The parsed date object, or None if parsing fails.
    """
    date_str = date_str.replace(' ', '').replace('\xa0', '')
    # Handle both - and –
    date_str = date_str.replace('–', '-')

    # Try full date
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
    if match:
        return datetime.strptime(match.group(0), '%d.%m.%Y').date()

    # Try date without year
    match = re.search(r'(\d{2})\.(\d{2})', date_str)
    if match and default_year:
        day = int(match.group(1))
        month = int(match.group(2))
        return datetime(default_year, month, day).date()

    return None

def get_nrw_holidays(year: int) -> holidays.HolidayBase:
    """Gets public holidays for North Rhine-Westphalia (NRW) for a given year.

    Args:
        year: The year for which to retrieve holidays.

    Returns:
        A holiday object containing NRW holidays and Rosenmontag.
    """
    nh = holidays.Germany(state='NW', years=[year, year+1])
    # Rosenmontag is 48 days before Easter Sunday
    for y in [year, year+1]:
        easter_date = easter.easter(y)
        rosenmontag = easter_date - timedelta(days=48)
        nh.update({rosenmontag: "Rosenmontag"})
        # Add 24.12. and 31.12. if they fall on a weekday
        for d in [date(y, 12, 24), date(y, 12, 31)]:
            if d.weekday() < 5:
                nh.update({d: "Heiligabend" if d.day == 24 else "Silvester"})
    return nh

def get_weiberfastnacht(year: int) -> date:
    """Calculates the date of Weiberfastnacht for a given year.

    Args:
        year: The year for which to calculate.

    Returns:
        The date of Weiberfastnacht.
    """
    easter_date = easter.easter(year)
    return easter_date - timedelta(days=52)

def get_working_days_in_week(monday: date) -> List[date]:
    """Gets a list of working days (Mon-Fri) for the week starting on the given Monday.

    Args:
        monday: The Monday of the week.

    Returns:
        A list of five date objects (Monday to Friday).
    """
    return [monday + timedelta(days=i) for i in range(5)]

def is_easter_week(monday: date) -> bool:
    """Checks if the week starting on the given Monday is the Easter week (containing Easter Monday).

    Args:
        monday: The Monday of the week to check.

    Returns:
        True if it is Easter week, False otherwise.
    """
    # Week in which Easter Monday lies
    easter_monday = easter.easter(monday.year) + timedelta(days=1)
    em_monday = easter_monday - timedelta(days=easter_monday.weekday())
    return monday == em_monday

def get_ws_holiday_weeks(p1_mon: date, p3_mon: date) -> int:
    """Counts the number of holiday weeks (Christmas/New Year) between two dates in a winter semester.

    Args:
        p1_mon: The start date (typically the first exam block).
        p3_mon: The end date (typically the last exam block).

    Returns:
        The number of holiday weeks found.
    """
    holiday_weeks = 0
    current = p1_mon
    while current <= p3_mon:
        week_days = [current + timedelta(days=i) for i in range(5)]
        is_christmas_holiday = any(d.month == 12 and d.day in [24, 25, 26] for d in week_days)
        is_new_year_holiday = any(d.month == 1 and d.day == 1 for d in week_days)
        if is_christmas_holiday or is_new_year_holiday:
            holiday_weeks += 1
        current += timedelta(days=7)
    return holiday_weeks

def get_exam_days(monday: date, nh: holidays.HolidayBase, used_days: Optional[Set[date]] = None) -> Tuple[List[date], List[Tuple[date, str]]]:
    """Determines the actual exam days for a given week, accounting for holidays and overlaps.

    Args:
        monday: The Monday of the week.
        nh: Public holidays object.
        used_days: Set of days already allocated to other exam blocks.

    Returns:
        A tuple containing:
            - A list of actual exam dates.
            - A list of holiday tuples (date, holiday name).
    """
    if used_days is None:
        used_days = set()
    target_days = get_working_days_in_week(monday)
    actual_exam_days = []
    found_holidays = []

    for d in target_days:
        if d in nh:
            found_holidays.append((d, nh[d]))
        elif d in used_days:
            pass # Day already taken by another week
        else:
            actual_exam_days.append(d)

    # Add days from previous week if holidays or overlaps found
    needed = 5 - len(actual_exam_days)
    if needed > 0:
        # Search backwards starting from the day before Monday
        current = monday - timedelta(days=1)
        while needed > 0:
            if current.weekday() < 5:
                if current in nh:
                    found_holidays.append((current, nh[current]))
                elif current in used_days:
                    pass
                else:
                    actual_exam_days.append(current)
                    needed -= 1
            current -= timedelta(days=1)

    actual_exam_days.sort()
    return actual_exam_days, found_holidays

def find_best_hip(l_start: date, l_end: date, is_winter: bool, num_exams: int, nh: holidays.HolidayBase) -> Optional[date]:
    """Finds the best HIP week candidate by scoring different buffer configurations.

    Args:
        l_start: Start of lecture period.
        l_end: End of lecture period.
        is_winter: Whether it's a winter semester.
        num_exams: Number of exam weeks in the first block.
        nh: Public holidays object.

    Returns:
        The Monday of the best HIP week candidate.
    """
    best_hip = None
    best_score = 9999

    p1_mon = l_start - timedelta(days=l_start.weekday())
    p3_mon = l_end - timedelta(days=l_end.weekday())

    # We try different buffers between the first exam block and the HIP week.
    for buffer in range(6, 11):
        hip_mon_cand = l_start + timedelta(weeks=num_exams + buffer)

        p1_opt = [p1_mon + timedelta(weeks=i) for i in range(num_exams)]
        candidate = p1_opt + [hip_mon_cand, p3_mon]

        stats = calculate_stats(candidate, is_winter, l_start, l_end, nh)

        score = 0
        # Heavily penalize any deviation from exactly 7 lecture weeks
        if stats['w_before'] != 7: score += abs(7 - stats['w_before']) * 100
        if stats['w_after'] != 7: score += abs(7 - stats['w_after']) * 100
        score += abs(stats['w_before'] - stats['w_after'])

        if score < best_score:
            best_score = score
            best_hip = hip_mon_cand

    return best_hip

def scrape_data() -> Tuple[Dict[str, Tuple[date, date]], Dict[str, Tuple[date, date]]]:
    """Scrapes lecture times and HIP weeks from the TH Köln website.

    Returns:
        A tuple containing:
            - A dictionary of lecture periods {semester_name: (start_date, end_date)}.
            - A dictionary of HIP periods {semester_name: (start_date, end_date)}.
    """
    # Scrape lecture times
    resp = requests.get(VORLESUNGSZEITEN_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    lecture_periods = {}
    table = soup.find('caption', string=re.compile('Allgemeine Vorlesungszeiten')).find_parent('table')
    rows = table.find_all('tr')

    current_sem = None
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if not cells: continue

        text = cells[0].get_text(strip=True)
        if 'semester' in text.lower():
            current_sem = text
        elif current_sem and len(cells) >= 2:
            # This row should contain dates
            dates_text = cells[1].get_text(strip=True)
            if '–' in dates_text or '-' in dates_text:
                parts = re.split(r'[–-]', dates_text)
                if len(parts) >= 2:
                    start = parse_date(parts[0])
                    end = parse_date(parts[1])
                    if start and end:
                        lecture_periods[current_sem] = (start, end)
            current_sem = None

    # Scrape HIP weeks
    resp = requests.get(HIP_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    hip_periods = {}
    # Add hardcoded fallback for known fixed semester if not on website
    hip_periods["Wintersemester 2025/26"] = (date(2025, 11, 17), date(2025, 11, 21))

    # Find all text and look for semester patterns
    page_text = soup.get_text(separator='\n')
    for line in page_text.split('\n'):
        if 'semester' in line.lower():
            match = re.search(r'(Wintersemester \d{4}/\d{2}|Sommersemester \d{4}):?\s*([\d\.\s–-]|bis)+', line)
            if match:
                sem = match.group(1).strip()
                dates = match.group(0).split(sem)[-1].strip(': ')

                # Find year in dates
                year_match = re.search(r'\d{4}', dates)
                year = int(year_match.group()) if year_match else None

                # Handle various separators
                parts = re.split(r'[–-]|bis', dates)
                if len(parts) >= 2:
                    end = parse_date(parts[1].strip(), default_year=year)
                    start = parse_date(parts[0].strip(), default_year=end.year if end else year)

                    if start and end:
                        hip_periods[sem] = (start, end)

    return lecture_periods, hip_periods

def sem_key(sem_name: str) -> Tuple[int, bool]:
    """Generates a sortable key for semester names.

    Args:
        sem_name: The semester name (e.g., 'Wintersemester 2023/24').

    Returns:
        A tuple (year, is_winter) for sorting.
    """
    year_match = re.search(r'\d{4}', sem_name)
    year = int(year_match.group()) if year_match else 0
    is_winter = 'Winter' in sem_name
    return (year, is_winter)

def extrapolate_periods(lecture_periods: Dict[str, Tuple[date, date]], hip_periods: Dict[str, Tuple[date, date]], proposal_boundary: Tuple[int, bool], num_years: int = 4) -> None:
    """Extrapolates lecture and HIP periods into the future.

    Args:
        lecture_periods: Dictionary of known lecture periods (updated in-place).
        hip_periods: Dictionary of known HIP periods (updated in-place).
        proposal_boundary: The last (year, is_winter) semester that was actually scraped.
        num_years: How many years to extrapolate.
    """
    # Ensure all semesters in lecture_periods have HIP periods
    for sem_name in lecture_periods:
        if sem_name not in hip_periods:
            l_start, l_end = lecture_periods[sem_name]
            is_winter = 'Winter' in sem_name
            num_exams = 2 if is_winter else 1
            nh = get_nrw_holidays(l_start.year)

            # For semesters before boundary, follow the "exactly 7 weeks" rule (week 9 for SS, 10 for WS)
            if sem_key(sem_name) <= proposal_boundary:
                hip_mon = l_start + timedelta(weeks=num_exams + 7)
            else:
                # Optimize for proposals
                hip_mon = find_best_hip(l_start, l_end, is_winter, num_exams, nh)

            hip_periods[sem_name] = (hip_mon, hip_mon + timedelta(days=4))

    all_sems = sorted(lecture_periods.keys(), key=sem_key)
    if not all_sems:
        last_year = datetime.now().year
        is_winter = False
    else:
        last_sem = all_sems[-1]
        last_year, is_winter = sem_key(last_sem)

    target_year = datetime.now().year + num_years
    curr_year = last_year
    curr_winter = is_winter

    while curr_year <= target_year:
        if curr_winter:
            curr_year += 1
            sem_name = f"Sommersemester {curr_year}"
            curr_winter = False
        else:
            sem_name = f"Wintersemester {curr_year}/{str(curr_year+1)[2:]}"
            curr_winter = True

        if sem_name not in lecture_periods:
            if not curr_winter: # SS
                # SS starts Monday of CW 12
                start = date(curr_year, 3, 10)
                while start.isocalendar()[1] < 12 or start.weekday() != 0:
                    start += timedelta(days=1)
                end = start + timedelta(weeks=17, days=4)
                lecture_periods[sem_name] = (start, end)
            else: # WS
                # WS starts Monday of CW 39
                start = date(curr_year, 9, 20)
                while start.isocalendar()[1] < 39 or start.weekday() != 0:
                    start += timedelta(days=1)
                end = start + timedelta(weeks=19, days=4)
                lecture_periods[sem_name] = (start, end)

        if sem_name not in hip_periods:
            l_start, l_end = lecture_periods[sem_name]
            num_exams = 2 if curr_winter else 1
            nh = get_nrw_holidays(l_start.year)

            if sem_key(sem_name) <= proposal_boundary:
                hip_mon = l_start + timedelta(weeks=num_exams + 7)
            else:
                hip_mon = find_best_hip(l_start, l_end, curr_winter, num_exams, nh)

            hip_periods[sem_name] = (hip_mon, hip_mon + timedelta(days=4))

def calculate_stats(p_list: List[date], is_winter: bool, l_start: date, l_end: date, nh: holidays.HolidayBase) -> Dict[str, int]:
    """Calculates statistics for a given semester schedule.

    Args:
        p_list: List of Mondays of exam/HIP weeks.
        is_winter: Whether it's a winter semester.
        l_start: Start of lecture period.
        l_end: End of lecture period.
        nh: Public holidays object.

    Returns:
        A dictionary containing 'lecture_weeks', 'w_before', and 'w_after'.
    """
    # Determine all actual exam days for this candidate
    # Process in reverse order to correctly account for shifts/overlaps
    p_days_map = {}
    used_days = set()
    for mon in reversed(p_list):
        days, _ = get_exam_days(mon, nh, used_days)
        p_days_map[mon] = days
        used_days.update(days)
    all_exam_days = used_days

    def is_full_lecture_week(monday: date) -> bool:
        """Checks if a week is a full lecture week.

        Args:
            monday: The Monday of the week to check.

        Returns:
            True if it's a full lecture week, False otherwise.
        """
        week_days = [monday + timedelta(days=i) for i in range(5)]
        # No exam days in the week
        if any(d in all_exam_days for d in week_days): return False
        # Not a holiday week (Christmas/New Year)
        is_christmas = any(d.month == 12 and d.day in [24, 25, 26] for d in week_days)
        is_new_year = any(d.month == 1 and d.day == 1 for d in week_days)
        if is_christmas or is_new_year: return False
        # Overlaps with lecture period
        if not any(l_start <= d <= l_end for d in week_days): return False
        return True

    # Total lecture weeks in semester
    lecture_w = 0
    curr = l_start - timedelta(days=l_start.weekday())
    while curr <= l_end:
        if is_full_lecture_week(curr):
            lecture_w += 1
        curr += timedelta(days=7)

    # Buffers
    # P1 (end) and P2 (HIP)
    p1_end_mon = p_list[1] if is_winter else p_list[0]
    p1_max_day = max(p_days_map[p1_end_mon])
    p2_mon = p_list[-2] # HIP
    p2_min_day = min(p_days_map[p2_mon])

    w_before = 0
    curr = p1_max_day + timedelta(days=1)
    if curr.weekday() != 0:
        curr += timedelta(days=(7-curr.weekday()))
    while curr < (p2_min_day - timedelta(days=p2_min_day.weekday())):
        if is_full_lecture_week(curr):
            w_before += 1
        curr += timedelta(days=7)

    # P2 (HIP) and P3
    p3_mon = p_list[-1]
    p3_min_day = min(p_days_map[p3_mon])

    w_after = 0
    curr = p2_min_day + timedelta(days=1)
    if curr.weekday() != 0:
        curr += timedelta(days=(7-curr.weekday()))
    while curr < (p3_min_day - timedelta(days=p3_min_day.weekday())):
        if is_full_lecture_week(curr):
            w_after += 1
        curr += timedelta(days=7)

    return {
        'lecture_weeks': lecture_w,
        'w_before': w_before,
        'w_after': w_after
    }

def get_violations(stats: Dict[str, int], p_list: List[date], is_winter: bool) -> List[str]:
    """Identifies rule violations in a given schedule.

    Args:
        stats: Statistics calculated by `calculate_stats`.
        p_list: List of Mondays of exam/HIP weeks.
        is_winter: Whether it's a winter semester.

    Returns:
        A list of strings describing any violations.
    """
    v = []
    if stats['lecture_weeks'] < 13: v.append(f"Vorlesungswochen < 13 ({stats['lecture_weeks']})")
    if stats['w_before'] < 7: v.append(f"Wochen vor HIP < 7 ({stats['w_before']})")
    if stats['w_after'] < 7: v.append(f"Wochen nach HIP < 7 ({stats['w_after']})")
    if any(is_easter_week(m) for m in p_list): v.append("Prüfung in Osterwoche")
    return v

def generate_pdf(all_semester_results: Dict[str, Any], proposal_boundary: Tuple[int, bool]) -> None:
    """Generates a visual PDF timeline for the calculated exam periods.

    Args:
        all_semester_results: Dictionary containing all calculation results per semester.
        proposal_boundary: The boundary after which results are considered proposals.
    """
    os.makedirs('files', exist_ok=True)
    c = canvas.Canvas("files/exam_periods.pdf", pagesize=landscape(A4))
    width, height = landscape(A4)

    for sem_name, data in all_semester_results.items():
        title = f"Semesterplan: {sem_name}"
        if sem_key(sem_name) > proposal_boundary:
            title += " (VORSCHLAG)"

        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, title)

        # Lecture period
        l_start = data['l_start']
        l_end = data['l_end']
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 70, f"Vorlesungszeit: {l_start.strftime('%d.%m.%Y')} - {l_end.strftime('%d.%m.%Y')}")

        # Legend
        c.setFont("Helvetica", 10)
        leg_x = 50
        leg_y = height - 95

        colors_map = {
            "Prüfung": colors.orange,
            "Vorlesung": colors.red,
            "HIP-Woche": colors.yellow,
            "Feiertag": colors.green
        }

        for label, color in colors_map.items():
            c.setFillColor(color)
            c.rect(leg_x, leg_y, 15, 10, fill=1)
            c.setFillColor(colors.black)
            c.drawString(leg_x + 20, leg_y + 2, label)
            leg_x += 100

        # Table
        p_list = data['p_list']
        l_start = data['l_start']
        l_end = data['l_end']
        hip_start = data['hip_start']
        nh = data['nh']
        all_exam_days = data['all_exam_days']

        # Calculate start of visual period
        v_start = min(l_start, min(all_exam_days))
        v_start = v_start - timedelta(days=v_start.weekday())
        v_end = max(l_end, p_list[-1])
        v_end = v_end + timedelta(days=(6 - v_end.weekday()))

        num_weeks = (v_end - v_start).days // 7 + 1
        cell_width = (width - 100) / num_weeks
        cell_height = 40
        y_pos = height - 150

        for i in range(num_weeks):
            mon = v_start + timedelta(weeks=i)
            x_pos = 50 + i * cell_width

            # Determine color
            week_days = [mon + timedelta(days=d) for d in range(5)]
            is_exam = any(d in all_exam_days for d in week_days)
            is_hip = (mon <= hip_start <= mon + timedelta(days=6))

            main_color = colors.red # Default lecture
            if is_exam: main_color = colors.orange
            if is_hip: main_color = colors.yellow

            # Draw main cell
            c.setFillColor(main_color)
            c.rect(x_pos, y_pos, cell_width, cell_height, fill=1)

            # Draw holidays
            hols_in_week = [d for d in week_days if d in nh]
            for idx, hol in enumerate(hols_in_week):
                # 1/5th width per holiday
                c.setFillColor(colors.green)
                c.rect(x_pos + (cell_width/5) * week_days.index(hol), y_pos, cell_width/5, cell_height, fill=1)

            # Borders and labels
            c.setStrokeColor(colors.black)
            c.rect(x_pos, y_pos, cell_width, cell_height, fill=0)
            c.setFillColor(colors.black)
            c.setFont("Helvetica", 8)
            c.drawCentredString(x_pos + cell_width/2, y_pos - 15, f"W{i+1}")
            c.drawCentredString(x_pos + cell_width/2, y_pos + cell_height + 5, mon.strftime("%d.%m."))

        # Stats and Table
        stats = data['stats']
        c.setFont("Helvetica", 10)
        y_pos -= 60
        c.drawString(50, y_pos, f"Anzahl Vorlesungswochen: {stats['lecture_weeks']}")
        c.drawString(50, y_pos - 15, f"Vorlesungswochen vor HIP: {stats['w_before']}")
        c.drawString(50, y_pos - 30, f"Vorlesungswochen nach HIP: {stats['w_after']}")

        y_pos -= 60
        table_data = [["P-Woche", "Zeitraum", "Feiertage", "Anmerkungen"]]
        for r in data['rows']:
            period = f"{r['start_wd']} {r['start_date'].strftime('%d.%m.%Y')} - {r['end_wd']} {r['end_date'].strftime('%d.%m.%Y')}"
            table_data.append([str(r['num']), period, r['holidays'], r['notes']])

        t = Table(table_data, colWidths=[60, 220, 150, 300])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        w_t, h_t = t.wrapOn(c, width, height)
        t.drawOn(c, 50, y_pos - h_t)
        y_pos -= h_t + 20

        # NRW School Holidays
        is_ws = 'Winter' in sem_name
        current_year = l_start.year
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y_pos, "Ferientermine NRW:")
        c.setFont("Helvetica", 10)
        y_pos -= 15

        if is_ws:
            hol_types = ["Herbst"]
        else:
            hol_types = ["Ostern", "Sommer"]

        for ht in hol_types:
            if current_year in SCHOOL_HOLIDAYS and ht in SCHOOL_HOLIDAYS[current_year]:
                s, e = SCHOOL_HOLIDAYS[current_year][ht]
                c.drawString(70, y_pos, f"{ht}: {s.strftime('%d.%m.%Y')} - {e.strftime('%d.%m.%Y')}")
                y_pos -= 15

        # Public Holidays during the week
        y_pos -= 5
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, y_pos, "Feiertage (unter der Woche):")
        c.setFont("Helvetica", 10)
        y_pos -= 15

        relevant_hols = []
        curr = v_start
        while curr <= v_end:
            if curr.weekday() < 5 and curr in nh:
                relevant_hols.append((curr, nh[curr]))
            curr += timedelta(days=1)

        # Sort and unique
        relevant_hols = sorted(list(set(relevant_hols)))
        for h_date, h_name in relevant_hols:
            c.drawString(70, y_pos, f"{h_date.strftime('%d.%m.%Y')} ({h_name})")
            y_pos -= 15

        c.showPage()
    c.save()

def main() -> None:
    """Main execution function for calculating and generating exam period files.
    """
    try:
        lecture_periods, hip_periods = scrape_data()
    except Exception as e:
        print(f"Error scraping data: {e}")
        sys.exit(1)

    # Determine boundary from what was ACTUALLY scraped
    if hip_periods:
        last_scraped_sem = max(hip_periods.keys(), key=sem_key)
        proposal_boundary = sem_key(last_scraped_sem)
    else:
        proposal_boundary = (0, False)

    extrapolate_periods(lecture_periods, hip_periods, proposal_boundary, num_years=4)
    available_sems = sorted(lecture_periods.keys(), key=sem_key)

    output_md = "# Vorschlag Prüfungszeiträume Informatik\n\n"
    cal = Calendar()
    cal.add('prodid', '-//TH Köln Exam Periods//mxm.dk//')
    cal.add('version', '2.0')

    all_semester_results = {}

    for sem in available_sems:
        is_ws = 'Winter' in sem
        l_start, l_end = lecture_periods[sem]
        hip_start, hip_end = hip_periods[sem]

        nh = get_nrw_holidays(l_start.year)
        p1_mon = l_start - timedelta(days=l_start.weekday())
        p2_mon = hip_start - timedelta(days=hip_start.weekday())
        p3_mon = l_end - timedelta(days=l_end.weekday())

        num_start = 2 if is_ws else 1
        p1_options = []
        for s in range(-2, 3):
            opt = [p1_mon + timedelta(weeks=s) + timedelta(weeks=i) for i in range(num_start)]
            p1_options.append(opt)

        p3_options = [p3_mon, p3_mon + timedelta(weeks=1)]

        best_p_mons = None
        best_score = 9999

        for p1_opt in p1_options:
            for p3_opt in p3_options:
                candidate = p1_opt + [p2_mon, p3_opt]
                stats = calculate_stats(candidate, is_ws, l_start, l_end, nh)
                violations = get_violations(stats, candidate, is_ws)

                score = 0
                if any(is_easter_week(m) for m in candidate): score += 1000
                if stats['lecture_weeks'] < 13: score += 500
                # Strictly prefer exactly 7 weeks buffer
                if stats['w_before'] != 7: score += abs(7 - stats['w_before']) * 50
                if stats['w_after'] != 7: score += abs(7 - stats['w_after']) * 50

                # Gap check: First block must end no more than 1 week before lecture start
                if p1_opt[-1] < p1_mon - timedelta(weeks=1):
                    score += 1000

                shift_size = abs((p1_mon - p1_opt[0]).days // 7) + abs((p3_opt - p3_mon).days // 7)
                if score < best_score:
                    best_score = score
                    best_p_mons = candidate
                elif score == best_score:
                    if shift_size < abs((p1_mon - best_p_mons[0]).days // 7) + abs((best_p_mons[-1] - p3_mon).days // 7):
                        best_p_mons = candidate

        p_mons_best = best_p_mons
        stats_best = calculate_stats(p_mons_best, is_ws, l_start, l_end, nh)
        v_best = get_violations(stats_best, p_mons_best, is_ws)

        detailed_rows = []
        WDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

        # Final day calculation (must be in reverse to handle overlaps correctly)
        best_days_map = {}
        used_days = set()
        for mon in reversed(p_mons_best):
            days, hols = get_exam_days(mon, nh, used_days)
            best_days_map[mon] = (days, hols)
            used_days.update(days)

        for i, mon in enumerate(p_mons_best):
            days, hols = best_days_map[mon]
            is_karneval = any((get_weiberfastnacht(d.year) - timedelta(days=get_weiberfastnacht(d.year).weekday())) == (d - timedelta(days=d.weekday())) for d in days)
            hol_str = ", ".join([f"{h[0].strftime('%d.%m.')} ({h[1]})" for h in hols])
            notes = []
            if is_karneval: notes.append("Karnevalswoche")

            # Identify HIP week (it's the second to last in the list of exam weeks)
            if i == len(p_mons_best) - 2:
                hip_note = "HIP-Woche"
                if sem_key(sem) > proposal_boundary:
                    hip_note += " (VORSCHLAG)"
                notes.append(hip_note)

            if i == (num_start - 1) and stats_best['w_before'] < 7: notes.append(f"Warnung: Puffer vor HIP nur {stats_best['w_before']} Wochen")
            if i == len(p_mons_best) - 1 and stats_best['w_after'] < 7: notes.append(f"Warnung: Puffer nach HIP nur {stats_best['w_after']} Wochen")

            s_wd, e_wd = WDAYS[min(days).weekday()], WDAYS[max(days).weekday()]
            detailed_rows.append({
                'num': i+1,
                'start_wd': s_wd,
                'start_date': min(days),
                'end_wd': e_wd,
                'end_date': max(days),
                'holidays': hol_str,
                'notes': "; ".join(notes)
            })

        all_semester_results[sem] = {
            'p_list': p_mons_best,
            'l_start': l_start,
            'l_end': l_end,
            'hip_start': hip_start,
            'nh': nh,
            'stats': stats_best,
            'violations': v_best,
            'rows': detailed_rows,
            'all_exam_days': used_days
        }

        sem_title = sem
        if sem_key(sem) > proposal_boundary:
            sem_title += " (VORSCHLAG)"

        output_md += f"## {sem_title}\n\n"
        output_md += f"Vorlesungszeit: {l_start.strftime('%d.%m.%Y')} - {l_end.strftime('%d.%m.%Y')}\n\n"
        if v_best:
            output_md += "**VERLETZTE BEDINGUNGEN:**\n"
            for vi in v_best: output_md += f"- {vi}\n"
            output_md += "\n"

        output_md += f"Anzahl Vorlesungswochen: {stats_best['lecture_weeks']}\n"
        output_md += f"Vorlesungswochen vor HIP: {stats_best['w_before']}\n"
        output_md += f"Vorlesungswochen nach HIP: {stats_best['w_after']}\n\n"
        output_md += "| Prüfungswoche | Zeitraum | Feiertage | Anmerkungen |\n| --- | --- | --- | --- |\n"

        for r in detailed_rows:
            output_md += f"| {r['num']} | {r['start_wd']} {r['start_date'].strftime('%d.%m.%Y')} - {r['end_wd']} {r['end_date'].strftime('%d.%m.%Y')} | {r['holidays']} | {r['notes']} |\n"
            event = ICalEvent()
            event.add('summary', f"Prüfungswoche {r['num']} {sem}")
            event.add('dtstart', r['start_date'])
            event.add('dtend', r['end_date'] + timedelta(days=1))
            cal.add_component(event)
        output_md += "\n"

    with open('files/exam_periods.md', 'w', encoding='utf-8') as f: f.write(output_md)
    with open('files/exam_periods.ics', 'wb') as f: f.write(cal.to_ical())
    generate_pdf(all_semester_results, proposal_boundary)
    print("Files generated: files/exam_periods.md, files/exam_periods.ics, files/exam_periods.pdf")

if __name__ == "__main__":
    main()
