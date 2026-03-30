"""Tests for Textract routing, mapping, and extraction integration."""

from __future__ import annotations

from pathlib import Path

from src.tools.document_router import route_document
from src.tools.document_tools import extract_document_data
from src.tools.field_mappings import map_textract_to_model

SAMPLE_DIR = Path("data/sample_documents")


def test_route_document_prefers_textract_for_standard_image_form() -> None:
    route = route_document(str(SAMPLE_DIR / "paystub_sample.png"), declared_document_type="paystub")
    assert route["primary_method"] == "textract"
    assert route["fallback_method"] == "vision"


def test_map_textract_marks_low_confidence_field_unclear() -> None:
    payload = {
        "raw_text": "W-2 Wage and Tax Statement\nTax Year: 2024",
        "fields": [
            {"key": "Employer Name", "value": "Acme Lending Services", "confidence": 60.0},
            {"key": "Employee Name", "value": "Jane Borrower", "confidence": 98.0},
            {"key": "Wages", "value": "86500.00", "confidence": 99.0},
            {"key": "Federal Tax Withheld", "value": "13240.00", "confidence": 99.0},
            {"key": "Social Security Wages", "value": "86500.00", "confidence": 99.0},
            {"key": "Tax Year", "value": "2024", "confidence": 99.0},
        ],
    }

    model = map_textract_to_model("w2", payload, confidence_threshold=80.0)

    assert model.employer_name == "Acme Lending Services"
    assert "employer_name" in model.unclear_fields
    assert model.confidence in {"MEDIUM", "LOW"}


def test_extract_document_data_textract_path_uses_mapping(monkeypatch) -> None:
    fake_payload = {
        "raw_text": "Pay Stub\nEmployer Name: Acme Lending Services",
        "fields": [
            {"key": "Employer Name", "value": "Acme Lending Services", "confidence": 99.0},
            {"key": "Employee Name", "value": "Jane Borrower", "confidence": 99.0},
            {"key": "Pay Period Start", "value": "2024-12-01", "confidence": 99.0},
            {"key": "Pay Period End", "value": "2024-12-15", "confidence": 99.0},
            {"key": "Gross Pay", "value": "3326.92", "confidence": 99.0},
            {"key": "Net Pay", "value": "2494.10", "confidence": 99.0},
            {"key": "YTD Gross", "value": "86500.00", "confidence": 99.0},
            {"key": "Pay Frequency", "value": "BIWEEKLY", "confidence": 99.0},
        ],
    }

    monkeypatch.setattr("src.tools.document_tools.detect_document_text", lambda _: fake_payload)

    result = extract_document_data.invoke(
        {
            "document_path": str(SAMPLE_DIR / "paystub_sample.png"),
            "document_type": "paystub",
            "preferred_method": "textract",
        }
    )

    assert "error" not in result
    assert result["metadata"]["processing_method"] == "textract"
    assert result["metadata"]["estimated_cost_usd"] > 0
    assert result["extracted_data"]["pay_frequency"] == "BIWEEKLY"


def test_extract_document_data_rejects_invalid_preferred_method() -> None:
    result = extract_document_data.invoke(
        {
            "document_path": str(SAMPLE_DIR / "w2_sample.txt"),
            "document_type": "w2",
            "preferred_method": "unknown",
        }
    )

    assert "error" in result
    assert "preferred_method" in result["error"]
