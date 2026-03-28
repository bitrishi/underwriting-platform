"""Conditional edge functions for underwriting graph routing."""

from __future__ import annotations

from src.orchestrator.state import UnderwritingState


def should_route_after_fetch(state: UnderwritingState) -> str:
    """Route fetch failures to fatal handling before any downstream scoring."""
    if state.get("fatal_error"):
        return "fatal_error"
    if state.get("borrower_package") is None:
        return "fatal_error"
    return "continue"


def should_review_documents(state: UnderwritingState) -> str:
    """Route to doc review only when document paths are present."""
    document_paths = state.get("document_paths", []) or []
    return "doc_review" if len(document_paths) > 0 else "risk_scoring"


def should_escalate(state: UnderwritingState) -> str:
    """Escalate to human review only for manual-review recommendations."""
    compliance = state.get("compliance_result") or {}
    override = str(compliance.get("recommendation_override", "")).upper()
    if override == "MANUAL_REVIEW":
        return "human_review"

    risk = state.get("risk_assessment") or {}
    recommendation = str(risk.get("recommendation", "")).upper()
    if state.get("needs_manual_review") or recommendation == "MANUAL_REVIEW":
        return "human_review"
    return "final_decision"


def route_after_human_review(state: UnderwritingState) -> str:
    """Route back to fetch_data when human requests more data.

    Safety: stop looping after 3 review iterations.
    """
    if not state.get("needs_additional_data", False):
        return "final_decision"

    iterations = int(state.get("review_iterations", 0) or 0)
    if iterations >= 3:
        return "final_decision"

    return "fetch_data"
