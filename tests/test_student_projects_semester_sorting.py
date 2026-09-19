"""Unit tests for student projects semester chronological sorting.

This module contains tests for verifying that student project semesters
are sorted in reverse chronological order (newest first: e.g. SoSe26, WS25/26, SoSe25).
"""

import re
import subprocess
from pathlib import Path
from typing import List, Tuple


def semester_sort_key(sem: str) -> Tuple[int, int]:
    """Generates a numeric sort key for a given semester string.

    Args:
        sem: The semester string, e.g. 'SoSe26' or 'WS25/26'.

    Returns:
        A tuple of (year, season_order) where season_order is 2 for WS and 1 for SoSe.
    """
    sem = sem.strip()
    if "WS" in sem:
        yr_str = sem.replace("WS", "").split("/")[0].strip()
        yr = int(yr_str) if len(yr_str) == 4 else 2000 + int(yr_str)
        return (yr, 2)
    elif "SoSe" in sem:
        yr_str = sem.replace("SoSe", "").strip()
        yr = int(yr_str) if len(yr_str) == 4 else 2000 + int(yr_str)
        return (yr, 1)
    return (0, 0)


def test_semester_sort_key_order() -> None:
    """Test that semester_sort_key produces the expected chronological descending order."""
    semesters: List[str] = [
        "WS22/23",
        "WS23/24",
        "SoSe24",
        "WS24/25",
        "SoSe25",
        "WS25/26",
        "SoSe26",
    ]
    sorted_semesters = sorted(semesters, key=semester_sort_key, reverse=True)
    expected: List[str] = [
        "SoSe26",
        "WS25/26",
        "SoSe25",
        "WS24/25",
        "SoSe24",
        "WS23/24",
        "WS22/23",
    ]
    assert sorted_semesters == expected


def test_rendered_student_projects_semester_sorting() -> None:
    """Test that the generated HTML file has semesters sorted chronologically descending."""
    site_file = Path("_site/student_projects/index.html")
    if not site_file.exists():
        subprocess.run(["bundle", "exec", "jekyll", "build"], check=True)

    content = site_file.read_text(encoding="utf-8")

    # Extract statistics semesters under "Nach Semester:"
    stats_match = re.search(r"Nach Semester:.*?(<span.*?</span>\s*<br\s*/?>\s*)+", content, re.DOTALL)
    assert stats_match is not None, "Statistics section for semesters not found."
    stats_semesters = re.findall(r'<span[^>]*>\s*([^:]+):', stats_match.group(0))
    assert len(stats_semesters) > 1

    sorted_stats = sorted(stats_semesters, key=semester_sort_key, reverse=True)
    assert stats_semesters == sorted_stats, f"Stats semesters not sorted correctly: {stats_semesters}"

    # Extract filter dropdown options
    filter_match = re.search(r'<select id="semester-filter">(.*?)</select>', content, re.DOTALL)
    assert filter_match is not None, "Semester filter dropdown not found."
    filter_options = re.findall(r'<option value="([^"]+)">', filter_match.group(1))
    # Remove empty option "Alle Semester"
    filter_semesters = [opt for opt in filter_options if opt]
    assert len(filter_semesters) > 1

    sorted_filters = sorted(filter_semesters, key=semester_sort_key, reverse=True)
    assert filter_semesters == sorted_filters, f"Filter dropdown semesters not sorted correctly: {filter_semesters}"

    # Check project section headers under a type (e.g. Bachelorthesis)
    ba_match = re.search(r'<h3 id="bachelorthesis">.*?</h3>(.*?)(?=<h3|$)', content, re.DOTALL)
    assert ba_match is not None, "Bachelorthesis section not found."
    ba_semesters = re.findall(r'<h4[^>]*>\s*([^<]+)\s*</h4>', ba_match.group(1))
    assert len(ba_semesters) > 1

    sorted_ba = sorted(ba_semesters, key=semester_sort_key, reverse=True)
    assert ba_semesters == sorted_ba, f"Bachelorthesis section semesters not sorted correctly: {ba_semesters}"
