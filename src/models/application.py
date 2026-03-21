"""Pydantic model representing a loan application.

This replaces the earlier Day 1 dataclass and provides validation on each field.
Computation helpers (DTI, LTV) and a formatter for generating human-readable
prompts are included as methods/properties.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, confloat


class LoanApplication(BaseModel):
    """Incoming borrower application data used throughout the underwriting flow.

    Attributes:
        borrower_name: Full name of the loan applicant.
        fico_score: FICO credit score (300-850).
        annual_income: Gross annual income in USD; must be positive.
        monthly_debt: Total recurring monthly debt payments (>=0).
        loan_amount: Requested loan principal (must be >0).
        property_value: Appraised value of the property (must be >0).
        employment_years: Years the borrower has been employed at current job.
    """

    borrower_name: str = Field(..., description="Applicant's full name")
    fico_score: int = Field(
        ..., ge=300, le=850, description="FICO score in the 300-850 range"
    )
    annual_income: confloat(gt=0) = Field(..., description="Gross annual income")
    monthly_debt: confloat(ge=0) = Field(..., description="Total monthly debt payments")
    loan_amount: confloat(gt=0) = Field(..., description="Requested loan amount")
    property_value: confloat(gt=0) = Field(..., description="Appraised property value")
    employment_years: confloat(ge=0) = Field(..., description="Years at current employment")

    def is_eligible(self) -> bool:
        """Eligibility based on core underwriting criteria.

        Existing unit tests and business logic currently require:
        * FICO score at least 700
        * Debt-to-income ratio below 0.36
        """
        return self.fico_score >= 700 and self.dti < 0.36

    @property
    def dti(self) -> float:
        """Debt-to-income ratio computed as monthly_debt / (annual_income/12)."""
        monthly_income = self.annual_income / 12
        return self.monthly_debt / monthly_income if monthly_income > 0 else 0.0

    @property
    def ltv(self) -> float:
        """Loan-to-value ratio loan_amount / property_value."""
        return self.loan_amount / self.property_value if self.property_value > 0 else 0.0

    def to_prompt_string(self) -> str:
        """Format the application into a multi-line string suitable for LLM prompts."""
        return (
            f"Borrower: {self.borrower_name}\n"
            f"FICO Score: {self.fico_score}\n"
            f"Annual Income: ${self.annual_income:,.0f}\n"
            f"Monthly Debt: ${self.monthly_debt:,.0f}\n"
            f"Debt-to-Income Ratio: {self.dti:.2%}\n"
            f"Requested Loan Amount: ${self.loan_amount:,.0f}\n"
            f"Property Value: ${self.property_value:,.0f}\n"
            f"Loan-to-Value Ratio: {self.ltv:.2%}\n"
            f"Employment Years: {self.employment_years}\n"
        )
