from __future__ import annotations

from typing import Any


SENSITIVE_MARKERS = {
    "password",
    "token",
    "secret",
    "apikey",
    "api_key",
    "authorization",
    "connectionstring",
    "connection_string",
    "otp",
    "pin",
    "cardnumber",
    "card_number",
    "cvv",
}


def is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").replace(" ", "_").lower()
    compact = normalized.replace("_", "")
    return any(marker in normalized or marker in compact for marker in SENSITIVE_MARKERS)


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "********" if is_sensitive_key(str(key)) and item not in {None, ""} else mask_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value
