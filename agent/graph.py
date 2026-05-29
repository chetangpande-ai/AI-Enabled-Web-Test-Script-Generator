from __future__ import annotations

from typing import Any

from agent.nodes.flow_analyzer import analyze_flow
from agent.nodes.hitl_review import prepare_hitl_review
from agent.nodes.missing_data_hitl import prepare_missing_data_hitl
from agent.nodes.page_context_extractor import finalize_page_context
from agent.nodes.playwright_explorer import explore_flow
from agent.nodes.script_generator import generate_script
from agent.nodes.test_data_connector import fetch_test_data_candidates
from agent.nodes.test_data_requirement import identify_test_data_requirements
from agent.nodes.test_data_resolver import resolve_test_data
from agent.nodes.validator import validate_generated_project
from agent.state import AgentState


def build_graph():
    """Build the small fixed LangGraph workflow."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph is required. Install dependencies with: pip install -r requirements.txt"
        ) from exc

    graph = StateGraph(AgentState)
    graph.add_node("flow_analyzer", analyze_flow)
    graph.add_node("test_data_requirement", identify_test_data_requirements)
    graph.add_node("test_data_connector", fetch_test_data_candidates)
    graph.add_node("test_data_resolver", resolve_test_data)
    graph.add_node("missing_data_hitl", prepare_missing_data_hitl)
    graph.add_node("playwright_explorer", explore_flow)
    graph.add_node("page_context_extractor", finalize_page_context)
    graph.add_node("script_generator", generate_script)
    graph.add_node("validator", validate_generated_project)
    graph.add_node("hitl_review", prepare_hitl_review)

    graph.set_entry_point("flow_analyzer")
    graph.add_edge("flow_analyzer", "test_data_requirement")
    graph.add_edge("test_data_requirement", "test_data_connector")
    graph.add_edge("test_data_connector", "test_data_resolver")
    graph.add_edge("test_data_resolver", "missing_data_hitl")
    graph.add_conditional_edges(
        "missing_data_hitl",
        _route_after_missing_data_hitl,
        {
            "resolve_again": "test_data_connector",
            "continue": "playwright_explorer",
        },
    )
    graph.add_edge("playwright_explorer", "page_context_extractor")
    graph.add_edge("page_context_extractor", "script_generator")
    graph.add_edge("script_generator", "validator")
    graph.add_edge("validator", "hitl_review")
    graph.add_edge("hitl_review", END)
    return graph.compile()


def _route_after_missing_data_hitl(state: AgentState) -> str:
    if state.get("missing_data_hitl_status") == "provided":
        return "resolve_again"
    return "continue"


async def run_agent(initial_state: dict[str, Any]) -> AgentState:
    app = build_graph()
    return await app.ainvoke(initial_state)
