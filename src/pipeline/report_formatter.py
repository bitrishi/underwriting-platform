"""Final report formatter for underwriting orchestration output."""

from __future__ import annotations

import json
from typing import Any


def _json_block(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=False, default=str)


def format_underwriting_report(state: dict[str, Any]) -> str:
    """Render complete underwriting report from final graph state."""
    app_id = state.get("app_id", "UNKNOWN")

    borrower_summary = state.get("computed_borrower_summary", "Borrower data unavailable")
    document_summary = state.get("computed_doc_summary", "Document review unavailable")
    risk_summary = state.get("computed_risk_block", "Risk assessment unavailable")
    compliance_summary = state.get("computed_compliance_summary", "Compliance not run")
    fha_summary = state.get("computed_fha_summary", "Not applicable")
    human_summary = state.get("computed_human_summary", "Human review not required")

    node_order = state.get("node_execution_order", [])
    node_timestamps = state.get("node_timestamps", {})
    node_durations = state.get("node_durations_s", {})
    errors = state.get("errors", [])
    error_categories = state.get("error_categories", {})
    circuit_breaker_states = state.get("circuit_breaker_states", {})
    guardrails_intervened = bool(state.get("guardrails_intervened", False))
    metrics_summary = state.get("metrics_summary", {})

    graph_version = state.get("graph_version", "v1")
    thread_id = state.get("thread_id", "")
    total_tool_calls = state.get("total_tool_calls", 0)
    total_llm_calls = state.get("total_llm_calls", 0)
    estimated_cost = state.get("estimated_cost_usd", 0.0)

    total_time = 0.0
    for value in node_durations.values():
        try:
            total_time += float(value)
        except Exception:
            pass

    return "\n".join(
        [
            "=" * 88,
            f"UNDERWRITING DECISION REPORT | App ID: {app_id}",
            "=" * 88,
            "",
            "BORROWER SUMMARY",
            borrower_summary,
            "",
            "DOCUMENT REVIEW FINDINGS",
            document_summary,
            "",
            "RISK ASSESSMENT",
            risk_summary,
            "",
            "COMPLIANCE VERIFICATION",
            compliance_summary,
            "",
            "FHA COMPLIANCE",
            fha_summary,
            "",
            "HUMAN REVIEW",
            human_summary,
            f"additional_data_request={state.get('additional_data_request')}",
            f"review_iterations={state.get('review_iterations', 0)}",
            "",
            "AUDIT TRAIL",
            f"nodes_ran={node_order}",
            "node_timestamps=",
            _json_block(node_timestamps),
            "node_durations_seconds=",
            _json_block(node_durations),
            f"errors_count={len(errors)}",
            _json_block(errors),
            "error_categories=",
            _json_block(error_categories),
            "guardrails_intervened=" + str(guardrails_intervened),
            "circuit_breaker_states=",
            _json_block(circuit_breaker_states),
            "",
            "PIPELINE METADATA",
            f"graph_version={graph_version}",
            f"thread_id={thread_id}",
            f"total_time_seconds={round(total_time, 6)}",
            f"total_tool_calls={total_tool_calls}",
            f"total_llm_calls={total_llm_calls}",
            f"estimated_cost_usd={estimated_cost}",
            "metrics_summary=",
            _json_block(metrics_summary),
            "",
        ]
    )
