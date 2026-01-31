import os
import requests
import yaml
import re

def get_orcid_id():
    try:
        with open('_config.yml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        orcid_url = config.get('author', {}).get('orcid', '')
        if not orcid_url:
            return None
        # Extract ID from URL like https://orcid.org/0009-0000-9669-4294
        return orcid_url.split('/')[-1]
    except Exception as e:
        print(f"Error reading _config.yml: {e}")
        return None

def clean_filename(title):
    # Remove HTML tags
    title = re.sub(r'<[^>]+>', '', title)
    title = title.lower()
    # Replace non-alphanumeric characters with hyphens
    title = re.sub(r'[^a-z0-9]+', '-', title)
    # Remove leading/trailing hyphens
    return title.strip('-')[:100] # Limit length

def fetch_orcid_works(orcid_id):
    headers = {'Accept': 'application/json'}
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def sync():
    orcid_id = get_orcid_id()
    if not orcid_id:
        print("No ORCID ID found in _config.yml")
        return

    print(f"Fetching works for ORCID: {orcid_id}")
    try:
        works_data = fetch_orcid_works(orcid_id)
    except Exception as e:
        print(f"Error fetching ORCID works: {e}")
        return

    works_groups = works_data.get('group', [])
    print(f"Found {len(works_groups)} work groups")

    if not os.path.exists('_publications'):
        os.makedirs('_publications')

    for group in works_groups:
        work_summary = group.get('work-summary', [{}])[0]
        title = work_summary.get('title', {}).get('title', {}).get('value', 'Untitled')

        pub_date = work_summary.get('publication-date', {})
        if pub_date:
            year = pub_date.get('year', {}).get('value', '1900') if pub_date.get('year') else '1900'
            month = pub_date.get('month', {}).get('value', '01') if pub_date.get('month') else '01'
            day = pub_date.get('day', {}).get('value', '01') if pub_date.get('day') else '01'
        else:
            year, month, day = '1900', '01', '01'

        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        venue = work_summary.get('journal-title', {}).get('value', '') if work_summary.get('journal-title') else ''

        work_type = work_summary.get('type', '')
        category = 'manuscripts'
        if work_type and 'CONFERENCE' in work_type.upper():
            category = 'conferences'
        elif work_type and 'BOOK' in work_type.upper():
            category = 'books'

        url = ''
        external_ids = work_summary.get('external-ids', {}).get('external-id', [])
        for eid in external_ids:
            if eid.get('external-id-type') == 'doi':
                url = f"https://doi.org/{eid.get('external-id-value')}"
                break
            elif eid.get('external-id-type') == 'url':
                url = eid.get('external-id-value')

        filename = f"{date_str}-{clean_filename(title)}.md"
        filepath = os.path.join('_publications', filename)

        if os.path.exists(filepath):
            continue

        # Basic front matter
        content = f"""---
title: "{title}"
collection: publications
category: {category}
permalink: /publication/{date_str}-{clean_filename(title)}
date: {date_str}
venue: '{venue}'
"""
        if url:
            content += f"paperurl: '{url}'\n"

        content += "---\n"

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Created {filepath}")

if __name__ == "__main__":
    sync()
