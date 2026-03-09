"""Pydantic representations for underwriting decisions and related artifacts.

This module defines a production-grade ``LoanDecision`` model with nested
sub-models for criterion checks and reasoning traces.  Every field includes a
``Field()`` description and constraints to enforce valid output from LLM
prompts or internal logic.
"""

from __future__ import annotations

from typing import List, Optional, Literal

from pydantic import BaseModel, Field, confloat, ConfigDict


class CriteriaCheck(BaseModel):
    """Boolean result for a single eligibility criterion.

    Attributes:
        name: Human-readable identifier for the rule or metric checked.
        passed: ``True`` if the application satisfied the criterion, otherwise
            ``False``.
    """

    name: str = Field(
        ..., description="Name of the criterion that was evaluated"
    )
    passed: bool = Field(
        ..., description="Whether the application satisfied the named criterion"
    )


class ReasoningTrace(BaseModel):
    """Structured record of the step-by-step reasoning produced by an LLM.

    Attributes:
        steps: Ordered list of individual reasoning statements.  This model
            is consumed by the prompt-testing utility to display the chain-of-
            thought produced by the underwriter prompt.
    """

    steps: List[str] = Field(
        ...,
        min_length=1,
        description="Sequential reasoning steps leading to the decision",
    )


class LoanDecision(BaseModel):
    """Comprehensive underwriting decision returned by the system.

    This model is the canonical structured response for the orchestrator
    prompt and for downstream agents that consume underwriting results.
    All fields are documented with constraints so that validators and tests
    can automatically verify LLM output.
    """

    decision: Literal["APPROVED", "CONDITIONAL_APPROVAL", "DECLINE"] = Field(
        ..., description="Final underwriting decision as one of the allowed values"
    )

    confidence: confloat(ge=0.0, le=1.0) = Field(
        ..., description="Model confidence score; 0.0 &le; confidence &le; 1.0"
    )

    risk_level: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ..., description="Qualitative risk category assigned to the application"
    )

    reasons: List[str] = Field(
        ..., min_length=1, description="List of textual reasons supporting the decision"
    )

    conditions: Optional[List[str]] = Field(
        None,
        description="Optional list of conditions required for conditional approvals",
    )

    criteria: Optional[List[CriteriaCheck]] = Field(
        None,
        description="Optional detailed criterion-by-criterion pass/fail results",
    )

    reasoning_trace: Optional[ReasoningTrace] = Field(
        None,
        description="Optional chain-of-thought produced by the LLM for auditing",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "decision": "APPROVED",
                "confidence": 0.92,
                "risk_level": "LOW",
                "reasons": [
                    "FICO score is excellent",
                    "DTI below threshold",
                ],
                "conditions": None,
                "criteria": [
                    {"name": "fico_check", "passed": True},
                    {"name": "dti_check", "passed": True},
                ],
                "reasoning_trace": {"steps": [
                    "Reviewed borrower profile",
                    "Calculated DTI and compared to limit",
                    "Prepared final recommendation"
                ]},
            }
        }
    )