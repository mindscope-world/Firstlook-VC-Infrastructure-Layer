from firstlook_ai.extraction import EXTRACTION_SCHEMA, locate_quote, validate


def test_locate_quote_tolerates_whitespace_and_smart_quotes():
    text = "Hi Paul,\n\nWe’re  raising a $3M\nseed round."
    span = locate_quote(text, "We're raising a $3M seed round.")
    assert span is not None
    assert text[span[0] : span[1]] == "We’re  raising a $3M\nseed round."
    assert locate_quote(text, "we are raising") is None
    assert locate_quote(text, "") is None


def test_validate_drops_uncited_and_empty_items():
    text = "I'll send the IC memo over tomorrow. Also, Acme is raising."
    result = {
        "intros": [],
        "next_steps": [
            {
                "owner": {"name": "F", "email": "", "company": ""},
                "owner_side": "them",
                "action": "Send the IC memo",
                "due": "",
                "quote": "I'll send the IC memo over tomorrow.",
                "confidence": "high",
            },
            {
                "owner": {"name": "F", "email": "", "company": ""},
                "owner_side": "them",
                "action": "Invented",
                "due": "",
                "quote": "This sentence is not in the email.",
                "confidence": "high",
            },
        ],
        "deal_mentions": [
            {
                "company_name": "",
                "company_domain": "",
                "stage": "",
                "round_size_usd": 0,
                "summary": "",
                "quote": "Acme is raising",
                "confidence": "low",
            },
        ],
    }
    rows = validate(result, text, "iid", "<m@x>")
    assert len(rows) == 1
    row = rows[0]
    assert row["kind"] == "next_step" and row["confidence"] == 0.9
    c = row["citations"][0]
    assert text[c["start"] : c["end"]] == c["quote"] and c["external_id"] == "<m@x>"
    assert "quote" not in row["payload"]


def test_schema_is_strict_for_structured_outputs():
    def walk(node):
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False
            assert set(node["required"]) == set(node["properties"])
            for child in node["properties"].values():
                walk(child)
        if node.get("type") == "array":
            walk(node["items"])

    walk(EXTRACTION_SCHEMA)
