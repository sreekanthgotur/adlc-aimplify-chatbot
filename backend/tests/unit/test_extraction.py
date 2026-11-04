from aimplify_intake.services.extraction import extract_safe_candidates


def test_extraction_drops_unsafe_invalid_and_human_only_candidates() -> None:
    candidates = extract_safe_candidates(
        "Transient source text.",
        lambda _text: {
            "problem_statement": "Policy discovery is difficult.",
            "expected_benefits": "Reduce effort by 20 percent.",
            "aimplify_platform": "Unknown platform",
            "declaration_accepted": True,
            "reviewer_notes": "Keep this for a reviewer.",
        },
    )

    assert candidates == [
        {
            "field_key": "problem_statement",
            "value": "Policy discovery is difficult.",
            "origin": "ai_extracted",
        }
    ]