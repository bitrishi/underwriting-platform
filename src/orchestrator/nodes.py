"""Node implementations for the underwriting StateGraph."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from langgraph.types import interrupt
from pydantic import ValidationError

from src.agents.compliance import create_compliance_agent
from src.agents.doc_review import create_doc_review_agent
from src.agents.fetch_data import create_fetch_data_agent
from src.agents.risk_scoring import (
    build_risk_assessment,
    create_risk_scoring_agent,
    score_dti,
    score_employment,
    score_fico,
    score_ltv,
)
from src.models.borrower import (
    BorrowerPackage,
    BorrowerProfile,
    CreditReport,
    EmploymentRecord,
    PolicyContext,
)
from src.models.compliance import ComplianceCheck, ComplianceResult
from src.models.human_review import HumanReviewRequest, HumanReviewResponse
from src.models.risk import IndustryContext, RiskAssessment
from src.orchestrator.state import UnderwritingState
from src.pipeline.report_formatter import format_underwriting_report
from src.tools.document_router import route_document
from src.tools.document_tools import classify_document, extract_document_data
from src.tools.fetch_tools import (
    pull_borrower_data,
    pull_credit_report,
    pull_employment_history,
)
from src.tools.policy_tools import search_lending_policies
from src.tools.compliance_tools import (
    check_disclosure_requirements,
    verify_audit_trail,
)
from src.tools.policy_tools_v2 import verify_compliance_requirement
from src.tools.underwriting_tools import calculate_dti, calculate_ltv
from src.utils.circuit_breaker import ALL_BREAKERS, bedrock_breaker
from src.utils.error_types import StructuredError, categorize_pipeline_errors
from src.utils.metrics import PipelineMetrics
from src.utils.retry import retry_with_backoff


@retry_with_backoff(
    max_retries=2,
    base_delay=0.4,
    max_delay=4.0,
    retryable_exceptions=(TimeoutError, ConnectionError),
    jitter=True,
)
def _invoke_agent(agent: Any, prompt: str) -> str:
    """Invoke a LangChain agent with the messages payload shape used in this repo."""
    result = bedrock_breaker.call(
        agent.invoke,
        {"messages": [{"role": "user", "content": prompt}]},
    )

    if isinstance(result, dict) and result.get("error") == "bedrock_circuit_open":
        raise RuntimeError("bedrock_circuit_open")

    messages = result.get("messages", []) if isinstance(result, dict) else []
    if messages:
        last = messages[-1]
        content = getattr(last, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if text:
                        parts.append(str(text))
                else:
                    parts.append(str(part))
            if parts:
                return "\n".join(parts)

    if isinstance(result, dict) and "output" in result:
        return str(result["output"])

    return str(result)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _append_error(errors: list[str], error: StructuredError) -> None:
    errors.append(error.to_state_string())


def _metrics_from_state(state: UnderwritingState) -> PipelineMetrics:
    app_id = state.get("app_id", "UNKNOWN")
    metrics = PipelineMetrics(evaluation_id=str(app_id))
    prior = state.get("metrics_summary") or {}
    for node_name, node_data in (prior.get("node_metrics") or {}).items():
        metrics.start_node(node_name)
        metrics.end_node(
            node_name,
            status=str(node_data.get("status", "success")),
            llm_calls=int(node_data.get("llm_calls", 0) or 0),
            tokens_in=int(node_data.get("tokens_in", 0) or 0),
            tokens_out=int(node_data.get("tokens_out", 0) or 0),
            tools_called=list(node_data.get("tools_called", [])),
            errors=list(node_data.get("errors", [])),
            retries=int(node_data.get("retries", 0) or 0),
            cost_estimate_usd=float(node_data.get("cost_estimate_usd", 0.0) or 0.0),
        )
    for err in prior.get("pipeline_errors", []) or []:
        metrics.record_pipeline_error(str(err))
    return metrics


def _stamp_node(state: UnderwritingState, node_name: str, started_at: float) -> dict[str, Any]:
    timestamps = dict(state.get("node_timestamps", {}))
    durations = dict(state.get("node_durations_s", {}))
    timestamps[node_name] = _now_iso()
    durations[node_name] = round(time.perf_counter() - started_at, 6)
    return {
        "node_timestamps": timestamps,
        "node_durations_s": durations,
        "node_execution_order": [node_name],
    }


def _estimate_usage_counts(state: UnderwritingState) -> tuple[int, int, float]:
    tool_calls = 0
    llm_calls = 0

    if state.get("borrower_package"):
        tool_calls += 4
        llm_calls += 1

    doc = state.get("document_review") or {}
    if doc and doc.get("status") == "COMPLETED":
        tool_calls += 4
        llm_calls += 1

    if state.get("risk_assessment"):
        tool_calls += 8
        llm_calls += 1

    if state.get("loan_type", "conventional").lower() == "fha":
        tool_calls += 1

    if state.get("compliance_result"):
        tool_calls += 4
        llm_calls += 1

    estimated_cost = round((llm_calls * 0.0012) + (tool_calls * 0.00005), 6)
    return tool_calls, llm_calls, estimated_cost


def _infer_industry(borrower_package: dict[str, Any]) -> str:
    employer = (
        borrower_package.get("employment", {}).get("employer", "")
        if borrower_package
        else ""
    ).lower()
    if "health" in employer:
        return "healthcare"
    if "energy" in employer:
        return "energy"
    if "crypto" in employer:
        return "cryptocurrency"
    return "technology"


def _industry_context(industry: str) -> IndustryContext:
    contexts = {
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
            context_note="Volatile earnings and elevated default volatility.",
        ),
    }
    return contexts.get(
        industry,
        IndustryContext(
            industry_name="technology",
            default_rate=0.04,
            similar_loans_total=100,
            similar_loans_defaulted=4,
            avg_defaulter_fico=655,
            risk_level="MEDIUM",
            context_note="Baseline technology segment risk profile.",
        ),
    )


def fetch_data_node(state: UnderwritingState) -> dict[str, Any]:
    """Run the FetchData agent and assemble a structured borrower package."""
    started_at = time.perf_counter()
    errors = list(state.get("errors", []))
    metrics = _metrics_from_state(state)
    metrics.start_node("fetch_data")
    try:
        app_id = state.get("app_id", "")
        agent_summary = ""

        try:
            agent = create_fetch_data_agent()
            agent_summary = _invoke_agent(agent, f"Gather all underwriting data for {app_id}.")
        except Exception as exc:
            _append_error(
                errors,
                StructuredError.recoverable(
                    source="fetch_data_agent",
                    message="FetchData agent call failed; continuing with deterministic tools.",
                    exc=exc,
                ),
            )

        try:
            borrower_raw = pull_borrower_data.invoke({"app_id": app_id})
            if isinstance(borrower_raw, dict) and borrower_raw.get("error"):
                raise ValueError(borrower_raw["error"])

            ssn_last_four = borrower_raw["ssn_last_four"]
            credit_raw = pull_credit_report.invoke({"ssn_last_four": ssn_last_four})
            employment_raw = pull_employment_history.invoke({"ssn_last_four": ssn_last_four})
            policy_report = search_lending_policies.invoke(
                {"query": f"Mortgage policy requirements for {borrower_raw['property_state']}"}
            )

            missing: list[str] = []
            if isinstance(credit_raw, dict) and credit_raw.get("error"):
                missing.append("credit")
                _append_error(
                    errors,
                    StructuredError.recoverable(
                        source="pull_credit_report",
                        message=str(credit_raw.get("error")),
                    ),
                )
            if isinstance(employment_raw, dict) and employment_raw.get("error"):
                missing.append("employment")
                _append_error(
                    errors,
                    StructuredError.recoverable(
                        source="pull_employment_history",
                        message=str(employment_raw.get("error")),
                    ),
                )

            quality = "COMPLETE"
            if missing:
                quality = "PARTIAL"
            if len(missing) >= 2:
                quality = "INSUFFICIENT"

            package = BorrowerPackage(
                borrower=BorrowerProfile(**borrower_raw),
                credit=CreditReport(**credit_raw),
                employment=EmploymentRecord(**employment_raw),
                policies=PolicyContext(
                    applicable_policies=[str(policy_report)],
                    jurisdiction_rules=[f"state={borrower_raw['property_state']}"],
                    sources=["policy_tools.search_lending_policies"],
                ),
                data_quality=quality,
                missing_fields=missing,
                fetch_timestamp="pipeline_fetch_node",
            )

            metrics.end_node(
                "fetch_data",
                status="degraded" if missing else "success",
                llm_calls=1 if agent_summary else 0,
                tools_called=[
                    "pull_borrower_data",
                    "pull_credit_report",
                    "pull_employment_history",
                    "search_lending_policies",
                ],
                errors=errors,
                cost_estimate_usd=0.0012,
            )

            return {
                "borrower_package": package.model_dump(),
                "has_documents": bool(state.get("document_paths")),
                "fatal_error": False,
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "fetch_data", started_at),
                "messages": [
                    (
                        "assistant",
                        "FetchData complete. "
                        f"data_quality={quality}. "
                        f"agent_summary={agent_summary[:280]}",
                    )
                ],
            }
        except Exception as exc:
            _append_error(
                errors,
                StructuredError.fatal(
                    source="fetch_data_node",
                    message="Unable to assemble borrower package.",
                    exc=exc,
                ),
            )
            metrics.end_node(
                "fetch_data",
                status="failed",
                tools_called=["pull_borrower_data", "pull_credit_report", "pull_employment_history"],
                errors=errors,
            )
            return {
                "borrower_package": None,
                "has_documents": bool(state.get("document_paths")),
                "fatal_error": True,
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "fetch_data", started_at),
                "messages": [("assistant", f"FetchData failed: {exc}")],
            }
    except Exception as exc:
        _append_error(
            errors,
            StructuredError.fatal(
                source="fetch_data_node",
                message="Unhandled error in fetch_data_node.",
                exc=exc,
            ),
        )
        metrics.end_node("fetch_data", status="failed", errors=errors)
        return {
            "borrower_package": None,
            "has_documents": bool(state.get("document_paths")),
            "fatal_error": True,
            "errors": errors,
            "metrics_summary": metrics.summary(),
            **_stamp_node(state, "fetch_data", started_at),
            "messages": [("assistant", f"FetchData unhandled error: {exc}")],
        }


def doc_review_node(state: UnderwritingState) -> dict[str, Any]:
    """Run the Doc Review agent and store a review package summary."""
    started_at = time.perf_counter()
    errors = list(state.get("errors", []))
    metrics = _metrics_from_state(state)
    metrics.start_node("doc_review")
    try:
        docs = state.get("document_paths", []) or []
        required = {
            "W2": "Income consistency checks.",
            "1040": "Tax-return verification for income claims.",
            "PAYSTUB": "Recent employment and pay continuity.",
        }

        if not docs:
            missing = [
                {
                    "document_type": doc_type,
                    "reason_required": reason,
                    "impact": "Document package not submitted.",
                }
                for doc_type, reason in required.items()
            ]
            skipped_review = {
                "status": "SKIPPED",
                "documents_classified": [],
                "extractions": [],
                "validations": [],
                "missing_documents": missing,
                "missing_document_flags": {
                    "missing_w2": True,
                    "missing_1040": True,
                    "missing_paystub": True,
                },
                "document_quality": "SKIPPED",
                "total_documents": 0,
                "total_issues": len(missing),
                "agent_summary": "No documents provided.",
            }
            metrics.end_node("doc_review", status="success", errors=errors)
            return {
                "document_review": skipped_review,
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "doc_review", started_at),
                "messages": [("assistant", "Document Review skipped (no documents provided).")],
            }

        agent_summary = ""
        try:
            agent = create_doc_review_agent()
            prompt = "Review these loan documents:\n" + "\n".join(f"- {path}" for path in docs)
            agent_summary = _invoke_agent(agent, prompt)
        except Exception as exc:
            _append_error(
                errors,
                StructuredError.recoverable(
                    source="doc_review_agent",
                    message="Doc review agent failed; continuing deterministic extraction.",
                    exc=exc,
                ),
            )

        try:
            lowered = " ".join(path.lower() for path in docs)
            missing: list[dict[str, str]] = []

            classifications: list[dict[str, Any]] = []
            extractions: list[dict[str, Any]] = []
            methods_used: list[dict[str, str]] = []
            total_extraction_cost = 0.0

            for path in docs:
                cls = classify_document.invoke({"document_path": path})
                classifications.append(cls)

                normalized_type = str(cls.get("document_type", "OTHER")).lower()
                route = route_document(path, declared_document_type=normalized_type)
                preferred_method = route.get("primary_method", "vision")

                extraction = None
                if normalized_type in {"w2", "1040", "paystub"}:
                    extraction = extract_document_data.invoke(
                        {
                            "document_path": path,
                            "document_type": normalized_type,
                            "preferred_method": preferred_method,
                        }
                    )

                    # Textract fallback to vision when confidence is low.
                    confidence = str((extraction or {}).get("extracted_data", {}).get("confidence", ""))
                    if (
                        preferred_method == "textract"
                        and extraction
                        and "error" not in extraction
                        and confidence == "LOW"
                    ):
                        extraction = extract_document_data.invoke(
                            {
                                "document_path": path,
                                "document_type": normalized_type,
                                "preferred_method": "vision",
                            }
                        )

                if extraction and "error" not in extraction:
                    extractions.append(extraction)
                    used_method = str(extraction.get("metadata", {}).get("processing_method", preferred_method))
                    methods_used.append({"file_path": path, "method": used_method})
                    total_extraction_cost += float(extraction.get("metadata", {}).get("estimated_cost_usd", 0.0) or 0.0)
                else:
                    methods_used.append({"file_path": path, "method": preferred_method})

            if "w2" not in lowered:
                missing.append({"document_type": "W2", "reason_required": required["W2"], "impact": "Cannot verify historical wages."})
            if "1040" not in lowered and "tax" not in lowered:
                missing.append({"document_type": "1040", "reason_required": required["1040"], "impact": "Cannot validate taxable income."})
            if "paystub" not in lowered and "pay_stub" not in lowered:
                missing.append({"document_type": "PAYSTUB", "reason_required": required["PAYSTUB"], "impact": "Cannot verify current cashflow."})

            quality = "COMPLETE"
            if missing:
                quality = "PARTIAL"
            if len(missing) >= 2:
                quality = "INSUFFICIENT"

            review = {
                "status": "COMPLETED",
                "documents_classified": classifications,
                "extractions": extractions,
                "validations": [],
                "missing_documents": missing,
                "missing_document_flags": {
                    "missing_w2": "w2" not in lowered,
                    "missing_1040": "1040" not in lowered and "tax" not in lowered,
                    "missing_paystub": "paystub" not in lowered and "pay_stub" not in lowered,
                },
                "document_quality": quality,
                "total_documents": len(docs),
                "total_issues": len(missing),
                "agent_summary": agent_summary,
                "extraction_methods": methods_used,
                "estimated_extraction_cost_usd": round(total_extraction_cost, 6),
            }

            metrics.end_node(
                "doc_review",
                status="degraded" if missing else "success",
                llm_calls=1 if agent_summary else 0,
                tools_called=["classify_document", "extract_document_data", "validate_document_package"],
                errors=errors,
                cost_estimate_usd=round(total_extraction_cost, 6),
            )

            return {
                "document_review": review,
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "doc_review", started_at),
                "messages": [
                    (
                        "assistant",
                        "Document Review complete. "
                        f"quality={quality}, missing_docs={len(missing)}, methods={methods_used}.",
                    )
                ],
            }
        except Exception as exc:
            _append_error(
                errors,
                StructuredError.degraded(
                    source="doc_review_node",
                    message="Document review degraded due to extraction error.",
                    exc=exc,
                ),
            )
            metrics.end_node("doc_review", status="failed", errors=errors)
            return {
                "document_review": {
                    "status": "FAILED",
                    "documents_classified": [],
                    "extractions": [],
                    "validations": [],
                    "missing_documents": [],
                    "missing_document_flags": {},
                    "document_quality": "INSUFFICIENT",
                    "total_documents": len(docs),
                    "total_issues": 0,
                    "agent_summary": "",
                },
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "doc_review", started_at),
                "messages": [("assistant", f"Document Review failed: {exc}")],
            }
    except Exception as exc:
        _append_error(
            errors,
            StructuredError.degraded(
                source="doc_review_node",
                message="Unhandled doc review error.",
                exc=exc,
            ),
        )
        metrics.end_node("doc_review", status="failed", errors=errors)
        return {
            "document_review": {
                "status": "FAILED",
                "documents_classified": [],
                "extractions": [],
                "validations": [],
                "missing_documents": [],
                "missing_document_flags": {},
                "document_quality": "INSUFFICIENT",
                "total_documents": 0,
                "total_issues": 0,
                "agent_summary": "",
            },
            "errors": errors,
            "metrics_summary": metrics.summary(),
            **_stamp_node(state, "doc_review", started_at),
            "messages": [("assistant", f"Document Review unhandled error: {exc}")],
        }


def risk_scoring_node(state: UnderwritingState) -> dict[str, Any]:
    """Run the Risk Scoring agent and generate a structured risk assessment."""
    started_at = time.perf_counter()
    errors = list(state.get("errors", []))
    metrics = _metrics_from_state(state)
    metrics.start_node("risk_scoring")
    try:
        borrower_package = state.get("borrower_package")
        document_review = state.get("document_review")
        agent_summary = ""

        if not borrower_package:
            msg = "Risk Scoring skipped: borrower_package missing."
            _append_error(
                errors,
                StructuredError.degraded(
                    source="risk_scoring_node",
                    message="Borrower package missing; risk scoring skipped.",
                ),
            )
            metrics.end_node("risk_scoring", status="degraded", errors=errors)
            return {
                "risk_assessment": None,
                "needs_manual_review": not bool(state.get("fatal_error", False)),
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "risk_scoring", started_at),
                "messages": [("assistant", msg)],
            }

        try:
            agent = create_risk_scoring_agent()
            prompt = (
                "Score underwriting risk using both packages.\n"
                f"BorrowerPackage:\n{json.dumps(borrower_package, indent=2)}\n"
                f"DocumentReviewPackage:\n{json.dumps(document_review or {}, indent=2)}"
            )
            agent_summary = _invoke_agent(agent, prompt)
        except Exception as exc:
            _append_error(
                errors,
                StructuredError.recoverable(
                    source="risk_scoring_agent",
                    message="Risk scoring agent call failed; continuing deterministic scoring.",
                    exc=exc,
                ),
            )

        try:
            annual_income = borrower_package["borrower"]["annual_income"]
            monthly_debt = borrower_package["borrower"]["monthly_debt"]
            loan_amount = borrower_package["borrower"]["loan_amount"]
            property_value = borrower_package["borrower"]["property_value"]
            fico_score = borrower_package["credit"]["fico_score"]
            years = borrower_package["employment"]["years_at_current"]

            dti = calculate_dti.invoke({"annual_income": annual_income, "monthly_debt": monthly_debt})["dti"]
            ltv = calculate_ltv.invoke({"loan_amount": loan_amount, "property_value": property_value})["ltv"]

            criteria = [
                score_dti(dti),
                score_ltv(ltv),
                score_fico(int(fico_score)),
                score_employment(float(years)),
            ]

            industry = _infer_industry(borrower_package)
            industry_context = _industry_context(industry)

            document_issues: list[str] = []
            if document_review and document_review.get("missing_documents"):
                for missing in document_review["missing_documents"]:
                    doc_type = missing.get("document_type", "UNKNOWN")
                    document_issues.append(f"Missing required document: {doc_type}")

            policy_violations: list[str] = []
            if int(fico_score) < 680:
                policy_violations.append("FICO below minimum threshold (680)")
            if dti > 43:
                policy_violations.append("DTI exceeds 43% guideline")
            if ltv > 95:
                policy_violations.append("LTV exceeds 95% maximum")

            assessment = build_risk_assessment(
                criteria_scores=criteria,
                industry_context=industry_context,
                policy_violations=policy_violations,
                policy_warnings=[],
                document_issues=document_issues,
                compensating_factors=[],
                risk_factors=document_issues + policy_violations,
            )

            risk_payload = assessment.model_dump()
            risk_payload["agent_summary"] = agent_summary

            metrics.end_node(
                "risk_scoring",
                status="success",
                llm_calls=1 if agent_summary else 0,
                tools_called=["calculate_dti", "calculate_ltv"],
                errors=errors,
                cost_estimate_usd=0.0012,
            )

            return {
                "risk_assessment": risk_payload,
                "needs_manual_review": assessment.recommendation in {"MANUAL_REVIEW", "DENY"},
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "risk_scoring", started_at),
                "messages": [
                    (
                        "assistant",
                        "Risk Scoring complete. "
                        f"recommendation={assessment.recommendation}, score={assessment.overall_score}.",
                    )
                ],
            }
        except Exception as exc:
            _append_error(
                errors,
                StructuredError.degraded(
                    source="risk_scoring_node",
                    message="Risk scoring failed; routing to manual review.",
                    exc=exc,
                ),
            )
            metrics.end_node("risk_scoring", status="failed", errors=errors)
            return {
                "risk_assessment": None,
                "needs_manual_review": True,
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "risk_scoring", started_at),
                "messages": [("assistant", f"Risk Scoring failed: {exc}")],
            }
    except Exception as exc:
        _append_error(
            errors,
            StructuredError.degraded(
                source="risk_scoring_node",
                message="Unhandled risk scoring error.",
                exc=exc,
            ),
        )
        metrics.end_node("risk_scoring", status="failed", errors=errors)
        return {
            "risk_assessment": None,
            "needs_manual_review": True,
            "errors": errors,
            "metrics_summary": metrics.summary(),
            **_stamp_node(state, "risk_scoring", started_at),
            "messages": [("assistant", f"Risk Scoring unhandled error: {exc}")],
        }


def compliance_node(state: UnderwritingState) -> dict[str, Any]:
    """Run compliance validation using deterministic and RAG-backed checks."""
    started_at = time.perf_counter()
    errors = list(state.get("errors", []))
    metrics = _metrics_from_state(state)
    metrics.start_node("compliance")
    try:
        if state.get("fatal_error"):
            metrics.end_node("compliance", status="degraded", errors=errors)
            return {
                "compliance_result": {
                    "required_disclosures": [],
                    "fair_lending_flag": False,
                    "audit_trail_complete": False,
                    "blocking_violations": ["skipped_due_to_fatal_error"],
                    "recommendation_override": "NONE",
                    "checks": [],
                    "summary": "Compliance skipped due to fatal upstream fetch failure.",
                },
                "needs_manual_review": False,
                "errors": errors,
                "metrics_summary": metrics.summary(),
                **_stamp_node(state, "compliance", started_at),
                "messages": [("assistant", "Compliance skipped due to fatal error.")],
            }

        risk_assessment = state.get("risk_assessment") or {}
        borrower_package = state.get("borrower_package") or {}
        recommendation = str(risk_assessment.get("recommendation", "MANUAL_REVIEW")).upper()
        property_state = str(
            borrower_package.get("borrower", {}).get("property_state", "federal")
        ).lower()

        agent_summary = ""
        try:
            agent = create_compliance_agent()
            prompt = (
                "Run compliance verification for this underwriting decision.\n"
                f"RiskAssessment:\n{json.dumps(risk_assessment, indent=2)}"
            )
            agent_summary = _invoke_agent(agent, prompt)
        except Exception as exc:
            _append_error(
                errors,
                StructuredError.recoverable(
                    source="compliance_agent",
                    message="Compliance agent call failed; continuing deterministic checks.",
                    exc=exc,
                ),
            )

        disclosures = check_disclosure_requirements.invoke(
            {
                "decision": recommendation if recommendation in {"APPROVE", "DENY", "MANUAL_REVIEW"} else "MANUAL_REVIEW",
                "state": property_state,
                "is_new_application": not bool(state.get("simulate_existing_application", False)),
            }
        )
        audit = verify_audit_trail.invoke({"risk_assessment": json.dumps(risk_assessment)})

        blocking_violations = list(disclosures.get("blocking_violations", []))
        if not audit.get("complete", False):
            blocking_violations.append("Audit trail is incomplete")

        # Optional legal verification pass for critical scenarios.
        try:
            if recommendation in {"DENY", "MANUAL_REVIEW"}:
                legal_check = verify_compliance_requirement.invoke(
                    {
                        "query": "Confirm adverse action and disclosure compliance requirements.",
                        "jurisdiction": f"state_{property_state}" if property_state else "federal",
                    }
                )
            else:
                legal_check = "Skipped critical legal verification for non-escalated decision."
        except Exception as exc:
            legal_check = f"Legal verification unavailable: {exc}"
            _append_error(
                errors,
                StructuredError.recoverable(
                    source="verify_compliance_requirement",
                    message="Legal verification unavailable.",
                    exc=exc,
                ),
            )

        fair_lending_flag = "discrimin" in str(legal_check).lower()
        recommendation_override = "NONE"
        if blocking_violations or fair_lending_flag:
            recommendation_override = "MANUAL_REVIEW"

        checks = [
            ComplianceCheck(
                name="disclosure_requirements",
                passed=len(disclosures.get("blocking_violations", [])) == 0,
                detail=disclosures.get("detail", "Disclosure checks complete."),
            ),
            ComplianceCheck(
                name="audit_trail_completeness",
                passed=bool(audit.get("complete", False)),
                detail=audit.get("detail", "Audit verification complete."),
            ),
        ]

        result = ComplianceResult(
            required_disclosures=disclosures.get("required_disclosures", []),
            fair_lending_flag=fair_lending_flag,
            audit_trail_complete=bool(audit.get("complete", False)),
            blocking_violations=blocking_violations,
            recommendation_override=recommendation_override,
            checks=checks,
            summary=(
                f"Compliance complete. override={recommendation_override}. "
                f"blocking_violations={len(blocking_violations)}."
            ),
        )

        payload = result.model_dump()
        payload["agent_summary"] = agent_summary
        payload["legal_verification"] = str(legal_check)

        needs_manual_review = bool(state.get("needs_manual_review", False))
        if recommendation_override == "MANUAL_REVIEW":
            needs_manual_review = True

        metrics.end_node(
            "compliance",
            status="degraded" if recommendation_override == "MANUAL_REVIEW" else "success",
            llm_calls=1 if agent_summary else 0,
            tools_called=["check_disclosure_requirements", "verify_audit_trail", "verify_compliance_requirement"],
            errors=errors,
            cost_estimate_usd=0.0015,
        )

        return {
            "compliance_result": payload,
            "needs_manual_review": needs_manual_review,
            "errors": errors,
            "metrics_summary": metrics.summary(),
            **_stamp_node(state, "compliance", started_at),
            "messages": [("assistant", result.summary)],
        }
    except Exception as exc:
        _append_error(
            errors,
            StructuredError.degraded(
                source="compliance_node",
                message="Compliance node failed.",
                exc=exc,
            ),
        )
        metrics.end_node("compliance", status="failed", errors=errors)
        return {
            "compliance_result": {
                "required_disclosures": [],
                "fair_lending_flag": False,
                "audit_trail_complete": False,
                "blocking_violations": [f"compliance_failed: {exc}"],
                "recommendation_override": "MANUAL_REVIEW",
                "checks": [],
                "summary": f"Compliance failed: {exc}",
            },
            "needs_manual_review": True,
            "errors": errors,
            "metrics_summary": metrics.summary(),
            **_stamp_node(state, "compliance", started_at),
            "messages": [("assistant", f"Compliance failed: {exc}")],
        }


def fha_compliance_node(state: UnderwritingState) -> dict[str, Any]:
    """Run FHA-specific pre-compliance checks before standard compliance."""
    started_at = time.perf_counter()
    errors = list(state.get("errors", []))
    metrics = _metrics_from_state(state)
    metrics.start_node("fha_compliance")
    risk = state.get("risk_assessment") or {}
    borrower = (state.get("borrower_package") or {}).get("borrower", {})

    try:
        dti_value = None
        for criterion in risk.get("criteria_scores", []):
            if str(criterion.get("name", "")).upper() == "DTI":
                dti_value = float(criterion.get("value", 0))
                break

        flags: list[str] = []
        if dti_value is not None and dti_value > 50:
            flags.append("FHA DTI guideline exceeded (50%)")

        loan_amount = float(borrower.get("loan_amount", 0) or 0)
        if loan_amount <= 0:
            flags.append("Missing loan amount for FHA checks")

        result = {
            "status": "REVIEW" if flags else "PASS",
            "flags": flags,
            "summary": (
                "FHA-specific compliance checks complete with findings."
                if flags
                else "FHA-specific compliance checks passed."
            ),
        }

        needs_manual_review = bool(state.get("needs_manual_review", False)) or bool(flags)
        metrics.end_node(
            "fha_compliance",
            status="degraded" if flags else "success",
            errors=errors,
        )
        return {
            "fha_compliance_result": result,
            "needs_manual_review": needs_manual_review,
            "errors": errors,
            "metrics_summary": metrics.summary(),
            **_stamp_node(state, "fha_compliance", started_at),
            "messages": [("assistant", result["summary"])],
        }
    except Exception as exc:
        _append_error(
            errors,
            StructuredError.degraded(
                source="fha_compliance_node",
                message="FHA-specific compliance checks failed.",
                exc=exc,
            ),
        )
        metrics.end_node("fha_compliance", status="failed", errors=errors)
        return {
            "fha_compliance_result": {
                "status": "REVIEW",
                "flags": [f"fha_compliance_failed: {exc}"],
                "summary": f"FHA checks failed: {exc}",
            },
            "needs_manual_review": True,
            "errors": errors,
            "metrics_summary": metrics.summary(),
            **_stamp_node(state, "fha_compliance", started_at),
            "messages": [("assistant", f"FHA checks failed: {exc}")],
        }


def fatal_error_node(state: UnderwritingState) -> dict[str, Any]:
    """Consolidate fatal pipeline errors before final decision output."""
    started_at = time.perf_counter()
    errors = list(state.get("errors", []))
    metrics = _metrics_from_state(state)
    metrics.start_node("fatal_error")
    if not errors:
        _append_error(
            errors,
            StructuredError.fatal(
                source="fatal_error_node",
                message="Fatal error node reached without prior error context.",
            ),
        )

    metrics.end_node("fatal_error", status="failed", errors=errors)

    return {
        "fatal_error": True,
        "needs_manual_review": True,
        "errors": errors,
        "metrics_summary": metrics.summary(),
        **_stamp_node(state, "fatal_error", started_at),
        "messages": [
            (
                "assistant",
                "Fatal pipeline error encountered. Routing to final decision with error report.",
            )
        ],
    }


def human_review_node(state: UnderwritingState) -> dict[str, Any]:
    """Pause for human decision and persist response on resume."""
    started_at = time.perf_counter()
    errors = list(state.get("errors", []))
    metrics = _metrics_from_state(state)
    metrics.start_node("human_review")
    risk = state.get("risk_assessment") or {}
    compliance = state.get("compliance_result") or {}
    borrower_package = state.get("borrower_package") or {}

    borrower = borrower_package.get("borrower", {})
    credit = borrower_package.get("credit", {})
    borrower_summary = (
        f"Borrower={borrower.get('name', 'Unknown')}, "
        f"state={borrower.get('property_state', 'unknown')}, "
        f"income={borrower.get('annual_income', 'n/a')}, "
        f"monthly_debt={borrower.get('monthly_debt', 'n/a')}, "
        f"fico={credit.get('fico_score', 'n/a')}"
    )

    risk_score = int(risk.get("overall_score", 0) or 0)
    risk_recommendation = str(risk.get("recommendation", "MANUAL_REVIEW"))

    compliance_summary = (
        f"override={compliance.get('recommendation_override', 'NONE')}, "
        f"audit_trail_complete={compliance.get('audit_trail_complete', False)}, "
        f"blocking_violations={len(compliance.get('blocking_violations', []))}"
    )

    detailed_summary = "\n".join(
        [
            "Manual review required. Please provide final underwriting decision.",
            f"Borrower summary: {borrower_summary}",
            f"Risk assessment: score={risk_score}, recommendation={risk_recommendation}",
            f"Compliance result: {compliance_summary}",
            "Allowed decisions: APPROVE, DENY, APPROVE_WITH_CONDITIONS",
        ]
    )

    request = HumanReviewRequest(
        summary=detailed_summary,
        risk_score=risk_score,
        recommendation=risk_recommendation,
    )

    interrupt_payload = {
        "human_review_request": request.model_dump(),
        "borrower_summary": borrower_summary,
        "risk_assessment": {
            "overall_score": risk_score,
            "recommendation": risk_recommendation,
            "risk_level": risk.get("risk_level"),
            "reasoning": risk.get("reasoning", ""),
        },
        "compliance_result": {
            "recommendation_override": compliance.get("recommendation_override", "NONE"),
            "blocking_violations": compliance.get("blocking_violations", []),
            "audit_trail_complete": compliance.get("audit_trail_complete", False),
            "summary": compliance.get("summary", ""),
        },
        "instructions": (
            "Resume with either a decision string (e.g. 'DENIED' or "
            "'APPROVED with conditions') or a JSON object with keys "
            "decision, conditions, notes."
        ),
    }

    human_input = interrupt(interrupt_payload)

    def _normalize_human_input(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            notes = str(value.get("notes", ""))
            upper_notes = notes.upper()
            needs_more_data = "NEED MORE" in upper_notes or "RECENT CREDIT" in upper_notes
            return {
                "decision": value.get("decision", "DENY"),
                "conditions": value.get("conditions", []),
                "notes": notes,
                "needs_additional_data": needs_more_data,
                "additional_data_request": notes if needs_more_data else None,
            }

        text = str(value or "").strip()
        upper = text.upper()
        if "CONDITION" in upper:
            decision = "APPROVE_WITH_CONDITIONS"
        elif "DENY" in upper:
            decision = "DENY"
        elif "APPROV" in upper:
            decision = "APPROVE"
        else:
            decision = "DENY"

        notes = ""
        if text:
            notes = f"Human raw input: {text}"

        conditions: list[str] = []
        if decision == "APPROVE_WITH_CONDITIONS":
            conditions = ["Final conditions to be documented by underwriter"]

        needs_more_data = "NEED MORE" in upper or "RECENT CREDIT" in upper

        return {
            "decision": decision,
            "conditions": conditions,
            "notes": notes,
            "needs_additional_data": needs_more_data,
            "additional_data_request": text if needs_more_data else None,
        }

    normalized = _normalize_human_input(human_input)

    try:
        response = HumanReviewResponse.model_validate(normalized)
    except ValidationError as exc:
        _append_error(
            errors,
            StructuredError.degraded(
                source="human_review_node",
                message="Human review response validation failed; default decision applied.",
                exc=exc,
            ),
        )
        response = HumanReviewResponse(
            decision="DENY",
            conditions=[],
            notes=f"Invalid human response payload. Defaulted to DENY. Details: {exc}",
        )

    needs_additional_data = bool(normalized.get("needs_additional_data", False))
    additional_data_request = normalized.get("additional_data_request")
    current_iterations = int(state.get("review_iterations", 0) or 0)
    if needs_additional_data:
        current_iterations += 1

    metrics.end_node(
        "human_review",
        status="degraded" if needs_additional_data else "success",
        errors=errors,
    )

    return {
        "human_review_request": request.model_dump(),
        "human_review_response": response.model_dump(),
        "needs_manual_review": bool(needs_additional_data),
        "needs_additional_data": needs_additional_data,
        "additional_data_request": additional_data_request,
        "review_iterations": current_iterations,
        "errors": errors,
        "metrics_summary": metrics.summary(),
        **_stamp_node(state, "human_review", started_at),
        "messages": [
            (
                "assistant",
                (
                    f"Human review completed with decision={response.decision}."
                    if not needs_additional_data
                    else "Human review noted additional data request for audit trail."
                ),
            )
        ],
    }


def final_decision_node(state: UnderwritingState) -> dict[str, Any]:
    """Create a complete, audit-ready underwriting report."""
    started_at = time.perf_counter()
    metrics = _metrics_from_state(state)
    metrics.start_node("final_decision")
    app_id = state.get("app_id", "UNKNOWN")
    borrower_package = state.get("borrower_package")
    document_review = state.get("document_review")
    risk_assessment_raw = state.get("risk_assessment")
    compliance_result = state.get("compliance_result")
    fha_compliance_result = state.get("fha_compliance_result")
    human_review_response = state.get("human_review_response")
    additional_data_request = state.get("additional_data_request")
    review_iterations = int(state.get("review_iterations", 0) or 0)
    errors = state.get("errors", [])
    categorized_errors = categorize_pipeline_errors(list(errors))

    borrower_summary = "Borrower data unavailable"
    if borrower_package:
        borrower = borrower_package.get("borrower", {})
        credit = borrower_package.get("credit", {})
        employment = borrower_package.get("employment", {})
        borrower_summary = (
            f"Borrower: {borrower.get('name', 'Unknown')} | "
            f"Income: ${borrower.get('annual_income', 'n/a')} | "
            f"Debt: ${borrower.get('monthly_debt', 'n/a')}/mo | "
            f"FICO: {credit.get('fico_score', 'n/a')} | "
            f"Employment: {employment.get('years_at_current', 'n/a')} years"
        )

    doc_summary = "Document review skipped"
    if document_review:
        doc_summary = (
            f"Document quality: {document_review.get('document_quality', 'UNKNOWN')} | "
            f"Total docs: {document_review.get('total_documents', 0)} | "
            f"Issues: {document_review.get('total_issues', 0)}"
        )

    risk_block = "Risk assessment unavailable"
    recommendation = "MANUAL_REVIEW"
    if risk_assessment_raw:
        try:
            risk_model = RiskAssessment.model_validate(risk_assessment_raw)
            risk_block = risk_model.format_report()
            recommendation = risk_model.recommendation
        except Exception:
            recommendation = str(risk_assessment_raw.get("recommendation", "MANUAL_REVIEW"))
            risk_block = json.dumps(risk_assessment_raw, indent=2)

    compliance_summary = "Compliance not run"
    if compliance_result:
        compliance_summary = (
            f"override={compliance_result.get('recommendation_override', 'NONE')} | "
            f"audit_trail_complete={compliance_result.get('audit_trail_complete', False)} | "
            f"blocking_violations={len(compliance_result.get('blocking_violations', []))}"
        )

    fha_summary = "Not applicable"
    if fha_compliance_result:
        fha_summary = (
            f"status={fha_compliance_result.get('status', 'UNKNOWN')} | "
            f"flags={json.dumps(fha_compliance_result.get('flags', []))}"
        )

    if state.get("fatal_error"):
        recommendation = "DENY"

    human_section = "Human review not required"
    if human_review_response:
        human_decision = human_review_response.get("decision", "UNKNOWN")
        recommendation = human_decision
        conditions = human_review_response.get("conditions", [])
        notes = human_review_response.get("notes", "")
        human_section = (
            f"decision={human_decision} | "
            f"conditions={json.dumps(conditions)} | "
            f"notes={notes}"
        )

    thread_id = str(state.get("thread_id", ""))
    tool_calls, llm_calls, estimated_cost = _estimate_usage_counts(state)
    circuit_states = {name: breaker.status() for name, breaker in ALL_BREAKERS.items()}
    guardrails_intervened = any("guardrail" in str(err).lower() for err in errors)

    metrics.end_node(
        "final_decision",
        status="success" if not state.get("fatal_error") else "failed",
        llm_calls=0,
        tools_called=[],
        errors=list(errors),
        cost_estimate_usd=estimated_cost,
    )
    metrics_summary = metrics.summary()

    stitched_state = dict(state)
    stitched_state.update(
        {
            "app_id": app_id,
            "total_tool_calls": tool_calls,
            "total_llm_calls": llm_calls,
            "estimated_cost_usd": estimated_cost,
            "computed_borrower_summary": borrower_summary,
            "computed_doc_summary": doc_summary,
            "computed_risk_block": risk_block,
            "computed_compliance_summary": compliance_summary,
            "computed_fha_summary": fha_summary,
            "computed_human_summary": human_section,
            "computed_recommendation": recommendation,
            "additional_data_request": additional_data_request,
            "review_iterations": review_iterations,
            "thread_id": thread_id,
            "error_categories": categorized_errors,
            "circuit_breaker_states": circuit_states,
            "guardrails_intervened": guardrails_intervened,
            "metrics_summary": metrics_summary,
        }
    )

    full_report = format_underwriting_report(stitched_state)

    return {
        "final_decision": full_report,
        "final_report": full_report,
        "total_tool_calls": tool_calls,
        "total_llm_calls": llm_calls,
        "estimated_cost_usd": estimated_cost,
        "error_categories": categorized_errors,
        "circuit_breaker_states": circuit_states,
        "guardrails_intervened": guardrails_intervened,
        "metrics_summary": metrics_summary,
        **_stamp_node(state, "final_decision", started_at),
        "messages": [("assistant", "Final decision report generated.")],
    }
