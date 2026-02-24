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

        l_start, l_end = lecture_periods[sem]
        hip_start, hip_end = hip_periods[sem]

        nh = get_nrw_holidays(l_start.year)

        # Determine standard P1, P2, P3
        # P1: first week of lectures
        p1_mon = l_start - timedelta(days=l_start.weekday())

        # P2: HIP week
        p2_mon = hip_start - timedelta(days=hip_start.weekday())

        # P3: last week of lectures
        p3_mon = l_end - timedelta(days=l_end.weekday())

        # Calculate lecture weeks
        total_weeks = ((p3_mon - p1_mon).days // 7) + 1
        lecture_weeks = total_weeks - 3 # excluding the 3 exam weeks

        warning = ""
        alternative_plan = None
        if lecture_weeks < 13:
            warning = f"**WARNUNG: Nur {lecture_weeks} Vorlesungswochen!**"
            # Alternative P1: week before lectures
            alt_p1_mon = p1_mon - timedelta(days=7)
            alternative_plan = alt_p1_mon

        def process_plan(p1_m, p2_m, p3_m):
            results = []
            for i, mon in enumerate([p1_m, p2_m, p3_m]):
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

        plans = [("Standard", p1_mon)]
        if alternative_plan:
            plans.append(("Alternativ (vorgezogen)", alternative_plan))

        output_md += f"## {sem}\n\n"
        if warning:
            output_md += f"{warning}\n\n"

        for plan_name, p1_m in plans:
            if len(plans) > 1:
                output_md += f"### Plan: {plan_name}\n\n"

            res = process_plan(p1_m, p2_mon, p3_mon)

            output_md += "| Prüfungswoche | Zeitraum | Feiertage | Anmerkungen |\n"
            output_md += "| --- | --- | --- | --- |\n"

            for r in res:
                hol_str = ", ".join([f"{h[0].strftime('%d.%m.')} ({h[1]})" for h in r['holidays']])
                note = "Karnevalswoche" if r['is_karneval'] else ""
                output_md += f"| {r['week_num']} | {r['start'].strftime('%d.%m.%Y')} - {r['end'].strftime('%d.%m.%Y')} | {hol_str} | {note} |\n"

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
