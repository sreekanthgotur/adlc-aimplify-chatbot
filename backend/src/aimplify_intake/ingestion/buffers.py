"""RAM-only streaming helpers."""

from __future__ import annotations

from collections.abc import AsyncIterable
from io import BytesIO

from fastapi import Request


async def read_stream_to_memory(stream: AsyncIterable[bytes], max_bytes: int) -> BytesIO:
    total = 0
    buffer = BytesIO()
    try:
        async for chunk in stream:
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Source exceeds configured size limit.")
            buffer.write(chunk)
        buffer.seek(0)
        return buffer
    except BaseException:
        buffer.close()
        raise


async def read_request_stream_to_memory(request: Request, max_bytes: int) -> BytesIO:
    return await read_stream_to_memory(request.stream(), max_bytes=max_bytes)

