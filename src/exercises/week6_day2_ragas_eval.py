"""Week 6 Day 2: Ragas-style evaluation for Kuber underwriting agents.

Part A
- Builds a 10-case evaluation dataset across four agents:
  FetchData (3), DocReview (3), RiskScoring (2), Compliance (2)
- Each case contains: question, retrieved_contexts, generated_answer, ground_truth.

Part B
- Runs four core metrics:
  faithfulness, answer_relevancy, context_precision, context_recall
- Uses Ragas when installed; otherwise falls back to deterministic proxy metrics.
- Prints a summary table and flags agent/metric combos below threshold.
- Explains what each failure means and how to fix it.

Part C
- Prints direct answers to production design questions.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import re
from typing import Any

THRESHOLD = 0.85
METRICS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]


@dataclass
class EvalCase:
    case_id: str
    agent: str
    question: str
    retrieved_contexts: list[str]
    generated_answer: str
    ground_truth: str


def build_kuber_eval_dataset() -> list[EvalCase]:
    """Part A: Build a 10-case underwriting evaluation dataset."""
    return [
        # FetchData (3)
        EvalCase(
            case_id="FD-001",
            agent="FetchData",
            question="Pull borrower profile for APP-001 including income, debt, loan amount, property state, and SSN last four.",
            retrieved_contexts=[
                "APP-001: name=Alice Strong, annual_income=120000, monthly_debt=2400, loan_amount=350000, property_state=texas, ssn_last_four=1234",
                "Data source: loan_origination_system v2",
            ],
            generated_answer="APP-001 borrower is Alice Strong with annual income 120000, monthly debt 2400, loan amount 350000, property in texas, ssn_last_four 1234.",
            ground_truth="Alice Strong | annual_income=120000 | monthly_debt=2400 | loan_amount=350000 | property_state=texas | ssn_last_four=1234",
        ),
        EvalCase(
            case_id="FD-002",
            agent="FetchData",
            question="Get credit and employment package for SSN last four 5678.",
            retrieved_contexts=[
                "Credit report 5678: fico_score=620, delinquencies=3, tier=BELOW_MINIMUM",
                "Employment 5678: employer=StartupXYZ, years_at_current=0.5, employment_type=FULL_TIME",
            ],
            generated_answer="Credit shows FICO 620 with 3 delinquencies and BELOW_MINIMUM tier; employment is StartupXYZ at 0.5 years full-time.",
            ground_truth="fico_score=620; delinquencies=3; tier=BELOW_MINIMUM; employer=StartupXYZ; years_at_current=0.5; employment_type=FULL_TIME",
        ),
        EvalCase(
            case_id="FD-003",
            agent="FetchData",
            question="Retrieve all required upstream fields for APP-002 for downstream underwriting.",
            retrieved_contexts=[
                "APP-002: annual_income=55000, monthly_debt=2200, loan_amount=280000, property_value=290000, property_state=california",
                "Credit 5678: fico=620, delinquencies=3",
                "Employment 5678: years_at_current=0.5",
            ],
            generated_answer="APP-002 has income 55000, debt 2200, loan 280000, property 290000 in california, fico 620, delinquencies 3, and 0.5 years at current employer.",
            ground_truth="annual_income=55000; monthly_debt=2200; loan_amount=280000; property_value=290000; property_state=california; fico=620; delinquencies=3; years_at_current=0.5",
        ),
        # DocReview (3)
        EvalCase(
            case_id="DR-001",
            agent="DocReview",
            question="Extract W-2 key fields from the uploaded W-2 document.",
            retrieved_contexts=[
                "W-2 text: Employer Name: Acme Lending Services | Employee Name: Jane Borrower | Wages: 86500.00 | Federal Tax Withheld: 13240.00 | Tax Year: 2024",
            ],
            generated_answer="W-2 extraction: employer=Acme Lending Services, employee=Jane Borrower, wages=86500.00, federal_tax_withheld=13240.00, tax_year=2024.",
            ground_truth="employer_name=Acme Lending Services; employee_name=Jane Borrower; wages=86500.00; federal_tax_withheld=13240.00; tax_year=2024",
        ),
        EvalCase(
            case_id="DR-002",
            agent="DocReview",
            question="Extract paystub details and identify pay frequency.",
            retrieved_contexts=[
                "Paystub OCR: Employer Name: Acme Lending Services | Gross Pay: 3326.92 | Net Pay: 2494.10 | YTD Gross: 86500.00 | Pay Frequency: BIWEEKLY",
            ],
            generated_answer="Paystub extraction shows employer Acme Lending Services, gross pay 3326.92, net pay 2494.10, ytd gross 86500.00, pay frequency BIWEEKLY.",
            ground_truth="employer_name=Acme Lending Services; gross_pay=3326.92; net_pay=2494.10; ytd_gross=86500.00; pay_frequency=BIWEEKLY",
        ),
        EvalCase(
            case_id="DR-003",
            agent="DocReview",
            question="Review package completeness for required docs (W2, 1040, PAYSTUB).",
            retrieved_contexts=[
                "Uploaded files: w2_sample.txt only",
                "Required documents: W2, 1040, PAYSTUB",
            ],
            generated_answer="Document package is partial with W2 present and 1040 plus PAYSTUB missing.",
            ground_truth="document_quality=PARTIAL; missing_documents=[1040,PAYSTUB]",
        ),
        # RiskScoring (2)
        EvalCase(
            case_id="RS-001",
            agent="RiskScoring",
            question="Score risk for APP-001 and produce recommendation.",
            retrieved_contexts=[
                "Borrower profile: income=120000, debt=2400/mo, loan=350000, value=440000, fico=740, employment_years=5",
                "Policy thresholds: max_dti=43, preferred_ltv=80, min_fico=680",
            ],
            generated_answer="DTI is 24, LTV is 79.55, FICO 740 exceeds threshold, employment stable. Overall recommendation APPROVE with low risk.",
            ground_truth="dti=24; ltv=79.55; fico_pass=true; employment_pass=true; recommendation=APPROVE; risk_level=LOW",
        ),
        EvalCase(
            case_id="RS-002",
            agent="RiskScoring",
            question="Score risk for APP-002 and produce recommendation.",
            retrieved_contexts=[
                "Borrower profile: income=55000, debt=2200/mo, loan=280000, value=290000, fico=620, employment_years=0.5",
                "Policy thresholds: max_dti=43, max_ltv=95, min_fico=680",
            ],
            generated_answer="DTI is about 48 and LTV about 96.55, FICO 620 is below policy minimum and employment is weak; recommendation should be MANUAL_REVIEW or DENY.",
            ground_truth="dti=48; ltv=96.55; fico_pass=false; employment_pass=false; recommendation=MANUAL_REVIEW_or_DENY",
        ),
        # Compliance (2)
        EvalCase(
            case_id="CP-001",
            agent="Compliance",
            question="For a Texas denial scenario, what disclosures are required?",
            retrieved_contexts=[
                "Texas adverse action guidance: provide adverse action notice and reason codes",
                "Audit trail requirement: decision inputs and model outputs must be retained",
            ],
            generated_answer="Required disclosures include adverse action notice with reason codes, and audit trail evidence must be complete.",
            ground_truth="required_disclosures include adverse_action_notice and reason_codes; audit_trail_complete=true",
        ),
        EvalCase(
            case_id="CP-002",
            agent="Compliance",
            question="Check if compliance should override risk recommendation when blocking violations exist.",
            retrieved_contexts=[
                "Rule: any blocking violation => recommendation_override=MANUAL_REVIEW",
                "Current case: blocking_violations=[missing_adverse_action_disclosure]",
            ],
            generated_answer="Because a blocking violation exists, compliance should override to MANUAL_REVIEW.",
            ground_truth="blocking_violations_present=true; recommendation_override=MANUAL_REVIEW",
        ),
    ]


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_\.]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _best_context_overlap(answer: str, contexts: list[str]) -> float:
    ans = _tokenize(answer)
    return max((_jaccard(ans, _tokenize(c)) for c in contexts), default=0.0)


def _heuristic_metric_scores(case: EvalCase) -> dict[str, float]:
    """Deterministic fallback metrics when Ragas is unavailable.

    These are proxy scores and should not replace true Ragas in production.
    """
    q = _tokenize(case.question)
    a = _tokenize(case.generated_answer)
    gt = _tokenize(case.ground_truth)
    all_ctx = " ".join(case.retrieved_contexts)
    c = _tokenize(all_ctx)

    answer_relevancy = _jaccard(q, a)
    faithfulness = _best_context_overlap(case.generated_answer, case.retrieved_contexts)
    context_precision = _jaccard(c, gt)
    context_recall = len(c & gt) / len(gt) if gt else 1.0

    return {
        "faithfulness": round(float(faithfulness), 4),
        "answer_relevancy": round(float(answer_relevancy), 4),
        "context_precision": round(float(context_precision), 4),
        "context_recall": round(float(context_recall), 4),
    }


def _run_ragas_if_available(cases: list[EvalCase]) -> tuple[dict[str, float] | None, str | None]:
    """Run true Ragas aggregate metrics when dependencies are installed.

    Returns:
        tuple: (aggregate_scores_or_none, error_message_or_none)
    """
    try:
        from datasets import Dataset  # type: ignore
        from ragas import evaluate  # type: ignore
        from ragas.metrics import (  # type: ignore
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except Exception as exc:
        return None, f"Dependency import failed: {type(exc).__name__}: {exc}"

    rows = [
        {
            "question": c.question,
            "answer": c.generated_answer,
            "contexts": c.retrieved_contexts,
            "ground_truth": c.ground_truth,
        }
        for c in cases
    ]

    dataset = Dataset.from_list(rows)
    try:
        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
    except Exception as exc:
        return None, f"Ragas evaluation failed: {type(exc).__name__}: {exc}"

    # result is dict-like with metric names
    return {
        "faithfulness": round(float(result["faithfulness"]), 4),
        "answer_relevancy": round(float(result["answer_relevancy"]), 4),
        "context_precision": round(float(result["context_precision"]), 4),
        "context_recall": round(float(result["context_recall"]), 4),
    }, None


def evaluate_dataset(cases: list[EvalCase]) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, float]],
    dict[str, float] | None,
    str | None,
]:
    """Part B: compute case-level and agent-level metric summaries."""
    case_rows: list[dict[str, Any]] = []
    by_agent_metric: dict[str, list[float]] = defaultdict(list)

    for case in cases:
        scores = _heuristic_metric_scores(case)
        row = {
            "case_id": case.case_id,
            "agent": case.agent,
            **scores,
        }
        case_rows.append(row)

        for metric_name, value in scores.items():
            by_agent_metric[f"{case.agent}:{metric_name}"].append(value)

    agent_summary: dict[str, dict[str, float]] = defaultdict(dict)
    for key, values in by_agent_metric.items():
        agent, metric_name = key.split(":", 1)
        agent_summary[agent][metric_name] = round(sum(values) / len(values), 4)

    ragas_aggregate, ragas_error = _run_ragas_if_available(cases)
    return case_rows, dict(agent_summary), ragas_aggregate, ragas_error


def _format_table(rows: list[dict[str, Any]]) -> str:
    headers = ["case_id", "agent", *METRICS]
    widths = {h: max(len(h), *(len(str(r.get(h, ""))) for r in rows)) for h in headers}

    def line(vals: list[str]) -> str:
        return " | ".join(v.ljust(widths[h]) for v, h in zip(vals, headers))

    out = [line(headers), "-+-".join("-" * widths[h] for h in headers)]
    for r in rows:
        out.append(
            line([
                str(r["case_id"]),
                str(r["agent"]),
                *(f"{float(r[m]):.4f}" for m in METRICS),
            ])
        )
    return "\n".join(out)


def _failure_explanations(agent_summary: dict[str, dict[str, float]], threshold: float = THRESHOLD) -> list[str]:
    fixes_by_metric = {
        "faithfulness": "Tighten grounding prompts, require direct citations, and reduce generation temperature for compliance/risk narratives.",
        "answer_relevancy": "Improve task routing prompts and add explicit intent extraction so answers stay focused on the user question.",
        "context_precision": "Improve retriever ranking/filtering (metadata filters, query rewriting) to remove noisy context chunks.",
        "context_recall": "Increase retrieval coverage (higher top-k, synonym expansion, hybrid retrieval) so required facts are not missed.",
    }

    failures: list[str] = []
    for agent, metrics in sorted(agent_summary.items()):
        for metric_name, score in metrics.items():
            if score < threshold:
                failures.append(
                    f"{agent}:{metric_name}={score:.4f} < {threshold:.2f} -> "
                    f"{metric_name} failure means quality risk for {agent}. Fix: {fixes_by_metric[metric_name]}"
                )
    return failures


def print_part_c_analysis() -> None:
    """Part C: answer the four production questions."""
    print("\nPart C — Analysis")
    print("Q1) For compliance evaluation, should faithfulness threshold be higher than 0.95? Why?")
    print(
        "A1) Yes in production-critical paths. Compliance responses can trigger legal exposure; "
        "a stricter faithfulness target (>=0.95, often >=0.98 for adverse-action logic) "
        "reduces hallucinated policy statements. Keep a slightly lower threshold in development "
        "to avoid blocking iteration, then enforce stricter gates in pre-prod/prod."
    )

    print("\nQ2) How to generate a 500-case synthetic test set from Kuber lending policy docs?")
    print(
        "A2) Build a policy-to-question generator pipeline: "
        "(1) chunk policy docs by section and metadata, "
        "(2) generate templated + paraphrased questions per section across jurisdictions/loan types, "
        "(3) synthesize grounded answers only from source chunks, "
        "(4) attach citation-based ground truth, "
        "(5) stratify 500 cases by topic (DTI/FICO/LTV/disclosures), criticality, and state, "
        "(6) run human spot-audit on 5-10% for label quality."
    )

    print("\nQ3) Where in CI/CD should Ragas evaluation run and what should trigger it?")
    print(
        "A3) Run in three stages: "
        "(a) PR gate on changed retrieval/prompt/agent files with a fast subset, "
        "(b) nightly full-suite regression on main, "
        "(c) pre-release gate before deploy. "
        "Triggers: prompt changes, retriever/index changes, model/version changes, "
        "and policy corpus updates."
    )

    print("\nQ4) How to handle Ragas judge hallucinations (LLM-as-judge is wrong)?")
    print(
        "A4) Use evaluator robustness controls: "
        "(1) consensus judging (2-3 judge runs/models), "
        "(2) confidence intervals and disagreement flags, "
        "(3) periodic human adjudication set as calibration anchor, "
        "(4) deterministic rule checks (citation/regex validators) alongside judge metrics, "
        "(5) do not auto-fail deploy on a single noisy metric without corroboration."
    )


def main() -> None:
    cases = build_kuber_eval_dataset()

    print("Part A — Dataset")
    print(f"Built {len(cases)} cases.")
    print("Case distribution:")
    distribution = defaultdict(int)
    for c in cases:
        distribution[c.agent] += 1
    print(json.dumps(dict(distribution), indent=2))

    case_rows, agent_summary, ragas_aggregate, ragas_error = evaluate_dataset(cases)

    print("\nPart B — Case-Level Summary Table")
    print(_format_table(case_rows))

    print("\nPart B — Agent-Level Means")
    print(json.dumps(agent_summary, indent=2))

    if ragas_aggregate is not None:
        print("\nPart B — True Ragas Aggregate (all 10 cases)")
        print(json.dumps(ragas_aggregate, indent=2))
    else:
        print("\nPart B — True Ragas Aggregate")
        print("Fell back to deterministic proxy metrics.")
        if ragas_error:
            print(f"Reason: {ragas_error}")
        print("Install/check with: pip install ragas datasets")

    failures = _failure_explanations(agent_summary, threshold=THRESHOLD)
    print(f"\nPart B — Below-Threshold Findings (< {THRESHOLD:.2f})")
    if not failures:
        print("No agent/metric combinations below threshold.")
    else:
        for item in failures:
            print(f"- {item}")

    print_part_c_analysis()


if __name__ == "__main__":
    main()
