# src/models/risk.py

from pydantic import BaseModel, Field
from typing import Literal


class CriterionScore(BaseModel):
    """Score for a single underwriting criterion."""
    name: str
    value: float = Field(description="Actual value (e.g., DTI 24.0)")
    threshold: float = Field(description="Maximum/minimum threshold")
    passed: bool
    score: int = Field(ge=0, le=100, description="0=worst, 100=best")
    detail: str


class IndustryContext(BaseModel):
    """Industry risk context from knowledge graph."""
    industry_name: str
    default_rate: float = Field(
        description="Historical default rate for this industry"
    )
    similar_loans_total: int
    similar_loans_defaulted: int
    avg_defaulter_fico: float | None = None
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    context_note: str = Field(
        description="Human-readable summary of industry risk"
    )


class RiskAssessment(BaseModel):
    """
    Complete risk assessment from the Risk Scoring agent.
    
    Combines:
    - Calculation-based criteria (DTI, LTV, FICO)
    - Industry context from knowledge graph
    - Policy compliance from RAG
    - Document verification from Doc Review
    """
    # Overall
    overall_score: int = Field(
        ge=0, le=100,
        description="Composite risk score: 0=highest risk, 100=lowest risk"
    )
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    recommendation: Literal["APPROVE", "DENY", "MANUAL_REVIEW"]
    
    # Individual criteria
    criteria_scores: list[CriterionScore]
    
    # Industry context (from knowledge graph)
    industry_context: IndustryContext | None = None
    
    # Policy compliance (from RAG)
    policy_violations: list[str] = Field(default_factory=list)
    policy_warnings: list[str] = Field(default_factory=list)
    
    # Document quality (from Doc Review)
    document_issues: list[str] = Field(default_factory=list)
    
    # Reasoning
    reasoning: str = Field(
        description="Detailed reasoning for the recommendation, "
                    "suitable for audit trail"
    )
    compensating_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    
    def format_report(self) -> str:
        """Format as underwriting decision report."""
        lines = [
            "=" * 60,
            f"  RISK ASSESSMENT: {self.recommendation}",
            f"  Score: {self.overall_score}/100 | Risk: {self.risk_level}",
            "=" * 60,
            "",
        ]
        
        # Criteria
        lines.append("CRITERIA:")
        for c in self.criteria_scores:
            icon = "\u2705" if c.passed else "\u274c"
            lines.append(
                f"  {icon} {c.name}: {c.value} "
                f"(threshold: {c.threshold}) — Score: {c.score}/100"
            )
        
        # Industry context
        if self.industry_context:
            ic = self.industry_context
            lines.append(f"\nINDUSTRY CONTEXT ({ic.industry_name}):")
            lines.append(f"  Default rate: {ic.default_rate:.1%}")
            lines.append(
                f"  Similar loans: {ic.similar_loans_total} total, "
                f"{ic.similar_loans_defaulted} defaulted"
            )
            lines.append(f"  Risk: {ic.risk_level} — {ic.context_note}")
        
        # Issues
        if self.policy_violations:
            lines.append("\n\u274c POLICY VIOLATIONS:")
            for v in self.policy_violations:
                lines.append(f"  - {v}")
        
        if self.risk_factors:
            lines.append("\n\u26a0\ufe0f RISK FACTORS:")
            for r in self.risk_factors:
                lines.append(f"  - {r}")
        
        if self.compensating_factors:
            lines.append("\n\u2705 COMPENSATING FACTORS:")
            for c in self.compensating_factors:
                lines.append(f"  + {c}")
        
        lines.append(f"\nREASONING:\n  {self.reasoning}")
        lines.append("=" * 60)
        
        return "\n".join(lines)