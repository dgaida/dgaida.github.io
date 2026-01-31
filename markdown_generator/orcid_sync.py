#!/usr/bin/env python3
"""
ORCID to Academic Pages Sync Script

Synchronisiert Publikationen von ORCID mit Academic Pages.
Verwendung: python orcid_sync.py

Author: Daniel Gaida
"""

import requests
import json
import os
import re
from datetime import datetime
from pathlib import Path


class ORCIDSync:
    """
    Synchronisiert ORCID-Daten mit Academic Pages.
    
    Args:
        orcid_id: ORCID Identifier (z.B. '0009-0000-9669-4294')
        output_dir: Verzeichnis für die generierten Markdown-Dateien
    """
    
    def __init__(self, orcid_id: str, output_dir: str = "_publications"):
        self.orcid_id = orcid_id
        self.output_dir = Path(output_dir)
        self.base_url = "https://pub.orcid.org/v3.0"
        self.headers = {"Accept": "application/json"}
        
    def fetch_works(self) -> list:
        """
        Ruft alle Publikationen von ORCID ab.
        
        Returns:
            Liste von Publikations-Dictionaries
        """
        url = f"{self.base_url}/{self.orcid_id}/works"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            works = []
            for group in data.get('group', []):
                work_summary = group.get('work-summary', [{}])[0]
                put_code = work_summary.get('put-code')
                
                if put_code:
                    work_detail = self.fetch_work_detail(put_code)
                    if work_detail:
                        works.append(work_detail)
                        
            return works
            
        except requests.exceptions.RequestException as e:
            print(f"Fehler beim Abrufen der ORCID-Daten: {e}")
            return []
    
    def fetch_work_detail(self, put_code: str) -> dict:
        """
        Ruft Details einer einzelnen Publikation ab.
        
        Args:
            put_code: ORCID Work-Identifier
            
        Returns:
            Dictionary mit Publikationsdetails
        """
        url = f"{self.base_url}/{self.orcid_id}/work/{put_code}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Fehler beim Abrufen von Work {put_code}: {e}")
            return None
    
    def parse_work(self, work: dict) -> dict:
        """
        Extrahiert relevante Informationen aus einem ORCID Work.
        
        Args:
            work: ORCID Work Dictionary
            
        Returns:
            Vereinfachtes Dictionary mit Publikationsdaten
        """
        title = work.get('title', {}).get('title', {}).get('value', 'Untitled')
        
        # Publikationsdatum
        pub_date = work.get('publication-date')
        if pub_date:
            year = pub_date.get('year', {}).get('value', '1900')
            month = pub_date.get('month', {}).get('value', '01')
            day = pub_date.get('day', {}).get('value', '01')
            date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            date_str = "1900-01-01"
        
        # Journal/Venue
        journal = work.get('journal-title', {}).get('value', '')
        
        # DOI
        external_ids = work.get('external-ids', {}).get('external-id', [])
        doi = None
        for ext_id in external_ids:
            if ext_id.get('external-id-type') == 'doi':
                doi = ext_id.get('external-id-value')
                break
        
        # URL
        url = work.get('url', {}).get('value', '')
        if not url and doi:
            url = f"https://doi.org/{doi}"
        
        # Citation
        citation_value = work.get('citation', {}).get('citation-value', '')
        
        return {
            'title': title,
            'date': date_str,
            'venue': journal,
            'url': url,
            'doi': doi,
            'citation': citation_value
        }
    
    def create_markdown(self, work_data: dict) -> str:
        """
        Erstellt Markdown-Inhalt für eine Publikation.
        
        Args:
            work_data: Dictionary mit Publikationsdaten
            
        Returns:
            Markdown-String
        """
        title = work_data['title']
        date = work_data['date']
        venue = work_data['venue']
        url = work_data['url']
        
        # URL-Slug erstellen
        clean_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
        clean_title = re.sub(r'\s+', '-', clean_title)
        url_slug = f"{date}-{clean_title}"[:100]
        
        # Markdown erstellen
        md = f"""---
title: "{title}"
collection: publications
category: manuscripts
permalink: /publication/{url_slug}
date: {date}
venue: '{venue}'
"""
        
        if url:
            md += f"paperurl: '{url}'\n"
        
        md += "---\n\n"
        
        if work_data.get('citation'):
            md += f"{work_data['citation']}\n\n"
        
        if url:
            md += f"[Zur Publikation]({url})\n"
        
        return md, url_slug
    
    def sync(self):
        """
        Führt die vollständige Synchronisation durch.
        """
        print(f"Synchronisiere ORCID {self.orcid_id}...")
        
        # Publikationen abrufen
        works = self.fetch_works()
        print(f"{len(works)} Publikationen gefunden")
        
        # Output-Verzeichnis erstellen
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Markdown-Dateien erstellen
        for work in works:
            work_data = self.parse_work(work)
            md_content, url_slug = self.create_markdown(work_data)
            
            filename = f"{url_slug}.md"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            print(f"✓ {work_data['title'][:60]}...")
        
        print(f"\n✓ Synchronisation abgeschlossen!")
        print(f"  {len(works)} Publikationen nach {self.output_dir} exportiert")


def main():
    """
    Hauptfunktion für die ORCID-Synchronisation.
    """
    # Deine ORCID-ID
    ORCID_ID = "0009-0000-9669-4294"
    
    # Ausgabeverzeichnis
    OUTPUT_DIR = "_publications"
    
    # Synchronisation durchführen
    sync = ORCIDSync(ORCID_ID, OUTPUT_DIR)
    sync.sync()


if __name__ == "__main__":
    main()
