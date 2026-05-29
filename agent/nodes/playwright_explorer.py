from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

from agent.nodes.page_context_extractor import extract_page_context
from agent.state import AgentState, ExploredAction, FlowStep, LocatorCandidate
from agent.utils.token_budget import keyword_list


FIELD_ALIASES = {
    "email": {"email", "e-mail", "mail"},
    "username": {"username", "user", "login"},
    "password": {"password", "passcode"},
    "searchTerm": {"search", "query", "keyword"},
    "firstName": {"first", "firstname", "given"},
    "lastName": {"last", "lastname", "surname", "family"},
}


def _avoid_url(url: str, constraints: dict[str, Any]) -> bool:
    patterns = constraints.get("pages_to_avoid") or constraints.get("avoid_pages") or []
    return any(str(pattern).lower() in url.lower() for pattern in patterns)


def _score_text(text: str, keywords: list[str]) -> int:
    normalized = " ".join(keyword_list(text))
    score = 0
    for keyword in keywords:
        if keyword in normalized:
            score += 3
        elif any(part.startswith(keyword) or keyword.startswith(part) for part in normalized.split()):
            score += 1
    return score


def _candidate_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in ("text", "label", "placeholder", "name", "type", "href")
        if item.get(key)
    )


def _locator_for_item(item: dict[str, Any], kind: str) -> LocatorCandidate:
    if kind in {"button", "link"} and item.get("text"):
        return {"kind": "role", "role": kind, "name": str(item["text"])}
    if item.get("label"):
        return {"kind": "label", "label": str(item["label"])}
    if item.get("placeholder"):
        return {"kind": "placeholder", "placeholder": str(item["placeholder"])}
    if item.get("selector"):
        return {"kind": "css", "selector": str(item["selector"])}
    if item.get("text"):
        return {"kind": "text", "text": str(item["text"])}
    return {"kind": "css", "selector": "body"}


def _backup_locators(item: dict[str, Any], kind: str) -> list[LocatorCandidate]:
    backups: list[LocatorCandidate] = []
    if item.get("label"):
        backups.append({"kind": "label", "label": str(item["label"])})
    if item.get("placeholder"):
        backups.append({"kind": "placeholder", "placeholder": str(item["placeholder"])})
    if item.get("text"):
        backups.append({"kind": "text", "text": str(item["text"])})
    if item.get("selector"):
        backups.append({"kind": "css", "selector": str(item["selector"])})
    primary = _locator_for_item(item, kind)
    return [locator for locator in backups if locator != primary][:3]


def _best_candidate(items: list[dict[str, Any]], keywords: list[str]) -> dict[str, Any] | None:
    scored = [(_score_text(_candidate_text(item), keywords), item) for item in items]
    scored = [(score, item) for score, item in scored if score > 0]
    if not scored:
        return items[0] if len(items) == 1 else None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]


def _test_data_key_for_field(field: dict[str, Any], step: FlowStep) -> str | None:
    haystack = " ".join([_candidate_text(field), step.get("text", "")]).lower()
    for key, aliases in FIELD_ALIASES.items():
        if any(alias in haystack for alias in aliases):
            return key
    field_type = str(field.get("type", "")).lower()
    if field_type == "password":
        return "password"
    if field_type in {"email", "search"}:
        return "email" if field_type == "email" else "searchTerm"
    return None


def _missing_placeholder(key: str | None, field: dict[str, Any]) -> str:
    if key:
        return f"TODO_{re.sub(r'[^A-Za-z0-9]+', '_', key).upper()}"
    label = field.get("label") or field.get("placeholder") or field.get("name") or "VALUE"
    return f"TODO_{re.sub(r'[^A-Za-z0-9]+', '_', str(label)).upper()}"


async def _playwright_locator(page, locator: LocatorCandidate):
    kind = locator.get("kind")
    if kind == "role":
        return page.get_by_role(locator["role"], name=locator["name"])
    if kind == "label":
        return page.get_by_label(locator["label"])
    if kind == "placeholder":
        return page.get_by_placeholder(locator["placeholder"])
    if kind == "text":
        return page.get_by_text(locator["text"])
    return page.locator(locator.get("selector", "body"))


async def _execute_click(page, item: dict[str, Any], kind: str) -> None:
    locator = await _playwright_locator(page, _locator_for_item(item, kind))
    await locator.first.click(timeout=6000)
    await page.wait_for_load_state("domcontentloaded", timeout=6000)


async def _execute_fill(page, field: dict[str, Any], value: str) -> None:
    locator = await _playwright_locator(page, _locator_for_item(field, "input"))
    await locator.first.fill(value, timeout=6000)


async def explore_flow(state: AgentState) -> dict[str, Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        return {
            "exploration_status": "blocked",
            "missing_info": list(state.get("missing_info", []))
            + ["Python Playwright is not installed. Run: pip install -r requirements.txt && python -m playwright install"],
        }

    url = state["app_url"]
    constraints = state.get("constraints", {})
    browser_name = str(constraints.get("browser", "chromium")).lower()
    headless = bool(constraints.get("headless", True))
    actions: list[ExploredAction] = []
    missing = list(state.get("missing_info", []))
    automated: list[str] = []
    not_automated: list[str] = []
    context_cache = dict(state.get("page_context_cache", {}))

    async with async_playwright() as p:
        browser_type = getattr(p, browser_name, p.chromium)
        browser = await browser_type.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=int(constraints.get("timeout_ms", 15000)))
            for step in state.get("analyzed_flow", []):
                context = await extract_page_context(page)
                context_cache[page.url] = context
                url_before = page.url
                intent = step.get("intent", "click")
                keywords = step.get("keywords") or keyword_list(step.get("text", ""))

                if context.get("errors"):
                    missing.append(f"Page reported error before step {step['index']}: {context['errors'][0]}")

                if intent == "assert":
                    target = step.get("text", "")
                    automated.append(step["text"])
                    actions.append(
                        {
                            "step_index": step["index"],
                            "step_text": step["text"],
                            "action": "assert_text_or_url",
                            "target": target,
                            "url_before": url_before,
                            "url_after": page.url,
                            "assertion": {"type": "text_or_url", "expected": target},
                            "status": "captured",
                        }
                    )
                    continue

                if intent in {"check", "uncheck"}:
                    checkable_fields = [
                        field
                        for field in context.get("inputs", [])
                        if str(field.get("type", "")).lower() in {"checkbox", "radio"}
                    ]
                    field = _best_candidate(checkable_fields, keywords)
                    if not field:
                        missing.append(f"Step {step['index']} could not find a matching checkbox or radio input.")
                        not_automated.append(step["text"])
                        continue
                    locator = await _playwright_locator(page, _locator_for_item(field, "input"))
                    if intent == "check":
                        await locator.first.check(timeout=6000)
                    else:
                        await locator.first.uncheck(timeout=6000)
                    automated.append(step["text"])
                    actions.append(
                        {
                            "step_index": step["index"],
                            "step_text": step["text"],
                            "action": intent,
                            "target": _candidate_text(field),
                            "url_before": url_before,
                            "url_after": page.url,
                            "primary_locator": _locator_for_item(field, "input"),
                            "backup_locators": _backup_locators(field, "input"),
                            "assertion": {"type": "checked", "expected": intent == "check"},
                            "status": "completed",
                        }
                    )
                    continue

                if intent in {"fill", "submit"}:
                    fields = context.get("inputs", [])
                    relevant_fields = [
                        field for field in fields if str(field.get("type", "")).lower() not in {"hidden", "submit", "button"}
                    ]
                    filled = False
                    for field in relevant_fields:
                        key = _test_data_key_for_field(field, step)
                        value = state.get("test_data", {}).get(key or "")
                        if not value:
                            if key:
                                missing.append(f"Step {step['index']} needs test data key '{key}'.")
                            continue
                        await _execute_fill(page, field, str(value))
                        filled = True
                        actions.append(
                            {
                                "step_index": step["index"],
                                "step_text": step["text"],
                                "action": "fill",
                                "value_key": key,
                                "value_placeholder": _missing_placeholder(key, field),
                                "target": _candidate_text(field),
                                "url_before": url_before,
                                "url_after": page.url,
                                "primary_locator": _locator_for_item(field, "input"),
                                "backup_locators": _backup_locators(field, "input"),
                                "assertion": {"type": "input_value", "value_key": key},
                                "status": "completed",
                            }
                        )

                    if intent == "fill" and filled:
                        automated.append(step["text"])
                        continue
                    if intent == "fill" and not filled:
                        not_automated.append(step["text"])
                        continue

                if intent == "select":
                    field = _best_candidate(context.get("inputs", []), keywords)
                    key = _test_data_key_for_field(field or {}, step) if field else None
                    value = state.get("test_data", {}).get(key or "")
                    if not field or not value:
                        missing.append(f"Step {step['index']} needs selectable field details and test data.")
                        not_automated.append(step["text"])
                        continue
                    locator = await _playwright_locator(page, _locator_for_item(field, "input"))
                    await locator.first.select_option(str(value), timeout=6000)
                    automated.append(step["text"])
                    actions.append(
                        {
                            "step_index": step["index"],
                            "step_text": step["text"],
                            "action": "select",
                            "value_key": key,
                            "value_placeholder": _missing_placeholder(key, field),
                            "target": _candidate_text(field),
                            "url_before": url_before,
                            "url_after": page.url,
                            "primary_locator": _locator_for_item(field, "input"),
                            "backup_locators": _backup_locators(field, "input"),
                            "status": "completed",
                        }
                    )
                    continue

                clickables = context.get("buttons", []) + [
                    link for link in context.get("links", []) if not _avoid_url(str(link.get("href", "")), constraints)
                ]
                target = _best_candidate(clickables, keywords)
                if not target:
                    missing.append(f"Step {step['index']} could not find a matching visible button or link.")
                    not_automated.append(step["text"])
                    continue

                kind = "link" if target in context.get("links", []) else "button"
                await _execute_click(page, target, kind)
                await asyncio.sleep(0.3)
                automated.append(step["text"])
                actions.append(
                    {
                        "step_index": step["index"],
                        "step_text": step["text"],
                        "action": "click",
                        "target": _candidate_text(target),
                        "url_before": url_before,
                        "url_after": page.url,
                        "primary_locator": _locator_for_item(target, kind),
                        "backup_locators": _backup_locators(target, kind),
                        "assertion": {"type": "url_changed", "from": url_before, "to": page.url}
                        if urlparse(url_before).path != urlparse(page.url).path
                        else {},
                        "status": "completed",
                    }
                )
        except Exception as exc:
            missing.append(f"Exploration blocked: {type(exc).__name__}: {exc}")
        finally:
            await browser.close()

    status = "completed" if automated and not not_automated and not missing else "partial" if automated else "blocked"
    return {
        "page_context_cache": context_cache,
        "explored_actions": actions,
        "missing_info": sorted(set(missing)),
        "automated_flows": automated,
        "not_automated_flows": not_automated,
        "exploration_status": status,
    }
