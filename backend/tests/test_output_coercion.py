from app.agents.output_coercion import coerce_json_container_strings


def test_coerce_json_container_strings_recurses_through_outputs() -> None:
    payload = {
        "customers": "[]",
        "risk": "{\"id\":\"R1\",\"tags\":\"[\\\"lease\\\"]\"}",
        "summary": "Keep plain text unchanged.",
    }

    assert coerce_json_container_strings(payload) == {
        "customers": [],
        "risk": {"id": "R1", "tags": ["lease"]},
        "summary": "Keep plain text unchanged.",
    }


def test_coerce_json_container_strings_ignores_invalid_json_text() -> None:
    payload = {"summary": "[not valid json]"}

    assert coerce_json_container_strings(payload) == payload
