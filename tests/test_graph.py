"""Tests for underwriting orchestrator graph routing and execution."""

from __future__ import annotations

from src.orchestrator.edges import (
    should_escalate,
    should_review_documents,
    should_route_after_fetch,
)
from src.orchestrator.graph import create_underwriting_graph
from src.orchestrator.graph import route_by_loan_type


def test_should_review_documents_routes_by_document_paths() -> None:
    assert should_review_documents({"document_paths": ["w2.txt"]}) == "doc_review"
    assert should_review_documents({"document_paths": []}) == "risk_scoring"


def test_should_escalate_routes_manual_review() -> None:
    assert should_escalate({"needs_manual_review": True}) == "human_review"
    assert should_escalate({"needs_manual_review": False}) == "final_decision"
    assert (
        should_escalate({"risk_assessment": {"recommendation": "MANUAL_REVIEW"}})
        == "human_review"
    )
    assert (
        should_escalate({"compliance_result": {"recommendation_override": "MANUAL_REVIEW"}})
        == "human_review"
    )


def test_should_route_after_fetch_routes_fatal_cases() -> None:
    assert should_route_after_fetch({"borrower_package": {"borrower": {}}}) == "continue"
    assert should_route_after_fetch({"borrower_package": None}) == "fatal_error"
    assert should_route_after_fetch({"fatal_error": True}) == "fatal_error"


def test_route_by_loan_type() -> None:
    assert route_by_loan_type({"loan_type": "conventional"}) == "compliance"
    assert route_by_loan_type({"loan_type": "fha"}) == "fha_compliance"
    assert route_by_loan_type({}) == "compliance"


def test_compiled_graph_executes_expected_sequence(monkeypatch) -> None:
    execution_order: list[str] = []

    def fake_fetch_data_node(state):
        execution_order.append("fetch_data")
        return {
            "borrower_package": {
                "borrower": {
                    "name": "Alice",
                    "annual_income": 120000,
                    "monthly_debt": 2400,
                    "loan_amount": 350000,
                    "property_value": 440000,
                },
                "credit": {"fico_score": 740},
                "employment": {"years_at_current": 5},
            },
            "has_documents": bool(state.get("document_paths")),
            "errors": [],
            "messages": [("assistant", "fetch ok")],
        }

    def fake_doc_review_node(_state):
        execution_order.append("doc_review")
        return {
            "document_review": {
                "missing_documents": [],
                "document_quality": "COMPLETE",
                "total_documents": 2,
                "total_issues": 0,
            },
            "messages": [("assistant", "doc ok")],
        }

    def fake_risk_scoring_node(_state):
        execution_order.append("risk_scoring")
        return {
            "risk_assessment": {
                "overall_score": 88,
                "risk_level": "LOW",
                "recommendation": "APPROVE",
                "criteria_scores": [],
                "reasoning": "Strong profile",
            },
            "needs_manual_review": False,
            "messages": [("assistant", "risk ok")],
        }

    def fake_compliance_node(_state):
        execution_order.append("compliance")
        return {
            "compliance_result": {
                "required_disclosures": [],
                "fair_lending_flag": False,
                "audit_trail_complete": True,
                "blocking_violations": [],
                "recommendation_override": "NONE",
            },
            "messages": [("assistant", "compliance ok")],
        }

    def fake_fha_compliance_node(_state):
        execution_order.append("fha_compliance")
        return {
            "fha_compliance_result": {"status": "PASS", "flags": []},
            "messages": [("assistant", "fha ok")],
        }

    def fake_fatal_error_node(_state):
        execution_order.append("fatal_error")
        return {
            "fatal_error": True,
            "messages": [("assistant", "fatal")],
        }

    def fake_human_review_node(_state):
        execution_order.append("human_review")
        return {"messages": [("assistant", "human review")]}

    def fake_final_decision_node(_state):
        execution_order.append("final_decision")
        return {"final_decision": "APPROVE", "messages": [("assistant", "final ok")]}

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fake_fetch_data_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", fake_doc_review_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", fake_risk_scoring_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", fake_compliance_node)
    monkeypatch.setattr("src.orchestrator.graph.fha_compliance_node", fake_fha_compliance_node)
    monkeypatch.setattr("src.orchestrator.graph.fatal_error_node", fake_fatal_error_node)
    monkeypatch.setattr("src.orchestrator.graph.human_review_node", fake_human_review_node)
    monkeypatch.setattr("src.orchestrator.graph.final_decision_node", fake_final_decision_node)

    graph = create_underwriting_graph()

    result = graph.invoke(
        {
            "app_id": "APP-001",
            "document_paths": ["w2.txt", "1040.txt"],
            "errors": [],
            "messages": [],
        },
        config={"configurable": {"thread_id": "test-graph-sequence"}},
    )

    assert "fetch_data" in execution_order
    assert "doc_review" in execution_order
    assert "risk_scoring" in execution_order
    assert "compliance" in execution_order
    assert "final_decision" in execution_order
    assert execution_order.index("risk_scoring") > execution_order.index("fetch_data")
    assert execution_order.index("risk_scoring") > execution_order.index("doc_review")
    assert execution_order.index("compliance") > execution_order.index("risk_scoring")
    assert execution_order.index("final_decision") > execution_order.index("compliance")
    assert result["final_decision"] == "APPROVE"


def test_fha_flow_includes_fha_compliance(monkeypatch) -> None:
    execution_order: list[str] = []

    def fake_fetch_data_node(state):
        execution_order.append("fetch_data")
        return {
            "borrower_package": {
                "borrower": {
                    "name": "Alice",
                    "annual_income": 120000,
                    "monthly_debt": 2400,
                    "loan_amount": 350000,
                    "property_value": 440000,
                },
                "credit": {"fico_score": 740},
                "employment": {"years_at_current": 5},
            },
            "errors": [],
            "messages": [("assistant", "fetch ok")],
        }

    def fake_doc_review_node(_state):
        execution_order.append("doc_review")
        return {"document_review": {}, "messages": [("assistant", "doc ok")]}

    def fake_risk_scoring_node(_state):
        execution_order.append("risk_scoring")
        return {
            "risk_assessment": {
                "overall_score": 75,
                "risk_level": "MEDIUM",
                "recommendation": "APPROVE",
                "criteria_scores": [],
                "reasoning": "ok",
            },
            "needs_manual_review": False,
            "messages": [("assistant", "risk ok")],
        }

    def fake_fha_compliance_node(_state):
        execution_order.append("fha_compliance")
        return {
            "fha_compliance_result": {"status": "PASS", "flags": []},
            "messages": [("assistant", "fha ok")],
        }

    def fake_compliance_node(_state):
        execution_order.append("compliance")
        return {
            "compliance_result": {
                "required_disclosures": [],
                "fair_lending_flag": False,
                "audit_trail_complete": True,
                "blocking_violations": [],
                "recommendation_override": "NONE",
            },
            "messages": [("assistant", "compliance ok")],
        }

    def fake_fatal_error_node(_state):
        execution_order.append("fatal_error")
        return {"fatal_error": True, "messages": [("assistant", "fatal")]}

    def fake_human_review_node(_state):
        execution_order.append("human_review")
        return {
            "needs_additional_data": False,
            "review_iterations": 0,
            "messages": [("assistant", "human")],
        }

    def fake_final_decision_node(_state):
        execution_order.append("final_decision")
        return {"final_decision": "APPROVE", "messages": [("assistant", "final")]}

    monkeypatch.setattr("src.orchestrator.graph.fetch_data_node", fake_fetch_data_node)
    monkeypatch.setattr("src.orchestrator.graph.doc_review_node", fake_doc_review_node)
    monkeypatch.setattr("src.orchestrator.graph.risk_scoring_node", fake_risk_scoring_node)
    monkeypatch.setattr("src.orchestrator.graph.fha_compliance_node", fake_fha_compliance_node)
    monkeypatch.setattr("src.orchestrator.graph.compliance_node", fake_compliance_node)
    monkeypatch.setattr("src.orchestrator.graph.fatal_error_node", fake_fatal_error_node)
    monkeypatch.setattr("src.orchestrator.graph.human_review_node", fake_human_review_node)
    monkeypatch.setattr("src.orchestrator.graph.final_decision_node", fake_final_decision_node)

    graph = create_underwriting_graph()

    result = graph.invoke(
        {
            "app_id": "APP-001",
            "loan_type": "fha",
            "document_paths": ["w2.txt", "1040.txt"],
            "errors": [],
            "messages": [],
        },
        config={"configurable": {"thread_id": "test-graph-fha"}},
    )

    assert "fha_compliance" in execution_order
    assert execution_order.index("fha_compliance") > execution_order.index("risk_scoring")
    assert execution_order.index("compliance") > execution_order.index("fha_compliance")
    assert result["final_decision"] == "APPROVE"
