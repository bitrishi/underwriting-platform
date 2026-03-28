from __future__ import annotations

import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.orchestrator.graph import create_underwriting_graph


def _base_state() -> dict:
    return {
        "app_id": "APP-001",
        "loan_type": "conventional",
        "document_paths": ["data/sample_documents/w2_sample.txt"],
        "errors": [],
        "messages": [],
        "review_iterations": 0,
    }


def test_human_request_for_more_data_loops_back_to_fetch(monkeypatch) -> None:
    saver = MemorySaver()
    fetch_count = {"n": 0}

    def fake_fetch_data_node(state):
        fetch_count["n"] += 1
        return {
            "borrower_package": {
                "borrower": {
                    "name": "Loop Borrower",
                    "property_state": "texas",
                    "annual_income": 100000,
                    "monthly_debt": 3000,
                    "loan_amount": 250000,
                    "property_value": 320000,
                },
                "credit": {"fico_score": 705},
                "employment": {"years_at_current": 2},
            },
            "has_documents": bool(state.get("document_paths")),
            "errors": state.get("errors", []),
            "messages": [("assistant", f"fetch pass {fetch_count['n']}")],
        }

    def fake_doc_review_node(_state):
        return {
            "document_review": {"missing_documents": []},
            "messages": [("assistant", "doc ok")],
        }

    def fake_risk_scoring_node(_state):
        return {
            "risk_assessment": {
                "overall_score": 55,
                "risk_level": "HIGH",
                "recommendation": "MANUAL_REVIEW",
                "criteria_scores": [],
                "reasoning": "borderline case",
            },
            "needs_manual_review": True,
            "messages": [("assistant", "risk complete")],
        }

    def fake_compliance_node(_state):
        return {
            "compliance_result": {
                "required_disclosures": [],
                "fair_lending_flag": False,
                "audit_trail_complete": True,
                "blocking_violations": [],
                "recommendation_override": "NONE",
                "summary": "ok",
            },
            "needs_manual_review": True,
            "messages": [("assistant", "compliance complete")],
        }

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fake_fetch_data_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", fake_doc_review_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", fake_risk_scoring_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", fake_compliance_node)

    graph = create_underwriting_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": f"loop-{uuid.uuid4().hex[:8]}"}}

    paused = graph.invoke(_base_state(), config=config)
    assert "__interrupt__" in paused

    # Human asks for additional data. The graph should loop to fetch_data,
    # then reach human_review again and interrupt a second time.
    paused_again = graph.invoke(
        Command(resume="need more recent credit report"),
        config=config,
    )

    assert "__interrupt__" in paused_again
    assert fetch_count["n"] >= 2


def test_human_loop_stops_after_max_iterations(monkeypatch) -> None:
    saver = MemorySaver()

    def fake_fetch_data_node(state):
        return {
            "borrower_package": {
                "borrower": {
                    "name": "Loop Borrower",
                    "property_state": "texas",
                    "annual_income": 100000,
                    "monthly_debt": 3000,
                    "loan_amount": 250000,
                    "property_value": 320000,
                },
                "credit": {"fico_score": 705},
                "employment": {"years_at_current": 2},
            },
            "has_documents": True,
            "errors": state.get("errors", []),
            "messages": [("assistant", "fetch")],
        }

    def fake_doc_review_node(_state):
        return {"document_review": {"missing_documents": []}}

    def fake_risk_scoring_node(_state):
        return {
            "risk_assessment": {
                "overall_score": 55,
                "risk_level": "HIGH",
                "recommendation": "MANUAL_REVIEW",
                "criteria_scores": [],
                "reasoning": "borderline case",
            },
            "needs_manual_review": True,
        }

    def fake_compliance_node(_state):
        return {
            "compliance_result": {
                "required_disclosures": [],
                "fair_lending_flag": False,
                "audit_trail_complete": True,
                "blocking_violations": [],
                "recommendation_override": "NONE",
                "summary": "ok",
            },
            "needs_manual_review": True,
        }

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fake_fetch_data_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", fake_doc_review_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", fake_risk_scoring_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", fake_compliance_node)

    graph = create_underwriting_graph(checkpointer=saver)
    config = {"configurable": {"thread_id": f"maxloop-{uuid.uuid4().hex[:8]}"}}

    out = graph.invoke(_base_state(), config=config)
    assert "__interrupt__" in out

    # Request more data repeatedly; after the 3rd iteration, graph should stop looping.
    out = graph.invoke(Command(resume="need more recent credit report"), config=config)
    assert "__interrupt__" in out
    out = graph.invoke(Command(resume="need more recent credit report"), config=config)
    assert "__interrupt__" in out
    out = graph.invoke(Command(resume="need more recent credit report"), config=config)

    assert "final_decision" in out
    assert "review_iterations=3" in out["final_decision"]
