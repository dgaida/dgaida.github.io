import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import holidays
from dateutil import easter
from icalendar import Calendar, Event as ICalEvent
import os
import sys

# URL configuration
VORLESUNGSZEITEN_URL = "https://www.th-koeln.de/studium/vorlesungszeiten_357.php"
HIP_URL = "https://www.th-koeln.de/studium/interdisziplinaere-projektwoche_48320.php"

def parse_date(date_str, default_year=None):
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

def get_nrw_holidays(year):
    nh = holidays.Germany(state='NW', years=[year, year+1])
    # Rosenmontag is 48 days before Easter Sunday
    for y in [year, year+1]:
        easter_date = easter.easter(y)
        rosenmontag = easter_date - timedelta(days=48)
        nh.update({rosenmontag: "Rosenmontag"})
    return nh

def get_weiberfastnacht(year):
    easter_date = easter.easter(year)
    return easter_date - timedelta(days=52)

def get_working_days_in_week(monday):
    return [monday + timedelta(days=i) for i in range(5)]

def is_easter_week(monday):
    # Week in which Easter Monday lies
    easter_monday = easter.easter(monday.year) + timedelta(days=1)
    em_monday = easter_monday - timedelta(days=easter_monday.weekday())
    return monday == em_monday

def get_ws_holiday_weeks(p1_mon, p3_mon):
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

def get_exam_days(monday, nh):
    target_days = get_working_days_in_week(monday)
    holiday_count = 0
    actual_exam_days = []
    found_holidays = []

    for d in target_days:
        if d in nh:
            holiday_count += 1
            found_holidays.append((d, nh[d]))
        else:
            actual_exam_days.append(d)

    # Add days from previous week if holidays found
    if holiday_count > 0:
        # Start from previous Friday
        current = monday - timedelta(days=3) # Friday
        while holiday_count > 0:
            if current.weekday() < 5 and current not in nh:
                actual_exam_days.append(current)
                holiday_count -= 1
            elif current in nh:
                found_holidays.append((current, nh[current]))
            current -= timedelta(days=1)

    actual_exam_days.sort()
    return actual_exam_days, found_holidays

def scrape_data():
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
    hip_box = soup.find('h2', string='Terminvorschau').find_next('p')
    hip_text = hip_box.get_text(separator='\n')

    for line in hip_text.split('\n'):
        if ':' in line:
            sem, dates = line.split(':', 1)
            sem = sem.strip()
            # Find year in dates
            year_match = re.search(r'\d{4}', dates)
            year = int(year_match.group()) if year_match else None

            parts = re.split(r'[–-]', dates)
            if len(parts) >= 2:
                end = parse_date(parts[1], default_year=year)
                # If end has year, start should use it too
                start = parse_date(parts[0], default_year=end.year if end else year)

                if start and end:
                    hip_periods[sem] = (start, end)

    return lecture_periods, hip_periods

def main():
    try:
        lecture_periods, hip_periods = scrape_data()
    except Exception as e:
        print(f"Error scraping data: {e}")
        sys.exit(1)

    # Start from WS 2026/27
    start_sem = "Wintersemester 2026/27"

    # End semester is the last one in HIP
    available_sems = sorted(hip_periods.keys(), key=lambda x: (int(re.search(r'\d{4}', x).group()), 'Winter' in x))
    if not available_sems:
        print("No HIP semesters found.")
        sys.exit(1)

    last_sem = available_sems[-1]

    output_md = "# Vorschlag Prüfungszeiträume Informatik\n\n"
    cal = Calendar()
    cal.add('prodid', '-//TH Köln Exam Periods//mxm.dk//')
    cal.add('version', '2.0')

    nh = get_nrw_holidays(2026) # Will be updated in loop

    current_year = 2026

    target_sems = []
    found_start = False
    for sem in sorted(lecture_periods.keys(), key=lambda x: (int(re.search(r'\d{4}', x).group()), 'Winter' in x)):
        if sem == start_sem:
            found_start = True
        if found_start:
            target_sems.append(sem)
        if sem == last_sem:
            break

    for sem in target_sems:
        if sem not in lecture_periods or sem not in hip_periods:
            continue

        is_ws = 'Winter' in sem
        l_start, l_end = lecture_periods[sem]
        hip_start, hip_end = hip_periods[sem]

        nh = get_nrw_holidays(l_start.year)

        # Determine standard P periods
        p1_mon = l_start - timedelta(days=l_start.weekday())
        p2_mon = hip_start - timedelta(days=hip_start.weekday())
        p3_mon = l_end - timedelta(days=l_end.weekday())

        def calculate_stats(p_list, is_winter):
            p_start = p_list[0]
            p_hip = p_list[-2]
            p_p1_end = p_list[1] if is_winter else p_list[0]
            p_stop = p_list[-1]

            total_w = ((p_stop - p_start).days // 7) + 1
            exam_w = len(p_list)
            h_w = get_ws_holiday_weeks(p_start, p_stop) if is_winter else 0
            lecture_w = total_w - exam_w - h_w

            # Buffers
            w_before = ((p_hip - p_p1_end).days // 7) - 1
            if is_winter:
                w_before -= get_ws_holiday_weeks(p_p1_end + timedelta(days=7), p_hip - timedelta(days=7))

            w_after = ((p_stop - p_hip).days // 7) - 1
            if is_winter:
                w_after -= get_ws_holiday_weeks(p_hip + timedelta(days=7), p_stop - timedelta(days=7))

            return {
                'lecture_weeks': lecture_w,
                'w_before': w_before,
                'w_after': w_after,
                'total_weeks': total_w
            }

        # Initial p_mons: WS has 2 start weeks
        if is_ws:
            p_mons_std = [p1_mon, p1_mon + timedelta(days=7), p2_mon, p3_mon]
        else:
            p_mons_std = [p1_mon, p2_mon, p3_mon]

        def apply_easter_rule(p_list, is_winter):
            for i in range(len(p_list)):
                if is_easter_week(p_list[i]):
                    temp = list(p_list)
                    temp[i] += timedelta(days=7)
                    if calculate_stats(temp, is_winter)['lecture_weeks'] >= 13:
                        return temp
            return p_list

        p_mons_std = apply_easter_rule(p_mons_std, is_ws)

        def get_violations(stats):
            v = []
            if stats['lecture_weeks'] < 13: v.append(f"Vorlesungswochen < 13 ({stats['lecture_weeks']})")
            if stats['w_before'] < 7: v.append(f"Wochen vor HIP < 7 ({stats['w_before']})")
            if stats['w_after'] < 7: v.append(f"Wochen nach HIP < 7 ({stats['w_after']})")
            return v

        # Find best plan by shifting
        p_mons_best = list(p_mons_std)

        # Calculate needed shift for P1
        stats_std = calculate_stats(p_mons_std, is_ws)
        if stats_std['w_before'] < 7:
            weeks_to_shift = 7 - stats_std['w_before']
            num_start = 2 if is_ws else 1
            for i in range(num_start):
                p_mons_best[i] -= timedelta(weeks=weeks_to_shift)

        # Calculate needed shift for P3
        stats_best_temp = calculate_stats(p_mons_best, is_ws)
        if stats_best_temp['w_after'] < 7:
            weeks_to_shift = 7 - stats_best_temp['w_after']
            p_mons_best[-1] += timedelta(weeks=weeks_to_shift)

        # Apply Easter rule to the shifted plan
        p_mons_best = apply_easter_rule(p_mons_best, is_ws)

        plans = []
        stats_std = calculate_stats(p_mons_std, is_ws)
        v_std = get_violations(stats_std)

        stats_best = calculate_stats(p_mons_best, is_ws)
        v_best = get_violations(stats_best)

        if not v_best:
            plans.append(("Vorschlag", p_mons_best))
        else:
            plans.append(("Standard", p_mons_std))
            if p_mons_best != p_mons_std:
                plans.append(("Optimierungsversuch", p_mons_best))

        WDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        def process_plan(p_list):
            results = []
            for i, mon in enumerate(p_list):
                days, hols = get_exam_days(mon, nh)

                # Check if any day in the exam period falls into a Karnevalswoche
                # A week is a Karnevalswoche if it contains Weiberfastnacht
                is_karneval = False
                for d in days:
                    wf = get_weiberfastnacht(d.year)
                    wf_monday = wf - timedelta(days=wf.weekday())
                    d_monday = d - timedelta(days=d.weekday())
                    if wf_monday == d_monday:
                        is_karneval = True
                        break

                results.append({
                    'week_num': i+1,
                    'start': min(days),
                    'end': max(days),
                    'holidays': hols,
                    'is_karneval': is_karneval
                })
            return results

        output_md += f"## {sem}\n\n"

        for plan_name, current_plan_mons in plans:
            stats = calculate_stats(current_plan_mons, is_ws)
            v = get_violations(stats)

            if len(plans) > 1:
                output_md += f"### Plan: {plan_name}\n\n"

            if v:
                output_md += "**VERLETZTE BEDINGUNGEN:**\n"
                for vi in v:
                    output_md += f"- {vi}\n"
                output_md += "\n"

            res = process_plan(current_plan_mons)

            output_md += f"Anzahl Vorlesungswochen: {stats['lecture_weeks']}\n"
            output_md += f"Vorlesungswochen vor HIP: {stats['w_before']}\n"
            output_md += f"Vorlesungswochen nach HIP: {stats['w_after']}\n\n"

            output_md += "| Prüfungswoche | Zeitraum | Feiertage | Anmerkungen |\n"
            output_md += "| --- | --- | --- | --- |\n"

            for r in res:
                hol_str = ", ".join([f"{h[0].strftime('%d.%m.')} ({h[1]})" for h in r['holidays']])
                note = "Karnevalswoche" if r['is_karneval'] else ""
                s_wd = WDAYS[r['start'].weekday()]
                e_wd = WDAYS[r['end'].weekday()]
                output_md += f"| {r['week_num']} | {s_wd} {r['start'].strftime('%d.%m.%Y')} - {e_wd} {r['end'].strftime('%d.%m.%Y')} | {hol_str} | {note} |\n"

            output_md += "\n"

            # Add to ICS (only standard if no warning, or both?)
            # Usually we want the proposed one. If warning, maybe both with different summaries.
            for r in res:
                event = ICalEvent()
                plan_suffix = f" ({plan_name})" if len(plans) > 1 else ""
                event.add('summary', f"Prüfungswoche {r['week_num']} {sem}{plan_suffix}")
                event.add('dtstart', r['start'])
                event.add('dtend', r['end'] + timedelta(days=1))
                cal.add_component(event)

    os.makedirs('files', exist_ok=True)
    with open('files/exam_periods.md', 'w', encoding='utf-8') as f:
        f.write(output_md)

    with open('files/exam_periods.ics', 'wb') as f:
        f.write(cal.to_ical())

    print("Files generated: files/exam_periods.md, files/exam_periods.ics")

if __name__ == "__main__":
    main()
