from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.connectors.api_connector import ApiConnector
from agent.connectors.csv_connector import CsvConnector
from agent.connectors.db_connector import DbConnector
from agent.connectors.env_connector import EnvConnector
from agent.connectors.json_connector import JsonConnector
from agent.state import AgentState, ConnectorResult, DataRequirement
from agent.utils.schema_validator import matches_constraints, validate_required_fields


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "agent" / "config" / "data_sources.yaml"
DEFAULT_CONFIG: dict[str, Any] = {
    "environment": "qa",
    "sources": {
        "inline": {"enabled": True},
        "env": {
            "enabled": True,
            "keys": {
                "customer_username": "QA_CUSTOMER_USERNAME",
                "customer_password": "QA_CUSTOMER_PASSWORD",
                "test_data_api_token": "TEST_DATA_API_TOKEN",
                "db_connection_string": "QA_DB_CONNECTION_STRING",
            },
        },
        "json": {
            "enabled": True,
            "paths": {
                "users": "generated-tests/test-data/users.json",
                "products": "generated-tests/test-data/products.json",
                "checkout": "generated-tests/test-data/checkout-data.json",
            },
        },
        "csv": {
            "enabled": True,
            "paths": {
                "users": "data/users.csv",
                "products": "data/products.csv",
                "checkout": "data/checkout-data.csv",
            },
        },
        "database": {
            "enabled": False,
            "type": "postgres",
            "connection_env_var": "QA_DB_CONNECTION_STRING",
            "allowed_queries": ["get_active_customer", "get_in_stock_product", "get_customer_with_balance"],
        },
        "api": {
            "enabled": False,
            "base_url_env_var": "TEST_DATA_API_URL",
            "token_env_var": "TEST_DATA_API_TOKEN",
            "allowed_operations": [
                "get_active_customer",
                "get_in_stock_product",
                "create_test_customer",
                "setup_cart",
            ],
        },
    },
}


def _load_config() -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError:
        return DEFAULT_CONFIG

    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or DEFAULT_CONFIG


def _type_key(requirement: DataRequirement) -> str:
    data_type = requirement.get("type", "")
    return {
        "user": "user",
        "product": "product",
        "address": "shippingAddress",
        "payment": "paymentMethod",
    }.get(data_type, requirement.get("name", data_type))


def _inline_fetch(requirement: DataRequirement, inline_data: dict[str, Any]) -> ConnectorResult:
    candidates = [
        inline_data.get(requirement.get("name", "")),
        inline_data.get(_type_key(requirement)),
        inline_data.get(requirement.get("type", "")),
    ]
    if requirement.get("type") == "user":
        candidates.append({key: inline_data.get(key) for key in ("username", "email", "password", "role", "status")})
    if requirement.get("type") == "product":
        candidates.append({key: inline_data.get(key) for key in ("sku", "name", "searchTerm", "status")})

    for candidate in candidates:
        if not isinstance(candidate, dict) or not any(candidate.values()):
            continue
        data = dict(candidate)
        for key, value in requirement.get("constraints", {}).items():
            data.setdefault(key, value)
        if not matches_constraints(data, requirement.get("constraints", {})):
            continue
        missing = validate_required_fields(data, requirement.get("fields", []))
        if missing:
            return {
                "status": "missing",
                "source": "inline",
                "requirement": requirement["name"],
                "reason": f"Inline data missed fields: {', '.join(missing)}",
            }
        return {
            "status": "success",
            "source": "inline",
            "requirement": requirement["name"],
            "data": data,
            "alias": str(data.get("alias", "")),
        }

    return {
        "status": "missing",
        "source": "inline",
        "requirement": requirement["name"],
        "reason": "No matching inline data was provided.",
    }


def fetch_test_data_candidates(state: AgentState) -> dict[str, Any]:
    config = _load_config()
    connector_map = {
        "env": EnvConnector(),
        "json": JsonConnector(),
        "csv": CsvConnector(),
        "database": DbConnector(),
        "api": ApiConnector(),
    }
    results: dict[str, list[ConnectorResult]] = {}
    inline_data = state.get("test_data", {})

    for requirement in state.get("test_data_requirements", []):
        requirement_results: list[ConnectorResult] = []
        for source in requirement.get("sourcePreference", []):
            if source == "synthetic":
                continue
            if source == "inline":
                requirement_results.append(_inline_fetch(requirement, inline_data))
                continue
            connector = connector_map.get(source)
            request = {"source": source, "requirement": requirement, "config": config, "root": ROOT}
            if not connector:
                requirement_results.append(
                    {
                        "status": "missing",
                        "source": source,
                        "requirement": requirement["name"],
                        "reason": "No connector exists for this source.",
                    }
                )
                continue
            if not connector.can_handle(request):
                requirement_results.append(
                    {
                        "status": "missing",
                        "source": source,
                        "requirement": requirement["name"],
                        "reason": "Source is disabled or not configured.",
                    }
                )
                continue
            result = connector.fetch(request)
            result["requirement"] = requirement["name"]
            requirement_results.append(result)
        results[requirement["name"]] = requirement_results

    return {"connector_results": results}
