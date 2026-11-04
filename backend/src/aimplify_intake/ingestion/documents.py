"""Document text extraction from request-scoped memory buffers."""

from __future__ import annotations

from io import BytesIO

from docx import Document
from pptx import Presentation
from PyPDF2 import PdfReader


def extract_pdf(source: BytesIO) -> str:
    if not isinstance(source, BytesIO):
        raise TypeError("PDF input must be an in-memory buffer.")
    reader = PdfReader(source, strict=True)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_docx(source: BytesIO) -> str:
    if not isinstance(source, BytesIO):
        raise TypeError("DOCX input must be an in-memory buffer.")
    document = Document(source)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    tables = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    return "\n".join(paragraphs + tables)


def extract_pptx(source: BytesIO) -> str:
    if not isinstance(source, BytesIO):
        raise TypeError("PPTX input must be an in-memory buffer.")
    presentation = Presentation(source)
    return "\n".join(
        shape.text
        for slide in presentation.slides
        for shape in slide.shapes
        if getattr(shape, "has_text_frame", False)
    )