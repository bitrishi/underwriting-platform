"""Tests for compliance models and deterministic compliance tools."""

from __future__ import annotations

from src.models.compliance import ComplianceCheck, ComplianceResult
from src.tools.compliance_tools import (
    check_disclosure_requirements,
    verify_audit_trail,
)


def test_check_disclosure_requirements_for_denial_includes_ecoa() -> None:
    result = check_disclosure_requirements.invoke(
        {"decision": "DENY", "state": "texas", "is_new_application": True}
    )

    disclosures = result["required_disclosures"]
    names = {item["disclosure"] for item in disclosures}

    assert "Adverse Action Notice" in names
    assert "Credit Score Disclosure" in names
    assert "Texas Section 50(a)(6) Notice" in names


def test_check_disclosure_requirements_invalid_state_returns_error() -> None:
    result = check_disclosure_requirements.invoke(
        {"decision": "DENY", "state": "", "is_new_application": True}
    )
    assert result["required_disclosures"] == []
    assert "error" in result


def test_verify_audit_trail_complete() -> None:
    risk_text = (
        "FICO 740 and DTI 24 were reviewed. "
        "LTV 79 also passed. "
        "Reason: low overall risk. "
        "Recommendation: APPROVE"
    )
    result = verify_audit_trail.invoke({"risk_assessment": risk_text})

    assert result["complete"] is True
    assert result["missing"] == []


def test_verify_audit_trail_incomplete() -> None:
    result = verify_audit_trail.invoke({"risk_assessment": "No evidence captured."})
    assert result["complete"] is False
    assert len(result["missing"]) > 0


def test_compliance_result_model_fields() -> None:
    model = ComplianceResult(
        required_disclosures=[{"disclosure": "Loan Estimate"}],
        fair_lending_flag=False,
        audit_trail_complete=True,
        blocking_violations=[],
        recommendation_override="NONE",
        checks=[
            ComplianceCheck(
                name="audit_trail_completeness",
                passed=True,
                detail="All required fields present.",
            )
        ],
        summary="Compliance complete.",
    )

    assert model.audit_trail_complete is True
    assert model.recommendation_override == "NONE"
