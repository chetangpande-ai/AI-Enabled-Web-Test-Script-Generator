from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class FlowStep(TypedDict, total=False):
    index: int
    text: str
    intent: str
    keywords: list[str]
    status: str
    notes: list[str]


class LocatorCandidate(TypedDict, total=False):
    kind: str
    role: str
    name: str
    label: str
    placeholder: str
    selector: str
    text: str


class ExploredAction(TypedDict, total=False):
    step_index: int
    step_text: str
    action: str
    value_key: str
    value_placeholder: str
    target: str
    url_before: str
    url_after: str
    primary_locator: LocatorCandidate
    backup_locators: list[LocatorCandidate]
    assertion: dict[str, Any]
    status: str
    notes: list[str]


class PageContext(TypedDict, total=False):
    url: str
    title: str
    buttons: list[dict[str, Any]]
    links: list[dict[str, Any]]
    inputs: list[dict[str, Any]]
    roles: list[dict[str, Any]]
    errors: list[str]


class AgentState(TypedDict, total=False):
    app_url: str
    flow: str
    test_data: dict[str, Any]
    constraints: dict[str, Any]
    run_tests: bool
    interactive_review: bool
    analyzed_flow: list[FlowStep]
    page_context_cache: dict[str, PageContext]
    explored_actions: list[ExploredAction]
    assumptions: list[str]
    missing_info: list[str]
    automated_flows: list[str]
    not_automated_flows: list[str]
    exploration_status: str
    generated_script_path: str
    validation_status: str
    validation_report: str
    hitl_status: NotRequired[str]

