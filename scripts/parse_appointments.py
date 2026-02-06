import os
import re
import requests
from datetime import datetime, timedelta
from docling.document_converter import DocumentConverter
from icalendar import Calendar, Event
import pandas as pd
import argparse

def get_dynamic_url():
    now = datetime.now()
    year = now.year
    # End of Feb -> SoSe of current year
    # End of Aug -> WiSe of current year / next year
    if now.month <= 6:
        semester = "sose"
        sem_str = f"{semester}{year}"
    else:
        semester = "wise"
        next_year_short = (year + 1) % 100
        sem_str = f"{semester}{year}{next_year_short:02d}"

    return f"https://www.th-koeln.de/mam/downloads/deutsch/hochschule/fakultaeten/informatik_und_ingenieurwissenschaften/termintabelle_{sem_str}.pdf"

def parse_appointments(pdf_url, output_ics):
    print(f"Downloading PDF from {pdf_url}...")
    response = requests.get(pdf_url)
    if response.status_code != 200:
        print(f"Failed to download PDF: {response.status_code}")
        return False

    with open("temp.pdf", "wb") as f:
        f.write(response.content)

    print("Converting PDF to data...")
    converter = DocumentConverter()
    result = converter.convert("temp.pdf")

    cal = Calendar()
    cal.add('prodid', '-//TH Köln Campus Gummersbach Appointments//mxm.dk//')
    cal.add('version', '2.0')

    found_events = 0
    for table in result.document.tables:
        df = table.export_to_dataframe(result.document)

        for _, row in df.iterrows():
            # Expected columns: 0: Date, 1: Time, 2: Description
            if len(row) < 3:
                continue

            date_str = str(row[0]).strip()
            time_str = str(row[1]).strip()
            desc = str(row[2]).strip()

            # Match date like 11.03.2026
            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
            if not date_match:
                continue

            day, month, year = map(int, date_match.groups())

            try:
                start_dt = datetime(year, month, day)
            except ValueError:
                continue

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

            event = Event()
            event.add('summary', desc)
            if is_all_day:
                event.add('dtstart', start_dt.date())
                event.add('dtend', end_dt.date())
            else:
                event.add('dtstart', start_dt)
                event.add('dtend', end_dt)

            cal.add_component(event)
            found_events += 1

    if found_events > 0:
        with open(output_ics, 'wb') as f:
            f.write(cal.to_ical())
        print(f"Successfully saved {found_events} events to {output_ics}")
        return True
    else:
        print("No events found in the PDF.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Parse TH Köln appointments PDF to ICS.')
    parser.add_argument('--url', type=str, help='URL of the PDF file')
    parser.add_argument('--output', type=str, default='files/appointments.ics', help='Output ICS file path')

    args = parser.parse_args()

    url = args.url if args.url else "https://www.th-koeln.de/mam/downloads/deutsch/hochschule/fakultaeten/informatik_und_ingenieurwissenschaften/termintabelle_sose2026.pdf"

    # If the default URL fails, try the dynamic one
    success = parse_appointments(url, args.output)
    if not success and not args.url:
        dynamic_url = get_dynamic_url()
        if dynamic_url != url:
            print(f"Retrying with dynamic URL: {dynamic_url}")
            parse_appointments(dynamic_url, args.output)

    if os.path.exists("temp.pdf"):
        os.remove("temp.pdf")
