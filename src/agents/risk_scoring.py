"""Risk scoring agent and helper scoring functions."""

from __future__ import annotations

from langchain.agents import create_agent

from src.config.bedrock import create_llm
from src.models.risk import CriterionScore, IndustryContext, RiskAssessment
from src.tools.graph_tools import find_similar_past_loans, get_borrower_risk_context
from src.tools.policy_tools_v2 import (
    search_lending_policies,
    verify_compliance_requirement,
)
from src.tools.underwriting_tools import (
    calculate_dti,
    calculate_ltv,
    check_employment_stability,
    check_fico_eligibility,
)
from src.utils.prompt_loader import load_prompt


def create_risk_scoring_agent():
    """Create the Risk Scoring sub-agent with all 8 required tools.

    Tool groups:
    - Calculation (4): DTI, LTV, FICO, employment stability
    - RAG (2): policy lookup and compliance verification
    - Knowledge graph (2): borrower risk context and similar loans
    """
    llm = create_llm(task="risk_scoring")

    tools = [
        calculate_dti,
        calculate_ltv,
        check_fico_eligibility,
        check_employment_stability,
        search_lending_policies,
        verify_compliance_requirement,
        get_borrower_risk_context,
        find_similar_past_loans,
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=load_prompt("risk_scoring"),
    )


def score_dti(dti: float) -> CriterionScore:
    """Score DTI according to underwriting thresholds."""
    if dti <= 36:
        score = 100
    elif dti <= 43:
        score = max(60, int(round(80 - (dti - 36) * 2.85)))
    else:
        score = max(0, int(round(40 - min(40, (dti - 43) * 4))))
    return CriterionScore(
        name="DTI",
        value=round(dti, 2),
        threshold=43.0,
        passed=dti <= 43.0,
        score=score,
        detail=f"Debt-to-income ratio {dti:.2f}% vs 43% threshold.",
    )


def score_fico(fico: int) -> CriterionScore:
    """Score FICO according to underwriting thresholds."""
    if fico >= 740:
        score = 100
    elif fico >= 680:
        score = max(70, int(round(70 + ((fico - 680) / 60) * 20)))
    else:
        score = max(0, int(round((fico - 300) / 380 * 50)))
    return CriterionScore(
        name="FICO",
        value=float(fico),
        threshold=680.0,
        passed=fico >= 680,
        score=score,
        detail=f"Credit score {fico} vs 680 minimum eligibility threshold.",
    )


def score_ltv(ltv: float) -> CriterionScore:
    """Score LTV according to underwriting thresholds."""
    if ltv <= 80:
        score = 100
    elif ltv <= 95:
        score = max(50, int(round(80 - ((ltv - 80) / 15) * 30)))
    else:
        score = max(0, int(round(30 - min(30, (ltv - 95) * 6))))
    return CriterionScore(
        name="LTV",
        value=round(ltv, 2),
        threshold=80.0,
        passed=ltv <= 95.0,
        score=score,
        detail=f"Loan-to-value ratio {ltv:.2f}% with preferred threshold at 80%.",
    )


def score_employment(years: float) -> CriterionScore:
    """Score employment stability according to tenure thresholds."""
    if years >= 5:
        score = 100
    elif years >= 2:
        score = max(70, int(round(70 + ((years - 2) / 3) * 20)))
    else:
        score = min(60, max(40, int(round(40 + years * 20))))
    return CriterionScore(
        name="Employment",
        value=round(years, 2),
        threshold=2.0,
        passed=years >= 2.0,
        score=score,
        detail=f"Employment tenure {years:.2f} years vs 2-year stability threshold.",
    )


def industry_penalty(default_rate: float | None) -> int:
    """Return risk penalty points from industry default rate."""
    if default_rate is None:
        return 0
    if default_rate < 0.03:
        return 0
    if default_rate < 0.05:
        return 5
    if default_rate <= 0.10:
        return 10
    return 20


def _risk_level_from_score(score: int) -> str:
    if score >= 80:
        return "LOW"
    if score >= 60:
        return "MEDIUM"
    if score >= 40:
        return "HIGH"
    return "CRITICAL"


def _recommendation_from_score(score: int) -> str:
    if score >= 60:
        return "APPROVE"
    if score >= 40:
        return "MANUAL_REVIEW"
    return "DENY"


def build_risk_assessment(
    *,
    criteria_scores: list[CriterionScore],
    industry_context: IndustryContext | None = None,
    policy_violations: list[str] | None = None,
    policy_warnings: list[str] | None = None,
    document_issues: list[str] | None = None,
    compensating_factors: list[str] | None = None,
    risk_factors: list[str] | None = None,
) -> RiskAssessment:
    """Synthesize criterion scores and contextual factors into a RiskAssessment."""
    base_score = int(round(sum(item.score for item in criteria_scores) / max(1, len(criteria_scores))))
    penalty = industry_penalty(industry_context.default_rate if industry_context else None)

    policy_violations = policy_violations or []
    policy_warnings = policy_warnings or []
    document_issues = document_issues or []
    compensating_factors = compensating_factors or []
    risk_factors = risk_factors or []

    total_penalty = penalty + (10 * len(policy_violations)) + (5 * len(document_issues))
    overall_score = max(0, min(100, base_score - total_penalty))

    risk_level = _risk_level_from_score(overall_score)
    recommendation = _recommendation_from_score(overall_score)
    if policy_violations and recommendation == "APPROVE":
        recommendation = "MANUAL_REVIEW"

    reasoning_parts = [
        f"Base score from criteria: {base_score}/100.",
        f"Penalty applied: {total_penalty} points.",
        f"Final score: {overall_score}/100 -> {recommendation}.",
    ]
    if industry_context:
        reasoning_parts.append(
            f"Industry {industry_context.industry_name} default rate {industry_context.default_rate:.1%} "
            f"contributed {penalty} penalty points."
        )

    return RiskAssessment(
        overall_score=overall_score,
        risk_level=risk_level,
        recommendation=recommendation,
        criteria_scores=criteria_scores,
        industry_context=industry_context,
        policy_violations=policy_violations,
        policy_warnings=policy_warnings,
        document_issues=document_issues,
        reasoning=" ".join(reasoning_parts),
        compensating_factors=compensating_factors,
        risk_factors=risk_factors,
    )
