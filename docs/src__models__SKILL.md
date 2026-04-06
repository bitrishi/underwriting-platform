# Models Documentation

This directory contains the core data models for the underwriting platform, implemented using Pydantic v2 for robust validation and type safety.

## Overview

The models follow a **nested composition pattern** where complex objects are built from simpler, validated components. This ensures data integrity throughout the underwriting pipeline.

## Pydantic Models

### LoanApplication

**Purpose**: Represents borrower application data used throughout the underwriting flow.

**Location**: `src/models/application.py`

**Fields**:
- `borrower_name: str` - Applicant's full name
- `fico_score: int` - FICO score (300-850 range)
- `annual_income: confloat(gt=0)` - Gross annual income
- `monthly_debt: confloat(ge=0)` - Total monthly debt payments
- `loan_amount: confloat(gt=0)` - Requested loan principal
- `property_value: confloat(gt=0)` - Appraised property value
- `employment_years: confloat(ge=0)` - Years at current employment

**Validation Rules**:
- All monetary values must be positive
- FICO score constrained to 300-850
- Employment years cannot be negative

**Computed Properties**:
- `dti: float` - Debt-to-Income ratio (monthly_debt / (annual_income/12))
- `ltv: float` - Loan-to-Value ratio (loan_amount / property_value)

**Methods**:
- `is_eligible() -> bool` - Eligibility check (FICO >= 700 and DTI < 0.36)
- `to_prompt_string() -> str` - Formats application for LLM prompts

### CriteriaCheck

**Purpose**: Boolean result for a single eligibility criterion.

**Location**: `src/models/decision.py`

**Fields**:
- `name: str` - Human-readable identifier for the rule
- `passed: bool` - Whether the application satisfied the criterion

### ReasoningTrace

**Purpose**: Structured record of LLM reasoning steps.

**Location**: `src/models/decision.py`

**Fields**:
- `steps: List[str]` - Ordered reasoning steps (minimum 1 step)

### LoanDecision

**Purpose**: Comprehensive underwriting decision with structured output.

**Location**: `src/models/decision.py`

**Fields**:
- `decision: Literal["APPROVED", "CONDITIONAL_APPROVAL", "DECLINE"]` - Final decision
- `confidence: confloat(ge=0.0, le=1.0)` - Model confidence score
- `risk_level: Literal["LOW", "MEDIUM", "HIGH"]` - Qualitative risk category
- `reasons: List[str]` - Explanatory reasons (minimum 1)
- `conditions: Optional[List[str]]` - Conditions for conditional approvals
- `criteria: Optional[List[CriteriaCheck]]` - Detailed criterion results
- `reasoning_trace: Optional[ReasoningTrace]` - LLM reasoning steps

## Nested Model Pattern

The models use **composition** to build complex structures from simpler components:

```
LoanDecision
├── reasons: List[str]
├── conditions: Optional[List[str]]
├── criteria: Optional[List[CriteriaCheck]]
│   └── CriteriaCheck
│       ├── name: str
│       └── passed: bool
└── reasoning_trace: Optional[ReasoningTrace]
    └── ReasoningTrace
        └── steps: List[str]
```

This pattern provides:
- **Modular validation**: Each component validates independently
- **Flexible composition**: Optional fields allow varying levels of detail
- **Type safety**: Nested models maintain strong typing throughout
- **JSON compatibility**: Automatic serialization for LLM interactions

## Usage Examples

### Creating Valid Instances

```python
from src.models.application import LoanApplication
from src.models.decision import LoanDecision, CriteriaCheck, ReasoningTrace

# Create a loan application
app = LoanApplication(
    borrower_name="John Doe",
    loan_amount=300000,
    fico_score=780,
    monthly_debt=1500,
    annual_income=120000,
    property_value=400000,
    employment_years=5,
)

print(f"DTI: {app.dti:.2%}")  # DTI: 15.00%
print(f"LTV: {app.ltv:.2%}")  # LTV: 75.00%
print(f"Eligible: {app.is_eligible()}")  # Eligible: True

# Create a decision with nested models
decision = LoanDecision(
    decision="APPROVED",
    confidence=0.92,
    risk_level="LOW",
    reasons=[
        "Excellent FICO score",
        "DTI below threshold",
        "Stable employment"
    ],
    criteria=[
        CriteriaCheck(name="fico_check", passed=True),
        CriteriaCheck(name="dti_check", passed=True),
        CriteriaCheck(name="employment_check", passed=True),
    ],
    reasoning_trace=ReasoningTrace(steps=[
        "Reviewed borrower profile",
        "Calculated DTI and compared to limit",
        "Prepared final recommendation"
    ])
)
```

### Validation and Error Handling

```python
from pydantic import ValidationError

# Invalid FICO score
try:
    invalid_app = LoanApplication(
        borrower_name="Bad Credit",
        loan_amount=200000,
        fico_score=900,  # Invalid: > 850
        monthly_debt=2000,
        annual_income=80000,
        property_value=250000,
        employment_years=2,
    )
except ValidationError as e:
    print(f"Validation error: {e}")

# Invalid confidence
try:
    invalid_decision = LoanDecision(
        decision="APPROVED",
        confidence=1.5,  # Invalid: > 1.0
        risk_level="LOW",
        reasons=["Good credit"]
    )
except ValidationError as e:
    print(f"Validation error: {e}")

# Empty reasons (invalid)
try:
    invalid_decision = LoanDecision(
        decision="DECLINE",
        confidence=0.3,
        risk_level="HIGH",
        reasons=[]  # Invalid: min_length=1
    )
except ValidationError as e:
    print(f"Validation error: {e}")
```

### JSON Serialization

```python
import json

# Models serialize to JSON automatically
decision_dict = decision.model_dump()
print(json.dumps(decision_dict, indent=2))

# Create from JSON
decision_from_json = LoanDecision.model_validate_json(json_str)
```

## Migration from Legacy Models

The platform previously used dataclasses in `loan.py` and `loan_decision.py`. The Pydantic models provide:

- **Runtime validation**: Catches invalid data at creation time
- **Type hints**: Better IDE support and static analysis
- **JSON schema**: Automatic API documentation
- **Field constraints**: Enforces business rules
- **Nested validation**: Complex object validation

## Testing

Comprehensive tests in `tests/test_decision.py` cover:
- Valid instance creation
- Invalid input rejection
- Property calculations
- Prompt string formatting
- Nested model validation

Run tests with: `pytest tests/test_decision.py`