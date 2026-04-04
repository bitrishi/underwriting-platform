"""Week 5 hardening tests: guardrails, doc routing, and categorized final errors."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.config.bedrock import create_llm
from src.orchestrator.nodes import doc_review_node, final_decision_node


def test_create_llm_skips_guardrails_for_internal_task() -> None:
    with patch("src.config.bedrock.ChatBedrock") as mock_bedrock:
        mock_bedrock.return_value = MagicMock()
        create_llm(task="retrieval_grading")
        kwargs = mock_bedrock.call_args.kwargs
        assert "guardrails" not in kwargs


def test_doc_review_node_logs_textract_and_vision_methods(monkeypatch) -> None:
    class DummyAgent:
        def invoke(self, _payload):
            return {"messages": [SimpleNamespace(content="ok")]}

    monkeypatch.setattr("src.orchestrator.nodes.create_doc_review_agent", lambda: DummyAgent())

    def fake_classify(payload):
        path = payload["document_path"]
        if "paystub" in path:
            return {
                "file_path": path,
                "document_type": "PAYSTUB",
                "confidence": "HIGH",
                "page_count": 1,
            }
        return {
            "file_path": path,
            "document_type": "OTHER",
            "confidence": "MEDIUM",
            "page_count": 1,
        }

    monkeypatch.setattr("src.orchestrator.nodes.classify_document", SimpleNamespace(invoke=fake_classify))

    def fake_route(path, declared_document_type=None):
        if "paystub" in path:
            return {"primary_method": "textract"}
        return {"primary_method": "vision"}

    monkeypatch.setattr("src.orchestrator.nodes.route_document", fake_route)

    def fake_extract(payload):
        return {
            "document_type": payload["document_type"],
            "extracted_data": {
                "confidence": "HIGH",
                "unclear_fields": [],
                "employer_name": "Acme",
                "employee_name": "Jane",
                "pay_period_start": "2024-01-01",
                "pay_period_end": "2024-01-15",
                "gross_pay": 1000.0,
                "net_pay": 800.0,
                "ytd_gross": 1000.0,
                "pay_frequency": "BIWEEKLY",
            },
            "metadata": {
                "document_path": payload["document_path"],
                "processing_method": payload["preferred_method"],
                "processing_time_ms": 2.0,
                "estimated_cost_usd": 0.0015,
            },
        }

    monkeypatch.setattr("src.orchestrator.nodes.extract_document_data", SimpleNamespace(invoke=fake_extract))

    state = {
        "app_id": "APP-001",
        "document_paths": [
            "data/sample_documents/paystub_sample.png",
            "data/sample_documents/unstructured_letter.png",
        ],
        "errors": [],
        "messages": [],
    }

    result = doc_review_node(state)
    methods = result["document_review"]["extraction_methods"]
    assert {m["method"] for m in methods} == {"textract", "vision"}


def test_final_decision_includes_error_categories() -> None:
    state = {
        "app_id": "APP-001",
        "errors": [
            "[RECOVERABLE] fetch_data_node: transient timeout",
            "[FATAL] fetch_data_node: borrower not found",
        ],
        "messages": [],
        "node_durations_s": {},
        "node_timestamps": {},
        "node_execution_order": [],
    }

    result = final_decision_node(state)
    categories = result["error_categories"]

    assert "RECOVERABLE" in categories
    assert "FATAL" in categories
    assert "error_categories" in result["final_report"]
