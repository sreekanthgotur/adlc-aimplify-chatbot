from aimplify_intake.schema.registry import load_canonical_schema, publish_schema


def test_canonical_schema_counts_and_non_ai_writable_constraints() -> None:
    schema = load_canonical_schema()
    published = publish_schema(schema)

    assert len(published.fields) == 27
    assert len(published.sections) == 6

    mandatory_fields = [field for field in published.fields if field["mandatory"]]
    optional_fields = [field for field in published.fields if not field["mandatory"]]
    assert len(mandatory_fields) == 18
    assert len(optional_fields) == 9

    declaration_fields = {"declaration_accepted", "submitter_signature", "date_of_submission"}
    non_ai_writable = {field["key"] for field in published.fields if not field["ai_writable"]}
    assert declaration_fields.issubset(non_ai_writable)
    assert "reviewer_notes" in non_ai_writable
