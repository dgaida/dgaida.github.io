# Agent Instructions

This repository is a Jekyll-based website using the 'Academic Pages' template. It includes automation for link checking, appointment parsing, and student project generation.

## Key Information

- **Primary Contact**: Daniel Gaida (daniel.gaida@th-koeln.de)
- **Python Version**: 3.12+
- **Jekyll Version**: Managed via Bundler

## Automated Tasks

- **Link Checking**: Monthly via `.github/workflows/check_links.yml`. Root-relative links are resolved using `--root-dir .`.
- **Appointments**: Scraped from TH Köln website and saved to `files/f10_appointments.ics`.
- **Student Projects**: Generated from `BachelorThesen/`, `MasterThesen/`, and `PraxisProjekte/` using `generate_student_projects.py`.
- **Exam Period Calculation**: Logic in `scripts/calculate_exam_periods.py` handles NRW holiday shifts and lecture week statistics.

## Testing

Run unit tests using:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/scripts
python -m pytest tests/
```

## Frontmatter and Content

- Use `.md` extension for pages to ensure TOC and Markdown tables are processed correctly.
- YouTube videos must be embedded using `https://www.youtube.com/embed/[VIDEO_ID]`.
- TOC can be added with `{% include toc %}`.
