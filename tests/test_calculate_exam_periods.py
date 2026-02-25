import sys
import os
from datetime import date, datetime, timedelta
import pytest
from unittest.mock import MagicMock, patch

# Add scripts directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from calculate_exam_periods import (
    parse_date,
    get_nrw_holidays,
    get_weiberfastnacht,
    get_working_days_in_week,
    is_easter_week,
    get_ws_holiday_weeks,
    get_exam_days,
    extrapolate_periods
)

def test_parse_date():
    assert parse_date("20.03.2024") == date(2024, 3, 20)
    assert parse_date("20.03.", default_year=2024) == date(2024, 3, 20)
    assert parse_date("20. 03. 2024") == date(2024, 3, 20)
    # The script currently finds the first date with a year in the whole string
    assert parse_date("20.03. – 21.03.2024") == date(2024, 3, 21)
    assert parse_date("invalid") is None

def test_get_nrw_holidays():
    nh = get_nrw_holidays(2024)
    # Check some known holidays in NRW 2024
    assert date(2024, 1, 1) in nh # Neujahr
    assert date(2024, 5, 1) in nh # Tag der Arbeit
    assert date(2024, 12, 25) in nh # 1. Weihnachtstag
    # Rosenmontag 2024 was Feb 12 (Easter was March 31)
    assert date(2024, 2, 12) in nh
    assert nh[date(2024, 2, 12)] == "Rosenmontag"

def test_get_weiberfastnacht():
    # Weiberfastnacht 2024 was Feb 8
    assert get_weiberfastnacht(2024) == date(2024, 2, 8)

def test_get_working_days_in_week():
    monday = date(2024, 3, 18)
    working_days = get_working_days_in_week(monday)
    assert len(working_days) == 5
    assert working_days[0] == date(2024, 3, 18)
    assert working_days[4] == date(2024, 3, 22)

def test_is_easter_week():
    # Easter Sunday 2024 was March 31. Easter Monday was April 1.
    # The week starting April 1 is the easter week.
    assert is_easter_week(date(2024, 4, 1)) is True
    assert is_easter_week(date(2024, 3, 25)) is False

def test_get_ws_holiday_weeks():
    p1 = date(2024, 12, 16)
    p3 = date(2025, 1, 6)
    # Week of Dec 23-27 contains Christmas
    # Week of Dec 30-Jan 3 contains New Year
    assert get_ws_holiday_weeks(p1, p3) == 2

def test_get_exam_days_no_holidays():
    nh = {}
    monday = date(2024, 3, 18)
    days, found_hols = get_exam_days(monday, nh)
    assert len(days) == 5
    assert days[0] == date(2024, 3, 18)
    assert days[4] == date(2024, 3, 22)
    assert len(found_hols) == 0

def test_get_exam_days_with_holidays():
    # May 1st 2024 was a Wednesday
    nh = {date(2024, 5, 1): "Tag der Arbeit"}
    monday = date(2024, 4, 29)
    days, found_hols = get_exam_days(monday, nh)
    assert len(days) == 5
    assert date(2024, 5, 1) not in days
    # It should have pulled Friday from previous week
    assert date(2024, 4, 26) in days
    assert len(found_hols) == 1
    assert found_hols[0][0] == date(2024, 5, 1)

@patch('calculate_exam_periods.requests.get')
def test_scrape_data(mock_get):
    mock_resp_v = MagicMock()
    # The script expects semester and dates in separate rows
    mock_resp_v.text = """
    <table>
    <caption>Allgemeine Vorlesungszeiten</caption>
    <tr><th>Sommersemester 2024</th></tr>
    <tr><td>Dates:</td><td>18.03.2024 – 12.07.2024</td></tr>
    <tr><th>Wintersemester 2024/25</th></tr>
    <tr><td>Dates:</td><td>23.09.2024 – 31.01.2025</td></tr>
    </table>
    """
    mock_resp_v.status_code = 200

    mock_resp_hip = MagicMock()
    mock_resp_hip.text = """
    <h2>Terminvorschau</h2>
    <p>
    Sommersemester 2024: 13.05.2024 – 17.05.2024
    Wintersemester 2024/25: 18.11.2024 – 22.11.2024
    </p>
    """
    mock_resp_hip.status_code = 200

    mock_get.side_effect = [mock_resp_v, mock_resp_hip]

    from calculate_exam_periods import scrape_data
    lp, hp = scrape_data()

    assert "Sommersemester 2024" in lp
    assert lp["Sommersemester 2024"] == (date(2024, 3, 18), date(2024, 7, 12))
    assert "Sommersemester 2024" in hp
    assert hp["Sommersemester 2024"] == (date(2024, 5, 13), date(2024, 5, 17))

def test_extrapolate_periods():
    lp = {"Sommersemester 2024": (date(2024, 3, 18), date(2024, 7, 12))}
    hp = {"Sommersemester 2024": (date(2024, 5, 13), date(2024, 5, 17))}

    extrapolate_periods(lp, hp, num_years=5)

    # Should have added WS 2024/25, SS 2025, etc.
    assert "Wintersemester 2024/25" in lp
    assert "Wintersemester 2024/25" in hp
    assert "Sommersemester 2025" in lp
    assert "Sommersemester 2025" in hp
    # Check boundary
    assert "Sommersemester 2028" in hp
    assert "Wintersemester 2028/29" in hp
