from __future__ import annotations

from typing import Any

from agent.nodes.flow_analyzer import analyze_flow
from agent.nodes.hitl_review import prepare_hitl_review
from agent.nodes.playwright_explorer import explore_flow
from agent.nodes.script_generator import generate_script
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
    graph.add_node("playwright_explorer", explore_flow)
    graph.add_node("script_generator", generate_script)
    graph.add_node("validator", validate_generated_project)
    graph.add_node("hitl_review", prepare_hitl_review)

    graph.set_entry_point("flow_analyzer")
    graph.add_edge("flow_analyzer", "playwright_explorer")
    graph.add_edge("playwright_explorer", "script_generator")
    graph.add_edge("script_generator", "validator")
    graph.add_edge("validator", "hitl_review")
    graph.add_edge("hitl_review", END)
    return graph.compile()


async def run_agent(initial_state: dict[str, Any]) -> AgentState:
    app = build_graph()
    return await app.ainvoke(initial_state)

