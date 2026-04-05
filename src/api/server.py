"""FastAPI server for underwriting evaluations."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import logging
import os
import time
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from src.api.evaluator import derive_recommendation, evaluate_application as run_underwriting_evaluation
from src.api.history_store import EvaluationHistoryStore
from src.api.job_store import EvaluationJobStore
from src.chains.underwriter_chain import UnderwriterChain
from src.models.application import LoanApplication
from src.models.decision import LoanDecision


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


class BorrowerData(BaseModel):
    """Normalized borrower inputs accepted by the API."""

    fico: int = Field(..., ge=300, le=850)
    dti: float = Field(..., gt=0, description="DTI as decimal (0.42) or percent (42)")
    income: float = Field(..., gt=0, description="Annual income in USD")
    borrower_name: str | None = Field(default=None)
    loan_amount: float = Field(default=250000, gt=0)
    property_value: float | None = Field(default=None, gt=0)
    employment_years: float = Field(default=2.0, ge=0)

    @field_validator("dti")
    @classmethod
    def normalize_dti(cls, value: float) -> float:
        if value > 100:
            raise ValueError("dti must be expressed as a decimal <= 1 or a percent <= 100")
        return value / 100 if value > 1 else value

    def to_loan_application(self, application_id: str) -> LoanApplication:
        annual_income = float(self.income)
        monthly_income = annual_income / 12
        monthly_debt = round(monthly_income * self.dti, 2)
        loan_amount = float(self.loan_amount)
        property_value = float(self.property_value or round(loan_amount / 0.8, 2))

        return LoanApplication(
            borrower_name=self.borrower_name or f"Borrower {application_id}",
            fico_score=self.fico,
            annual_income=annual_income,
            monthly_debt=monthly_debt,
            loan_amount=loan_amount,
            property_value=property_value,
            employment_years=float(self.employment_years),
        )


class EvaluationRequest(BaseModel):
    application_id: str = Field(..., min_length=1)
    borrower_data: BorrowerData


class BatchEvaluationRequest(BaseModel):
    applications: list[EvaluationRequest] = Field(..., min_length=1)


class AgentReport(BaseModel):
    agent_name: str
    status: str
    summary: str
    details: dict[str, str | int | float | bool]


class AuditTrailEvent(BaseModel):
    step: str
    status: str
    timestamp: str
    detail: str


class EvaluationResult(BaseModel):
    application_id: str
    evaluated_at: str
    borrower_data: BorrowerData
    decision: LoanDecision
    recommendation: str
    risk_score: int = Field(..., ge=0, le=100)
    agent_reports: list[AgentReport]
    audit_trail: list[AuditTrailEvent]
    human_decision_status: str


class EvaluateAcceptedResponse(BaseModel):
    job_id: str
    application_id: str
    status: str
    status_url: str
    result_url: str


class JobStatusResponse(BaseModel):
    job_id: str
    application_id: str
    status: str
    current_agent: str | None
    progress_pct: int = Field(..., ge=0, le=100)
    created_at: str
    updated_at: str
    agent_progress: dict[str, str]
    error: str | None = None


class BatchEvaluationItem(BaseModel):
    application_id: str
    status: str
    evaluated_at: str | None = None
    borrower_data: BorrowerData | None = None
    decision: LoanDecision | None = None
    risk_score: int | None = None
    agent_reports: list[AgentReport] | None = None
    audit_trail: list[AuditTrailEvent] | None = None
    human_decision_status: str | None = None
    error: str | None = None


class BatchEvaluationResponse(BaseModel):
    success_count: int
    failure_count: int
    results: list[BatchEvaluationItem]


class EvaluationHistoryResponse(BaseModel):
    application_id: str
    evaluations: list[EvaluationResult]


app = FastAPI(
    title="Underwriting Evaluation API",
    version="1.0.0",
    description="Batch and history API for underwriting model evaluations.",
)


@lru_cache
def get_chain() -> UnderwriterChain:
    return UnderwriterChain()


@lru_cache
def get_history_store() -> EvaluationHistoryStore:
    return EvaluationHistoryStore(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))


@lru_cache
def get_job_store() -> EvaluationJobStore:
    return EvaluationJobStore()


def _compute_risk_score(decision: LoanDecision) -> int:
    base = {
        "LOW": 25,
        "MEDIUM": 55,
        "HIGH": 82,
    }[decision.risk_level]

    if decision.decision == "CONDITIONAL_APPROVAL":
        base += 5
    elif decision.decision == "DECLINE":
        base += 10

    uncertainty_penalty = round((1 - float(decision.confidence)) * 10)
    return max(0, min(100, base + uncertainty_penalty))


def _build_agent_reports(
    request: EvaluationRequest,
    application: LoanApplication,
    decision: LoanDecision,
    risk_score: int,
) -> list[AgentReport]:
    borrower = request.borrower_data
    return [
        AgentReport(
            agent_name="FetchData",
            status="completed",
            summary="Borrower and loan fields normalized for underwriting.",
            details={
                "fico": borrower.fico,
                "annual_income": borrower.income,
                "loan_amount": borrower.loan_amount,
                "employment_years": borrower.employment_years,
            },
        ),
        AgentReport(
            agent_name="DocReview",
            status="completed",
            summary="Document review placeholder completed with structured API intake only.",
            details={
                "document_count": 0,
                "note": "No uploaded documents were included in this API flow.",
            },
        ),
        AgentReport(
            agent_name="RiskScoring",
            status="completed",
            summary=f"Computed DTI/LTV and assigned risk score {risk_score}.",
            details={
                "dti": round(application.dti * 100, 2),
                "ltv": round(application.ltv * 100, 2),
                "risk_level": decision.risk_level,
                "confidence": round(float(decision.confidence), 4),
            },
        ),
        AgentReport(
            agent_name="Compliance",
            status="completed",
            summary="Final decision checked for conditions and auditability.",
            details={
                "decision": decision.decision,
                "conditions_count": len(decision.conditions or []),
                "reason_count": len(decision.reasons),
            },
        ),
    ]


def _build_audit_trail(
    request: EvaluationRequest,
    decision: LoanDecision,
    evaluated_at: str,
    risk_score: int,
) -> list[AuditTrailEvent]:
    return [
        AuditTrailEvent(
            step="submission_received",
            status="completed",
            timestamp=evaluated_at,
            detail=f"Received application {request.application_id} with normalized borrower payload.",
        ),
        AuditTrailEvent(
            step="fetch_data",
            status="completed",
            timestamp=evaluated_at,
            detail="Borrower financial fields validated and converted into underwriting input schema.",
        ),
        AuditTrailEvent(
            step="risk_scoring",
            status="completed",
            timestamp=evaluated_at,
            detail=f"Decision {decision.decision} produced with derived risk score {risk_score}.",
        ),
        AuditTrailEvent(
            step="compliance_review",
            status="completed",
            timestamp=evaluated_at,
            detail="Output packaged with reasons, conditions, and audit trail for human review.",
        ),
    ]


def _build_record(request: EvaluationRequest, decision: LoanDecision, evaluated_at: str) -> dict[str, object]:
    application = request.borrower_data.to_loan_application(request.application_id)
    recommendation = derive_recommendation(application)
    risk_score = _compute_risk_score(decision)
    agent_reports = _build_agent_reports(request, application, decision, risk_score)
    audit_trail = _build_audit_trail(request, decision, evaluated_at, risk_score)

    return {
        "application_id": request.application_id,
        "evaluated_at": evaluated_at,
        "borrower_data": request.borrower_data.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
        "recommendation": recommendation,
        "risk_score": risk_score,
        "agent_reports": [report.model_dump(mode="json") for report in agent_reports],
        "audit_trail": [event.model_dump(mode="json") for event in audit_trail],
        "human_decision_status": "REQUIRED" if recommendation == "MANUAL_REVIEW" else "PENDING",
    }


async def _evaluate_application(
    request: EvaluationRequest,
    chain: UnderwriterChain,
    history_store: EvaluationHistoryStore,
) -> EvaluationResult:
    application = request.borrower_data.to_loan_application(request.application_id)
    decision = await run_in_threadpool(chain.evaluate_safe, application)

    if decision is None:
        raise RuntimeError("Evaluation failed in underwriting chain.")

    evaluated_at = datetime.now(timezone.utc).isoformat()
    record = _build_record(request, decision, evaluated_at)
    await run_in_threadpool(history_store.append, request.application_id, record)
    return EvaluationResult.model_validate(record)


def _run_evaluation_job(
    job_id: str,
    request: EvaluationRequest,
    chain: UnderwriterChain,
    history_store: EvaluationHistoryStore,
    job_store: EvaluationJobStore,
) -> None:
    agent_order = ["FetchData", "DocReview", "RiskScoring", "Compliance"]
    delay_s = float(os.environ.get("SIMULATED_AGENT_DELAY_S", "0.10"))

    try:
        for index, agent_name in enumerate(agent_order, start=1):
            snapshot = job_store.get_job(job_id)
            if snapshot is None:
                return

            agent_progress = snapshot["agent_progress"]
            for prior_index, prior_agent in enumerate(agent_order, start=1):
                if prior_index < index:
                    agent_progress[prior_agent] = "COMPLETED"
                elif prior_index == index:
                    agent_progress[prior_agent] = "RUNNING"
                else:
                    agent_progress[prior_agent] = "PENDING"

            job_store.update_job(
                job_id,
                status="RUNNING",
                current_agent=agent_name,
                progress_pct=int(((index - 1) / len(agent_order)) * 100),
                agent_progress=agent_progress,
            )
            if delay_s > 0:
                time.sleep(delay_s)

        application = request.borrower_data.to_loan_application(request.application_id)
        decision = run_underwriting_evaluation(chain, application)

        evaluated_at = datetime.now(timezone.utc).isoformat()
        record = _build_record(request, decision, evaluated_at)
        history_store.append(request.application_id, record)
        job_store.update_job(
            job_id,
            status="COMPLETE",
            current_agent=None,
            progress_pct=100,
            agent_progress={agent: "COMPLETED" for agent in agent_order},
            result=record,
        )
    except Exception as exc:
        snapshot = job_store.get_job(job_id)
        agent_progress = snapshot["agent_progress"] if snapshot else {}
        job_store.update_job(
            job_id,
            status="FAILED",
            error=str(exc),
            current_agent=None,
            progress_pct=100,
            agent_progress=agent_progress,
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/evaluate", response_model=EvaluateAcceptedResponse, status_code=202)
async def evaluate_application(
    request: EvaluationRequest,
    background_tasks: BackgroundTasks,
    chain: UnderwriterChain = Depends(get_chain),
    history_store: EvaluationHistoryStore = Depends(get_history_store),
    job_store: EvaluationJobStore = Depends(get_job_store),
) -> EvaluateAcceptedResponse:
    job_id = str(uuid4())
    job_store.create_job(job_id, request.application_id)
    background_tasks.add_task(_run_evaluation_job, job_id, request, chain, history_store, job_store)
    return EvaluateAcceptedResponse(
        job_id=job_id,
        application_id=request.application_id,
        status="QUEUED",
        status_url=f"/status?job_id={job_id}",
        result_url=f"/result?job_id={job_id}",
    )


@app.get("/status", response_model=JobStatusResponse)
async def get_status(
    job_id: str = Query(..., min_length=1),
    job_store: EvaluationJobStore = Depends(get_job_store),
) -> JobStatusResponse:
    record = await run_in_threadpool(job_store.get_job, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    return JobStatusResponse.model_validate(record)


@app.get("/result")
async def get_result(
    job_id: str = Query(..., min_length=1),
    job_store: EvaluationJobStore = Depends(get_job_store),
) -> dict[str, object]:
    record = await run_in_threadpool(job_store.get_job, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")

    if record["status"] == "FAILED":
        raise HTTPException(status_code=500, detail=record.get("error") or "Evaluation job failed.")

    if record["status"] != "COMPLETE" or not record.get("result"):
        raise HTTPException(status_code=202, detail="Evaluation still in progress.")

    return {
        "job_id": job_id,
        "status": record["status"],
        "result": record["result"],
    }


@app.post("/evaluate/batch", response_model=BatchEvaluationResponse)
async def evaluate_batch(
    request: BatchEvaluationRequest,
    chain: UnderwriterChain = Depends(get_chain),
    history_store: EvaluationHistoryStore = Depends(get_history_store),
) -> BatchEvaluationResponse:
    results: list[BatchEvaluationItem] = []
    success_count = 0

    for item in request.applications:
        try:
            evaluation = await _evaluate_application(item, chain, history_store)
            results.append(
                BatchEvaluationItem(
                    application_id=item.application_id,
                    status="success",
                    evaluated_at=evaluation.evaluated_at,
                    borrower_data=evaluation.borrower_data,
                    decision=evaluation.decision,
                    risk_score=evaluation.risk_score,
                    agent_reports=evaluation.agent_reports,
                    audit_trail=evaluation.audit_trail,
                    human_decision_status=evaluation.human_decision_status,
                )
            )
            success_count += 1
        except RuntimeError as exc:
            logger.error("Batch evaluation failed for %s: %s", item.application_id, exc)
            results.append(
                BatchEvaluationItem(
                    application_id=item.application_id,
                    status="error",
                    borrower_data=item.borrower_data,
                    error=str(exc),
                )
            )

    return BatchEvaluationResponse(
        success_count=success_count,
        failure_count=len(results) - success_count,
        results=results,
    )


@app.get("/evaluate/history", response_model=EvaluationHistoryResponse)
async def get_evaluation_history(
    application_id: str = Query(..., min_length=1),
    history_store: EvaluationHistoryStore = Depends(get_history_store),
) -> EvaluationHistoryResponse:
    history = await run_in_threadpool(history_store.get_history, application_id)
    evaluations = [EvaluationResult.model_validate(item) for item in history]
    return EvaluationHistoryResponse(application_id=application_id, evaluations=evaluations)