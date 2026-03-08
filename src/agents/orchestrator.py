"""Orchestrator agent that coordinates loan application evaluation."""

from src.models.loan import LoanApplication
from src.models.loan_decision import LoanDecision


def evaluate_applications(applications: list[LoanApplication]) -> list[LoanDecision]:
    """
    Evaluate a list of loan applications and generate decisions.
    
    Uses list comprehension to filter eligible applications and create
    LoanDecision objects with confidence scores and reasons.
    
    Args:
        applications: List of LoanApplication objects to evaluate
        
    Returns:
        List of LoanDecision objects with outcomes and confidence scores
    """
    decisions = [
        LoanDecision(
            decision=app.is_eligible(),
            confidence=0.85 if app.is_eligible() else 0.75,
            reasons=_build_reasons(app)
        )
        for app in applications
    ]
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
    
    if app.fico_score >= 700:
        reasons.append(f"Good FICO score ({app.fico_score})")
    else:
        reasons.append(f"Low FICO score ({app.fico_score})")
    
    dti = app.calculate_dti()
    if dti < 0.36:
        reasons.append(f"Acceptable DTI ({dti:.2%})")
    else:
        reasons.append(f"High DTI ({dti:.2%})")
    
    if app.loan_amount <= app.annual_income * 0.5:
        reasons.append("Loan amount reasonable relative to income")
    else:
        reasons.append("Loan amount high relative to income")
    
    return reasons
