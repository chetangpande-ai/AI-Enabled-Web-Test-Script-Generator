from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.state import AgentState
from agent.utils.data_masking import mask_sensitive
from agent.utils.file_writer import ensure_dir, write_json


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
MISSING_DATA_HITL = REPORTS / "missing_data_hitl.json"
SUPPORTED_DECISIONS = {"provide", "skip", "synthetic", "change-source", "reject"}


def _merge_dict(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _write_hitl_payload(state: AgentState, status: str, notes: str = "") -> None:
    ensure_dir(REPORTS)
    payload = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
        "missingData": state.get("missing_test_data", []),
        "supportedResponses": [
            "provide missing data",
            "skip this flow",
            "use synthetic data if allowed",
            "change data source",
            "reject and stop",
        ],
    }
    write_json(MISSING_DATA_HITL, mask_sensitive(payload))


def prepare_missing_data_hitl(state: AgentState) -> dict[str, Any]:
    missing = state.get("missing_test_data", [])
    if not missing:
        _write_hitl_payload(state, "not_needed")
        return {"missing_data_hitl_status": "not_needed"}

    _write_hitl_payload(state, "pending", "Awaiting human decision before browser exploration.")

    if not state.get("interactive_review"):
        return {"missing_data_hitl_status": "pending"}

    print("Required test data is missing. Browser exploration is paused.")
    for item in missing:
        print(f"- {item.get('exactInputNeeded', item.get('item', 'missing data'))}")
    decision = input("Choose: provide, skip, synthetic, change-source, reject: ").strip().lower()
    if decision not in SUPPORTED_DECISIONS:
        _write_hitl_payload(state, "pending", f"Unsupported decision entered: {decision}")
        return {"missing_data_hitl_status": "pending"}

    if decision == "provide":
        raw = input("Provide missing data as JSON: ").strip()
        try:
            provided = json.loads(raw)
        except json.JSONDecodeError as exc:
            _write_hitl_payload(state, "pending", f"Invalid JSON provided: {exc}")
            return {"missing_data_hitl_status": "pending"}
        _write_hitl_payload(state, "provided", "Human provided missing data interactively.")
        return {
            "missing_data_hitl_status": "provided",
            "test_data": _merge_dict(state.get("test_data", {}), provided),
        }

    if decision == "skip":
        _write_hitl_payload(state, "skipped", "Human chose to skip the flow.")
        return {"missing_data_hitl_status": "skipped", "skip_flow": True}

    if decision == "synthetic":
        allowed = all(item.get("canContinue") for item in missing)
        note = "Synthetic data request recorded; rerun after allowing synthetic data for the missing requirement."
        if not allowed:
            note = "Synthetic data was requested, but one or more missing requirements do not allow continuation."
        _write_hitl_payload(state, "synthetic_requested", note)
        return {"missing_data_hitl_status": "synthetic_requested"}

    if decision == "change-source":
        _write_hitl_payload(state, "change_source_requested", "Human chose to change data source config and rerun.")
        return {"missing_data_hitl_status": "change_source_requested"}

    _write_hitl_payload(state, "rejected", "Human rejected the flow because data is unavailable.")
    return {"missing_data_hitl_status": "rejected", "stop_requested": True}


def apply_missing_data_decision(decision: str, notes: str = "", data: dict[str, Any] | None = None) -> str:
    if decision not in SUPPORTED_DECISIONS:
        raise ValueError("decision must be one of: provide, skip, synthetic, change-source, reject")
    ensure_dir(REPORTS)
    payload: dict[str, Any] = {}
    if MISSING_DATA_HITL.exists():
        payload = json.loads(MISSING_DATA_HITL.read_text(encoding="utf-8"))
    payload.update(
        {
            "status": decision,
            "notes": notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if data:
        payload["providedDataPreview"] = mask_sensitive(data)
    write_json(MISSING_DATA_HITL, payload)
    return str(MISSING_DATA_HITL)

