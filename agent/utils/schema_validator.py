from __future__ import annotations

from typing import Any


def _normalize(value: Any) -> str:
    return str(value).strip().lower()


def matches_constraints(record: dict[str, Any], constraints: dict[str, Any]) -> bool:
    for key, expected in (constraints or {}).items():
        if expected is None:
            continue
        actual = record.get(key)
        if actual is None:
            return False
        if _normalize(actual) != _normalize(expected):
            return False
    return True


def validate_required_fields(record: dict[str, Any], fields: list[str]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        if field not in record or record.get(field) in {None, ""}:
            missing.append(field)
    return missing
