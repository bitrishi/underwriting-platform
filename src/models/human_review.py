"""Pydantic models for human-in-the-loop underwriting review."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class HumanReviewRequest(BaseModel):
    """Payload shown to a human underwriter during interrupt."""

    summary: str = Field(..., description="Detailed review summary for the human.")
    risk_score: int = Field(..., ge=0, le=100)
    recommendation: str = Field(..., description="Automated recommendation before override.")


class HumanReviewResponse(BaseModel):
    """Human decision captured when the graph resumes."""

    decision: str = Field(..., description="APPROVE, DENY, or APPROVE_WITH_CONDITIONS")
    conditions: list[str] = Field(default_factory=list)
    notes: str = Field(default="")

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: str) -> str:
        normalized = str(value).strip().upper()
        allowed = {"APPROVE", "DENY", "APPROVE_WITH_CONDITIONS"}
        if normalized not in allowed:
            raise ValueError(
                "decision must be one of APPROVE, DENY, APPROVE_WITH_CONDITIONS"
            )
        return normalized
