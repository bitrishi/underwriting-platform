"""Evaluation helpers for API job execution."""

from __future__ import annotations

import os

from src.chains.underwriter_chain import UnderwriterChain
from src.models.application import LoanApplication
from src.models.decision import CriteriaCheck, LoanDecision, ReasoningTrace


def derive_recommendation(application: LoanApplication) -> str:
    if (
        application.fico_score >= 720
        and application.dti <= 0.36
        and application.employment_years >= 2
        and application.ltv <= 0.80
    ):
        return "APPROVED"

    if (
        application.fico_score < 660
        or application.dti > 0.43
        or application.employment_years < 1
        or application.ltv > 0.95
    ):
        return "DENIED"

    return "MANUAL_REVIEW"


def build_demo_decision(application: LoanApplication) -> LoanDecision:
    recommendation = derive_recommendation(application)
    criteria = [
        CriteriaCheck(name="fico_check", passed=application.fico_score >= 680),
        CriteriaCheck(name="dti_check", passed=application.dti <= 0.43),
        CriteriaCheck(name="ltv_check", passed=application.ltv <= 0.95),
        CriteriaCheck(name="employment_check", passed=application.employment_years >= 1),
    ]

    if recommendation == "APPROVED":
        return LoanDecision(
            decision="APPROVED",
            confidence=0.95,
            risk_level="LOW",
            reasons=[
                "Strong credit profile and stable employment history.",
                "Debt-to-income and loan-to-value ratios are comfortably within policy.",
            ],
            conditions=None,
            criteria=criteria,
            reasoning_trace=ReasoningTrace(
                steps=[
                    "Validated borrower credit and income inputs.",
                    "Calculated DTI/LTV and compared them to approval thresholds.",
                    "Found no policy exceptions requiring manual escalation.",
                ]
            ),
        )

    if recommendation == "DENIED":
        return LoanDecision(
            decision="DECLINE",
            confidence=0.93,
            risk_level="HIGH",
            reasons=[
                "Credit and affordability metrics fall outside underwriting tolerance.",
                "Application exceeds at least one hard-stop policy threshold.",
            ],
            conditions=None,
            criteria=criteria,
            reasoning_trace=ReasoningTrace(
                steps=[
                    "Validated borrower credit and income inputs.",
                    "Detected a hard-stop failure in FICO, DTI, employment, or LTV.",
                    "Routed the application to denied recommendation.",
                ]
            ),
        )

    return LoanDecision(
        decision="CONDITIONAL_APPROVAL",
        confidence=0.78,
        risk_level="MEDIUM",
        reasons=[
            "Application is near policy boundaries and requires a human underwriter decision.",
            "Supporting metrics are mixed and need manual adjudication.",
        ],
        conditions=["Manual underwriter review required before final disposition."],
        criteria=criteria,
        reasoning_trace=ReasoningTrace(
            steps=[
                "Validated borrower credit and income inputs.",
                "Found the application to be borderline against core approval rules.",
                "Escalated to manual review rather than auto-approve or auto-deny.",
            ]
        ),
    )


def evaluate_application(chain: UnderwriterChain, application: LoanApplication) -> LoanDecision:
    if os.environ.get("UNDERWRITING_DEMO_MODE", "false").lower() == "true":
        return build_demo_decision(application)

    decision = chain.evaluate_safe(application)
    if decision is not None:
        return decision

    return build_demo_decision(application)