from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agent.connectors.base_connector import BaseConnector, source_config, source_enabled
from agent.utils.schema_validator import matches_constraints, validate_required_fields


TYPE_TO_PATH_KEY = {
    "user": "users",
    "product": "products",
    "address": "checkout",
    "payment": "checkout",
}


class JsonConnector(BaseConnector):
    def can_handle(self, request: dict[str, Any]) -> bool:
        return request.get("source") == "json" and source_enabled(request, "json")

    def fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        requirement = request["requirement"]
        path_key = TYPE_TO_PATH_KEY.get(requirement.get("type", ""), requirement.get("type", ""))
        configured_path = source_config(request, "json").get("paths", {}).get(path_key)
        if not configured_path:
            return self.missing("json", f"No configured JSON path for type={requirement.get('type')}")

        path = Path(request["root"]) / configured_path
        if not path.exists():
            return self.missing("json", f"Configured JSON file not found: {configured_path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        records = self._records(payload, requirement)
        for record in records:
            if not matches_constraints(record, requirement.get("constraints", {})):
                continue
            data = dict(record)
            self._hydrate_env_secret(data)
            missing = validate_required_fields(data, requirement.get("fields", []))
            if missing:
                return self.missing("json", f"Record matched constraints but missed fields: {', '.join(missing)}")
            return self.success("json", data, str(record.get("alias", "")))

        return self.missing("json", f"No matching {requirement.get('type')} record found.")

    def _records(self, payload: dict[str, Any], requirement: dict[str, Any]) -> list[dict[str, Any]]:
        data_type = requirement.get("type")
        candidates = [
            requirement.get("name"),
            data_type,
            f"{data_type}s",
            "users",
            "products",
            "addresses",
            "shippingAddresses",
            "paymentMethods",
        ]
        for key in candidates:
            value = payload.get(key or "")
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                return [value]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    def _hydrate_env_secret(self, data: dict[str, Any]) -> None:
        for key, value in list(data.items()):
            if key.endswith("Env") and value and isinstance(value, str):
                field = key[:-3]
                env_value = os.getenv(value)
                if env_value:
                    data[field] = env_value

