import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional
import academic_doc_generator.core.web_metadata as web_metadata

# Konfiguration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BASE_DIRS = ["BachelorThesen", "MasterThesen", "PraxisProjekte"]
OUTPUT_DIR = Path("_student_projects")

# Keyword Mapping für automatische Tags
KEYWORD_TAGS = {
    "KI": ["KI", "Künstliche Intelligenz", "Artificial Intelligence", "Neural", "Deep Learning", "Machine Learning", "LLM", "GPT"],
    "Robotik": ["Robotik", "Robot", "Cobot", "Manipulation", "Greifer"],
    "Web": ["Web", "Frontend", "Backend", "React", "Angular", "Vue", "JavaScript", "TypeScript", "App"],
    "Data Science": ["Data Science", "Datenanalyse", "Visualisierung", "Big Data", "Analytics"],
    "Software Engineering": ["Software Engineering", "Architektur", "Entwicklung", "Testing", "DevOps"],
    "IoT": ["IoT", "Internet of Things", "Sensor", "Embedded"],
}

def extract_tags(text: str) -> List[str]:
    """Extrahiert Tags basierend auf Keywords im Text."""
    tags = set()
    text_lower = text.lower()
    for tag, keywords in KEYWORD_TAGS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                tags.add(tag)
                break
    return sorted(list(tags))

def process_projects():
    if not GROQ_API_KEY:
        print("Fehler: GROQ_API_KEY nicht gesetzt.")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)

    for base_dir_name in BASE_DIRS:
        base_path = Path(base_dir_name)
        if not base_path.exists():
            continue

        print(f"Verarbeite Verzeichnis: {base_dir_name}")

        # Gehe durch Semester-Ordner
        for semester_path in base_path.iterdir():
            if not semester_path.is_dir():
                continue

            # Gehe durch Projekt-Ordner
            for student_path in semester_path.iterdir():
                if not student_path.is_dir():
                    continue

                print(f"Verarbeite Projekt: {student_path}")

                # Finde JSON-Datei
                json_files = list(student_path.glob("*.json"))
                if not json_files:
                    continue

                json_file = json_files[0]
                print(f"Gefunden: {json_file}")

                with json_file.open('r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        print(f"Fehler beim Lesen von JSON: {json_file}")
                        continue

                # Finde PDF-Datei
                pdf_files = list(student_path.glob("*.pdf"))
                pdf_path = pdf_files[0] if pdf_files else None

                # Metadaten vorbereiten
                author = data.get("author", "Unbekannt")
                title = data.get("title", "Kein Titel")
                date = data.get("date", "")

                # Typ basierend auf Ordnerstruktur
                project_type = base_dir_name[:-2] if base_dir_name.endswith("en") else base_dir_name
                if project_type == "PraxisProjekte": project_type = "Praxisprojekt"

                semester = semester_path.name

                # Tags extrahieren
                tags = extract_tags(title + " " + data.get("abstract", ""))

                # Generiere Web-Metadaten (dies nutzt die academic_doc_generator Lib)
                # Die Lib schreibt die Datei direkt
                try:
                    # Wir nutzen die Lib-Funktion, müssen aber evtl. Tags danach einfügen
                    # da die Standard-Lib diese vielleicht nicht unterstützt.
                    md_file_path = web_metadata.generate_web_metadata_file(
                        author=author,
                        title=title,
                        date=date,
                        abstract=data.get("abstract", ""),
                        type=project_type,
                        semester=semester,
                        output_dir=str(OUTPUT_DIR)
                    )

                    # Post-Processing: Tags in Frontmatter einfügen
                    if md_file_path and os.path.exists(md_file_path) and tags:
                        with open(md_file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()

                        # Suche nach dem zweiten ---
                        dash_count = 0
                        new_lines = []
                        for line in lines:
                            new_lines.append(line)
                            if line.strip() == "---":
                                dash_count += 1
                                if dash_count == 1:
                                    # Füge Tags nach dem ersten --- ein
                                    new_lines.append(f"tags: {json.dumps(tags)}\n")

                        with open(md_file_path, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)

                except Exception as e:
                    print(f"Fehler bei Generierung für {author}: {e}")

if __name__ == "__main__":
    process_projects()
