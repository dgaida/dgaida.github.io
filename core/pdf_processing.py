# src/academic_doc_generator/core/pdf_processing.py
"""PDF processing utilities (Docling + pypdf) with comprehensive type annotations."""

from typing import Dict, List, Tuple, Optional
import re
from pypdf import PdfReader
from docling_parse.pdf_parser import DoclingPdfParser
from docling_core.types.doc.page import TextCellUnit
from .types import (
    WordBox,
    AnnotationContext,
    CommentStats,
    CommentCategory,
    AnnotationData,
)

# ============================================================================
# Type Definitions
# ============================================================================
# Redundant type definitions removed to avoid F811.
# Using definitions from .types instead.


# ============================================================================
# Public Functions
# ============================================================================


def extract_text_with_positions(pdf_path: str) -> Dict[int, List[WordBox]]:
    """Extract text and bounding boxes for words from a PDF using Docling.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Dictionary mapping 0-based page indices to a list of words with bounding boxes.

    Example:
        >>> words = extract_text_with_positions("thesis.pdf")
        >>> words[0][0]
        {'text': 'Introduction', 'bbox': (72.0, 720.0, 150.0, 735.0)}
    """
    parser = DoclingPdfParser()
    pdf_doc = parser.load(path_or_stream=pdf_path)

    pages_words: Dict[int, List[WordBox]] = {}

    # Enumerate to force 0-based indexing, regardless of docling's page_no (1-based)
    for zero_idx, (_page_no, pred_page) in enumerate(pdf_doc.iterate_pages(), start=0):
        words: List[WordBox] = []
        for cell in pred_page.iterate_cells(unit_type=TextCellUnit.WORD):
            r = (
                cell.rect
            )  # BoundingRectangle with r_x0, r_y0, r_x1, r_y1 (bottom-left origin)

            words.append(
                {
                    "text": cell.text,
                    "bbox": (
                        float(r.r_x0),
                        float(r.r_y0),
                        float(r.r_x1),
                        float(r.r_y1),
                    ),
                }
            )
        pages_words[zero_idx] = words

    return pages_words


def is_quelle_comment(text: str, max_length: int = 20) -> bool:
    """Check if a comment is a source-related comment that should be counted but not rewritten.

    Source comments (containing "Quelle" or "source") are counted in statistics but not
    sent to the LLM for rewriting. They must be short (≤max_length characters) and contain
    the keyword as a whole word (not part of another word like "Consequent").

    Args:
        text: The comment text to check.
        max_length: Maximum length for a comment to be considered a Quelle comment.
            Defaults to 20 characters.

    Returns:
        True if this is a source-related comment, False otherwise.

    Examples:
        >>> is_quelle_comment("Quelle?")
        True
        >>> is_quelle_comment("Source missing")
        True
        >>> is_quelle_comment("Consequent")  # Not a whole word match
        False
        >>> is_quelle_comment("Quelle fehlt hier an dieser Stelle komplett")
        False  # Too long
    """
    # Normalize text
    normalized = text.strip().lower()

    # Check length constraint
    if len(normalized) > max_length:
        return False

    # Check for "quelle" or "source" keywords using regex word boundaries
    quelle_pattern = r"\bquelle\b|\bsource\b"
    return bool(re.search(quelle_pattern, normalized, re.IGNORECASE))


def extract_annotations_with_positions(
    pdf_path: str, ignore_source: bool = True
) -> Tuple[Dict[int, List[AnnotationData]], CommentStats]:
    """Extract annotations (comments/highlights) and their positions using pypdf.

    Annotations are categorized for processing:
    - "llm": Regular comments sent to LLM for rewriting
    - "quelle": Source-related comments (counted only)
    - "language": Grammar/spelling comments (counted only)
    - "ignore": Special markers like "ab hier" (excluded from output)

    Args:
        pdf_path: Path to the PDF file.
        ignore_source: Whether to categorize source-related comments as "quelle".
            If False, they are treated as regular "llm" comments. Defaults to True.

    Returns:
        Tuple of (annotations, stats):
        - annotations: Dict mapping 0-based page indices to lists of annotations
        - stats: Comment category statistics

    Example:
        >>> annotations, stats = extract_annotations_with_positions("thesis.pdf")
        >>> stats
        {'quelle': 5, 'language': 3, 'ignore': 1}
        >>> annotations[0][0]['category']
        'llm'
    """
    reader = PdfReader(pdf_path)
    annotations: Dict[int, List[AnnotationData]] = {}
    stats: CommentStats = {"quelle": 0, "language": 0, "ignore": 0}

    for idx, page in enumerate(reader.pages):
        page_annots: List[AnnotationData] = []
        if "/Annots" in page:
            for annot_ref in page["/Annots"]:
                annot = annot_ref.get_object()
                subtype = annot.get("/Subtype")
                rect = annot.get("/Rect")
                quadpoints = annot.get("/QuadPoints")
                content = annot.get("/Contents")

                if content:
                    text = content.strip()
                    category: CommentCategory = "llm"  # default

                    # --- Categorize ---
                    # Check for "ab hier" first (highest priority, complete ignore)
                    if text.lower() == "ab hier":
                        category = "ignore"
                        stats["ignore"] += 1

                    # Check for "Quelle" comments
                    elif ignore_source and is_quelle_comment(text):
                        category = "quelle"
                        stats["quelle"] += 1

                    # Check for language-related comments
                    elif any(
                        kw in text.lower()
                        for kw in [
                            "rechtschreibung",
                            "grammatik",
                            "tippfehler",
                            "ausdruck",
                        ]
                    ):
                        category = "language"
                        stats["language"] += 1

                    page_annots.append(
                        {
                            "comment": text,
                            "subtype": subtype,
                            "rect": rect,
                            "quadpoints": quadpoints,
                            "category": category,
                        }
                    )

        if page_annots:
            annotations[idx] = page_annots

    return annotations, stats


def words_overlapping_rect(
    words: List[WordBox], rect: Tuple[float, float, float, float], tol: float = 0.5
) -> List[WordBox]:
    """Find all words that overlap with a given rectangle.

    Args:
        words: List of word dictionaries with 'text' and 'bbox'.
        rect: Annotation rectangle as (x0, y0, x1, y1).
        tol: Tolerance factor for overlap detection in points. Defaults to 0.5.

    Returns:
        List of words that overlap with the rectangle.

    Example:
        >>> words = [{'text': 'Hello', 'bbox': (10, 10, 50, 20)}]
        >>> rect = (5, 5, 55, 25)
        >>> overlapping = words_overlapping_rect(words, rect)
        >>> len(overlapping)
        1
    """
    x0, y0, x1, y1 = rect
    hits: List[WordBox] = []
    for w in words:
        wx0, wy0, wx1, wy1 = w["bbox"]
        if wx1 >= x0 - tol and wx0 <= x1 + tol and wy1 >= y0 - tol and wy0 <= y1 + tol:
            hits.append(w)
    return hits


def get_words_for_annotation_on_page(
    pages_words: Dict[int, List[WordBox]],
    page_index: int,
    rect: Tuple[float, float, float, float],
) -> Tuple[int, List[WordBox]]:
    """Get words that match an annotation rectangle, checking neighboring pages if necessary.

    Sometimes annotations appear on the wrong page in the PDF structure. This function
    checks the specified page first, then the next page (+1), then the previous page (-1).

    Args:
        pages_words: Dictionary of pages mapped to word lists.
        page_index: Index of the annotated page (0-based).
        rect: Annotation rectangle as (x0, y0, x1, y1).

    Returns:
        Tuple of (page_index_used, words) where page_index_used is the page
        where words were actually found, and words is the list of matching word dicts.

    Example:
        >>> pages_words = {0: [{'text': 'test', 'bbox': (10, 10, 50, 20)}]}
        >>> rect = (5, 5, 55, 25)
        >>> page_idx, words = get_words_for_annotation_on_page(pages_words, 0, rect)
        >>> page_idx
        0
        >>> len(words)
        1
    """
    # Try the given page, then +1, then -1
    candidates = [page_index, page_index + 1, page_index - 1]
    for idx in candidates:
        if idx in pages_words:
            hits = words_overlapping_rect(pages_words[idx], rect)
            if hits:
                return idx, hits
    # fall back to the original page even if empty
    return page_index, []


def rect_overlap(
    word_bbox: Tuple[float, float, float, float],
    annot_bbox: Tuple[float, float, float, float],
) -> bool:
    """Check if a word bounding box overlaps with an annotation rectangle.

    Args:
        word_bbox: Word bounding box as (x0, y0, x1, y1).
        annot_bbox: Annotation bounding box as (x0, y0, x1, y1).

    Returns:
        True if the bounding boxes overlap, False otherwise.

    Example:
        >>> rect_overlap((10, 10, 50, 20), (5, 5, 55, 25))
        True
        >>> rect_overlap((10, 10, 50, 20), (100, 100, 150, 120))
        False
    """
    x1, y1, x2, y2 = word_bbox
    ax1, ay1, ax2, ay2 = annot_bbox
    return not (x2 < ax1 or x1 > ax2 or y2 < ay1 or y1 > ay2)


def find_annotation_context(
    pages_words: Dict[int, List[WordBox]], annotations: Dict[int, List[AnnotationData]]
) -> Dict[int, List[AnnotationContext]]:
    """Match annotations to the words and paragraphs they reference.

    For each annotation, this function:
    1. Finds the words that overlap with the annotation's bounding box
    2. Extracts the highlighted text from those words
    3. Finds the paragraph containing the highlighted text
    4. Returns all context information for LLM processing

    Args:
        pages_words: Words with bounding boxes per page (0-based indices).
        annotations: Annotations per page with rects and comments (0-based indices).

    Returns:
        Dictionary mapping 1-based page numbers to lists of annotation contexts.
        Page numbers are 1-based for user display purposes.

    Example:
        >>> pages_words = {0: [{'text': 'test', 'bbox': (10, 10, 50, 20)}]}
        >>> annotations = {0: [{'comment': 'Why?', 'rect': [5, 5, 55, 25],
        ...                     'category': 'llm', 'subtype': '/Text', 'quadpoints': None}]}
        >>> context = find_annotation_context(pages_words, annotations)
        >>> context[1][0]['highlighted']
        'test'
    """
    context_dict: Dict[int, List[AnnotationContext]] = {}

    for page_num, annots in annotations.items():
        page_results: List[AnnotationContext] = []

        for annot in annots:
            rect = annot["rect"]
            if rect:
                annot_bbox = tuple(rect)
            elif annot["quadpoints"]:
                qp = annot["quadpoints"]
                xs = qp[0::2]
                ys = qp[1::2]
                annot_bbox = (min(xs), min(ys), max(xs), max(ys))
            else:
                continue

            # Words under the annotation (with neighbor-page fallback)
            page_idx_for_words, hit_words = get_words_for_annotation_on_page(
                pages_words, page_num, annot_bbox
            )
            highlighted_text = " ".join([w["text"] for w in hit_words]).strip()

            # Use the full text of the page where words were actually found
            full_page_text = " ".join(
                [w["text"] for w in pages_words.get(page_idx_for_words, [])]
            )
            paragraphs = re.split(r"\n\s*\n| {2,}", full_page_text)

            # Find paragraph containing the highlighted words
            para_match: Optional[str] = None
            for para in paragraphs:
                if highlighted_text and highlighted_text in para:
                    para_match = para
                    break

            if not para_match and paragraphs:
                para_match = paragraphs[0]  # fallback

            page_results.append(
                {
                    "comment": annot["comment"],
                    "highlighted": highlighted_text,
                    "paragraph": para_match if para_match else "",
                    "category": annot.get("category", "llm"),
                }
            )

        if page_results:
            # +1 so reported page number is human-readable (1-based)
            context_dict[page_num + 1] = page_results

    return context_dict


def extract_text_per_page(pdf_path: str, max_pages: int = 10) -> Dict[int, str]:
    """Extract plain text (without positions) for the first `max_pages` pages.

    This is faster than extracting word positions and is sufficient for metadata
    extraction and thesis summarization.

    Args:
        pdf_path: Path to the PDF file.
        max_pages: Maximum number of pages to read. Defaults to 10.

    Returns:
        Dictionary mapping 0-based page indices to the full concatenated text
        of that page.

    Example:
        >>> text = extract_text_per_page("thesis.pdf", max_pages=2)
        >>> text[0][:50]
        'Introduction This thesis examines the impact of...'
    """
    parser = DoclingPdfParser()
    pdf_doc = parser.load(path_or_stream=pdf_path)

    pages_text: Dict[int, str] = {}
    for zero_idx, (_page_no, pred_page) in enumerate(pdf_doc.iterate_pages(), start=0):
        if zero_idx >= max_pages:
            break
        words = [
            cell.text for cell in pred_page.iterate_cells(unit_type=TextCellUnit.WORD)
        ]
        page_text = " ".join(words)
        pages_text[zero_idx] = page_text
    return pages_text
