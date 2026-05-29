from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    @abstractmethod
    def can_handle(self, request: dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        pass

    def success(self, source: str, data: dict[str, Any], alias: str = "") -> dict[str, Any]:
        return {"status": "success", "source": source, "data": data, "alias": alias}

    def missing(self, source: str, reason: str) -> dict[str, Any]:
        return {"status": "missing", "source": source, "reason": reason}


def source_config(request: dict[str, Any], source: str) -> dict[str, Any]:
    return request.get("config", {}).get("sources", {}).get(source, {})


def source_enabled(request: dict[str, Any], source: str) -> bool:
    return bool(source_config(request, source).get("enabled", False))
