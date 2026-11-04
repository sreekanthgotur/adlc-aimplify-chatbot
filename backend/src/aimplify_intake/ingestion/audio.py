"""Transient audio transcription adapter."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO

SUPPORTED_AUDIO_TYPES = {"audio/wav", "audio/mpeg", "audio/webm"}
TranscriptionProvider = Callable[[BytesIO, str], str]


def transcribe_audio(
    source: BytesIO,
    media_type: str,
    provider: TranscriptionProvider | None = None,
    *,
    no_retention_approved: bool = False,
) -> str:
    if not isinstance(source, BytesIO):
        raise TypeError("Audio input must be an in-memory buffer.")
    if media_type not in SUPPORTED_AUDIO_TYPES:
        raise ValueError("Unsupported audio type.")
    if provider is None or not no_retention_approved:
        raise RuntimeError("No approved no-retention transcription provider is configured.")
    source.seek(0)
    transcript = provider(source, media_type)
    if not isinstance(transcript, str):
        raise TypeError("Transcription provider returned an invalid result.")
    return transcript