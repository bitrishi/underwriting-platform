"""StateGraph builder for the three-agent underwriting workflow."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.orchestrator.edges import (
    route_after_human_review,
    should_escalate,
    should_route_after_fetch,
)
from src.orchestrator.nodes import (
    compliance_node,
    doc_review_node,
    fatal_error_node,
    fha_compliance_node,
    fetch_data_node,
    final_decision_node,
    human_review_node,
    risk_scoring_node,
)
from src.orchestrator.state import UnderwritingState


def route_by_loan_type(state: UnderwritingState) -> str:
    """Route risk scoring output to loan-type-specific compliance sequence."""
    loan_type = str(state.get("loan_type", "conventional")).strip().lower()
    if loan_type == "fha":
        return "fha_compliance"
    return "compliance"


def create_underwriting_graph(checkpointer: MemorySaver | None = None):
    """Build and compile the full underwriting orchestration graph.

    Uses ``MemorySaver`` by default for local development interrupt/resume flows.
    """
    graph = StateGraph(UnderwritingState)

    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("doc_review", doc_review_node)
    graph.add_node("risk_scoring", risk_scoring_node)
    graph.add_node("fha_compliance", fha_compliance_node)
    graph.add_node("compliance", compliance_node)
    graph.add_node("fatal_error", fatal_error_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("final_decision", final_decision_node)

    graph.add_edge(START, "fetch_data")
    graph.add_edge(START, "doc_review")

    graph.add_conditional_edges(
        "fetch_data",
        should_route_after_fetch,
        {
            "fatal_error": "fatal_error",
            "continue": "risk_scoring",
        },
    )

    graph.add_edge("doc_review", "risk_scoring")

    graph.add_conditional_edges(
        "risk_scoring",
        route_by_loan_type,
        {
            "fha_compliance": "fha_compliance",
            "compliance": "compliance",
        },
    )

    graph.add_edge("fha_compliance", "compliance")

    graph.add_conditional_edges(
        "compliance",
        should_escalate,
        {
            "human_review": "human_review",
            "final_decision": "final_decision",
        },
    )

    graph.add_edge("fatal_error", "final_decision")
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "fetch_data": "fetch_data",
            "final_decision": "final_decision",
        },
    )
    graph.add_edge("final_decision", END)

    saver = checkpointer or MemorySaver()
    return graph.compile(checkpointer=saver)
