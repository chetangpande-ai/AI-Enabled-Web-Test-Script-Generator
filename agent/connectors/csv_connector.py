from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from agent.connectors.base_connector import BaseConnector, source_config, source_enabled
from agent.connectors.json_connector import TYPE_TO_PATH_KEY
from agent.utils.schema_validator import matches_constraints, validate_required_fields


class CsvConnector(BaseConnector):
    def can_handle(self, request: dict[str, Any]) -> bool:
        return request.get("source") == "csv" and source_enabled(request, "csv")

    def fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        requirement = request["requirement"]
        path_key = TYPE_TO_PATH_KEY.get(requirement.get("type", ""), requirement.get("type", ""))
        configured_path = source_config(request, "csv").get("paths", {}).get(path_key)
        if not configured_path:
            return self.missing("csv", f"No configured CSV path for type={requirement.get('type')}")

        path = Path(request["root"]) / configured_path
        if not path.exists():
            return self.missing("csv", f"Configured CSV file not found: {configured_path}")

        with path.open(newline="", encoding="utf-8") as handle:
            for record in csv.DictReader(handle):
                if not matches_constraints(record, requirement.get("constraints", {})):
                    continue
                data = dict(record)
                self._hydrate_env_secret(data)
                missing = validate_required_fields(data, requirement.get("fields", []))
                if missing:
                    return self.missing("csv", f"Record matched constraints but missed fields: {', '.join(missing)}")
                return self.success("csv", data, str(record.get("alias", "")))

        return self.missing("csv", f"No matching {requirement.get('type')} row found.")

    def _hydrate_env_secret(self, data: dict[str, Any]) -> None:
        for key, value in list(data.items()):
            if key.endswith("Env") and value:
                field = key[:-3]
                env_value = os.getenv(str(value))
                if env_value:
                    data[field] = env_value

