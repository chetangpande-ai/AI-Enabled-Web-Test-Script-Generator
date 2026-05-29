from __future__ import annotations

import os
from typing import Any

from agent.connectors.base_connector import BaseConnector, source_config, source_enabled
from agent.utils.schema_validator import validate_required_fields


FIELD_ALIASES = {
    "username": ["customer_username", "username", "user_username"],
    "email": ["customer_username", "email", "user_email"],
    "password": ["customer_password", "password", "user_password"],
    "token": ["test_data_api_token", "token"],
    "connectionString": ["db_connection_string", "connection_string"],
}


class EnvConnector(BaseConnector):
    def can_handle(self, request: dict[str, Any]) -> bool:
        return request.get("source") == "env" and source_enabled(request, "env")

    def fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        requirement = request["requirement"]
        config_keys = source_config(request, "env").get("keys", {})
        fields = requirement.get("fields", [])
        constraints = requirement.get("constraints", {})
        data: dict[str, Any] = {}

        for field in fields:
            value, env_name = self._read_field(field, config_keys)
            if value:
                data[field] = value
                data[f"{field}Env"] = env_name

        for key, value in constraints.items():
            data.setdefault(key, value)

        missing = validate_required_fields(data, fields)
        if missing:
            names = ", ".join(missing)
            return self.missing("env", f"Missing environment-backed fields: {names}")

        return self.success("env", data)

    def _read_field(self, field: str, config_keys: dict[str, str]) -> tuple[str | None, str | None]:
        aliases = FIELD_ALIASES.get(field, [field])
        candidates: list[str] = []
        for alias in aliases:
            configured = config_keys.get(alias)
            if configured:
                candidates.append(configured)
            candidates.append(alias.upper())
        candidates.append(field.upper())

        for env_name in candidates:
            value = os.getenv(env_name)
            if value:
                return value, env_name
        return None, None

