from pydantic import BaseModel, Field
from typing import Literal


class BorrowerProfile(BaseModel):
    """Basic borrower information."""
    name: str
    ssn_last_four: str = Field(description="Last 4 digits only")
    annual_income: float = Field(gt=0)
    monthly_debt: float = Field(ge=0)
    loan_amount: float = Field(gt=0)
    property_value: float = Field(gt=0)
    property_state: str


class CreditReport(BaseModel):
    """Credit bureau data."""
    fico_score: int = Field(ge=300, le=850)
    delinquencies: int = Field(ge=0)
    open_accounts: int = Field(ge=0)
    credit_history_years: float = Field(ge=0)
    tier: Literal["EXCELLENT", "GOOD", "ACCEPTABLE", "BELOW_MINIMUM"]


class EmploymentRecord(BaseModel):
    """Employment verification data."""
    employer: str
    position: str
    years_at_current: float = Field(ge=0)
    employment_type: Literal["FULL_TIME", "PART_TIME", "SELF_EMPLOYED", "RETIRED"]
    verified: bool


class PolicyContext(BaseModel):
    """Relevant policies retrieved via RAG."""
    applicable_policies: list[str]
    jurisdiction_rules: list[str]
    sources: list[str]


class BorrowerPackage(BaseModel):
    """Complete data package assembled by FetchData agent.
    
    This is what gets passed to the Risk Scoring agent.
    Contains everything needed for underwriting evaluation.
    """
    borrower: BorrowerProfile
    credit: CreditReport
    employment: EmploymentRecord
    policies: PolicyContext
    data_quality: Literal["COMPLETE", "PARTIAL", "INSUFFICIENT"]
    missing_fields: list[str] = Field(default_factory=list)
    fetch_timestamp: str