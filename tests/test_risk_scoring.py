"""Tests for risk scoring models, report formatting, and scoring logic."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.agents.risk_scoring import (
    build_risk_assessment,
    score_dti,
    score_employment,
    score_fico,
    score_ltv,
)
from src.models.risk import CriterionScore, IndustryContext, RiskAssessment


def _industry(default_rate: float = 0.025, level: str = "LOW") -> IndustryContext:
    return IndustryContext(
        industry_name="healthcare",
        default_rate=default_rate,
        similar_loans_total=40,
        similar_loans_defaulted=2,
        avg_defaulter_fico=662,
        risk_level=level,
        context_note="Test industry context",
    )


def _criteria(score: int) -> list[CriterionScore]:
    return [
        CriterionScore(
            name="DTI",
            value=24.0,
            threshold=43.0,
            passed=True,
            score=score,
            detail="ok",
        ),
        CriterionScore(
            name="LTV",
            value=75.0,
            threshold=80.0,
            passed=True,
            score=score,
            detail="ok",
        ),
        CriterionScore(
            name="FICO",
            value=740.0,
            threshold=680.0,
            passed=True,
            score=score,
            detail="ok",
        ),
        CriterionScore(
            name="Employment",
            value=6.0,
            threshold=2.0,
            passed=True,
            score=score,
            detail="ok",
        ),
    ]


def test_risk_assessment_model_validation() -> None:
    model = RiskAssessment(
        overall_score=82,
        risk_level="LOW",
        recommendation="APPROVE",
        criteria_scores=_criteria(82),
        industry_context=_industry(),
        policy_violations=[],
        policy_warnings=[],
        document_issues=[],
        reasoning="Well-qualified profile.",
        compensating_factors=["High FICO"],
        risk_factors=[],
    )
    assert model.overall_score == 82
    assert model.recommendation == "APPROVE"


def test_risk_assessment_invalid_score_rejected() -> None:
    with pytest.raises(ValidationError):
        RiskAssessment(
            overall_score=120,
            risk_level="LOW",
            recommendation="APPROVE",
            criteria_scores=_criteria(80),
            reasoning="invalid score",
        )


def test_format_report_contains_core_sections() -> None:
    model = RiskAssessment(
        overall_score=77,
        risk_level="MEDIUM",
        recommendation="APPROVE",
        criteria_scores=_criteria(77),
        industry_context=_industry(),
        policy_violations=["Example policy warning"],
        policy_warnings=["Borderline DTI"],
        document_issues=[],
        reasoning="Composite risk acceptable with conditions.",
        compensating_factors=["Strong reserves"],
        risk_factors=["Borderline DTI"],
    )
    report = model.format_report()
    assert "RISK ASSESSMENT" in report
    assert "CRITERIA" in report
    assert "INDUSTRY CONTEXT" in report
    assert "REASONING" in report


def test_score_ranges_for_low_risk() -> None:
    assessment = build_risk_assessment(
        criteria_scores=[
            score_dti(24.0),
            score_ltv(75.0),
            score_fico(740),
            score_employment(7.0),
        ],
        industry_context=_industry(default_rate=0.02, level="LOW"),
    )
    assert 80 <= assessment.overall_score <= 100
    assert assessment.risk_level == "LOW"
    assert assessment.recommendation == "APPROVE"


def test_score_ranges_for_medium_risk() -> None:
    assessment = build_risk_assessment(
        criteria_scores=[
            score_dti(38.0),
            score_ltv(84.0),
            score_fico(705),
            score_employment(2.3),
        ],
        industry_context=_industry(default_rate=0.04, level="MEDIUM"),
    )
    assert 60 <= assessment.overall_score <= 79
    assert assessment.risk_level == "MEDIUM"
    assert assessment.recommendation == "APPROVE"


def test_score_ranges_for_high_risk_manual_review() -> None:
    assessment = build_risk_assessment(
        criteria_scores=[
            score_dti(40.0),
            score_ltv(85.0),
            score_fico(710),
            score_employment(2.2),
        ],
        industry_context=IndustryContext(
            industry_name="cryptocurrency",
            default_rate=0.12,
            similar_loans_total=34,
            similar_loans_defaulted=8,
            avg_defaulter_fico=629,
            risk_level="HIGH",
            context_note="Volatile sector",
        ),
    )
    assert 40 <= assessment.overall_score <= 59
    assert assessment.risk_level == "HIGH"
    assert assessment.recommendation == "MANUAL_REVIEW"


def test_score_ranges_for_critical_risk_deny() -> None:
    assessment = build_risk_assessment(
        criteria_scores=[
            score_dti(48.0),
            score_ltv(96.0),
            score_fico(620),
            score_employment(0.7),
        ],
        industry_context=_industry(default_rate=0.12, level="CRITICAL"),
    )
    assert 0 <= assessment.overall_score <= 39
    assert assessment.risk_level == "CRITICAL"
    assert assessment.recommendation == "DENY"
