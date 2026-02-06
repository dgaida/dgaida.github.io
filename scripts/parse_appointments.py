import os
import re
import requests
from datetime import datetime, timedelta
from docling.document_converter import DocumentConverter
from icalendar import Calendar, Event
import pandas as pd
import argparse
from bs4 import BeautifulSoup
import pdfplumber

BASE_URL = "https://www.th-koeln.de/informatik-und-ingenieurwissenschaften/informatik-und-ingenieurwissenschaften/termine-und-fristen_19440.php"
TH_MAM_BASE = "https://www.th-koeln.de"

def scrape_pdf_links():
    print(f"Scraping {BASE_URL} for PDF links...")
    links = {
        'campus': None,
        'pruefungszeiten': None
    }
    try:
        response = requests.get(BASE_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find Campus-Termine
        campus_header = soup.find(lambda tag: tag.name == "h2" and "Campus-Termine" in tag.text)
        if campus_header:
            next_p = campus_header.find_next("p")
            if next_p:
                link = next_p.find("a", class_="download")
                if link and link.get("href"):
                    links['campus'] = TH_MAM_BASE + link.get("href")

        # Find Prüfungszeiten
        pruefung_header = soup.find(lambda tag: tag.name == "h2" and "Prüfungszeiten" in tag.text)
        if pruefung_header:
            next_p = pruefung_header.find_next("p")
            if next_p:
                link = next_p.find("a", class_="download")
                if link and link.get("href"):
                    links['pruefungszeiten'] = TH_MAM_BASE + link.get("href")

        return links
    except Exception as e:
        print(f"Error scraping links: {e}")
        return links

def parse_campus_appointments(pdf_url, cal):
    print(f"Parsing Campus-Termine from {pdf_url}...")
    try:
        response = requests.get(pdf_url)
        if response.status_code != 200:
            return 0

        with open("temp_campus.pdf", "wb") as f:
            f.write(response.content)

        converter = DocumentConverter()
        result = converter.convert("temp_campus.pdf")

        found_events = 0
        for table in result.document.tables:
            df = table.export_to_dataframe(result.document)
            for _, row in df.iterrows():
                if len(row) < 3: continue
                date_str = str(row[0]).strip()
                time_str = str(row[1]).strip()
                desc = str(row[2]).strip()

                date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
                if not date_match: continue

                day, month, year = map(int, date_match.groups())
                try:
                    start_dt = datetime(year, month, day)
                except ValueError: continue

                is_all_day = True
                if time_str and 'Uhr' in time_str:
                    time_match = re.search(r'(\d{2})[\.:](\d{2})', time_str)
                    if time_match:
                        hour, minute = map(int, time_match.groups())
                        start_dt = start_dt.replace(hour=hour, minute=minute)
                        end_dt = start_dt + timedelta(hours=2)
                        is_all_day = False
                    else:
                        end_dt = start_dt + timedelta(days=1)
                else:
                    end_dt = start_dt + timedelta(days=1)

                # Split description by dash (en-dash or hyphen)
                # Part before dash is summary, part after is location
                summary = desc
                location = None
                dash_match = re.split(r' [–-] ', desc, maxsplit=1)
                if len(dash_match) == 2:
                    summary = dash_match[0].strip()
                    location = dash_match[1].strip()

                event = Event()
                event.add('summary', summary)
                if location:
                    event.add('location', location)

                if is_all_day:
                    event.add('dtstart', start_dt.date())
                    event.add('dtend', end_dt.date())
                else:
                    event.add('dtstart', start_dt)
                    event.add('dtend', end_dt)
                cal.add_component(event)
                found_events += 1

        if os.path.exists("temp_campus.pdf"):
            os.remove("temp_campus.pdf")
        return found_events
    except Exception as e:
        print(f"Error parsing campus appointments: {e}")
        return 0

def is_strikethrough(page, table_cell):
    if not table_cell: return False
    x0, y0, x1, y1 = table_cell
    # Strikethrough is a horizontal line in the middle of the cell
    for line in page.lines:
        if abs(line['top'] - line['bottom']) < 2: # horizontal
            ly = line['top']
            # Check if line is inside the cell vertically, avoiding borders
            if y0 + 3 < ly < y1 - 3:
                lx0 = min(line['x0'], line['x1'])
                lx1 = max(line['x0'], line['x1'])
                overlap_x0 = max(x0, lx0)
                overlap_x1 = min(x1, lx1)
                if overlap_x1 > overlap_x0:
                    overlap_ratio = (overlap_x1 - overlap_x0) / (x1 - x0)
                    if overlap_ratio > 0.4:
                        return True
    return False

def parse_pruefungszeiten(pdf_url, cal):
    print(f"Parsing Prüfungszeiten from {pdf_url}...")
    try:
        response = requests.get(pdf_url)
        if response.status_code != 200:
            return 0

        with open("temp_pruefung.pdf", "wb") as f:
            f.write(response.content)

        found_events = 0
        with pdfplumber.open("temp_pruefung.pdf") as pdf:
            for page in pdf.pages:
                tables = page.find_tables()
                for table in tables:
                    extract_data = table.extract()
                    for row_idx, row_text in enumerate(extract_data):
                        if row_idx < 2: continue
                        if not row_text or len(row_text) < 7: continue

                        sem = row_text[0]
                        if not sem: continue

                        # Indices 3, 4 (Informatik) and 5, 6 (Ingenieurwissenschaften)
                        for col_idx in [3, 4, 5, 6]:
                            text = row_text[col_idx]
                            if not text or len(text.strip()) < 5: continue

                            # Check for strikethrough using cell bbox
                            try:
                                cell_bbox = table.rows[row_idx].cells[col_idx]
                                if is_strikethrough(page, cell_bbox):
                                    print(f"Skipping strikethrough text in {sem}: {text}")
                                    continue
                            except (IndexError, AttributeError):
                                pass

                            date_matches = re.findall(r'(\d{2})\.(\d{2})\.(\d{2,4})', text)
                            if len(date_matches) >= 2:
                                try:
                                    d1, m1, y1_str = date_matches[0]
                                    d2, m2, y2_str = date_matches[1]

                                    y1 = int(y1_str)
                                    if len(y1_str) == 2: y1 += 2000
                                    y2 = int(y2_str)
                                    if len(y2_str) == 2: y2 += 2000

                                    start_dt = datetime(y1, int(m1), int(d1))
                                    end_dt = datetime(y2, int(m2), int(d2)) + timedelta(days=1)

                                    label = "Informatik" if col_idx in [3, 4] else "Ingenieurwissenschaften"
                                    summary = f"Prüfungszeitraum {label} ({sem})"

                                    event = Event()
                                    event.add('summary', summary)
                                    event.add('dtstart', start_dt.date())
                                    event.add('dtend', end_dt.date())
                                    cal.add_component(event)
                                    found_events += 1
                                except ValueError:
                                    continue

        if os.path.exists("temp_pruefung.pdf"):
            os.remove("temp_pruefung.pdf")
        return found_events
    except Exception as e:
        print(f"Error parsing Prüfungszeiten: {e}")
        return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parse TH Köln appointments to ICS.')
    parser.add_argument('--output', type=str, default='files/f10_appointments.ics', help='Output ICS file path')
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    links = scrape_pdf_links()

    cal = Calendar()
    cal.add('prodid', '-//TH Köln Campus Gummersbach Appointments//mxm.dk//')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', 'Termine F10 Campus Gummersbach')

    total_events = 0

    if links['campus']:
        total_events += parse_campus_appointments(links['campus'], cal)
    else:
        print("Could not find Campus-Termine PDF link.")

    if links['pruefungszeiten']:
        total_events += parse_pruefungszeiten(links['pruefungszeiten'], cal)
    else:
        print("Could not find Prüfungszeiten PDF link.")

    if total_events > 0:
        with open(args.output, 'wb') as f:
            f.write(cal.to_ical())
        print(f"Successfully saved {total_events} events to {args.output}")
    else:
        print("No events found.")
