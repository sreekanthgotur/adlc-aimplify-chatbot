import time
import zlib
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from aimplify_intake.api.app import create_app
from aimplify_intake.ingestion import documents
from aimplify_intake.ingestion.documents import extract_pdf


def _pdf(content: bytes, *, compress: bool = False, filter_name: bytes | None = None) -> bytes:
    data = zlib.compress(content, 9) if compress else content
    stream_filter = b" /Filter /FlateDecode" if compress else b""
    if filter_name is not None:
        stream_filter = b" /Filter /" + filter_name
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d%s >>\nstream\n" % (len(data), stream_filter) + data + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1))
    out.write(b"startxref\n%d\n%%%%EOF\n" % xref)
    return out.getvalue()


def _xform_pdf(xform_content: bytes, invocations: int) -> bytes:
    xform = zlib.compress(xform_content, 9)
    page = zlib.compress(b"/X0 Do\n" * invocations, 9)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> /XObject << /X0 6 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(page) + page + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        (
            b"<< /Type /XObject /Subtype /Form /BBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Length %d /Filter /FlateDecode >>\nstream\n"
            % len(xform)
            + xform
            + b"\nendstream"
        ),
    ]
    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1))
    out.write(b"startxref\n%d\n%%%%EOF\n" % xref)
    return out.getvalue()


def _upload(content: bytes) -> dict:
    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
    )
    with TestClient(app, headers={"origin": "http://testserver"}) as client:
        client.cookies.set("oidc_session", "test-session")
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        response = client.post(
            f"/api/v1/sessions/{session_id}/sources/pdf",
            content=content,
            headers={"content-type": "application/octet-stream"},
        )
    assert response.status_code == 400
    return response.json()["error"]


def test_content_stream_ending_inside_comment_terminates() -> None:
    pdf = _pdf(b"BT /F1 12 Tf 72 720 Td (Hi) Tj ET %unterminated comment")

    assert extract_pdf(BytesIO(pdf)) == "Hi"


def test_non_stream_page_contents_is_treated_as_empty() -> None:
    pdf = _pdf(b"BT /F1 12 Tf 72 720 Td (Hi) Tj ET").replace(b"/Contents 4 0 R", b"/Contents 5    ")

    assert extract_pdf(BytesIO(pdf)) == ""


def test_highly_compressible_stream_is_rejected_as_source_invalid() -> None:
    pdf = _pdf(b" " * (documents.MAX_PDF_STREAM_BYTES + 1), compress=True)

    assert len(pdf) < 64 * 1024
    assert _upload(pdf)["code"] == "SOURCE_INVALID"


def test_jbig2_stream_is_rejected_as_source_invalid() -> None:
    pdf = _pdf(b"BT /F1 12 Tf 72 720 Td (Hi) Tj ET", filter_name=b"JBIG2Decode")

    with pytest.raises(ValueError, match="unsupported feature"):
        extract_pdf(BytesIO(pdf))
    assert _upload(pdf)["code"] == "SOURCE_INVALID"


def test_page_count_over_limit_is_rejected_as_source_invalid() -> None:
    writer = PdfWriter()
    for _ in range(documents.MAX_PDF_PAGES + 1):
        writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)

    assert _upload(buffer.getvalue())["code"] == "SOURCE_INVALID"


def test_decoded_content_and_extracted_text_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = _pdf(b"BT /F1 12 Tf 72 720 Td (Hello world) Tj ET")

    monkeypatch.setattr(documents, "MAX_PDF_CONTENT_BYTES", 8)
    with pytest.raises(ValueError, match="decoded content"):
        extract_pdf(BytesIO(pdf))

    monkeypatch.undo()
    monkeypatch.setattr(documents, "MAX_PDF_TEXT_CHARS", 5)
    with pytest.raises(ValueError, match="extracted text"):
        extract_pdf(BytesIO(pdf))


def test_form_xobject_text_amplification_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(documents, "MAX_PDF_TEXT_CHARS", 1_000)
    pdf = _xform_pdf(b"BT /F1 12 Tf (" + b"A" * 600 + b") Tj ET", invocations=1_000)

    with pytest.raises(ValueError, match="extracted text"):
        extract_pdf(BytesIO(pdf))


def test_repeated_form_xobject_parsing_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    # Each `Do` re-parses the form, even when it yields no operations or text.
    monkeypatch.setattr(documents, "MAX_PDF_SECONDS", 0.5)
    pdf = _xform_pdf(b"0 " * 100_000, invocations=5_000)

    with pytest.raises(ValueError, match="processing time"):
        extract_pdf(BytesIO(pdf))


def _font_pdf(font_count: int, to_unicode: bytes) -> bytes:
    data = zlib.compress(to_unicode, 9)
    fonts = b" ".join(b"/F%d 5 0 R" % index for index in range(font_count))
    page = b"BT /F0 12 Tf (A) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << " + fonts + b" >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(page) + page + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>",
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream",
    ]
    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1))
    out.write(b"startxref\n%d\n%%%%EOF\n" % xref)
    return out.getvalue()


def test_repeated_font_resources_are_bounded_by_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # pypdf loads every font up front, outside any visitor callback.
    monkeypatch.setattr(documents, "MAX_PDF_SECONDS", 0.5)
    cmap = b"begincmap\n" + b"<0041> <0041>\n" * 50_000 + b"endcmap"
    pdf = _font_pdf(200, cmap)

    with pytest.raises(ValueError, match="processing time"):
        extract_pdf(BytesIO(pdf))


def test_expired_deadline_is_source_invalid_and_never_fires_later(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(documents, "MAX_PDF_SECONDS", 0.0)
    with pytest.raises(ValueError, match="processing time"):
        extract_pdf(BytesIO(_pdf(b"BT ET %" + b"0 " * 200_000)))

    monkeypatch.setattr(documents, "MAX_PDF_SECONDS", 0.05)
    assert extract_pdf(BytesIO(_pdf(b"BT /F1 12 Tf (Hi) Tj ET"))) == "Hi"
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        pass
