# Week 1 — Day 5: Structured Output with Pydantic

**Date:** Session 5  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. The reliability problem with raw JSON from LLMs
2. Pydantic BaseModel (Python's Jackson + Bean Validation)
3. Field constraints (ge, le, Literal, min_length)
4. Nested models (CriteriaCheck, ReasoningTrace, LoanDecision)
5. with_structured_output() and json_mode fallback
6. Building a complete structured chain
7. Production error handling

---

## The Problem

```python
# Raw LLM response is a STRING, not typed data
response = llm.invoke(messages)
raw_text = response.content        # "{"decision": "APPROVED"...}"

# Manual parsing is fragile:
data = json.loads(raw_text)        # JSONDecodeError if LLM adds backticks
decision = data["decision"]        # KeyError if LLM misspells field
confidence = data["confidence"]    # Could be string, int, or float
```

Like calling a REST API that returns untyped `Object` instead of a typed POJO.

---

## Pydantic = Jackson + Bean Validation

| Java | Python (Pydantic) |
|------|-------------------|
| `@Data` | `BaseModel` |
| `@NotNull` | `Field(...)` with no default |
| `@Min(0) @Max(1)` | `Field(ge=0, le=1)` |
| `@Size(min=1)` | `Field(min_length=1)` |
| Java `enum` | `Literal["APPROVED", "DENIED"]` |
| `objectMapper.readValue()` | `model.model_validate(data)` |
| `JsonMappingException` | `ValidationError` |
| Nested POJOs | Nested BaseModels |

---

## The Pydantic Models

### CriteriaCheck (nested)

```python
from pydantic import BaseModel, Field

class CriteriaCheck(BaseModel):
    """Result of checking a single underwriting criterion."""
    value: float = Field(description="Actual value")
    threshold: float = Field(description="Threshold to compare against")
    passed: bool = Field(description="Whether value meets threshold")
    detail: str = Field(description="Explanation of check result")
```

### ReasoningTrace (nested)

```python
class ReasoningTrace(BaseModel):
    """Step-by-step reasoning for audit trail."""
    step_1_fico: str = Field(description="FICO evaluation")
    step_2_dti: str = Field(description="DTI calculation")
    step_3_ltv: str = Field(description="LTV evaluation")
    step_4_employment: str = Field(description="Employment assessment")
    step_5_compensating: str = Field(description="Compensating factors")
    step_6_decision: str = Field(description="Final reasoning")
```

### LoanDecision (main)

```python
from typing import Literal

class LoanDecision(BaseModel):
    """Complete underwriting decision with audit trail."""
    decision: Literal["APPROVED", "DENIED", "MANUAL_REVIEW"]
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    criteria_checks: dict[str, CriteriaCheck]
    reasoning_trace: ReasoningTrace
    reasons: list[str] = Field(min_length=1)
```

### LoanApplication (input)

```python
class LoanApplication(BaseModel):
    """Loan application input with auto-calculated metrics."""
    borrower_name: str
    fico_score: int = Field(ge=300, le=850)
    annual_income: float = Field(gt=0)
    monthly_debt: float = Field(ge=0)
    loan_amount: float = Field(gt=0)
    property_value: float = Field(gt=0)
    employment_years: float = Field(ge=0)

    @property
    def dti(self) -> float:
        return (self.monthly_debt * 12) / self.annual_income * 100

    @property
    def ltv(self) -> float:
        return self.loan_amount / self.property_value * 100

    def to_prompt_string(self) -> str:
        return f"""Borrower: {self.borrower_name}
FICO: {self.fico_score}
Annual Income: ${self.annual_income:,.0f}
Monthly Debt: ${self.monthly_debt:,.0f}
Loan Amount: ${self.loan_amount:,.0f}
Property Value: ${self.property_value:,.0f}
Employment: {self.employment_years} years"""
```

---

## with_structured_output()

```python
# For models with function calling (Claude, Nova Pro):
structured_llm = llm.with_structured_output(LoanDecision)
result = structured_llm.invoke(messages)  # returns LoanDecision object

# For models without function calling (Nova Micro):
structured_llm = llm.with_structured_output(
    LoanDecision,
    method="json_mode"    # prompt-based JSON fallback
)
```

**Note:** Nova Micro required manual `json.loads` fallback. Function calling models (Claude, Nova Pro) work natively with `with_structured_output()`.

---

## Production Chain Pattern

```python
def create_underwriter_chain():
    """Create structured underwriting chain."""
    llm = create_llm(temperature=0)
    structured_llm = llm.with_structured_output(LoanDecision)
    system_prompt = load_prompt("underwriter")

    def evaluate(application: LoanApplication) -> LoanDecision:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=application.to_prompt_string()),
        ]
        return structured_llm.invoke(messages)

    return evaluate
```

---

## Error Handling

```python
from pydantic import ValidationError

def evaluate_safe(app: LoanApplication) -> LoanDecision | None:
    try:
        return evaluate(app)
    except ValidationError as e:
        logger.error(f"Output validation failed: {e.errors()}")
        return None
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        return None
```

---

## Assignments (Completed ✅)

- [x] Task 1: Full LoanDecision Pydantic model with nested models
- [x] Task 2: LoanApplication Pydantic model with calculated properties
- [x] Task 3: Underwriter chain with structured output
- [x] Task 4: End-to-end test (3 applications) — used json.loads fallback
- [x] Task 5: Validation tests (good data + rejection of bad data)
- [x] Task 6: Models SKILL.md documentation