"""Golden evaluation manifest and result checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_NOFACTS = {"number", "date", "cost", "percentage", "word_quantity"}
REQUIRED_MODALITIES = {"chat", "document", "audio"}
REQUIRED_SECTIONS = {
    "section_01",
    "section_02",
    "section_03",
    "section_04",
    "section_05",
    "section_06",
}
REQUIRED_HUMAN_ONLY_FIELDS = {
    "declaration_accepted",
    "submitter_signature",
    "date_of_submission",
}


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_cases(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        records.append(json.loads(text))
    return records


def validate_manifest(manifest: dict[str, Any]) -> None:
    minimum_cases = manifest.get("minimum_cases")
    if not isinstance(minimum_cases, int) or minimum_cases < 50:
        raise ValueError("Golden manifest minimum_cases must be >= 50.")

    required_coverage = manifest.get("required_coverage", {})
    sections = set(required_coverage.get("sections", []))
    no_facts_categories = set(required_coverage.get("no_facts_categories", []))
    modalities = set(required_coverage.get("modalities", []))
    human_only_fields = set(required_coverage.get("human_only_fields", []))

    if sections != REQUIRED_SECTIONS:
        raise ValueError("Manifest must require all six canonical sections.")
    if no_facts_categories != REQUIRED_NOFACTS:
        raise ValueError("Manifest must require all NoFacts categories.")
    if modalities != REQUIRED_MODALITIES:
        raise ValueError("Manifest must require all three modalities.")
    if human_only_fields != REQUIRED_HUMAN_ONLY_FIELDS:
        raise ValueError("Manifest must require all human-only declaration fields.")

    if not required_coverage.get("single_question_pacing", False):
        raise ValueError("Manifest must require single-question pacing coverage.")
    if not required_coverage.get("human_only_protection", False):
        raise ValueError("Manifest must require human-only protection coverage.")


def validate_case_coverage(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    minimum_cases = manifest["minimum_cases"]
    if len(cases) < minimum_cases:
        raise ValueError(f"Golden suite must include at least {minimum_cases} cases.")

    section_coverage = {section for case in cases for section in case.get("sections", [])}
    no_facts_coverage = {category for case in cases for category in case.get("no_facts_categories", [])}
    modality_coverage = {case.get("modality") for case in cases}
    human_only_coverage = {field for case in cases for field in case.get("human_only_fields", [])}

    if not REQUIRED_SECTIONS.issubset(section_coverage):
        raise ValueError("Golden cases are missing canonical section coverage.")
    if not REQUIRED_NOFACTS.issubset(no_facts_coverage):
        raise ValueError("Golden cases are missing NoFacts category coverage.")
    if not REQUIRED_MODALITIES.issubset(modality_coverage):
        raise ValueError("Golden cases are missing modality coverage.")
    if not REQUIRED_HUMAN_ONLY_FIELDS.issubset(human_only_coverage):
        raise ValueError("Golden cases are missing human-only field coverage.")

    if not any(case.get("single_question_pacing") for case in cases):
        raise ValueError("Golden cases must include single-question pacing coverage.")
    if not any(case.get("human_only_protection") for case in cases):
        raise ValueError("Golden cases must include human-only protection coverage.")


def validate_results(cases: list[dict[str, Any]], results: dict[str, str]) -> None:
    case_ids = {case["id"] for case in cases}
    result_ids = set(results.keys())
    if case_ids != result_ids:
        raise ValueError("Golden runner requires one result for every case; no skipped or omitted cases allowed.")
    if any(results[case_id] != "pass" for case_id in case_ids):
        raise ValueError("Golden suite requires a 100% pass rate.")


def run_golden_evaluation(
    manifest_path: Path, cases_path: Path, results: dict[str, str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = load_manifest(manifest_path)
    cases = load_cases(cases_path)
    validate_manifest(manifest)
    validate_case_coverage(cases, manifest)
    validate_results(cases, results)
    return manifest, cases

