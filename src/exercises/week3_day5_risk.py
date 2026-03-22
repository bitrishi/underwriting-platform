"""Week 3 Day 5 risk scoring exercise with three scenarios."""

from __future__ import annotations

import os
from pprint import pformat

from src.agents.risk_scoring import (
    create_risk_scoring_agent,
    build_risk_assessment,
    score_dti,
    score_employment,
    score_fico,
    score_ltv,
)
from src.models.risk import IndustryContext
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


def _industry_context(industry: str) -> IndustryContext:
    mapping = {
        "healthcare": IndustryContext(
            industry_name="healthcare",
            default_rate=0.025,
            similar_loans_total=120,
            similar_loans_defaulted=2,
            avg_defaulter_fico=661,
            risk_level="LOW",
            context_note="Stable sector with low historical defaults.",
        ),
        "energy": IndustryContext(
            industry_name="energy",
            default_rate=0.045,
            similar_loans_total=85,
            similar_loans_defaulted=5,
            avg_defaulter_fico=648,
            risk_level="MEDIUM",
            context_note="Moderate cyclicality and downturn exposure.",
        ),
        "cryptocurrency": IndustryContext(
            industry_name="cryptocurrency",
            default_rate=0.12,
            similar_loans_total=34,
            similar_loans_defaulted=8,
            avg_defaulter_fico=629,
            risk_level="HIGH",
            context_note="Volatile earnings and elevated historical defaults.",
        ),
    }
    return mapping[industry]


def run_scenario(name: str, payload: dict) -> None:
    print("\n" + "=" * 84)
    print(f"SCENARIO: {name}")
    print("=" * 84)

    calc_trace = {}
    calc_trace["dti"] = calculate_dti.invoke(
        {
            "annual_income": payload["annual_income"],
            "monthly_debt": payload["monthly_debt"],
        }
    )
    calc_trace["ltv"] = calculate_ltv.invoke(
        {
            "loan_amount": payload["loan_amount"],
            "property_value": payload["property_value"],
        }
    )
    calc_trace["fico"] = check_fico_eligibility.invoke({"fico_score": payload["fico"]})
    calc_trace["employment"] = check_employment_stability.invoke(
        {"years": payload["employment_years"]}
    )

    # Use local scenario-backed graph context so this exercise remains runnable
    # without live Neo4j, while still exercising graph-informed scoring paths.
    industry = _industry_context(payload["industry"])
    graph_trace = {
        "industry_context": industry.model_dump(),
        "similar_loans_summary": {
            "count": industry.similar_loans_total,
            "defaulted": industry.similar_loans_defaulted,
            "default_ratio": round(
                industry.similar_loans_defaulted / max(1, industry.similar_loans_total),
                4,
            ),
        },
    }

    # Run RAG tools only when explicitly enabled; otherwise use deterministic
    # policy context to keep this exercise runnable without external services.
    policy_trace = {}
    if os.getenv("RUN_LIVE_RAG", "0") == "1":
        try:
            policy_trace["search_lending_policies"] = search_lending_policies.invoke(
                {
                    "query": "DTI, LTV, and FICO eligibility thresholds",
                    "topic": "dti",
                    "jurisdiction": payload["jurisdiction"],
                }
            )
        except Exception as exc:
            policy_trace["search_lending_policies"] = f"RAG unavailable: {exc}"

        try:
            policy_trace["verify_compliance_requirement"] = verify_compliance_requirement.invoke(
                {
                    "query": "State-specific LTV and cash-out constraints",
                    "jurisdiction": payload["jurisdiction"],
                }
            )
        except Exception as exc:
            policy_trace["verify_compliance_requirement"] = (
                f"Compliance verification unavailable: {exc}"
            )
    else:
        policy_trace["search_lending_policies"] = (
            "Policy baseline: DTI <= 43 and LTV <= 95 for general eligibility."
        )
        policy_trace["verify_compliance_requirement"] = (
            "Texas caution: elevated scrutiny when LTV exceeds 80."
        )

    criteria = [
        score_dti(calc_trace["dti"]["dti"]),
        score_ltv(calc_trace["ltv"]["ltv"]),
        score_fico(calc_trace["fico"]["fico"]),
        score_employment(payload["employment_years"]),
    ]

    policy_violations: list[str] = []
    policy_warnings: list[str] = []
    if payload["jurisdiction"] == "state_texas" and calc_trace["ltv"]["ltv"] > 80:
        policy_violations.append(
            f"Texas risk check: LTV {calc_trace['ltv']['ltv']:.1f}% exceeds preferred 80% threshold."
        )
    if calc_trace["dti"]["dti"] > 43:
        policy_violations.append(f"DTI {calc_trace['dti']['dti']:.1f}% exceeds 43% threshold.")
    elif calc_trace["dti"]["dti"] > 36:
        policy_warnings.append("Borderline DTI above 36%; compensating factors required.")

    risk_factors = [
        f"Industry default rate {industry.default_rate:.1%} ({industry.risk_level}).",
    ]
    if payload["employment_years"] < 2:
        risk_factors.append("Employment tenure below 2 years.")

    compensating = []
    if payload["fico"] >= 740:
        compensating.append("Strong FICO profile.")
    if calc_trace["ltv"]["ltv"] <= 80:
        compensating.append("Conservative LTV.")

    assessment = build_risk_assessment(
        criteria_scores=criteria,
        industry_context=industry,
        policy_violations=policy_violations,
        policy_warnings=policy_warnings,
        risk_factors=risk_factors,
        compensating_factors=compensating,
    )

    print("\n[CALCULATION TOOLS]")
    print(pformat(calc_trace, indent=2, width=100))

    print("\n[KNOWLEDGE GRAPH CONTEXT]")
    print(pformat(graph_trace, indent=2, width=100))

    print("\n[RAG / POLICY CONTEXT]")
    print(pformat(policy_trace, indent=2, width=100))

    print("\n[RISK ASSESSMENT REPORT]")
    print(assessment.format_report())

    # Expected outcomes for the three required scenarios.
    expected = payload["expected_recommendation"]
    assert assessment.recommendation == expected, (
        f"Expected {expected}, got {assessment.recommendation}"
    )

    data_sources_used = {
        "calculation": bool(calc_trace),
        "graph": bool(graph_trace),
        "rag": bool(policy_trace),
    }
    assert all(data_sources_used.values()), f"Missing data source: {data_sources_used}"
    print(f"\n[PASS] recommendation={assessment.recommendation} sources={data_sources_used}")

    # Optional live agent call to test the end-to-end risk-scoring agent.
    # Enable only when dependencies are available:
    #   RUN_LIVE_AGENT=1 python -m src.exercises.week3_day5_risk
    if os.getenv("RUN_LIVE_AGENT", "0") == "1":
        try:
            agent = create_risk_scoring_agent()
            live_query = (
                f"Score this application: fico={payload['fico']}, annual_income={payload['annual_income']}, "
                f"monthly_debt={payload['monthly_debt']}, loan_amount={payload['loan_amount']}, "
                f"property_value={payload['property_value']}, state=Texas, "
                f"employment_years={payload['employment_years']}, industry={payload['industry']}."
            )
            live_result = agent.invoke(
                {"messages": [{"role": "user", "content": live_query}]}
            )
            message = live_result["messages"][-1].content
            print("\n[LIVE AGENT OUTPUT]")
            print(message)
        except Exception as exc:
            print(f"\n[LIVE AGENT SKIPPED] {exc}")


def main() -> None:
    scenarios = [
        {
            "name": "Strong application",
            "payload": {
                "fico": 740,
                "annual_income": 180000,
                "monthly_debt": 3600,
                "loan_amount": 375000,
                "property_value": 500000,
                "employment_years": 7.0,
                "industry": "healthcare",
                "jurisdiction": "state_texas",
                "expected_recommendation": "APPROVE",
            },
        },
        {
            "name": "Weak application",
            "payload": {
                "fico": 620,
                "annual_income": 100000,
                "monthly_debt": 4000,
                "loan_amount": 480000,
                "property_value": 500000,
                "employment_years": 0.7,
                "industry": "energy",
                "jurisdiction": "state_texas",
                "expected_recommendation": "DENY",
            },
        },
        {
            "name": "Borderline application",
            "payload": {
                "fico": 710,
                "annual_income": 96000,
                "monthly_debt": 3200,
                "loan_amount": 340000,
                "property_value": 400000,
                "employment_years": 2.2,
                "industry": "cryptocurrency",
                "jurisdiction": "state_texas",
                "expected_recommendation": "MANUAL_REVIEW",
            },
        },
    ]

    for scenario in scenarios:
        run_scenario(scenario["name"], scenario["payload"])


if __name__ == "__main__":
    main()
