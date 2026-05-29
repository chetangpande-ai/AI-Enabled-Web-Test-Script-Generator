from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.state import AgentState
from agent.utils.file_writer import ensure_dir, write_json, write_text


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
SUMMARY = REPORTS / "exploration_summary.md"
MISSING = REPORTS / "missing_info.md"
REVIEW = REPORTS / "hitl_review.json"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def prepare_hitl_review(state: AgentState) -> dict[str, Any]:
    ensure_dir(REPORTS)
    script_path = state.get("generated_script_path", "")
    actions = state.get("explored_actions", [])

    summary = [
        "# Exploration Summary",
        "",
        f"- Generated test script: `{script_path}`",
        f"- Exploration status: `{state.get('exploration_status', 'unknown')}`",
        f"- Validation status: `{state.get('validation_status', 'unknown')}`",
        "",
        "## Explored Steps",
        "",
    ]
    if actions:
        for action in actions:
            summary.append(
                f"- Step {action.get('step_index')}: {action.get('action')} `{action.get('target', action.get('step_text', ''))}` "
                f"from `{action.get('url_before', '')}` to `{action.get('url_after', '')}`"
            )
    else:
        summary.append("- None captured.")

    summary.extend(
        [
            "",
            "## Assumptions",
            "",
            _bullets(state.get("assumptions", [])),
            "",
            "## Flows Successfully Automated",
            "",
            _bullets(state.get("automated_flows", [])),
            "",
            "## Flows Not Automated",
            "",
            _bullets(state.get("not_automated_flows", [])),
            "",
            "## Human Review Options",
            "",
            "- Approve: `python -m agent review --decision approve --notes \"looks good\"`",
            "- Reject: `python -m agent review --decision reject --notes \"reason\"`",
            "- Request changes: `python -m agent review --decision changes --notes \"specific changes\"`",
            "",
        ]
    )
    write_text(SUMMARY, "\n".join(summary))

    missing = state.get("missing_info", [])
    write_text(
        MISSING,
        "# Missing Information\n\n"
        + (_bullets(missing) if missing else "- None\n")
        + "\n",
    )

    review_payload = {
        "status": "pending",
        "generated_script_path": script_path,
        "validation_status": state.get("validation_status"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Awaiting human approval, rejection, or requested changes.",
    }
    write_json(REVIEW, review_payload)

    if state.get("interactive_review"):
        decision = input("Review generated script: approve, reject, or changes? ").strip().lower()
        notes = input("Review notes: ").strip()
        apply_review_decision(decision, notes)
        return {"hitl_status": decision}

    return {"hitl_status": "pending"}


def apply_review_decision(decision: str, notes: str = "") -> str:
    if decision not in {"approve", "reject", "changes"}:
        raise ValueError("decision must be one of: approve, reject, changes")
    ensure_dir(REPORTS)
    payload: dict[str, Any] = {}
    if REVIEW.exists():
        payload = json.loads(REVIEW.read_text(encoding="utf-8"))
    payload.update(
        {
            "status": decision,
            "notes": notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_json(REVIEW, payload)
    return str(REVIEW)

