import builtins
from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pptx import Presentation
from PyPDF2 import PdfWriter

from aimplify_intake.api.app import create_app
from aimplify_intake.ingestion.audio import transcribe_audio
from aimplify_intake.ingestion.documents import extract_docx, extract_pdf, extract_pptx


def _pdf() -> BytesIO:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    stream = BytesIO()
    writer.write(stream)
    stream.seek(0)
    return stream


def _docx() -> BytesIO:
    document = Document()
    document.add_paragraph("A safe document describes a policy discovery assistant.")
    stream = BytesIO()
    document.save(stream)
    stream.seek(0)
    return stream


def _pptx() -> BytesIO:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(0, 0, 100, 100).text = "A safe presentation describes policy discovery."
    stream = BytesIO()
    presentation.save(stream)
    stream.seek(0)
    return stream


@pytest.mark.parametrize("media_type", ["audio/wav", "audio/mpeg", "audio/webm"])
def test_audio_adapters_receive_memory_stream_and_release_provider_text(media_type: str) -> None:
    audio = BytesIO(b"audio sample")
    received: list[BytesIO] = []

    def provider(stream: BytesIO, _media_type: str) -> str:
        received.append(stream)
        assert stream.read() == b"audio sample"
        return "A safe spoken idea."

    assert transcribe_audio(audio, media_type, provider, no_retention_approved=True) == "A safe spoken idea."
    assert received == [audio]


def test_audio_provider_requires_explicit_no_retention_approval() -> None:
    with pytest.raises(RuntimeError, match="no-retention"):
        transcribe_audio(BytesIO(b"audio sample"), "audio/wav", lambda _stream, _type: "text")


def test_document_adapters_parse_only_bytesio_inputs_and_do_not_write_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_attempts: list[str] = []
    original_open = builtins.open

    def trap_open(file: str, mode: str = "r", *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            write_attempts.append(file)
            raise RuntimeError("Parser attempted a disk write.")
        return original_open(file, mode, *args, **kwargs)

    streams = (_pdf(), _docx(), _pptx())
    monkeypatch.setattr(builtins, "open", trap_open)
    assert isinstance(extract_pdf(streams[0]), str)
    assert isinstance(extract_docx(streams[1]), str)
    assert isinstance(extract_pptx(streams[2]), str)
    assert all(isinstance(stream, BytesIO) for stream in streams)
    assert write_attempts == []


def test_all_supported_raw_uploads_stay_in_memory_and_commit_only_safe_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = [
        ("pdf", "application/pdf", _pdf().getvalue()),
        ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", _docx().getvalue()),
        ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", _pptx().getvalue()),
        ("wav", "audio/wav", b"RIFFsample"),
        ("mp3", "audio/mpeg", b"ID3sample"),
        ("webm", "audio/webm", b"\x1aE\xdf\xa3sample"),
    ]
    write_attempts: list[str] = []
    original_open = builtins.open

    def trap_open(file: str, mode: str = "r", *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            write_attempts.append(file)
            raise RuntimeError("Ingress or parser attempted a disk write.")
        return original_open(file, mode, *args, **kwargs)

    app = create_app(
        database_url="sqlite+pysqlite:///:memory:",
        identity_verifier=lambda _cookie: {"subject": "employee-1"},
        candidate_extractor=lambda _text: {"problem_statement": "Policy discovery can be simplified."},
        transcription_provider=lambda stream, _media_type: "A safe spoken idea.",
        transcription_no_retention_approved=True,
        max_upload_bytes=1024 * 1024,
    )
    monkeypatch.setattr(builtins, "open", trap_open)
    with TestClient(app, headers={"origin": "http://testserver"}) as client:
        client.cookies.set("oidc_session", "test-session")
        session_id = client.post("/api/v1/sessions").json()["session_id"]
        for extension, content_type, payload in payloads:
            response = client.post(
                f"/api/v1/sessions/{session_id}/sources/{extension}",
                content=payload,
                headers={"content-type": content_type, "x-source-name": f"private.{extension}"},
            )
            assert response.status_code == 200
            assert response.json()["field_updates"] == [
                {
                    "field_key": "problem_statement",
                    "value": "Policy discovery can be simplified.",
                    "origin": "ai_extracted",
                }
            ]
            assert f"private.{extension}" not in response.text
        fields = client.get(f"/api/v1/sessions/{session_id}/fields").json()

    accepted_values = [
        field["value"]
        for section in fields["sections"]
        for field in section["fields"]
        if "value" in field
    ]
    assert accepted_values == ["Policy discovery can be simplified."]
    assert write_attempts == []