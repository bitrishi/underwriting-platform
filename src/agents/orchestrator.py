"""Orchestrator agent that coordinates loan application evaluation."""

from src.models.application import LoanApplication
from src.models.decision import LoanDecision  # Pydantic model replaces legacy dataclass


def evaluate_applications(applications: list[LoanApplication]) -> list[LoanDecision]:
    """Evaluate a batch of loan applications.

    This function now returns the **Pydantic :class:`LoanDecision` model**
    (see :mod:`src.models.decision`) instead of the old dataclass.  The
    decision logic remains simple for now but includes additional
    metadata fields needed by downstream agents.

    Args:
        applications: List of LoanApplication objects to evaluate

    Returns:
        List of LoanDecision models, each populated with decision, confidence,
        risk_level and explanatory reasons.
    """
    decisions: list[LoanDecision] = []

    for app in applications:
        eligible = app.is_eligible()
        # map boolean eligibility to decision literal
        final_decision = "APPROVED" if eligible else "DECLINE"
        confidence = 0.85 if eligible else 0.75
        # simple risk mapping; could be replaced with a more nuanced
        # calculation in the future
        risk_level = "LOW" if eligible else "HIGH"

        decisions.append(
            LoanDecision(
                decision=final_decision,
                confidence=confidence,
                risk_level=risk_level,
                reasons=_build_reasons(app),
            )
        )

    return decisions


def _build_reasons(app: LoanApplication) -> list[str]:
    """
    Generate evaluation reasons for a loan application.
    
    Args:
        app: LoanApplication to evaluate
        
    Returns:
        List of reason strings explaining the decision factors
    """
    reasons = []
    
    # FICO evaluation
    if app.fico_score >= 700:
        reasons.append(f"Good FICO score ({app.fico_score})")
    else:
        reasons.append(f"Low FICO score ({app.fico_score})")

    # Debt-to-income evaluation uses the property provided by Pydantic model
    dti = app.dti
    if dti < 0.36:
        reasons.append(f"Acceptable DTI ({dti:.2%})")
    else:
        reasons.append(f"High DTI ({dti:.2%})")
    
    if app.loan_amount <= app.annual_income * 0.5:
        reasons.append("Loan amount reasonable relative to income")
    else:
        reasons.append("Loan amount high relative to income")
    
    return reasons
