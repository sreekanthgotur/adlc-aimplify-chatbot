from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "telemetry_drift", Path(__file__).resolve().parents[2] / "scripts/simulate_telemetry_drift.py"
)
drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drift)


def test_spike_is_not_allowed_to_contaminate_its_own_baseline():
    anomalies = drift.detect_drift(drift.simulated_records())
    assert any(item["metric"] == "durationMs" for item in anomalies)
    assert all(item["observed"] > item["threshold"] for item in anomalies)


def test_healthy_remediation_has_no_drift():
    assert drift.detect_drift(drift.simulated_records(remediated=True)) == []


def test_error_rate_increase_from_zero_is_detected():
    records = [{"error": False} for _ in range(50)]
    records.extend({"error": True} for _ in range(10))
    assert any(item["metric"] == "error_rate" for item in drift.detect_drift(records))


def test_different_models_are_not_compared():
    records = [{"model": "fast", "durationMs": 100} for _ in range(50)]
    records.extend({"model": "slow", "durationMs": 10000} for _ in range(10))
    assert drift.detect_drift(records) == []


@pytest.mark.parametrize("value", [None, True, -1, float("nan"), float("inf"), "100"])
def test_invalid_metrics_are_ignored(value):
    assert drift.detect_drift([{"durationMs": value} for _ in range(60)]) == []


def test_insufficient_history_does_not_invent_a_baseline():
    assert drift.detect_drift([{"durationMs": 10000}] * 10) == []


def test_constant_baseline_detects_a_spike():
    records = [{"durationMs": 100}] * 50 + [{"durationMs": 101}] * 10
    assert drift.detect_drift(records)[0]["metric"] == "durationMs"


def test_jsonl_validation_and_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        drift.read_records(tmp_path / "missing.jsonl")
    path = tmp_path / "usage.jsonl"
    path.write_text('[]\n', encoding="utf-8")
    with pytest.raises(TypeError, match="object"):
        drift.read_records(path)


def test_status_codes_are_error_signals():
    records = [{"statusCode": 200}] * 50 + [{"statusCode": 503}] * 10
    assert drift.detect_drift(records)[0]["metric"] == "error_rate"
