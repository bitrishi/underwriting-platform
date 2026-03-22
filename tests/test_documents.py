"""Tests for document extraction models and document tools."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.models.documents import (
    PayStubExtraction,
    TaxReturn1040Extraction,
    W2Extraction,
)
from src.tools.document_tools import (
    classify_document,
    compare_documents,
    encode_image,
    has_extractable_text,
    extract_document_data,
    validate_document_package,
)


SAMPLE_DIR = Path("data/sample_documents")


def test_w2_model_validation_valid() -> None:
    model = W2Extraction(
        employer_name="Acme Lending Services",
        employee_name="Jane Borrower",
        wages=86500.0,
        federal_tax_withheld=13240.0,
        social_security_wages=86500.0,
        tax_year=2024,
        confidence="HIGH",
        unclear_fields=[],
    )
    assert model.tax_year == 2024


def test_1040_model_validation_invalid_filing_status() -> None:
    with pytest.raises(ValidationError):
        TaxReturn1040Extraction(
            tax_year=2024,
            filing_status="INVALID_STATUS",
            adjusted_gross_income=90250.0,
            taxable_income=74450.0,
            total_tax=12680.0,
            confidence="MEDIUM",
            unclear_fields=[],
        )


def test_paystub_model_validation_invalid_frequency() -> None:
    with pytest.raises(ValidationError):
        PayStubExtraction(
            employer_name="Acme",
            employee_name="Jane",
            pay_period_start="2024-12-01",
            pay_period_end="2024-12-15",
            gross_pay=3326.92,
            net_pay=2494.10,
            ytd_gross=86500.0,
            pay_frequency="YEARLY",
            confidence="HIGH",
            unclear_fields=[],
        )


def test_encode_image_real_file() -> None:
    encoded = encode_image(str(SAMPLE_DIR / "paystub_sample.png"))
    assert isinstance(encoded, str)
    assert len(encoded) > 10


def test_has_extractable_text_smart_routing() -> None:
    assert has_extractable_text(str(SAMPLE_DIR / "w2_sample.txt")) is True
    assert has_extractable_text(str(SAMPLE_DIR / "tax_return_1040_sample.pdf")) is True
    assert has_extractable_text(str(SAMPLE_DIR / "paystub_sample.png")) is False


def test_compare_documents_matching_income() -> None:
    result = compare_documents.invoke(
        {
            "doc1_data": {"wages": 86500.0},
            "doc2_data": {"adjusted_gross_income": 86200.0},
            "comparison_type": "income_consistency",
        }
    )
    assert result["match"] is True
    assert result["flag"] == "CONSISTENT"


def test_compare_documents_mismatching_income() -> None:
    result = compare_documents.invoke(
        {
            "doc1_data": {"wages": 86500.0},
            "doc2_data": {"adjusted_gross_income": 60000.0},
            "comparison_type": "income_consistency",
        }
    )
    assert result["match"] is False
    assert result["flag"] == "DISCREPANCY_DETECTED"


def test_classify_document_detects_known_types() -> None:
    w2_result = classify_document.invoke(
        {"document_path": str(SAMPLE_DIR / "w2_sample.txt")}
    )
    paystub_result = classify_document.invoke(
        {"document_path": str(SAMPLE_DIR / "paystub_sample.png")}
    )

    assert w2_result["document_type"] == "W2"
    assert w2_result["confidence"] == "HIGH"
    assert paystub_result["document_type"] == "PAYSTUB"
    assert paystub_result["page_count"] == 1


def test_validate_document_package_flags_missing_1040() -> None:
    w2_extraction = extract_document_data.invoke(
        {
            "document_path": str(SAMPLE_DIR / "w2_sample.txt"),
            "document_type": "w2",
        }
    )
    paystub_extraction = extract_document_data.invoke(
        {
            "document_path": str(SAMPLE_DIR / "paystub_sample.png"),
            "document_type": "paystub",
        }
    )

    package = validate_document_package.invoke(
        {"extractions": [w2_extraction, paystub_extraction]}
    )

    assert package["document_quality"] == "PARTIAL"
    assert any(item["document_type"] == "1040" for item in package["missing_documents"])
    assert any(item["status"] == "MATCH" for item in package["validations"])
