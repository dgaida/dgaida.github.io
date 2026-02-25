import sys
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from datetime import date

# Add scripts directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

# Mock docling BEFORE importing parse_appointments
sys.modules['docling'] = MagicMock()
sys.modules['docling.document_converter'] = MagicMock()

from parse_appointments import scrape_pdf_links, is_strikethrough

@patch("parse_appointments.requests.get")
def test_scrape_pdf_links(mock_get):
    mock_resp = MagicMock()
    mock_resp.text = """
    <div>
        <h2>Campus-Termine</h2>
        <p><a class="download" href="/campus.pdf">Download</a></p>
        <h2>Prüfungszeiten</h2>
        <p><a class="download" href="/pruefung.pdf">Download</a></p>
    </div>
    """
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    links = scrape_pdf_links()
    assert links['campus'] == "https://www.th-koeln.de/campus.pdf"
    assert links['pruefungszeiten'] == "https://www.th-koeln.de/pruefung.pdf"

def test_is_strikethrough():
    page = MagicMock()
    # Horizontal line in the middle
    page.lines = [{'top': 50, 'bottom': 50.5, 'x0': 10, 'x1': 90}]

    # Cell bbox: x0, y0, x1, y1 (y0 is top, y1 is bottom in many PDF libs,
    # but let's check parse_appointments code:
    # x0, y0, x1, y1 = table_cell
    # ly = line['top']
    # if y0 + 3 < ly < y1 - 3:

    cell_bbox = (0, 40, 100, 60)
    assert is_strikethrough(page, cell_bbox) is True

    # Line outside cell
    cell_bbox_outside = (0, 60, 100, 80)
    assert is_strikethrough(page, cell_bbox_outside) is False

@patch("parse_appointments.requests.get")
@patch("parse_appointments.DocumentConverter")
@patch("builtins.open", new_callable=mock_open)
def test_parse_campus_appointments(mock_file, mock_converter_class, mock_get):
    from parse_appointments import parse_campus_appointments
    from icalendar import Calendar

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"PDF content"
    mock_get.return_value = mock_resp

    mock_converter = mock_converter_class.return_value
    mock_result = MagicMock()
    mock_converter.convert.return_value = mock_result

    mock_table = MagicMock()
    mock_result.document.tables = [mock_table]

    import pandas as pd
    df = pd.DataFrame([
        ["20.03.2024", "10:00 Uhr", "Meeting - Room 1"],
        ["21.03.2024", "", "All day event"]
    ])
    mock_table.export_to_dataframe.return_value = df

    cal = Calendar()
    found = parse_campus_appointments("https://example.com/test.pdf", cal)

    assert found == 2
    events = [c for c in cal.subcomponents if c.name == 'VEVENT']
    assert len(events) == 2
    assert str(events[0]['summary']) == "Meeting"
    assert str(events[0]['location']) == "Room 1"
    assert str(events[1]['summary']) == "All day event"
