"""Document text extraction from request-scoped memory buffers."""

from __future__ import annotations

import ctypes
import threading
from io import BytesIO

from docx import Document
from pptx import Presentation
from pypdf import PdfReader, apply_configuration
from pypdf.errors import DependencyError

MAX_PDF_PAGES = 500
MAX_PDF_STREAM_BYTES = 10 * 1024 * 1024
MAX_PDF_CONTENT_BYTES = 64 * 1024 * 1024
MAX_PDF_TEXT_CHARS = 1_000_000
MAX_PDF_SECONDS = 10.0


class _PdfLimitExceeded(BaseException):
    """Raised inside pypdf; a BaseException so pypdf's ``except Exception`` cannot swallow it."""


class _PdfLimitExceededTime(_PdfLimitExceeded):
    def __str__(self) -> str:
        return "PDF exceeds the processing time limit."


def extract_pdf(source: BytesIO) -> str:
    if not isinstance(source, BytesIO):
        raise TypeError("PDF input must be an in-memory buffer.")
    try:
        return _extract_pdf_text(source)
    except _PdfLimitExceeded as error:
        raise ValueError(str(error)) from None
    except DependencyError:
        # pypdf needs an optional decoder (e.g. JBIG2, which is disabled above).
        raise ValueError("PDF uses an unsupported feature.") from None


def _set_async_exc(thread_id: int, exc: type[BaseException] | None) -> None:
    ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread_id), ctypes.py_object(exc) if exc else None
    )


def _extract_pdf_text(source: BytesIO) -> str:
    thread_id = threading.get_ident()
    deadline_lock = threading.Lock()
    deadline_active = True
    streamed_chars = 0

    # On expiry, raise _PdfLimitExceeded in this thread at its next bytecode,
    # which interrupts any pypdf loop, including ones with no visitor callback.
    def expire() -> None:
        with deadline_lock:
            if deadline_active:
                _set_async_exc(thread_id, _PdfLimitExceededTime)

    def count_text(text: str, *_args: object) -> None:
        nonlocal streamed_chars
        streamed_chars += len(text)
        if streamed_chars > MAX_PDF_TEXT_CHARS:
            raise _PdfLimitExceeded("PDF exceeds the extracted text limit.")

    with apply_configuration(
        zlib_maximum_output_length=MAX_PDF_STREAM_BYTES,
        lzw_maximum_output_length=MAX_PDF_STREAM_BYTES,
        run_length_maximum_output_length=MAX_PDF_STREAM_BYTES,
        brotli_maximum_output_length=MAX_PDF_STREAM_BYTES,
        array_based_stream_maximum_output_length=MAX_PDF_STREAM_BYTES,
        # Never shell out to jbig2dec, which spools the stream to a temporary file.
        jbig2dec_binary=None,
    ):
        timer = threading.Timer(MAX_PDF_SECONDS, expire)
        timer.daemon = True
        try:
            timer.start()
            reader = PdfReader(source, strict=True)
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError("PDF exceeds the page limit.")
            texts: list[str] = []
            content_bytes = 0
            text_chars = 0
            for page in reader.pages:
                try:
                    contents = page.get_contents()
                except (AttributeError, AssertionError):
                    # A malformed, non-stream /Contents entry; extract_text treats
                    # it as an empty page, so do the same here.
                    contents = None
                if contents is not None:
                    content_bytes += len(contents.get_data())
                    if content_bytes > MAX_PDF_CONTENT_BYTES:
                        raise ValueError("PDF exceeds the decoded content limit.")
                text = page.extract_text(visitor_text=count_text) or ""
                text_chars += len(text)
                if text_chars > MAX_PDF_TEXT_CHARS:
                    raise ValueError("PDF exceeds the extracted text limit.")
                texts.append(text)
        finally:
            with deadline_lock:
                deadline_active = False
                _set_async_exc(thread_id, None)  # drop an expiry not yet delivered
            timer.cancel()
    return "\n".join(texts)


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