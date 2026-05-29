from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from agent.connectors.base_connector import BaseConnector, source_config, source_enabled
from agent.utils.schema_validator import validate_required_fields


ALLOWED_QUERIES = {
    "get_active_customer": """
        SELECT username, role
        FROM qa_test_users
        WHERE status = 'ACTIVE'
        AND role = :role
        LIMIT 1
    """,
    "get_in_stock_product": """
        SELECT sku, name, searchTerm
        FROM qa_products
        WHERE status = 'IN_STOCK'
        LIMIT 1
    """,
    "get_customer_with_balance": """
        SELECT username, role
        FROM qa_test_users
        WHERE status = 'ACTIVE'
        AND role = :role
        AND balance > 0
        LIMIT 1
    """,
}


TYPE_TO_QUERY = {
    "user": "get_active_customer",
    "product": "get_in_stock_product",
}


class DbConnector(BaseConnector):
    def can_handle(self, request: dict[str, Any]) -> bool:
        return request.get("source") == "database" and source_enabled(request, "database")

    def fetch(self, request: dict[str, Any]) -> dict[str, Any]:
        requirement = request["requirement"]
        config = source_config(request, "database")
        query_name = TYPE_TO_QUERY.get(requirement.get("type", ""))
        if not query_name:
            return self.missing("database", f"No predefined query for type={requirement.get('type')}")
        if query_name not in set(config.get("allowed_queries", [])):
            return self.missing("database", f"Named query is not allowed: {query_name}")

        connection_env_var = config.get("connection_env_var", "")
        connection_string = os.getenv(connection_env_var)
        if not connection_string:
            return self.missing("database", f"Connection string env var is not set: {connection_env_var}")

        if "password" in requirement.get("fields", []):
            return self.missing("database", "Database connector does not return passwords; use env or inline secrets.")

        params = self._safe_params(requirement)
        db_type = str(config.get("type", "postgres")).lower()
        if db_type == "sqlite":
            return self._fetch_sqlite(connection_string, query_name, params, requirement)
        if db_type in {"postgres", "postgresql"}:
            return self._fetch_postgres(connection_string, query_name, params, requirement)

        return self.missing("database", f"Configured database type requires a project-approved driver: {db_type}")

    def _safe_params(self, requirement: dict[str, Any]) -> dict[str, Any]:
        constraints = requirement.get("constraints", {})
        params: dict[str, Any] = {}
        if "role" in constraints:
            params["role"] = str(constraints["role"])
        return params

    def _fetch_sqlite(
        self,
        connection_string: str,
        query_name: str,
        params: dict[str, Any],
        requirement: dict[str, Any],
    ) -> dict[str, Any]:
        db_path = connection_string.removeprefix("sqlite:///")
        readonly_uri = f"file:{Path(db_path).as_posix()}?mode=ro"
        with sqlite3.connect(readonly_uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(ALLOWED_QUERIES[query_name], params).fetchone()
        if not row:
            return self.missing("database", f"Named query returned no data: {query_name}")
        data = dict(row)
        missing = validate_required_fields(data, requirement.get("fields", []))
        if missing:
            return self.missing("database", f"Query result missed fields: {', '.join(missing)}")
        return self.success("database", data, query_name)

    def _fetch_postgres(
        self,
        connection_string: str,
        query_name: str,
        params: dict[str, Any],
        requirement: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            import psycopg
        except ImportError:
            return self.missing("database", "Postgres driver is not installed; add an approved psycopg dependency.")

        query = ALLOWED_QUERIES[query_name].replace(":role", "%(role)s")
        with psycopg.connect(connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(query, params)
                row = cursor.fetchone()
                columns = [column.name if hasattr(column, "name") else column[0] for column in cursor.description or []]
        if not row:
            return self.missing("database", f"Named query returned no data: {query_name}")
        data = dict(zip(columns, row))
        missing = validate_required_fields(data, requirement.get("fields", []))
        if missing:
            return self.missing("database", f"Query result missed fields: {', '.join(missing)}")
        return self.success("database", data, query_name)
