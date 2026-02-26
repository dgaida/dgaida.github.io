"""Unit tests for the CV Markdown to JSON conversion script.

This module contains tests for parsing Markdown-formatted CVs and converting
them into a JSON structure suitable for the website.
"""

import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open

# Add scripts directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

from cv_markdown_to_json import (
    parse_markdown_cv,
    extract_author_info,
    parse_education,
    parse_work_experience,
    parse_skills
)

def test_parse_markdown_cv() -> None:
    """Test parsing of a Markdown CV file into sections."""
    md_content = """---
layout: archive
title: "CV"
---

Education
=========
* B.Sc. in CS, TH Köln, 2020

Work experience
===============
* Dev, Tech Corp, 2021-present
"""
    with patch("builtins.open", mock_open(read_data=md_content)):
        sections = parse_markdown_cv("dummy.md")
        assert "Education" in sections
        assert "Work experience" in sections
        assert "B.Sc. in CS, TH Köln, 2020" in sections["Education"]
        assert "Dev, Tech Corp, 2021-present" in sections["Work experience"]

def test_extract_author_info() -> None:
    """Test extraction of author information from a configuration dictionary."""
    config = {
        "name": "John Doe",
        "url": "https://example.com",
        "author": {
            "name": "John Q. Doe",
            "email": "john@example.com",
            "github": "johndoe",
            "bio": "Software Engineer"
        }
    }
    info = extract_author_info(config)
    assert info["name"] == "John Q. Doe"
    assert info["email"] == "john@example.com"
    assert info["website"] == "https://example.com"
    assert info["summary"] == "Software Engineer"
    assert any(p["network"] == "GitHub" and p["username"] == "johndoe" for p in info["profiles"])

def test_parse_education() -> None:
    """Test parsing of education entries from a text string."""
    text = "* B.Sc. in Computer Science, TH Köln, 2020, GPA: 1.3"
    edu = parse_education(text)
    assert len(edu) == 1
    assert edu[0]["institution"] == "TH Köln"
    assert edu[0]["area"] == "B.Sc. in Computer Science"
    assert edu[0]["endDate"] == "2020"
    assert edu[0]["gpa"] == "1.3"

def test_parse_work_experience() -> None:
    """Test parsing of work experience entries including highlights from a text string."""
    text = """* Software Engineer, Tech Corp, 2021 - present
    * Developed awesome features
    - Fixed many bugs"""
    work = parse_work_experience(text)
    assert len(work) == 1
    assert work[0]["company"] == "Tech Corp"
    assert work[0]["position"] == "Software Engineer"
    assert work[0]["startDate"] == "2021"
    assert work[0]["endDate"] == "present"
    assert "Developed awesome features" in work[0]["highlights"]
    assert "Fixed many bugs" in work[0]["highlights"]

def test_parse_skills() -> None:
    """Test parsing of skills and keywords from a text string."""
    text = "Languages: Python, JavaScript, Java\nTools: Docker, Git"
    skills = parse_skills(text)
    assert len(skills) == 2
    assert skills[0]["name"] == "Languages"
    assert "Python" in skills[0]["keywords"]
    assert "JavaScript" in skills[0]["keywords"]
    assert skills[1]["name"] == "Tools"
    assert "Docker" in skills[1]["keywords"]
