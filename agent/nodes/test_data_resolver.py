from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.state import AgentState, ConnectorResult, DataRequirement
from agent.utils.data_masking import mask_sensitive
from agent.utils.file_writer import ensure_dir, write_json, write_text


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
SUMMARY_REPORT = REPORTS / "resolved_test_data_summary.md"
MISSING_REPORT = REPORTS / "missing_test_data.md"
RESOLVED_JSON = ROOT / "generated-tests" / "test-data" / "resolved-test-data.json"
RESOLUTION_ORDER = ["inline", "env", "json", "csv", "database", "api", "synthetic"]


def _resolved_key(requirement: DataRequirement) -> str:
    data_type = requirement.get("type", "")
    return {
        "user": "user",
        "product": "product",
        "address": "shippingAddress",
        "payment": "paymentMethod",
    }.get(data_type, requirement.get("name", data_type))


def _pick_result(requirement: DataRequirement, results: list[ConnectorResult]) -> ConnectorResult | None:
    allowed = requirement.get("sourcePreference", [])
    ordered_sources = [source for source in RESOLUTION_ORDER if source in allowed]
    for source in ordered_sources:
        for result in results:
            if result.get("source") == source and result.get("status") == "success":
                return result
    return None


def _synthetic_data(requirement: DataRequirement) -> dict[str, Any] | None:
    if not requirement.get("syntheticAllowed"):
        return None
    if requirement.get("type") == "address":
        return {
            "alias": "syntheticShippingAddress",
            "line1": "Test Street 1",
            "city": "Pune",
            "state": "MH",
            "postalCode": "411014",
        }
    return None


def _missing_item(requirement: DataRequirement, results: list[ConnectorResult]) -> dict[str, Any]:
    sources_checked = [result.get("source", "") for result in results]
    reasons = [result.get("reason", "") for result in results if result.get("reason")]
    exact_fields = ", ".join(requirement.get("fields", [])) or "manual approval"
    return {
        "item": requirement["name"],
        "whyRequired": requirement.get("reason", "Required for the requested flow."),
        "sourcesChecked": sources_checked,
        "failureReasons": reasons,
        "exactInputNeeded": f"Provide {exact_fields} for {requirement['name']}.",
        "canContinue": False,
    }


def _write_summary(resolved: dict[str, Any], sources_used: list[str], assumptions: list[str]) -> None:
    masked = mask_sensitive(resolved.get("resolvedData", {}))
    lines = [
        "# Resolved Test Data Summary",
        "",
        f"- Environment: `{resolved.get('environment', 'qa')}`",
        f"- Flow name: {resolved.get('flowName', '')}",
        f"- Data sources used: `{', '.join(sorted(set(sources_used))) or 'none'}`",
        "",
        "## Masked Resolved Data",
        "",
        "```json",
    ]
    import json

    lines.append(json.dumps(masked, indent=2, sort_keys=True))
    lines.extend(["```", "", "## Assumptions", ""])
    lines.extend(f"- {item}" for item in assumptions)
    write_text(SUMMARY_REPORT, "\n".join(lines).rstrip() + "\n")


def _write_missing(missing: list[dict[str, Any]]) -> None:
    lines = ["# Missing Test Data", ""]
    if not missing:
        lines.append("- None")
    for item in missing:
        lines.extend(
            [
                f"## {item['item']}",
                "",
                f"- Why it is required: {item['whyRequired']}",
                f"- Sources checked: `{', '.join(item['sourcesChecked']) or 'none'}`",
                f"- Exact input needed from user: {item['exactInputNeeded']}",
                f"- Flow can continue: `{item['canContinue']}`",
            ]
        )
        if item.get("failureReasons"):
            lines.append(f"- Failure reasons: `{'; '.join(item['failureReasons'])}`")
        lines.append("")
    write_text(MISSING_REPORT, "\n".join(lines).rstrip() + "\n")


def _write_resolved_json(resolved: dict[str, Any]) -> None:
    safe = mask_sensitive(resolved)
    # Keep env indirection for secrets in committed test-data; never persist secret values.
    write_json(RESOLVED_JSON, safe)


def resolve_test_data(state: AgentState) -> dict[str, Any]:
    ensure_dir(REPORTS)
    resolved: dict[str, Any] = {
        "environment": state.get("environment", "qa"),
        "flowName": state.get("resolved_test_data", {}).get("flowName", state.get("flow", "Generated flow")),
        "resolvedData": {},
        "missingData": [],
        "dataSourcesUsed": [],
    }
    missing: list[dict[str, Any]] = []
    connector_results = state.get("connector_results", {})

    for requirement in state.get("test_data_requirements", []):
        if requirement.get("classification") == "not_automatable_due_to_security_control":
            missing.append(_missing_item(requirement, []))
            continue

        results = connector_results.get(requirement["name"], [])
        picked = _pick_result(requirement, results)
        if picked:
            resolved["resolvedData"][_resolved_key(requirement)] = picked.get("data", {})
            resolved["dataSourcesUsed"].append(picked.get("source", ""))
            continue

        synthetic = _synthetic_data(requirement)
        if synthetic:
            resolved["resolvedData"][_resolved_key(requirement)] = synthetic
            resolved["dataSourcesUsed"].append("synthetic")
            continue

        if requirement.get("required", True):
            missing.append(_missing_item(requirement, results))

    resolved["missingData"] = missing
    data_ready = not missing
    assumptions = list(state.get("assumptions", []))
    if missing:
        assumptions.append("Browser exploration is paused until required test data is provided or the flow is skipped.")

    _write_summary(resolved, resolved["dataSourcesUsed"], assumptions)
    _write_missing(missing)
    _write_resolved_json(resolved)

    missing_info = list(state.get("missing_info", []))
    for item in missing:
        missing_info.append(item["exactInputNeeded"])

    return {
        "resolved_test_data": resolved,
        "data_ready": data_ready,
        "missing_test_data": missing,
        "missing_info": sorted(set(missing_info)),
        "assumptions": assumptions,
    }

