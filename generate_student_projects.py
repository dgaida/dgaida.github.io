import os
import re
import json
from datetime import datetime
from academic_doc_generator.core import llm_interface, pdf_processing
from llm_client import LLMClient

# Configuration
BASE_PATHS = ["BachelorThesen", "MasterThesen", "PraxisProjekte"]
OUTPUT_DIR = "_student_projects"

TYPE_MAPPING = {
    "BachelorThesen": "Bachelorthesis",
    "MasterThesen": "Masterthesis",
    "PraxisProjekte": "Praxisprojekt"
}


def get_semester_name(folder_name):
    folder_name_upper = folder_name.upper()
    # Wintersemester
    if 'WS' in folder_name_upper:
        # Match years like 2025_26, 25_26, 25-26
        match = re.search(r'(\d{2,4})[_-](\d{2})', folder_name_upper)
        if match:
            y1, y2 = match.groups()
            if len(y1) == 4: y1 = y1[2:]
            return f"Wintersemester {y1}/{y2}"
        # Match WS2526
        match = re.search(r'WS(\d{2})(\d{2})', folder_name_upper)
        if match:
            y1, y2 = match.groups()
            return f"Wintersemester {y1}/{y2}"
        # Fallback for folder like 2025WS
        match = re.search(r'(\d{2,4})', folder_name_upper)
        if match:
            y = match.group(1)
            if len(y) == 4: y = y[2:]
            return f"Wintersemester {y}"
    # Sommersemester
    if 'SOSE' in folder_name_upper or 'SS' in folder_name_upper or 'SOMMER' in folder_name_upper:
        match = re.search(r'(\d{2,4})', folder_name_upper)
        if match:
            y = match.group(1)
            if len(y) == 4: y = y[2:]
            return f"Sommersemester {y}"
    return folder_name


def get_initials(name):
    if not name or name == "Unknown Author":
        return "U. A."
    # Replace hyphens with spaces to treat as separate parts
    name_clean = name.replace("-", " ")
    parts = name_clean.split()
    initials = [p[0].upper() + "." for p in parts if p]
    return " ".join(initials)


def get_author_slug(name):
    if not name or name == "Unknown Author":
        return "unkn"
    # Replace hyphens with spaces
    name_clean = name.replace("-", " ")
    parts = name_clean.split()
    if len(parts) >= 2:
        first = parts[0][:2].lower()
        last = parts[-1][:2].lower()
        return first + last
    elif len(parts) == 1:
        return parts[0][:4].lower()
    return "unkn"


def summarize_for_web(pages_text, llm_client):
    full_text = "\n\n".join([pages_text.get(i, "") for i in sorted(pages_text.keys())])
    prompt = f"""
You are given the first ten pages of a student's thesis or project report. 
Please provide a very concise summary (2-3 sentences) in English that is suitable for publication on a website.
It should be easy to understand for a general audience. Do not write 'A student ...' or mention the student's name, but use passive voice instead.

Text:
{full_text}

Summary:
"""
    messages = [{"role": "user", "content": prompt}]
    return llm_client.chat_completion(messages).strip()


def process_pdf(pdf_path, llm_client):
    print(f"Processing PDF: {pdf_path}")

    # Extract plain text for metadata and summary
    pages_text = pdf_processing.extract_text_per_page(pdf_path)

    # Extract metadata
    metadata = llm_interface.extract_document_metadata(pages_text, "German", llm_client, pdf_path=pdf_path)

    # Generate summary
    summary = summarize_for_web(pages_text, llm_client)

    # Get last modified date
    mtime = os.path.getmtime(pdf_path)
    date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

    return {
        "title": metadata.get("title", "Unknown Title"),
        "author": metadata.get("author", "Unknown Author"),
        "date": date_str,
        "summary": summary
    }

def main():
    llm_client = LLMClient()

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for base_path_i in BASE_PATHS:
        base_path = os.path.join("..", "BachelorMasterThesen", base_path_i)

        if not os.path.exists(base_path):
            print(f"Path not found: {base_path}")
            continue

        work_type = TYPE_MAPPING.get(base_path_i, "Other")

        for semester_folder in os.listdir(base_path):
            semester_path = os.path.join(base_path, semester_folder)
            if not os.path.isdir(semester_path):
                continue

            semester_name = get_semester_name(semester_folder)

            for student_folder in os.listdir(semester_path):
                student_path = os.path.join(semester_path, student_folder)
                if not os.path.isdir(student_path):
                    continue

                # Look for JSON file
                json_file = None
                for f in os.listdir(student_path):
                    if f.endswith(".json"):
                        json_file = os.path.join(student_path, f)
                        break

                if not json_file:
                    continue

                print(f"Found JSON: {json_file}")
                with open(json_file, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        print(f"Error decoding JSON: {json_file}")
                        continue

                pdf_info = data.get("pdf")
                if not pdf_info or "filename" not in pdf_info:
                    continue

                pdf_filename = pdf_info["filename"]
                pdf_path = os.path.join(student_path, pdf_filename)

                if not os.path.exists(pdf_path):
                    print(f"PDF not found: {pdf_path}")
                    continue

                result = process_pdf(pdf_path, llm_client)

                full_author = result.get('author', "Unknown Author")
                initials = get_initials(full_author)
                author_slug = get_author_slug(full_author)

                summary = result.get('summary', "")
                if full_author != "Unknown Author":
                    summary = summary.replace(full_author, initials)

                # Create .md filename
                # format: {year}_{semester}_{author_slug}.md
                year = result['date'][:4]
                md_filename = f"{year}_{semester_folder.lower()}_{base_path_i[:2].lower()}_{author_slug}.md"
                md_path = os.path.join(OUTPUT_DIR, md_filename)

                content = f"""---
title: "{result['title']}"
author: "{initials}"
date: "{result['date']}"
excerpt: |
  {summary}
collection: student_projects
type: "{work_type}"
semester: "{semester_name}"
---

{summary}
"""
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Generated: {md_path}")


if __name__ == "__main__":
    main()
