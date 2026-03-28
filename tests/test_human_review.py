from __future__ import annotations

import uuid

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.models.human_review import HumanReviewResponse
from src.orchestrator.graph import create_underwriting_graph


def _initial_state() -> dict:
    return {
        "app_id": "APP-002",
        "document_paths": ["data/sample_documents/w2_sample.txt"],
        "errors": [],
        "messages": [],
    }


def _get_interrupt_payload(result: dict) -> dict:
    interrupts = result.get("__interrupt__") or []
    assert interrupts, "Expected interrupt payload but none was found"
    first = interrupts[0]
    value = getattr(first, "value", first)
    assert isinstance(value, dict)
    return value


def test_human_review_response_validation_accepts_allowed_decisions() -> None:
    ok = HumanReviewResponse(decision="approve_with_conditions", conditions=["doc update"])
    assert ok.decision == "APPROVE_WITH_CONDITIONS"


def test_human_review_response_validation_rejects_invalid_decision() -> None:
    with pytest.raises(ValueError):
        HumanReviewResponse(decision="ESCALATE")


def test_interrupt_and_resume_with_approved_with_conditions() -> None:
    saver = MemorySaver()
    graph = create_underwriting_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": f"test-human-{uuid.uuid4().hex[:8]}"}}

    paused = graph.invoke(_initial_state(), config=config)
    payload = _get_interrupt_payload(paused)

    assert "human_review_request" in payload
    assert "risk_assessment" in payload
    assert "compliance_result" in payload
    assert "borrower_summary" in payload

    resumed = graph.invoke(Command(resume="APPROVED with conditions"), config=config)
    final_decision = resumed.get("final_decision", "")
    assert "APPROVE_WITH_CONDITIONS" in final_decision


def test_checkpoint_persistence_with_new_graph_instance() -> None:
    saver = MemorySaver()
    graph_1 = create_underwriting_graph(checkpointer=saver)
    thread_id = f"test-restart-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    paused = graph_1.invoke(_initial_state(), config=config)
    _get_interrupt_payload(paused)

    snapshot = graph_1.get_state(config)
    saved = snapshot.values or {}
    assert "borrower_package" in saved
    assert "risk_assessment" in saved
    assert "compliance_result" in saved

    graph_2 = create_underwriting_graph(checkpointer=saver)
    resumed = graph_2.invoke(Command(resume="DENIED"), config=config)
    final_decision = resumed.get("final_decision", "")
    assert "DENY" in final_decision
