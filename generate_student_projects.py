import os
import re
import json
from datetime import datetime
from academic_doc_generator.core import llm_interface, pdf_processing, web_metadata
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




def process_pdf(pdf_path, llm_client):
    print(f"Processing PDF: {pdf_path}")

    # Extract plain text for metadata and summary
    pages_text = pdf_processing.extract_text_per_page(pdf_path)

    # Extract metadata
    metadata = llm_interface.extract_document_metadata(pages_text, "German", llm_client, pdf_path=pdf_path)

    # Get last modified date
    mtime = os.path.getmtime(pdf_path)
    date_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

    return pages_text, metadata, date_str

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

                pages_text, metadata, date_str = process_pdf(pdf_path, llm_client)

                # Generate web metadata file using the library method
                md_path = web_metadata.generate_web_metadata_file(
                    output_folder=OUTPUT_DIR,
                    title=metadata.get("title", "Unknown Title"),
                    author=metadata.get("author", "Unknown Author"),
                    pages_text=pages_text,
                    llm_client=llm_client,
                    work_type=work_type,
                    semester=semester_name,
                    date_str=date_str
                )
                print(f"Generated: {md_path}")


if __name__ == "__main__":
    main()
