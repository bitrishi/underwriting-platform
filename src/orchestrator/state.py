"""State schema shared by all nodes in the underwriting graph."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class UnderwritingState(TypedDict, total=False):
    """State bag accumulated across orchestrator node execution."""

    # Inputs
    app_id: str
    document_paths: list[str]
    loan_type: str

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

    # Observability
    messages: Annotated[list, add_messages]
    errors: Annotated[list[str], add]