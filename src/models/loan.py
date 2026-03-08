"""Loan application models."""

from src.utils.decorators import log_call


class LoanApplication:
    """Represents a loan application with borrower and financial information."""
    
    borrower_name: str
    loan_amount: float
    fico_score: int
    monthly_debt: float
    annual_income: float

    def __init__(
        self,
        borrower_name: str,
        loan_amount: float,
        fico_score: int,
        monthly_debt: float,
        annual_income: float,
    ) -> None:
        """Initialize a loan application."""
        self.borrower_name = borrower_name
        self.loan_amount = loan_amount
        self.fico_score = fico_score
        self.monthly_debt = monthly_debt
        self.annual_income = annual_income

    @log_call
    def calculate_dti(self) -> float:
        """Calculate Debt-to-Income ratio."""
        if self.annual_income == 0:
            return float('inf')  # Avoid division by zero
        monthly_income = self.annual_income / 12
        dti = self.monthly_debt / monthly_income
        return dti
    
    def is_eligible(self) -> bool:
        """Check if applicant meets basic eligibility criteria."""
        dti = self.calculate_dti()
        if self.fico_score >= 700 and dti < 0.36:
            return True
        return False
    