from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGRESSION = '''from __future__ import annotations

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
    path.write_text('[]\\n', encoding="utf-8")
    with pytest.raises(TypeError, match="object"):
        drift.read_records(path)


def test_status_codes_are_error_signals():
    records = [{"statusCode": 200}] * 50 + [{"statusCode": 503}] * 10
    assert drift.detect_drift(records)[0]["metric"] == "error_rate"
'''


def read_records(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise TypeError(f"Telemetry line {line_number} must be an object")
            records.append(record)
    return records


def numeric(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def detect_drift(records: list[dict], window: int = 10) -> list[dict]:
    if window < 1:
        raise ValueError("window must be positive")
    groups = defaultdict(lambda: defaultdict(lambda: deque(maxlen=500 + window)))
    for record in records:
        context = tuple(str(record.get(key, "unknown")) for key in ("model", "feature", "requestType"))
        metrics = groups[context]
        for metric in ("durationMs", "costUsd", "errorRate"):
            value = record.get(metric)
            if numeric(value):
                metrics[metric].append(float(value))
        status_code = record.get("statusCode")
        if any(key in record for key in ("error", "status", "statusCode")):
            failed = bool(record.get("error")) or record.get("status") in ("error", "failed")
            failed = failed or (numeric(status_code) and status_code >= 400)
            metrics["error_rate"].append(float(failed))
    anomalies = []
    for context, metrics in sorted(groups.items()):
        for metric, values in sorted(metrics.items()):
            samples = list(values)
            baseline = samples[:-window]
            if len(baseline) < 30:
                continue
            observed = statistics.mean(samples[-window:])
            mean = statistics.mean(baseline)
            sigma = statistics.pstdev(baseline)
            threshold = mean + 3 * sigma
            if observed > threshold:
                anomalies.append({
                    "context": dict(zip(("model", "feature", "requestType"), context)),
                    "metric": metric,
                    "baseline_mean": mean,
                    "baseline_sigma": sigma,
                    "observed": observed,
                    "threshold": threshold,
                    "baseline_samples": len(baseline),
                    "window_samples": window,
                })
    return anomalies


def simulated_records(remediated: bool = False) -> list[dict]:
    records = [{"durationMs": 100 + (index % 5 - 2)} for index in range(50)]
    records.extend({"durationMs": 100 if remediated else 1000} for _ in range(10))
    return records


def recent_changes() -> dict:
    history = subprocess.run(
        ["git", "log", "-5", "--format=%H", "--", "backend"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    candidates = []
    for commit in history:
        diff = subprocess.run(
            ["git", "show", "--format=", "--unified=3", commit, "--", "backend"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
        score = sum(diff.lower().count(term) for term in ("duration", "timeout", "retry", "latency"))
        candidates.append({"commit": commit, "signal_matches": score})
    return {
        "candidates": sorted(candidates, key=lambda item: (-item["signal_matches"], item["commit"])),
        "conclusion": "Correlation only; no production root cause established by a synthetic incident.",
    }


def simulate() -> None:
    test_path = ROOT / "backend/tests/regression/test_telemetry_drift.py"
    if test_path.exists() and test_path.read_text(encoding="utf-8") != REGRESSION:
        raise RuntimeError("Refusing to overwrite an edited regression test")
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(REGRESSION, encoding="utf-8")
    print(json.dumps({
        "event_type": "telemetry-anomaly", "simulation": True,
        "anomalies": detect_drift(simulated_records()), "git_correlation": recent_changes(),
        "root_cause": "Synthetic bug: current anomaly samples contaminate the historical baseline.",
        "remediation": "Exclude the observation window from the baseline; never auto-merge.",
    }, indent=2), flush=True)
    with tempfile.TemporaryDirectory(prefix="telemetry-drift-") as temporary:
        backend = Path(temporary) / "backend"
        script = backend / "scripts/simulate_telemetry_drift.py"
        regression = backend / "tests/regression/test_telemetry_drift.py"
        script.parent.mkdir(parents=True)
        regression.parent.mkdir(parents=True)
        source = Path(__file__).read_text(encoding="utf-8")
        script.write_text(source.replace("baseline = samples[:-window]", "baseline = samples"), encoding="utf-8")
        regression.write_text(REGRESSION, encoding="utf-8")
        reproduction = subprocess.run(
            [sys.executable, "-m", "pytest", str(regression), "-q", "-k", "spike_is_not"],
            cwd=temporary, capture_output=True, text=True, check=False,
        )
        if reproduction.returncode != 1 or "1 failed" not in reproduction.stdout:
            raise RuntimeError(f"Expected a failing assertion, got: {reproduction.stdout}\n{reproduction.stderr}")
        print("RED: regression fails against the isolated baseline-contamination mutation.", flush=True)
    subprocess.run([sys.executable, "-m", "pytest", str(test_path), "-v"], cwd=ROOT, check=True)
    print("GREEN: regression passes with remediation. Human SRE merge authorization required.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 6 telemetry drift inspection and incident simulation")
    parser.add_argument("--inspect", type=Path, help="Inspect JSONL telemetry without modifying the repository")
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps({"anomalies": detect_drift(read_records(args.inspect))}, indent=2))
    else:
        simulate()


if __name__ == "__main__":
    main()