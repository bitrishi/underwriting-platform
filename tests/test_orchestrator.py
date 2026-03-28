from __future__ import annotations

import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.orchestrator.graph import create_underwriting_graph


def _init_state(app_id: str = "APP-001", docs: list[str] | None = None, loan_type: str = "conventional") -> dict:
    return {
        "app_id": app_id,
        "document_paths": docs if docs is not None else ["w2.txt", "1040.txt"],
        "loan_type": loan_type,
        "graph_version": "v1",
        "errors": [],
        "messages": [],
        "review_iterations": 0,
    }


def test_complete_happy_path(monkeypatch) -> None:
    order: list[str] = []

    def fetch_node(state):
        order.append("fetch_data")
        return {
            "borrower_package": {
                "borrower": {
                    "name": "Alice",
                    "annual_income": 120000,
                    "monthly_debt": 2000,
                    "loan_amount": 250000,
                    "property_value": 350000,
                    "property_state": "texas",
                },
                "credit": {"fico_score": 740},
                "employment": {"years_at_current": 5},
            },
            "has_documents": True,
            "fatal_error": False,
            "errors": [],
        }

    def doc_node(_state):
        order.append("doc_review")
        return {
            "document_review": {
                "status": "COMPLETED",
                "document_quality": "COMPLETE",
                "total_documents": 2,
                "total_issues": 0,
                "missing_documents": [],
            }
        }

    def risk_node(_state):
        order.append("risk_scoring")
        return {
            "risk_assessment": {
                "overall_score": 92,
                "risk_level": "LOW",
                "recommendation": "APPROVE",
                "criteria_scores": [],
                "reasoning": "strong profile",
            },
            "needs_manual_review": False,
        }

    def comp_node(_state):
        order.append("compliance")
        return {
            "compliance_result": {
                "required_disclosures": [],
                "audit_trail_complete": True,
                "blocking_violations": [],
                "recommendation_override": "NONE",
                "summary": "ok",
            },
            "needs_manual_review": False,
        }

    def final_node(_state):
        order.append("final_decision")
        return {"final_decision": "APPROVE", "final_report": "APPROVE"}

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fetch_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", doc_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", risk_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", comp_node)
    monkeypatch.setattr("src.orchestrator.graph.final_decision_node", final_node)

    graph = create_underwriting_graph()
    result = graph.invoke(_init_state(), config={"configurable": {"thread_id": "orch-happy"}})

    assert result["final_decision"] == "APPROVE"
    assert "human_review" not in order


def test_parallel_execution_fetch_and_doc_both_run_before_risk(monkeypatch) -> None:
    order: list[str] = []

    def fetch_node(_state):
        order.append("fetch_data")
        return {"borrower_package": {"borrower": {"property_state": "texas"}}, "fatal_error": False}

    def doc_node(_state):
        order.append("doc_review")
        return {"document_review": {"status": "COMPLETED", "missing_documents": []}}

    def risk_node(_state):
        order.append("risk_scoring")
        return {"risk_assessment": {"recommendation": "APPROVE"}, "needs_manual_review": False}

    def comp_node(_state):
        order.append("compliance")
        return {"compliance_result": {"recommendation_override": "NONE"}, "needs_manual_review": False}

    def final_node(_state):
        order.append("final_decision")
        return {"final_decision": "DONE", "final_report": "DONE"}

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fetch_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", doc_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", risk_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", comp_node)
    monkeypatch.setattr("src.orchestrator.graph.final_decision_node", final_node)

    graph = create_underwriting_graph()
    graph.invoke(_init_state(), config={"configurable": {"thread_id": "orch-parallel"}})

    assert "fetch_data" in order
    assert "doc_review" in order
    assert order.index("risk_scoring") > order.index("fetch_data")
    assert order.index("risk_scoring") > order.index("doc_review")


def test_doc_review_skip_when_no_documents() -> None:
    graph = create_underwriting_graph()
    result = graph.invoke(
        _init_state(app_id="APP-001", docs=[]),
        config={"configurable": {"thread_id": "orch-skip-docs"}},
    )
    doc = result.get("document_review") or {}
    assert doc.get("status") == "SKIPPED"


def test_fatal_error_handling_fetch_failure_routes_to_final() -> None:
    graph = create_underwriting_graph()
    result = graph.invoke(
        _init_state(app_id="APP-999", docs=[]),
        config={"configurable": {"thread_id": "orch-fatal"}},
    )
    assert result.get("borrower_package") is None
    assert "final_decision" in result


def test_compliance_override_forces_manual_review(monkeypatch) -> None:
    def fetch_node(_state):
        return {
            "borrower_package": {"borrower": {"property_state": "texas"}},
            "fatal_error": False,
        }

    def doc_node(_state):
        return {"document_review": {"status": "SKIPPED", "missing_documents": []}}

    def risk_node(_state):
        return {
            "risk_assessment": {"recommendation": "APPROVE"},
            "needs_manual_review": False,
        }

    def comp_node(_state):
        return {
            "compliance_result": {"recommendation_override": "MANUAL_REVIEW"},
            "needs_manual_review": True,
        }

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fetch_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", doc_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", risk_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", comp_node)

    graph = create_underwriting_graph()
    paused = graph.invoke(_init_state(), config={"configurable": {"thread_id": "orch-override"}})
    assert "__interrupt__" in paused


def test_interrupt_resume_cycle() -> None:
    saver = MemorySaver()
    graph = create_underwriting_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": f"orch-ir-{uuid.uuid4().hex[:8]}"}}

    paused = graph.invoke(_init_state(app_id="APP-002", docs=["w2.txt"]), config=config)
    assert "__interrupt__" in paused

    resumed = graph.invoke(Command(resume="APPROVED with conditions"), config=config)
    assert "final_decision" in resumed
    assert "APPROVE_WITH_CONDITIONS" in resumed["final_decision"]


def test_checkpoint_persistence_survives_restart() -> None:
    saver = MemorySaver()
    graph_a = create_underwriting_graph(checkpointer=saver)
    thread = f"orch-restart-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread}}

    paused = graph_a.invoke(_init_state(app_id="APP-002", docs=["w2.txt"]), config=config)
    assert "__interrupt__" in paused

    graph_b = create_underwriting_graph(checkpointer=saver)
    resumed = graph_b.invoke(Command(resume="DENIED"), config=config)
    assert "final_decision" in resumed
    assert "DENY" in resumed["final_decision"]


def test_error_accumulation_across_nodes(monkeypatch) -> None:
    def fetch_node(_state):
        return {
            "borrower_package": {"borrower": {"property_state": "texas"}},
            "fatal_error": False,
            "errors": ["fetch_warning"],
        }

    def doc_node(_state):
        return {
            "document_review": {"status": "COMPLETED", "missing_documents": []},
            "errors": ["doc_warning"],
        }

    def risk_node(_state):
        return {
            "risk_assessment": {"recommendation": "APPROVE"},
            "needs_manual_review": False,
            "errors": ["risk_warning"],
        }

    def comp_node(_state):
        return {
            "compliance_result": {"recommendation_override": "NONE"},
            "needs_manual_review": False,
            "errors": ["compliance_warning"],
        }

    def final_node(state):
        return {"final_decision": "done", "final_report": "done", "errors": state.get("errors", [])}

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fetch_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", doc_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", risk_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", comp_node)
    monkeypatch.setattr("src.orchestrator.graph.final_decision_node", final_node)

    graph = create_underwriting_graph()
    result = graph.invoke(_init_state(), config={"configurable": {"thread_id": "orch-errors"}})

    joined = " ".join(result.get("errors", []))
    assert "fetch_warning" in joined
    assert "doc_warning" in joined
    assert "risk_warning" in joined
    assert "compliance_warning" in joined
