import asyncio
import builtins
from io import BytesIO
from typing import AsyncIterator

import pytest
from fastapi import Request

from aimplify_intake.ingestion.buffers import read_request_stream_to_memory, read_stream_to_memory


class _DummyReceive:
    def __init__(self, body: bytes) -> None:
        self._sent = False
        self._body = body

    async def __call__(self) -> dict[str, object]:
        if self._sent:
            return {"type": "http.disconnect"}
        self._sent = True
        return {"type": "http.request", "body": self._body, "more_body": False}


def _request_with_body(body: bytes) -> Request:
    scope = {"type": "http", "method": "POST", "path": "/upload", "headers": []}
    return Request(scope=scope, receive=_DummyReceive(body))


@pytest.mark.parametrize(
    ("media_type", "payload"),
    [
        ("application/pdf", b"%PDF-1.7 sample"),
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"DOCX sample"),
        ("application/vnd.openxmlformats-officedocument.presentationml.presentation", b"PPTX sample"),
        ("audio/wav", b"RIFFsample"),
        ("audio/mpeg", b"MP3 sample"),
        ("audio/webm", b"WEBM sample"),
    ],
)
def test_request_stream_reads_each_supported_media_type_into_bytesio_without_disk_write(
    media_type: str, payload: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_attempts: list[str] = []
    original_open = builtins.open

    def trap_open(file: str, mode: str = "r", *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            write_attempts.append(file)
            raise RuntimeError("Disk write attempted during RAM-only ingestion.")
        return original_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", trap_open)
    request = _request_with_body(payload)
    request.scope["headers"] = [(b"content-type", media_type.encode("utf-8"))]

    result = asyncio.run(read_request_stream_to_memory(request, max_bytes=1024))

    assert isinstance(result, BytesIO)
    assert result.read() == payload
    assert write_attempts == []


def test_stream_rejects_over_limit() -> None:
    async def stream() -> AsyncIterator[bytes]:
        yield b"a" * 5
        yield b"b" * 5

    with pytest.raises(ValueError, match="size limit"):
        asyncio.run(read_stream_to_memory(stream(), max_bytes=8))
