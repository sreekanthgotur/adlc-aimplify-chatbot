"""Deterministic NoFacts safety gate."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

_DIGIT_PATTERN = re.compile(r"\d")
_PERCENT_PATTERN = re.compile(r"(?:\d\s*%|\bpercent(?:age)?\b)", re.IGNORECASE)
_CURRENCY_PATTERN = re.compile(
    r"(?:[$€£₹]\s*\d|\b(?:usd|eur|gbp|inr|dollars?|euros?|rupees?|cost|price|budget)\b)",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"(?:\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?\b)",
    re.IGNORECASE,
)
_WORD_QUANTITY_PATTERN = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
    r"seventy|eighty|ninety|hundred|thousand|million|billion)\b"
    r"(?:\s+(?:percent|hours?|days?|weeks?|months?|years?|users?|employees?|dollars?|rupees?))?",
    re.IGNORECASE,
)
_QUALIFIER_WITH_WORD_NUMBER_PATTERN = re.compile(
    r"\b(?:over|under|about|around|approximately|at least|at most|more than|less than)\s+"
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
    r"seventy|eighty|ninety|hundred|thousand)\b",
    re.IGNORECASE,
)
_VALIDATION_TOKEN = object()


class _NoFactsValidatedCandidate(dict[str, str]):
    __slots__ = ("_validation_proof",)

    def __init__(self, candidate: dict[str, str], token: object) -> None:
        if token is not _VALIDATION_TOKEN:
            raise ValueError("Candidate has not passed NoFacts validation.")
        super().__init__(candidate)
        self._validation_proof = (_VALIDATION_TOKEN, tuple(sorted(self.items())))


def mark_no_facts_validated(candidate: dict[str, str]) -> _NoFactsValidatedCandidate:
    if no_facts_decision(candidate) != "pass":
        raise ValueError("Candidate has not passed NoFacts validation.")
    return _NoFactsValidatedCandidate(candidate, _VALIDATION_TOKEN)


def is_no_facts_validated(candidate: object) -> bool:
    if not isinstance(candidate, _NoFactsValidatedCandidate):
        return False
    return candidate._validation_proof == (
        _VALIDATION_TOKEN,
        tuple(sorted(candidate.items())),
    )


def _iter_text_leaves(candidate: Any) -> Iterable[str]:
    if isinstance(candidate, str):
        yield candidate
        return
    if isinstance(candidate, dict):
        for value in candidate.values():
            yield from _iter_text_leaves(value)
        return
    if isinstance(candidate, (list, tuple, set)):
        for item in candidate:
            yield from _iter_text_leaves(item)


def _contains_unverified_quantity(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in (
            _DIGIT_PATTERN,
            _PERCENT_PATTERN,
            _CURRENCY_PATTERN,
            _DATE_PATTERN,
            _WORD_QUANTITY_PATTERN,
            _QUALIFIER_WITH_WORD_NUMBER_PATTERN,
        )
    )


def no_facts_decision(candidate: Any) -> str:
    """Return ``pass`` or ``drop`` for one candidate."""
    for leaf_text in _iter_text_leaves(candidate):
        if _contains_unverified_quantity(leaf_text):
            return "drop"
    return "pass"


def passes_no_facts(candidate: Any) -> bool:
    """Return True when candidate passes deterministic NoFacts checks."""
    return no_facts_decision(candidate) == "pass"

