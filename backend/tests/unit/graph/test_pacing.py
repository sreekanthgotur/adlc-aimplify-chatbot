from aimplify_intake.graph.pacing import select_next_clarification


def _fields() -> list[dict[str, object]]:
    return [
        {"key": "mandatory_a", "mandatory": True, "clarification_prompt": "Question A?"},
        {"key": "mandatory_b", "mandatory": True, "clarification_prompt": "Question B?"},
        {"key": "optional_c", "mandatory": False, "clarification_prompt": "Optional C?"},
    ]


def test_selects_one_missing_mandatory_field() -> None:
    decision = select_next_clarification(_fields(), {"mandatory_a": "done"})
    assert decision is not None
    assert decision.field_key == "mandatory_b"
    assert decision.question == "Question B?"


def test_returns_none_when_all_mandatory_fields_are_present() -> None:
    decision = select_next_clarification(
        _fields(), {"mandatory_a": "done", "mandatory_b": "done", "optional_c": ""}
    )
    assert decision is None


def test_empty_optional_field_does_not_trigger_clarification() -> None:
    decision = select_next_clarification(
        _fields(), {"mandatory_a": "done", "mandatory_b": "done", "optional_c": None}
    )
    assert decision is None

