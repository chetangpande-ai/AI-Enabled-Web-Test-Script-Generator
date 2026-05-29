from __future__ import annotations

import json
import os
import re
from typing import Any

from agent.state import AgentState, FlowStep
from agent.utils.token_budget import compact_text, keyword_list


INTENT_HINTS = {
    "fill": {"enter", "fill", "type", "provide", "input"},
    "click": {"click", "open", "choose", "tap", "go", "navigate"},
    "select": {"select", "pick", "choose"},
    "check": {"check", "enable", "tick"},
    "uncheck": {"uncheck", "disable", "untick"},
    "submit": {"submit", "save", "continue", "sign", "login", "log", "register"},
    "assert": {"verify", "assert", "see", "confirm", "expect", "should"},
}


def _split_flow(flow: str) -> list[str]:
    lines = [line.strip(" -\t") for line in flow.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines

    parts = re.split(r"\b(?:then|and then|after that)\b|[.;]", flow, flags=re.I)
    return [part.strip(" -\t") for part in parts if part.strip()]


def _classify_intent(text: str) -> str:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    for intent, hints in INTENT_HINTS.items():
        if words & hints:
            return intent
    if "password" in words or "email" in words or "username" in words:
        return "fill"
    return "click"


def _deterministic_analysis(flow: str) -> list[FlowStep]:
    steps: list[FlowStep] = []
    for index, text in enumerate(_split_flow(flow), start=1):
        steps.append(
            {
                "index": index,
                "text": compact_text(text, 240),
                "intent": _classify_intent(text),
                "keywords": keyword_list(text),
                "status": "pending",
                "notes": [],
            }
        )
    return steps


def _llm_analysis(flow: str) -> list[FlowStep] | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "flow_analysis_prompt.md")
    with open(prompt_path, encoding="utf-8") as prompt_file:
        prompt = prompt_file.read()

    llm = ChatOpenAI(model=os.getenv("CRAWLER_AGENT_MODEL", "gpt-4o-mini"), temperature=0)
    response = llm.invoke(prompt.replace("{{FLOW}}", compact_text(flow, 1600)))

    try:
        payload = json.loads(str(response.content))
    except json.JSONDecodeError:
        return None

    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        return None

    normalized: list[FlowStep] = []
    for index, item in enumerate(steps, start=1):
        if not isinstance(item, dict) or not item.get("text"):
            continue
        normalized.append(
            {
                "index": index,
                "text": compact_text(str(item["text"]), 240),
                "intent": str(item.get("intent") or _classify_intent(str(item["text"]))),
                "keywords": keyword_list(" ".join([str(item["text"]), " ".join(item.get("keywords", []))])),
                "status": "pending",
                "notes": [],
            }
        )
    return normalized or None


def analyze_flow(state: AgentState) -> dict[str, Any]:
    flow = state.get("flow", "").strip()
    if not flow:
        return {"missing_info": ["High-level functional flow is required."], "analyzed_flow": []}

    steps = _llm_analysis(flow) or _deterministic_analysis(flow)
    assumptions = list(state.get("assumptions", []))
    assumptions.append("The explorer follows only controls that score against the provided flow text.")
    assumptions.append("Full HTML is never sent to an LLM; only compact page context is cached.")

    return {
        "analyzed_flow": steps,
        "assumptions": assumptions,
        "missing_info": list(state.get("missing_info", [])),
        "page_context_cache": {},
    }

