from pathlib import Path

from aimplify_intake.schema.registry import load_canonical_schema

ROOT = Path(__file__).parents[3]
DATA_MODEL_PATH = ROOT / "specs" / "001-conversational-intake" / "data-model.md"


def _inventory_from_data_model() -> dict[str, dict[str, object]]:
    inventory: dict[str, dict[str, object]] = {}
    for line in DATA_MODEL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        key = cells[0].strip("`")
        if key == "Key":
            continue
        type_spec = cells[3]
        allowed_values = None
        value_type = type_spec
        if type_spec.startswith("enum:"):
            value_type = "enum"
            allowed_values = [value.strip() for value in type_spec.removeprefix("enum:").split(";")]
        inventory[key] = {
            "display_name": cells[1],
            "section_key": cells[2].strip("`"),
            "value_type": value_type,
            "allowed_values": allowed_values,
            "mandatory": cells[4] == "Yes",
            "fill_mode": cells[5],
            "ai_writable": cells[6].strip("*") == "Yes",
            "declaration_only": cells[7].strip("*") == "Yes",
        }
    return inventory


def test_canonical_schema_matches_authoritative_inventory() -> None:
    expected = _inventory_from_data_model()
    schema = load_canonical_schema()
    actual_fields = {field["key"]: field for field in schema["fields"]}

    assert len(schema["sections"]) == 6
    assert len(schema["fields"]) == 27
    assert len(actual_fields) == 27
    assert set(actual_fields) == set(expected)
    assert sum(field["mandatory"] for field in actual_fields.values()) == 18
    assert sum(not field["mandatory"] for field in actual_fields.values()) == 9
    assert sum(field["mandatory"] and field["ai_writable"] for field in actual_fields.values()) == 15
    assert sum(field["declaration_only"] for field in actual_fields.values()) == 3

    for key, expected_field in expected.items():
        actual_field = actual_fields[key]
        for attribute in (
            "display_name",
            "section_key",
            "value_type",
            "mandatory",
            "fill_mode",
            "ai_writable",
            "declaration_only",
        ):
            assert actual_field[attribute] == expected_field[attribute], f"{key}: {attribute} differs"
        if expected_field["allowed_values"] is not None:
            assert actual_field["allowed_values"] == expected_field["allowed_values"], f"{key}: enum differs"
        else:
            assert "allowed_values" not in actual_field, f"{key}: unexpected enum values"