import json
from pathlib import Path

import pytest

from aimplify_intake.evaluation.golden_runner import (
    load_cases,
    load_manifest,
    run_golden_evaluation,
    validate_manifest,
)


def test_manifest_has_required_coverage_and_at_least_50_cases() -> None:
    golden_dir = Path(__file__).resolve().parents[2] / "golden"
    manifest_path = golden_dir / "golden_manifest.json"
    cases_path = golden_dir / "cases.jsonl"

    manifest = load_manifest(manifest_path)
    validate_manifest(manifest)
    cases = load_cases(cases_path)
    assert len(cases) >= 50


def test_runner_fails_if_case_is_missing_from_results() -> None:
    golden_dir = Path(__file__).resolve().parents[2] / "golden"
    manifest_path = golden_dir / "golden_manifest.json"
    cases_path = golden_dir / "cases.jsonl"
    cases = load_cases(cases_path)
    incomplete_results = {case["id"]: "pass" for case in cases[:-1]}

    with pytest.raises(ValueError, match="no skipped or omitted cases"):
        run_golden_evaluation(manifest_path, cases_path, incomplete_results)


def test_runner_requires_single_question_and_human_only_manifest_flags(tmp_path: Path) -> None:
    source_manifest = load_manifest(Path(__file__).resolve().parents[2] / "golden" / "golden_manifest.json")
    source_manifest["required_coverage"]["single_question_pacing"] = False
    source_manifest["required_coverage"]["human_only_protection"] = False
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text(json.dumps(source_manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="single-question pacing"):
        validate_manifest(load_manifest(bad_manifest))
