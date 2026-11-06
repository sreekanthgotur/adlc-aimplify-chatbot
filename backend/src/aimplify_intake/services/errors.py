"""Errors raised when external AI providers cannot safely process a request."""

from __future__ import annotations


class ProviderUnavailable(RuntimeError):
    """An external AI provider failed or returned an invalid response."""


class ExtractionInputTooLarge(ValueError):
    """The source text exceeds the configured model input limit."""


class InvalidAudioInput(ValueError):
    """The uploaded audio cannot be decoded into a supported stream."""
