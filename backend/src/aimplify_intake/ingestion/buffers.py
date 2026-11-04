"""RAM-only streaming helpers."""

from __future__ import annotations

from io import BytesIO
from typing import AsyncIterable

from fastapi import Request


async def read_stream_to_memory(stream: AsyncIterable[bytes], max_bytes: int) -> BytesIO:
    total = 0
    buffer = BytesIO()
    async for chunk in stream:
        total += len(chunk)
        if total > max_bytes:
            buffer.close()
            raise ValueError("Source exceeds configured size limit.")
        buffer.write(chunk)
    buffer.seek(0)
    return buffer


async def read_request_stream_to_memory(request: Request, max_bytes: int) -> BytesIO:
    return await read_stream_to_memory(request.stream(), max_bytes=max_bytes)

