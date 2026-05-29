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
    value_path: str
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


class DataRequirement(TypedDict, total=False):
    name: str
    type: str
    required: bool
    fields: list[str]
    constraints: dict[str, Any]
    sourcePreference: list[str]
    syntheticAllowed: bool
    classification: str
    reason: str


class ConnectorResult(TypedDict, total=False):
    requirement: str
    status: str
    source: str
    data: dict[str, Any]
    alias: str
    reason: str


class AgentState(TypedDict, total=False):
    app_url: str
    flow: str
    environment: str
    data_profile: dict[str, Any]
    test_data: dict[str, Any]
    constraints: dict[str, Any]
    run_tests: bool
    interactive_review: bool
    analyzed_flow: list[FlowStep]
    test_data_requirements: list[DataRequirement]
    connector_results: dict[str, list[ConnectorResult]]
    resolved_test_data: dict[str, Any]
    data_ready: bool
    missing_test_data: list[dict[str, Any]]
    missing_data_hitl_status: str
    missing_data_decision: dict[str, Any]
    skip_flow: bool
    stop_requested: bool
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
