"""LaTeX generation and helper functions."""

from typing import Dict, Optional
import os
import subprocess
import unicodedata


def escape_for_latex(text: str, preserve_latex: bool = True) -> str:
    """Escape LaTeX-special characters and normalize dash-like unicode chars.

    Args:
        text (str): Input string (may contain Unicode dashes).
        preserve_latex (bool, optional):
            - True: keep LaTeX commands, replace dash-like chars with "{-}".
            - False: escape all LaTeX specials, normalize dash-like chars to "-".
            Defaults to True.

    Returns:
        str: LaTeX-safe string.
    """
    if text is None:
        return ""

    text = unicodedata.normalize("NFKC", text)

    # Remove invisible chars (soft hyphen, zero-width spaces, etc.)
    for ch in ("\u00ad", "\u200b", "\u200c", "\u200d", "\ufeff"):
        text = text.replace(ch, "")

    # Replace dash-like characters
    if preserve_latex:
        dash_replacement = "{-}"
    else:
        dash_replacement = "-"  # plain ASCII hyphen is fine in LaTeX
    out_chars = []
    for ch in text:
        if unicodedata.category(ch) == "Pd":  # any punctuation-dash
            out_chars.append(dash_replacement)
        elif ch == "ß":
            out_chars.append(r"{\ss}")  # German sharp s
        else:
            out_chars.append(ch)
    text = "".join(out_chars)

    # Escape LaTeX specials
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "„": r"``",
        "“": r"''",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    if not preserve_latex:
        # Escape braces and backslashes in plain text
        text = text.replace("{", r"\{").replace("}", r"\}")
        text = text.replace("\\", r"\textbackslash{}")

    return text


def return_seite_page(lang: str) -> str:
    """Returns 'Seite' if German, 'page' if English.

    Args:
        lang (str): English or German

    Returns:
        str: "Seite" if German, "page" if English.
    """
    return "Seite" if lang.lower().startswith("german") else "page"


def create_formal_letter_tex(
    filename: str,
    recipient: str,
    subject: str,
    title: str,
    author: str,
    summary: str,
    first_examiner: str,
    second_examiner: str,
    first_examiner_mail: str,
    questions: str,
    place: str = "Gummersbach",
    date: str = r"\today",
    gemini_evaluation: Optional[str] = None,
):
    """Create a LaTeX file for a formal letter with TH Köln footer.

    Args:
        filename (str): Output path for the LaTeX file.
        recipient (str): Recipient of the letter.
        subject (str): Subject line.
        title (str): Thesis title.
        author (str): Author name and matriculation number.
        summary (str): summary of the thesis.
        first_examiner (str): name of first examiner.
        second_examiner (str): name of second examiner.
        first_examiner_mail (str): email of first examiner.
        questions (str): questions from first examiner.
        place (str, optional): Place of issue. Defaults to "Gummersbach".
        date (str, optional): Date string. Defaults to LaTeX \today.
        gemini_evaluation (str, optional): Automatische Bewertung von Gemini.
    """
    # Füge Gemini-Bewertung hinzu, falls vorhanden
    gemini_section = ""
    if gemini_evaluation:
        gemini_section = f"\n\n{gemini_evaluation}\n"

    tex_template = rf"""
\documentclass[11pt,ngerman,parskip=full]{{scrlttr2}}
\usepackage{{fontspec}}
\setmainfont{{Latin Modern Roman}}
\usepackage[ngerman]{{babel}}
\usepackage{{geometry}}
\geometry{{a4paper, top=25mm, left=25mm, right=25mm, bottom=30mm}}
\usepackage{{url}}

% Sender info
\setkomavar{{fromname}}{{{first_examiner}}}
\setkomavar{{fromaddress}}{{Steinmüllerallee 1\\51643 Gummersbach}}
\setkomavar{{fromphone}}{{+49 2261-8196-6204}}
\setkomavar{{fromemail}}{{{first_examiner_mail}}}
\setkomavar{{place}}{{{place}}}
\setkomavar{{date}}{{{date}}}
\setkomavar{{signature}}{{{first_examiner}}}
\setkomavar{{subject}}{{{escape_for_latex(subject, preserve_latex=False)}}}

% Footer
\setkomavar{{firstfoot}}{{%
  \parbox[t]{{\textwidth}}{{\footnotesize
    Technische Hochschule Köln, Campus Gummersbach \\
    Sitz des Präsidiums: Claudiusstrasse 1, 50678 Köln \\
    www.th-koeln.de \\
    Steuer-Nr.: 214/5817/3402 - USt-IdNr.: DE 122653679 \\
    Bankverbindung: Sparkasse KölnBonn \\
    IBAN: DE34 3705 0198 1900 7098 56 - BIC: COLSDE33
  }}
}}

\begin{{document}}

\begin{{letter}}{{{escape_for_latex(recipient, preserve_latex=False)}}}

\opening{{Sehr geehrte Damen und Herren,}}

Bewertung folgender Thesis:\\[1ex]

\textbf{{Titel:}} {escape_for_latex(title, preserve_latex=False)} \\[1ex]
\textbf{{Autor:}} {escape_for_latex(author, preserve_latex=False)} \\[2ex]

\textbf{{Zusammenfassung der Thesis:}} \\

{summary}


\textbf{{Protokoll des Kolloquiums:}}\\[1ex]

\textbf{{Fragen {first_examiner}:}}\\

{questions}\\


\textbf{{Fragen {second_examiner}:}}\\

\textbf{{Vortrag:}} xx Minuten\\

Bewertung des Vortrags:

1. Inhaltliche Qualität & Struktur:

Kriterien:
\begin{{itemize}}
\item Verständlichkeit von Ziel, Problemstellung und Ergebnissen
\item Fachliche Richtigkeit
\item Logischer Aufbau, klarer roter Faden, sinnvolle Schwerpunktsetzung
\item Einhaltung der Zeit
\end{{itemize}}

Bewertung der Kriterien:

\begin{{itemize}}
\item sehr gut
\item gut
\item befriedigend
\item ausreichend
\end{{itemize}}

2. Darstellung & Visualisierung:

Kriterien:
\begin{{itemize}}
\item Unterstützung des Vortrags durch Folien und Visualisierungen
\item Übersichtlichkeit und Angemessenheit der Gestaltung
\item Verständliche Vermittlung auch komplexer Inhalte
\end{{itemize}}

Bewertung der Kriterien:

\begin{{itemize}}
\item sehr gut
\item gut
\item befriedigend
\item ausreichend
\end{{itemize}}

3. Präsentation & Auftreten:

Kriterien:
\begin{{itemize}}
\item Freier, sicherer und verständlicher Vortrag (Sprache, Tempo, Körpersprache)
\item Souveräner Umgang mit Fragen
\item Kritische Reflexion der eigenen Arbeit (Stärken, Grenzen, Ausblick)
\end{{itemize}}

Bewertung der Kriterien:

\begin{{itemize}}
\item sehr gut
\item gut
\item befriedigend
\item ausreichend
\end{{itemize}}

Demo:
\begin{{itemize}}
\item ja, live
\item ja, live, aber Fehlerhaft/nicht so gut
\item ja, Video
\item nein
\item nicht möglich
\end{{itemize}}

Fragen konnten beantwortet werden:
\begin{{itemize}}
\item sehr gut
\item sehr gut, manche gut
\item gut
\item gut, manche nicht so gut
\item viele nicht so gut oder gar nicht
\end{{itemize}}

.\\[2ex]

Dauer des Kolloquiums: 45 Minuten
{gemini_section}

\closing{{Mit freundlichen Grü{{\ss}}en}}

\end{{letter}}

\end{{document}}
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(tex_template)
    print(f"LaTeX file created: {filename}")


def concatenate_comments(
    results: Dict[int, list], language: str, verbose: bool = False
) -> str:
    """Concatenate rewritten comments into a LaTeX-formatted string.

    Each comment is prefixed with the page number and separated by two
    LaTeX line breaks (\\\\ \\\\) for readability.

    Args:
        results (dict): Dictionary mapping page numbers to lists of rewritten
            comment dictionaries (as returned by `rewrite_comments_in_pdf`).
        language (str): Language of the comments ("German" or "English") to
            determine whether "Seite" or "page" is used as the prefix.
        verbose (bool, optional): If True, prints the concatenated comments.
            Defaults to False.

    Returns:
        str: A LaTeX-ready string with all rewritten comments, separated by
        two line breaks and labeled with their page numbers.
    """
    seite_page = return_seite_page(language)

    questions = " \\\\\n\\\\\n".join(
        f"{seite_page} {page}: {item['rewritten']}"
        for page, items in results.items()
        for item in items
    )

    if verbose:
        print(questions)

    return questions


def compile_latex_to_pdf(
    tex_path: str, output_dir: str = None, engine: str = "lualatex"
) -> str:
    """Compile a LaTeX file into a PDF using pdflatex.

    Args:
        tex_path (str): Path to the .tex file.
        output_dir (str, optional): Directory for the PDF. Defaults to same as tex file.
        engine (str, optional): "lualatex" or "pdflatex"

    Returns:
        str: Path to the generated PDF.
    """
    if output_dir is None:
        output_dir = os.path.dirname(tex_path)

    cmd = [
        engine,
        "-interaction=nonstopmode",
        f"-output-directory={output_dir}",
        tex_path,
    ]

    subprocess.run(cmd, check=True)

    pdf_path = os.path.join(
        output_dir, os.path.splitext(os.path.basename(tex_path))[0] + ".pdf"
    )
    return pdf_path
