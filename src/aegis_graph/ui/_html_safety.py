"""Safe embedding helpers for self-contained REG HTML documents."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    return str(value)


def json_for_script(payload: Mapping[str, Any]) -> str:
    """Serialize data for an inline script without allowing HTML parser break-out."""

    return (
        json.dumps(payload, ensure_ascii=False, default=_json_default)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
