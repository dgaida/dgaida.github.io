# colloquium_creator/utils.py
"""Small utility helpers."""

import glob
import os
from typing import Optional, Tuple


def split_student_name(full_name: str) -> Tuple[str, str]:
    """Split a student's full name into first and last name.

    Handles formats like "Last, First" or "First Last".

    Args:
        full_name: The complete name string.

    Returns:
        Tuple of (first_name, last_name).
    """
    if not full_name:
        return "Student", "Name"

    if "," in full_name:
        last_name, first_name = full_name.split(",", 1)
        return first_name.strip(), last_name.strip()

    parts = full_name.split()
    if len(parts) > 1:
        first_name = " ".join(parts[:-1])
        last_name = parts[-1]
        return first_name, last_name

    return full_name, "Name"


def find_latest_tex(
    folder: str, pattern: str = "bewertung_brief_*.tex"
) -> Optional[str]:
    """Find the most recently modified TeX file in a folder matching a pattern.

    This function searches for files in the given folder whose names match
    a specified glob pattern (e.g., ``bewertung_brief_*.tex``). If one or more
    files match, the function returns the path to the file with the most
    recent modification time. If no files match, it returns ``None``.

    Args:
        folder: Path to the folder where TeX files are searched.
        pattern: Glob pattern for matching file names.
            Defaults to ``"bewertung_brief_*.tex"``.

    Returns:
        The absolute path to the newest matching TeX file as a string,
        or ``None`` if no file matches the pattern.

    Raises:
        None directly, but errors may propagate if:
            * The provided folder does not exist.
            * There are permission issues when accessing the folder.

    Example:
        >>> find_latest_tex("/tmp", "bewertung_brief_*.tex")
        '/tmp/bewertung_brief_12345.tex'

    Notes:
        - The "newest" file is determined by the last modification time
          (`os.path.getmtime`).
        - The function returns an absolute path suitable for further processing,
          e.g., compilation with LuaLaTeX.
    """
    pat = os.path.join(folder, pattern)
    matches = glob.glob(pat)
    if not matches:
        return None
    return max(matches, key=os.path.getmtime)
