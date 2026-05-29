from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from agent.state import AgentState
from agent.utils.command_runner import run_command
from agent.utils.file_writer import ensure_dir, write_text


ROOT = Path(__file__).resolve().parents[2]
GENERATED_ROOT = ROOT / "generated-tests"
REPORT_PATH = ROOT / "reports" / "validation_report.md"


def _package_scripts() -> dict[str, str]:
    package_path = GENERATED_ROOT / "package.json"
    if not package_path.exists():
        return {}
    return json.loads(package_path.read_text(encoding="utf-8")).get("scripts", {})


def _npm_available() -> bool:
    return bool(shutil.which("npm") or shutil.which("npm.cmd"))


async def validate_generated_project(state: AgentState) -> dict[str, Any]:
    ensure_dir(REPORT_PATH.parent)
    lines = ["# Validation Report", ""]
    status = "passed"

    if not _npm_available():
        status = "blocked"
        lines.append("- BLOCKED: npm was not found on PATH, so Playwright project validation could not run.")
        lines.append("- Python files were still generated and can be inspected.")
        report = "\n".join(lines) + "\n"
        write_text(REPORT_PATH, report)
        return {"validation_status": status, "validation_report": report}

    commands: list[tuple[str, list[str]]] = [("npm install", ["npm", "install"])]
    scripts = _package_scripts()
    if "install:browsers" in scripts:
        commands.append(("npm run install:browsers", ["npm", "run", "install:browsers"]))
    if "test:list" in scripts:
        commands.append(("npm run test:list", ["npm", "run", "test:list"]))
    else:
        commands.append(("npx playwright test --list", ["npx", "playwright", "test", "--list"]))
    if "typecheck" in scripts:
        commands.append(("npm run typecheck", ["npm", "run", "typecheck"]))
    if "lint" in scripts:
        commands.append(("npm run lint", ["npm", "run", "lint"]))
    if state.get("run_tests") and "test" in scripts and not state.get("missing_info"):
        commands.append(("npm test", ["npm", "test"]))
    elif state.get("run_tests"):
        lines.append("- SKIPPED: full test execution needs missing information to be resolved first.")

    for label, command in commands:
        result = await run_command(command, cwd=GENERATED_ROOT, timeout=120)
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- exit_code: {result.exit_code}")
        if result.stdout:
            lines.append("")
            lines.append("```text")
            lines.append(result.stdout[-3000:])
            lines.append("```")
        if result.stderr:
            lines.append("")
            lines.append("```text")
            lines.append(result.stderr[-3000:])
            lines.append("```")
        lines.append("")
        if result.exit_code != 0:
            status = "failed"
            break

    report = "\n".join(lines).rstrip() + "\n"
    write_text(REPORT_PATH, report)
    return {"validation_status": status, "validation_report": report}
