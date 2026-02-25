import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, date, timedelta
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

def find_best_hip(l_start, l_end, is_winter, num_exams):
    best_hip = None
    best_score = 9999

    # We try different buffers between the first exam block and the HIP week.
    # buffer is the number of lecture weeks.
    for buffer in range(6, 11):
        hip_mon_cand = l_start + timedelta(weeks=num_exams + buffer)

        # Estimate w_after including holidays for winter
        p_stop_approx = l_end - timedelta(days=l_end.weekday())
        w_after_cand = ((p_stop_approx - hip_mon_cand).days // 7) - 1
        if is_winter:
            w_after_cand -= get_ws_holiday_weeks(hip_mon_cand + timedelta(days=7), p_stop_approx - timedelta(days=7))

        w_before_cand = buffer
        # Technically holidays could be in w_before, but rare for Oct-Dec
        if is_winter:
            w_before_cand -= get_ws_holiday_weeks(l_start + timedelta(weeks=num_exams), hip_mon_cand - timedelta(days=7))

        score = 0
        # Heavily penalize any deviation from exactly 7 lecture weeks
        if w_before_cand != 7: score += abs(7 - w_before_cand) * 100
        if w_after_cand != 7: score += abs(7 - w_after_cand) * 100
        score += abs(w_before_cand - w_after_cand)

        if score < best_score:
            best_score = score
            best_hip = hip_mon_cand

    return best_hip

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

def sem_key(sem_name):
    year_match = re.search(r'\d{4}', sem_name)
    year = int(year_match.group()) if year_match else 0
    is_winter = 'Winter' in sem_name
    return (year, is_winter)

PROPOSAL_BOUNDARY = (2028, False) # Sommersemester 2028

def extrapolate_periods(lecture_periods, hip_periods, num_years=4):
    # Ensure all semesters in lecture_periods have HIP periods
    for sem_name in lecture_periods:
        if sem_name not in hip_periods:
            l_start, l_end = lecture_periods[sem_name]
            is_winter = 'Winter' in sem_name
            num_exams = 2 if is_winter else 1

            # For fixed semesters, follow the "exactly 7 weeks" rule (week 9 for SS, 10 for WS)
            if sem_key(sem_name) < PROPOSAL_BOUNDARY:
                hip_mon = l_start + timedelta(weeks=num_exams + 7)
            else:
                # Optimize for proposals
                hip_mon = find_best_hip(l_start, l_end, is_winter, num_exams)

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

            if sem_key(sem_name) < PROPOSAL_BOUNDARY:
                hip_mon = l_start + timedelta(weeks=num_exams + 7)
            else:
                hip_mon = find_best_hip(l_start, l_end, curr_winter, num_exams)

            hip_periods[sem_name] = (hip_mon, hip_mon + timedelta(days=4))

def calculate_stats(p_list, is_winter, l_start, l_end):
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

def get_violations(stats, p_list, is_winter):
    v = []
    if stats['lecture_weeks'] < 13: v.append(f"Vorlesungswochen < 13 ({stats['lecture_weeks']})")
    if stats['w_before'] < 7: v.append(f"Wochen vor HIP < 7 ({stats['w_before']})")
    if stats['w_after'] < 7: v.append(f"Wochen nach HIP < 7 ({stats['w_after']})")
    if any(is_easter_week(m) for m in p_list): v.append("Prüfung in Osterwoche")
    return v

def generate_pdf(all_semester_results):
    os.makedirs('files', exist_ok=True)
    c = canvas.Canvas("files/exam_periods.pdf", pagesize=landscape(A4))
    width, height = landscape(A4)

    for sem_name, data in all_semester_results.items():
        title = f"Semesterplan: {sem_name}"
        if sem_key(sem_name) >= PROPOSAL_BOUNDARY:
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

        # Calculate start of visual period
        v_start = min(l_start, p_list[0])
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
            is_exam = mon in p_list
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

        c.showPage()
    c.save()

def main():
    try:
        lecture_periods, hip_periods = scrape_data()
    except Exception as e:
        print(f"Error scraping data: {e}")
        sys.exit(1)

    extrapolate_periods(lecture_periods, hip_periods, num_years=4)
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
                stats = calculate_stats(candidate, is_ws, l_start, l_end)
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
        stats_best = calculate_stats(p_mons_best, is_ws, l_start, l_end)
        v_best = get_violations(stats_best, p_mons_best, is_ws)

        detailed_rows = []
        WDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        for i, mon in enumerate(p_mons_best):
            days, hols = get_exam_days(mon, nh)
            is_karneval = any((get_weiberfastnacht(d.year) - timedelta(days=get_weiberfastnacht(d.year).weekday())) == (d - timedelta(days=d.weekday())) for d in days)
            hol_str = ", ".join([f"{h[0].strftime('%d.%m.')} ({h[1]})" for h in hols])
            notes = []
            if is_karneval: notes.append("Karnevalswoche")

            # Identify HIP week (it's the second to last in the list of exam weeks)
            if i == len(p_mons_best) - 2:
                hip_note = "HIP-Woche"
                if sem_key(sem) >= PROPOSAL_BOUNDARY:
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
            'rows': detailed_rows
        }

        sem_title = sem
        if sem_key(sem) >= PROPOSAL_BOUNDARY:
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
    generate_pdf(all_semester_results)
    print("Files generated: files/exam_periods.md, files/exam_periods.ics, files/exam_periods.pdf")

if __name__ == "__main__":
    main()
