from __future__ import annotations

import json
from typing import Any


def coerce_json_container_strings(value: Any) -> Any:
    """Normalize model outputs that stringify JSON arrays/objects."""
    if isinstance(value, dict):
        return {key: coerce_json_container_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [coerce_json_container_strings(item) for item in value]
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not (
        (stripped.startswith("[") and stripped.endswith("]"))
        or (stripped.startswith("{") and stripped.endswith("}"))
    ):
        return value

    try:
        parsed = json.loads(stripped)
    except (TypeError, ValueError):
        return value
    if not isinstance(parsed, (dict, list)):
        return value
    return coerce_json_container_strings(parsed)
