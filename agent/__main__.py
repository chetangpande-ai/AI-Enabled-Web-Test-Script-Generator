from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from agent.graph import run_agent
from agent.nodes.hitl_review import apply_review_decision
from agent.nodes.missing_data_hitl import apply_missing_data_decision


def _load_json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    candidate = Path(value)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))

    return json.loads(value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agent",
        description="Generate reviewable Playwright Test scripts from a focused web flow.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Explore a flow and generate a TypeScript test.")
    run.add_argument("--url", required=True, help="Application URL to open.")
    run.add_argument("--flow", required=True, help="High-level functional flow to automate.")
    run.add_argument("--environment", default="qa", help="Environment name used by data source config.")
    run.add_argument("--data-profile", help="JSON object or path with optional data profile preferences.")
    run.add_argument(
        "--test-data",
        help="JSON object or path with optional data such as email, username, password, searchTerm.",
    )
    run.add_argument(
        "--constraints",
        help="JSON object or path with options such as browser, headless, pages_to_avoid.",
    )
    run.add_argument(
        "--run-tests",
        action="store_true",
        help="Run generated Playwright tests after static validation when enough data is present.",
    )
    run.add_argument(
        "--interactive-review",
        action="store_true",
        help="Prompt for approve/reject/change after generation.",
    )

    review = subcommands.add_parser("review", help="Record a human review decision.")
    review.add_argument("--decision", required=True, choices=["approve", "reject", "changes"])
    review.add_argument("--notes", default="", help="Reviewer notes or requested changes.")

    missing = subcommands.add_parser("missing-data", help="Record a missing-data HITL decision.")
    missing.add_argument(
        "--decision",
        required=True,
        choices=["provide", "skip", "synthetic", "change-source", "reject"],
    )
    missing.add_argument("--notes", default="", help="Reviewer notes or requested data-source changes.")
    missing.add_argument("--data", help="JSON object or path with provided missing data. Values are masked in metadata.")

    return parser


async def _run(args: argparse.Namespace) -> int:
    state = await run_agent(
        {
            "app_url": args.url,
            "flow": args.flow,
            "environment": args.environment,
            "data_profile": _load_json_arg(args.data_profile),
            "test_data": _load_json_arg(args.test_data),
            "constraints": _load_json_arg(args.constraints),
            "run_tests": args.run_tests,
            "interactive_review": args.interactive_review,
        }
    )

    print(f"Generated script: {state.get('generated_script_path', 'not generated')}")
    print(f"Exploration status: {state.get('exploration_status', 'unknown')}")
    print(f"Test data ready: {state.get('data_ready', False)}")
    print(f"Validation status: {state.get('validation_status', 'unknown')}")
    missing = state.get("missing_info", [])
    if missing:
        print("Missing information:")
        for item in missing:
            print(f"- {item}")
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "review":
        path = apply_review_decision(args.decision, args.notes)
        print(f"Review metadata updated: {path}")
        return 0

    if args.command == "missing-data":
        path = apply_missing_data_decision(args.decision, args.notes, _load_json_arg(args.data))
        print(f"Missing-data HITL metadata updated: {path}")
        return 0

    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
