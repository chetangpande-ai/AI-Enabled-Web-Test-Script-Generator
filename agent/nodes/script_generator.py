from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from agent.state import AgentState, ExploredAction, LocatorCandidate
from agent.utils.file_writer import ensure_dir, write_text
from agent.utils.token_budget import compact_text


ROOT = Path(__file__).resolve().parents[2]
GENERATED_TEST = ROOT / "generated-tests" / "tests" / "generated-flow.spec.ts"


def _ts_string(value: str) -> str:
    return json.dumps(value)


def _regex_literal(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return "/.+/"
    escaped = re.escape(cleaned[:80]).replace("/", r"\/")
    return f"/{escaped}/i"


def _locator_ts(locator: LocatorCandidate) -> str:
    kind = locator.get("kind")
    if kind == "role":
        return f"page.getByRole({_ts_string(locator.get('role', 'button'))}, {{ name: {_regex_literal(locator.get('name', ''))} }})"
    if kind == "label":
        return f"page.getByLabel({_regex_literal(locator.get('label', ''))})"
    if kind == "placeholder":
        return f"page.getByPlaceholder({_regex_literal(locator.get('placeholder', ''))})"
    if kind == "text":
        return f"page.getByText({_regex_literal(locator.get('text', ''))})"
    return f"page.locator({_ts_string(locator.get('selector', 'body'))})"


def _locator_comment(action: ExploredAction) -> str:
    backups = [_locator_ts(item) for item in action.get("backup_locators", [])]
    if not backups:
        return ""
    return "    // Backup locators: " + "; ".join(backups)


def _safe_name(prefix: str, index: int) -> str:
    return f"{prefix}{index}"


def _data_keys(actions: list[ExploredAction]) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    seen: set[str] = set()
    for action in actions:
        key = action.get("value_key")
        if key and key not in seen:
            seen.add(key)
            keys.append((key, action.get("value_placeholder", f"TODO_{key.upper()}")))
    return keys


def _action_lines(action: ExploredAction, index: int) -> list[str]:
    lines: list[str] = []
    lines.append(f"    // Step {action.get('step_index', index)}: {action.get('step_text', '')}")
    primary = _locator_ts(action.get("primary_locator", {"kind": "css", "selector": "body"}))
    locator_name = _safe_name("target", index)
    lines.append(f"    const {locator_name} = {primary};")
    comment = _locator_comment(action)
    if comment:
        lines.append(comment)

    action_type = action.get("action")
    if action_type == "fill":
        value_key = action.get("value_key", "value")
        lines.append(f"    await {locator_name}.fill(testData.{value_key});")
        lines.append(f"    await expect({locator_name}).toHaveValue(testData.{value_key});")
    elif action_type == "select":
        value_key = action.get("value_key", "value")
        lines.append(f"    await {locator_name}.selectOption(testData.{value_key});")
    elif action_type == "check":
        lines.append(f"    await {locator_name}.check();")
        lines.append(f"    await expect({locator_name}).toBeChecked();")
    elif action_type == "uncheck":
        lines.append(f"    await {locator_name}.uncheck();")
        lines.append(f"    await expect({locator_name}).not.toBeChecked();")
    elif action_type == "assert_text_or_url":
        expected = str(action.get("assertion", {}).get("expected", action.get("target", "")))
        lines.append(f"    await expect(page.getByText({_regex_literal(expected)})).toBeVisible();")
    else:
        lines.append(f"    await {locator_name}.click();")
        lines.append("    await page.waitForLoadState('domcontentloaded');")
        assertion = action.get("assertion", {})
        if assertion.get("type") == "url_changed" and assertion.get("to"):
            lines.append(f"    await expect(page).toHaveURL({_regex_literal(str(assertion['to']))});")
    lines.append("")
    return lines


def _deterministic_script(state: AgentState) -> str:
    actions = state.get("explored_actions", [])
    title = "Generated web flow"
    flow = compact_text(state.get("flow", "Generated flow"), 140)
    data_entries = _data_keys(actions)
    data_lines = [
        f"      {key}: process.env.{key.upper()} ?? {_ts_string(placeholder)},"
        for key, placeholder in data_entries
    ]
    if not data_lines:
        data_lines = ["      exampleValue: process.env.EXAMPLE_VALUE ?? 'TODO_VALUE',"]

    body: list[str] = []
    body.append("import { test, expect } from '@playwright/test';")
    body.append("")
    body.append(f"test.describe({_ts_string(title)}, () => {{")
    body.append(f"  test({_ts_string(flow)}, async ({{ page }}) => {{")
    body.append("    const testData = {")
    body.extend(data_lines)
    body.append("    };")
    body.append("")
    body.append(f"    await page.goto({_ts_string(state.get('app_url', ''))});")
    body.append("    await expect(page).not.toHaveURL('about:blank');")
    body.append("")

    for index, action in enumerate(actions, start=1):
        body.extend(_action_lines(action, index))

    if not actions:
        body.append("    // TODO: Add steps after providing missing information listed in reports/missing_info.md.")
        body.append("    await expect(page.locator('body')).toBeVisible();")

    body.append("  });")
    body.append("});")
    body.append("")
    return "\n".join(body)


def _llm_refine_script(state: AgentState, script: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return script

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return script

    prompt_path = ROOT / "agent" / "prompts" / "script_generation_prompt.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    compact_trace = {
        "url": state.get("app_url"),
        "flow": state.get("flow"),
        "actions": state.get("explored_actions", []),
        "missing_info": state.get("missing_info", []),
    }
    llm = ChatOpenAI(model=os.getenv("CRAWLER_AGENT_MODEL", "gpt-4o-mini"), temperature=0)
    response = llm.invoke(
        prompt.replace("{{TRACE_JSON}}", compact_text(json.dumps(compact_trace), 6000)).replace(
            "{{DRAFT_SCRIPT}}", compact_text(script, 8000)
        )
    )
    content = str(response.content).strip()
    match = re.search(r"```(?:typescript|ts)?\s*(.*?)```", content, flags=re.S | re.I)
    return (match.group(1).strip() if match else content) or script


def generate_script(state: AgentState) -> dict[str, Any]:
    ensure_dir(GENERATED_TEST.parent)
    script = _llm_refine_script(state, _deterministic_script(state))
    write_text(GENERATED_TEST, script)
    return {"generated_script_path": str(GENERATED_TEST)}
