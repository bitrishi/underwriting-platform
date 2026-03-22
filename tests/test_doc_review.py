"""Tests for DocumentReviewPackage models and validate_document_package tool."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.document_review import (
    CrossValidationResult,
    DocumentClassification,
    DocumentReviewPackage,
    ExtractionResult,
    MissingDocument,
)
from src.models.documents import PayStubExtraction, W2Extraction
from src.tools.document_tools import extract_document_data, validate_document_package

SAMPLE_DIR = "data/sample_documents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_w2(wages: float = 86500.0, employer: str = "Acme Lending Services") -> W2Extraction:
    return W2Extraction(
        employer_name=employer,
        employee_name="Jane Borrower",
        wages=wages,
        federal_tax_withheld=13240.0,
        social_security_wages=wages,
        tax_year=2024,
        confidence="HIGH",
        unclear_fields=[],
    )


def _make_paystub(ytd: float = 86500.0, employer: str = "Acme Lending Services") -> PayStubExtraction:
    return PayStubExtraction(
        employer_name=employer,
        employee_name="Jane Borrower",
        pay_period_start="2024-12-01",
        pay_period_end="2024-12-15",
        gross_pay=3326.92,
        net_pay=2494.10,
        ytd_gross=ytd,
        pay_frequency="BIWEEKLY",
        confidence="HIGH",
        unclear_fields=[],
    )


def _classification(doc_type: str = "W2", path: str = "data/sample_documents/w2_sample.txt") -> DocumentClassification:
    return DocumentClassification(
        file_path=path,
        document_type=doc_type,
        confidence="HIGH",
        page_count=1,
    )


def _extraction(doc_type: str, data, method: str = "TEXT", path: str = "") -> ExtractionResult:
    return ExtractionResult(
        file_path=path or f"data/sample_documents/{doc_type.lower()}_sample.txt",
        document_type=doc_type,
        extraction_method=method,
        extracted_data=data,
        confidence=data.confidence,
        unclear_fields=data.unclear_fields,
        processing_time_ms=1.0,
    )


def _cross(check: str, status: str, severity: str = "INFO") -> CrossValidationResult:
    return CrossValidationResult(
        check_name=check,
        status=status,
        details="test detail",
        severity=severity,
    )


def _package(
    validations: list[CrossValidationResult] | None = None,
    missing: list[MissingDocument] | None = None,
    quality: str = "COMPLETE",
) -> DocumentReviewPackage:
    w2 = _make_w2()
    paystub = _make_paystub()
    return DocumentReviewPackage(
        documents_classified=[_classification("W2"), _classification("PAYSTUB", "data/sample_documents/paystub_sample.png")],
        extractions=[_extraction("W2", w2), _extraction("PAYSTUB", paystub, method="VISION")],
        validations=validations or [_cross("W-2 wages vs 1040 AGI", "MATCH", "INFO")],
        missing_documents=missing or [],
        document_quality=quality,
        total_documents=2,
        total_issues=len(missing or []),
    )


# ---------------------------------------------------------------------------
# DocumentReviewPackage — model validation
# ---------------------------------------------------------------------------

class TestDocumentReviewPackageModel:
    def test_valid_complete_package(self) -> None:
        pkg = _package(quality="COMPLETE")
        assert pkg.document_quality == "COMPLETE"
        assert pkg.total_documents == 2

    def test_invalid_document_quality_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DocumentReviewPackage(
                documents_classified=[],
                extractions=[],
                validations=[],
                missing_documents=[],
                document_quality="UNKNOWN",  # not in Literal
                total_documents=0,
                total_issues=0,
            )

    def test_missing_document_model(self) -> None:
        m = MissingDocument(
            document_type="1040",
            reason_required="Tax filing verification",
            impact="Cannot verify AGI or filing status.",
        )
        assert m.document_type == "1040"

    def test_invalid_missing_document_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MissingDocument(
                document_type="INVALID_TYPE",
                reason_required="n/a",
                impact="n/a",
            )


# ---------------------------------------------------------------------------
# has_critical_issues()
# ---------------------------------------------------------------------------

class TestHasCriticalIssues:
    def test_no_issues_returns_false(self) -> None:
        pkg = _package(validations=[_cross("check", "MATCH", "INFO")])
        assert pkg.has_critical_issues() is False

    def test_critical_validation_returns_true(self) -> None:
        pkg = _package(validations=[_cross("employer mismatch", "DISCREPANCY", "CRITICAL")])
        assert pkg.has_critical_issues() is True

    def test_missing_w2_returns_true(self) -> None:
        missing = [MissingDocument(document_type="W2", reason_required="required", impact="blocking")]
        pkg = _package(missing=missing, quality="PARTIAL")
        assert pkg.has_critical_issues() is True

    def test_missing_1040_returns_true(self) -> None:
        missing = [MissingDocument(document_type="1040", reason_required="required", impact="blocking")]
        pkg = _package(missing=missing, quality="PARTIAL")
        assert pkg.has_critical_issues() is True

    def test_missing_paystub_returns_true(self) -> None:
        missing = [MissingDocument(document_type="PAYSTUB", reason_required="required", impact="blocking")]
        pkg = _package(missing=missing, quality="PARTIAL")
        assert pkg.has_critical_issues() is True

    def test_warning_severity_alone_is_not_critical(self) -> None:
        pkg = _package(validations=[_cross("ytd check", "DISCREPANCY", "WARNING")])
        assert pkg.has_critical_issues() is False


# ---------------------------------------------------------------------------
# format_report()
# ---------------------------------------------------------------------------

class TestFormatReport:
    def test_report_contains_quality(self) -> None:
        report = _package(quality="COMPLETE").format_report()
        assert "COMPLETE" in report

    def test_report_contains_document_types(self) -> None:
        report = _package().format_report()
        assert "W2" in report
        assert "PAYSTUB" in report

    def test_report_shows_missing_documents(self) -> None:
        missing = [MissingDocument(document_type="1040", reason_required="Tax verification", impact="Cannot verify AGI")]
        report = _package(missing=missing, quality="PARTIAL").format_report()
        assert "1040" in report
        assert "Tax verification" in report

    def test_report_shows_critical_flag(self) -> None:
        pkg = _package(validations=[_cross("employer check", "DISCREPANCY", "CRITICAL")])
        report = pkg.format_report()
        assert "Critical" in report or "critical" in report

    def test_report_no_critical_confirmation(self) -> None:
        report = _package(validations=[_cross("check", "MATCH", "INFO")]).format_report()
        # Should contain "no critical" or similar green-path message
        lowered = report.lower()
        assert "no critical" in lowered


# ---------------------------------------------------------------------------
# validate_document_package — tool integration (uses real sample files)
# ---------------------------------------------------------------------------

class TestValidateDocumentPackageTool:
    def _extract(self, path: str, doc_type: str) -> dict:
        return extract_document_data.invoke({"document_path": path, "document_type": doc_type})

    def test_matching_w2_and_paystub_yields_match(self) -> None:
        w2 = self._extract(f"{SAMPLE_DIR}/w2_sample.txt", "w2")
        paystub = self._extract(f"{SAMPLE_DIR}/paystub_sample.png", "paystub")
        pkg = validate_document_package.invoke({"extractions": [w2, paystub]})

        assert "error" not in pkg
        assert pkg["document_quality"] == "PARTIAL"  # 1040 is missing

        ytd_check = next(
            (v for v in pkg["validations"] if "YTD" in v["check_name"]),
            None,
        )
        assert ytd_check is not None
        assert ytd_check["status"] == "MATCH"

    def test_missing_1040_is_flagged(self) -> None:
        w2 = self._extract(f"{SAMPLE_DIR}/w2_sample.txt", "w2")
        paystub = self._extract(f"{SAMPLE_DIR}/paystub_sample.png", "paystub")
        pkg = validate_document_package.invoke({"extractions": [w2, paystub]})

        missing_types = [m["document_type"] for m in pkg["missing_documents"]]
        assert "1040" in missing_types

    def test_all_three_docs_reduces_missing_list(self) -> None:
        w2 = self._extract(f"{SAMPLE_DIR}/w2_sample.txt", "w2")
        paystub = self._extract(f"{SAMPLE_DIR}/paystub_sample.png", "paystub")
        tax = self._extract(f"{SAMPLE_DIR}/tax_return_1040_sample.pdf", "1040")
        pkg = validate_document_package.invoke({"extractions": [w2, paystub, tax]})

        missing_types = [m["document_type"] for m in pkg["missing_documents"]]
        # All three types were provided — none should appear as missing
        assert "W2" not in missing_types
        assert "PAYSTUB" not in missing_types
        assert "1040" not in missing_types

    def test_employer_mismatch_triggers_discrepancy(self) -> None:
        # Build extractions manually with a different employer on paystub
        w2_ext = W2Extraction(
            employer_name="Acme Corp",
            employee_name="Jane Borrower",
            wages=86500.0,
            federal_tax_withheld=13240.0,
            social_security_wages=86500.0,
            tax_year=2024,
            confidence="HIGH",
            unclear_fields=[],
        )
        paystub_ext = _make_paystub(employer="Totally Different LLC")

        # Wrap in the DocumentExtractionResult shape that validate_document_package expects
        from src.models.documents import DocumentExtractionMetadata, DocumentExtractionResult

        w2_raw = DocumentExtractionResult(
            document_type="w2",
            extracted_data=w2_ext,
            metadata=DocumentExtractionMetadata(
                document_path=f"{SAMPLE_DIR}/w2_sample.txt",
                processing_method="text",
                processing_time_ms=1.0,
            ),
        ).model_dump()

        paystub_raw = DocumentExtractionResult(
            document_type="paystub",
            extracted_data=paystub_ext,
            metadata=DocumentExtractionMetadata(
                document_path=f"{SAMPLE_DIR}/paystub_sample.png",
                processing_method="vision",
                processing_time_ms=1.0,
            ),
        ).model_dump()

        pkg = validate_document_package.invoke({"extractions": [w2_raw, paystub_raw]})
        employer_check = next(
            (v for v in pkg["validations"] if "employer" in v["check_name"].lower()),
            None,
        )
        assert employer_check is not None
        assert employer_check["status"] == "DISCREPANCY"

    def test_empty_extractions_yields_insufficient(self) -> None:
        pkg = validate_document_package.invoke({"extractions": []})
        assert pkg["document_quality"] == "INSUFFICIENT"
        assert len(pkg["missing_documents"]) == 3  # W2, 1040, PAYSTUB all missing
