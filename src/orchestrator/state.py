"""State schema shared by all nodes in the underwriting graph."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


def merge_string_dicts(
    left: dict[str, str] | None,
    right: dict[str, str] | None,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    if left:
        merged.update(left)
    if right:
        merged.update(right)
    return merged


def merge_float_dicts(
    left: dict[str, float] | None,
    right: dict[str, float] | None,
) -> dict[str, float]:
    merged: dict[str, float] = {}
    if left:
        merged.update(left)
    if right:
        merged.update(right)
    return merged


def merge_any_dicts(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if left:
        merged.update(left)
    if right:
        merged.update(right)
    return merged


class UnderwritingState(TypedDict, total=False):
    """State bag accumulated across orchestrator node execution."""

    # Inputs
    app_id: str
    document_paths: list[str]
    loan_type: str
    graph_version: str
    thread_id: str

    # Agent outputs
    borrower_package: dict[str, Any] | None
    document_review: dict[str, Any] | None
    risk_assessment: dict[str, Any] | None
    compliance_result: dict[str, Any] | None
    fha_compliance_result: dict[str, Any] | None
    human_review_request: dict[str, Any] | None
    human_review_response: dict[str, Any] | None
    additional_data_request: str | None

    # Routing flags
    has_documents: bool
    needs_manual_review: bool
    fatal_error: bool
    simulate_existing_application: bool
    needs_additional_data: bool
    review_iterations: int

    # Final output
    final_decision: str | None
    final_report: str | None

    # Audit metadata
    node_timestamps: Annotated[dict[str, str], merge_string_dicts]
    node_durations_s: Annotated[dict[str, float], merge_float_dicts]
    node_execution_order: Annotated[list[str], add]
    total_tool_calls: int
    total_llm_calls: int
    estimated_cost_usd: float

    # Observability
    messages: Annotated[list, add_messages]
    errors: Annotated[list[str], add]
    error_categories: Annotated[dict[str, Any], merge_any_dicts]
    metrics_summary: Annotated[dict[str, Any], merge_any_dicts]
    guardrails_intervened: bool
    circuit_breaker_states: dict[str, Any]