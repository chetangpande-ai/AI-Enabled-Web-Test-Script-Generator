from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.state import AgentState, DataRequirement
from agent.utils.file_writer import ensure_dir, write_text
from agent.utils.token_budget import compact_text


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "reports" / "test_data_requirements.md"


SECURITY_WORDS = {"otp", "captcha", "mfa", "2fa", "two-factor", "two factor", "one-time"}


def _flow_name(flow: str) -> str:
    return compact_text(flow.strip().splitlines()[0] if flow.strip() else "Generated flow", 80)


def _has_any(flow: str, words: set[str]) -> bool:
    lowered = flow.lower()
    return any(word in lowered for word in words)


def _requirement(
    name: str,
    data_type: str,
    fields: list[str],
    constraints: dict[str, Any],
    source_preference: list[str],
    synthetic_allowed: bool,
    classification: str,
    reason: str,
    required: bool = True,
) -> DataRequirement:
    return {
        "name": name,
        "type": data_type,
        "required": required,
        "fields": fields,
        "constraints": constraints,
        "sourcePreference": source_preference,
        "syntheticAllowed": synthetic_allowed,
        "classification": classification,
        "reason": reason,
    }


def _deterministic_requirements(flow: str) -> list[DataRequirement]:
    requirements: list[DataRequirement] = []

    if _has_any(flow, SECURITY_WORDS):
        requirements.append(
            _requirement(
                "restrictedAccess",
                "restricted_access",
                [],
                {},
                [],
                False,
                "not_automatable_due_to_security_control",
                "The flow references OTP, CAPTCHA, MFA, or another restricted access control.",
            )
        )

    if _has_any(flow, {"login", "log in", "sign in", "signin", "authenticate", "account"}):
        requirements.append(
            _requirement(
                "validCustomerUser",
                "user",
                ["username", "password", "role"],
                {"role": "customer", "status": "active"},
                ["inline", "env", "json", "database", "api"],
                False,
                "existing_qa_data_required",
                "A valid existing QA user is required before browser exploration.",
            )
        )

    if _has_any(flow, {"product", "search", "cart", "checkout", "order", "purchase", "buy"}):
        requirements.append(
            _requirement(
                "inStockProduct",
                "product",
                ["sku", "name", "searchTerm"],
                {"status": "inStock"},
                ["inline", "json", "csv", "database", "api"],
                False,
                "existing_qa_data_required",
                "The flow needs a valid in-stock product to avoid random search data.",
            )
        )

    if _has_any(flow, {"shipping", "address", "delivery", "checkout"}):
        requirements.append(
            _requirement(
                "shippingAddress",
                "address",
                ["line1", "city", "state", "postalCode"],
                {},
                ["inline", "json", "csv", "synthetic"],
                True,
                "synthetic_data_allowed",
                "A non-sensitive shipping address can safely use synthetic QA data.",
            )
        )

    if _has_any(flow, {"payment", "card", "cvv"}):
        requirements.append(
            _requirement(
                "paymentMethod",
                "payment",
                ["cardNumber", "expiry", "cvv"],
                {"environment": "test"},
                ["inline", "env", "json", "api"],
                False,
                "user_provided_data_required",
                "Payment data must be approved QA test data and will be masked in reports.",
            )
        )

    return requirements


def _write_requirements_report(flow_name: str, requirements: list[DataRequirement]) -> None:
    ensure_dir(REPORT_PATH.parent)
    lines = ["# Test Data Requirements", "", f"- Flow name: {flow_name}", ""]
    if not requirements:
        lines.append("- No external test data requirements were inferred.")
    for item in requirements:
        lines.extend(
            [
                f"## {item['name']}",
                "",
                f"- Type: `{item['type']}`",
                f"- Required: `{item.get('required', True)}`",
                f"- Required fields: `{', '.join(item.get('fields', [])) or 'none'}`",
                f"- Data constraints: `{item.get('constraints', {})}`",
                f"- Preferred sources: `{', '.join(item.get('sourcePreference', [])) or 'none'}`",
                f"- Synthetic data allowed: `{item.get('syntheticAllowed', False)}`",
                f"- Classification: `{item.get('classification', '')}`",
                f"- Why: {item.get('reason', '')}",
                "",
            ]
        )
    write_text(REPORT_PATH, "\n".join(lines).rstrip() + "\n")


def identify_test_data_requirements(state: AgentState) -> dict[str, Any]:
    flow = state.get("flow", "")
    flow_name = _flow_name(flow)
    requirements = _deterministic_requirements(flow)
    _write_requirements_report(flow_name, requirements)

    assumptions = list(state.get("assumptions", []))
    assumptions.append("Test data is resolved before Playwright exploration starts.")
    assumptions.append("Secrets are fetched by deterministic connectors and masked in reports.")

    return {
        "test_data_requirements": requirements,
        "resolved_test_data": {"environment": state.get("environment", "qa"), "flowName": flow_name},
        "assumptions": assumptions,
    }

