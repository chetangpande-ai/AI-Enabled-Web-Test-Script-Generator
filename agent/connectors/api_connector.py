from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agent.connectors.base_connector import BaseConnector, source_config, source_enabled
from agent.utils.schema_validator import matches_constraints, validate_required_fields


ALLOWED_OPERATIONS = {
    "get_active_customer": {
        "method": "GET",
        "path": "/test-data/users",
        "allowedParams": ["role", "status"],
    },
    "get_in_stock_product": {
        "method": "GET",
        "path": "/test-data/products",
        "allowedParams": ["status", "category"],
    },
    "create_test_customer": {
        "method": "POST",
        "path": "/test-data/users",
        "allowedBodyFields": ["role", "region"],
    },
    "setup_cart": {
        "method": "POST",
        "path": "/test-data/cart/setup",
        "allowedBodyFields": ["userId", "sku"],
    },
}


TYPE_TO_OPERATION = {
    "user": "get_active_customer",
    "product": "get_in_stock_product",
}


class ApiConnector(BaseConnector):
    def can_handle(self, request: dict[str, Any]) -> bool:
        return request.get("source") == "api" and source_enabled(request, "api")

    def fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        requirement = request["requirement"]
        config = source_config(request, "api")
        operation_name = TYPE_TO_OPERATION.get(requirement.get("type", ""))
        if not operation_name:
            return self.missing("api", f"No predefined API operation for type={requirement.get('type')}")
        if operation_name not in set(config.get("allowed_operations", [])):
            return self.missing("api", f"API operation is not allowed: {operation_name}")

        base_url = os.getenv(config.get("base_url_env_var", ""))
        token = os.getenv(config.get("token_env_var", ""))
        if not base_url:
            return self.missing("api", "API base URL env var is not set.")
        if not token:
            return self.missing("api", "API token env var is not set.")

        operation = ALLOWED_OPERATIONS[operation_name]
        try:
            payload = self._call(base_url.rstrip("/"), token, operation, requirement)
        except Exception as exc:
            return self.missing("api", f"API operation failed: {type(exc).__name__}: {exc}")

        records = payload if isinstance(payload, list) else payload.get("items", payload.get("data", [payload]))
        if isinstance(records, dict):
            records = [records]
        for record in records:
            if not isinstance(record, dict):
                continue
            if not matches_constraints(record, requirement.get("constraints", {})):
                continue
            missing = validate_required_fields(record, requirement.get("fields", []))
            if missing:
                return self.missing("api", f"API data missed fields: {', '.join(missing)}")
            return self.success("api", record, operation_name)

        return self.missing("api", f"API operation returned no matching {requirement.get('type')} data.")

    def _call(
        self,
        base_url: str,
        token: str,
        operation: dict[str, Any],
        requirement: dict[str, Any],
    ) -> Any:
        method = operation["method"]
        constraints = requirement.get("constraints", {})
        url = base_url + operation["path"]
        body = None

        if method == "GET":
            allowed = set(operation.get("allowedParams", []))
            params = {key: str(value) for key, value in constraints.items() if key in allowed}
            if params:
                url = f"{url}?{urlencode(params)}"
        else:
            allowed = set(operation.get("allowedBodyFields", []))
            body_payload = {key: value for key, value in constraints.items() if key in allowed}
            body = json.dumps(body_payload).encode("utf-8")

        request = Request(
            url,
            data=body,
            method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

