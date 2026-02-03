# src/academic_doc_generator/core/types.py
"""Common type definitions for academic-doc-generator.

This module provides TypedDicts and type aliases for complex data structures
used throughout the package, improving type safety and IDE support.
"""

from typing import TypedDict, Literal, Optional, Tuple, Protocol, List, Dict

# ==============================================================================
# Literals for constrained string values
# ==============================================================================

LocationType = Literal["campus", "company", "online"]
"""Type of colloquium location."""

CommentCategory = Literal["llm", "quelle", "language", "ignore"]
"""Category of PDF annotation comment."""

DegreeType = Literal["Bachelor", "Master"]
"""Type of academic degree."""

GenderType = Literal["Herr", "Frau", "Herr/Frau"]
"""Formal German address form."""

# ==============================================================================
# Bounding Box Types
# ==============================================================================

BBox = Tuple[float, float, float, float]
"""Bounding box as (x0, y0, x1, y1) in PDF coordinates (bottom-left origin)."""


# ==============================================================================
# Protocols for Flexible Interfaces
# ==============================================================================


class LLMClientProtocol(Protocol):
    """Protocol defining the interface for LLM clients.

    This allows for flexible LLM implementations and easier testing with mocks.

    Attributes:
        api_choice: The API provider being used (e.g., "openai", "groq").
        llm: The specific model name being used.
    """

    api_choice: str
    llm: str

    def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            The LLM's response text.
        """
        ...


# ==============================================================================
# PDF Processing Types
# ==============================================================================


class WordBox(TypedDict):
    """A word extracted from a PDF with its bounding box."""

    text: str
    bbox: BBox


class AnnotationData(TypedDict):
    """Raw annotation data extracted from PDF."""

    comment: str
    subtype: str
    rect: Optional[BBox]
    quadpoints: Optional[List[float]]
    category: CommentCategory


class AnnotationContext(TypedDict):
    """Annotation with surrounding context from the document."""

    comment: str
    highlighted: str
    paragraph: str
    category: CommentCategory


class AnnotationWithLine(AnnotationContext):
    """Annotation context with line number for review generation."""

    line: int


class CommentStats(TypedDict):
    """Statistics about comment categories in a document."""

    quelle: int
    language: int
    ignore: int


# ==============================================================================
# LLM Processing Types
# ==============================================================================


class RewrittenComment(TypedDict):
    """A comment that has been rewritten by the LLM."""

    original: str
    rewritten: Optional[str]  # None if category != "llm"
    highlighted: str
    paragraph: str
    category: CommentCategory


class RewrittenReviewComment(TypedDict):
    """A review comment rewritten for peer review with line info."""

    original: str
    rewritten: str
    line: int
    page: int


# ==============================================================================
# Metadata Types
# ==============================================================================


class ThesisMetadata(TypedDict, total=False):
    """Metadata extracted from a thesis PDF.

    Note: total=False allows all fields to be optional.
    """

    author: Optional[str]
    matriculation_number: Optional[str]
    title: Optional[str]
    first_examiner: Optional[str]
    second_examiner: Optional[str]
    first_examiner_christian: Optional[str]
    first_examiner_family: Optional[str]
    bachelor_master: Optional[DegreeType]


class ProjectMetadata(TypedDict, total=False):
    """Metadata extracted from a project work PDF."""

    student_name: Optional[str]
    student_first_name: Optional[str]
    matriculation_number: Optional[str]
    title: Optional[str]
    first_examiner: Optional[str]
    first_examiner_christian: Optional[str]
    first_examiner_family: Optional[str]
    work_type: Optional[str]
    student_email: Optional[str]


# ==============================================================================
# Configuration Types
# ==============================================================================


class LLMConfig(TypedDict, total=False):
    """LLM configuration settings."""

    api_choice: Optional[str]
    model: Optional[str]
    groq_free: bool


class OutputConfig(TypedDict, total=False):
    """Output configuration settings."""

    folder: Optional[str]
    compile_pdf: bool
    fill_form_only: bool
    signature_file: Optional[str]
    create_feedback_mail: bool


class ColloquiumConfig(TypedDict, total=False):
    """Configuration for colloquium tasks."""

    date: str  # Format: DD.MM.YYYY
    time: str  # Format: HH:MM
    location_type: LocationType
    room: Optional[str]  # Required if location_type="campus"
    company_name: Optional[str]  # Required if location_type="company"
    company_address: Optional[str]  # Optional for company
    zoom_link: Optional[str]  # Required if location_type="online"
    zoom_meeting_access: Optional[str]  # Optional for online


class GeminiEvaluationConfig(TypedDict, total=False):
    """Configuration for Gemini automatic evaluation."""

    enabled: bool
    model: Optional[str]


class PDFConfig(TypedDict):
    """PDF file configuration."""

    filename: str


# ==============================================================================
# Pipeline Result Types
# ==============================================================================

ColloquiumResult = Tuple[str, str, str]
"""Result of colloquium pipeline: (tex_path, pdf_path, email_path)."""

ProjectResult = Tuple[str, str, str, str]
"""Result of project pipeline: (tex_path, pdf_path, service_email_path, student_email_path)."""

ReviewResult = str
"""Result of review pipeline: markdown_path."""

# ==============================================================================
# Type Aliases for Common Patterns
# ==============================================================================

PageWords = Dict[int, List[WordBox]]
"""Mapping of page indices (0-based) to lists of words."""

PageAnnotations = Dict[int, List[AnnotationData]]
"""Mapping of page indices (0-based) to lists of annotations."""

PageContexts = Dict[int, List[AnnotationContext]]
"""Mapping of page numbers (1-based) to annotation contexts."""

RewrittenComments = Dict[int, List[RewrittenComment]]
"""Mapping of page numbers (1-based) to rewritten comments."""

PageText = Dict[int, str]
"""Mapping of page indices (0-based) to full text content."""
