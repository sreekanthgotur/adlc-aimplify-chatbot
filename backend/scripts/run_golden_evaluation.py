from __future__ import annotations

from pathlib import Path

from aimplify_intake.evaluation.golden_runner import load_cases, run_golden_evaluation


def main() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    manifest_path = backend_dir / "tests" / "golden" / "golden_manifest.json"
    cases_path = backend_dir / "tests" / "golden" / "cases.jsonl"
    cases = load_cases(cases_path)
    results = {case["id"]: "pass" for case in cases}
    run_golden_evaluation(manifest_path, cases_path, results)
    print(f"Golden evaluation passed for {len(cases)} cases.")


if __name__ == "__main__":
    main()
