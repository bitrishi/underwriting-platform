# Underwriting Tools and Callbacks Documentation

## Tool Design Rules

### Single Responsibility Principle
Each tool performs exactly one underwriting calculation or check:
- `calculate_dti`: Debt-to-income ratio calculation only
- `calculate_ltv`: Loan-to-value ratio calculation only  
- `check_fico_eligibility`: FICO score eligibility assessment only

### Structured Returns
All tools return a consistent dictionary structure with:
- `pass` or `eligible`: Boolean indicating threshold compliance
- `threshold`: Numeric threshold value used
- `detail`: Human-readable explanation string
- Additional calculation-specific fields (e.g., `dti`, `ltv`, `tier`)

### Docstring Requirements
Every tool must include:
- Purpose description with "Use this tool to..." guidance
- Args section with type hints and descriptions
- Returns section describing the output structure
- Input validation error descriptions

## Underwriting Tools

### calculate_dti
**Purpose**: Calculate the debt-to-income ratio for underwriting to evaluate borrower's debt burden against their income.

**Input Schema**:
- `annual_income: float` - Borrower's annual income in dollars (must be positive)
- `monthly_debt: float` - Borrower's total monthly debt payments in dollars

**Output Schema**:
```python
{
    "dti": float,        # Calculated DTI percentage
    "threshold": 43,     # DTI threshold (43%)
    "pass": bool,        # True if DTI <= 43%
    "detail": str        # Formatted explanation (e.g., "DTI 35.2% <= 43% threshold")
}
```

### calculate_ltv
**Purpose**: Calculate Loan-to-Value ratio for mortgage underwriting to assess how much of the property value is being financed.

**Input Schema**:
- `loan_amount: float` - Requested loan amount in USD
- `property_value: float` - Appraised property value in USD (must be positive)

**Output Schema**:
```python
{
    "ltv": float,        # Calculated LTV percentage (rounded to 2 decimals)
    "threshold": 80.0,   # PMI requirement threshold (80%)
    "requires_pmi": bool,# True if LTV > 80%
    "pass": bool,        # True if LTV <= 95%
    "detail": str        # Formatted explanation (e.g., "LTV 75.0% — No PMI")
}
```

### check_fico_eligibility
**Purpose**: Check if a FICO score meets minimum underwriting requirements to evaluate creditworthiness against lending thresholds.

**Input Schema**:
- `fico_score: int` - Borrower's FICO credit score (300-850 range)

**Output Schema**:
```python
{
    "fico": int,              # Input FICO score
    "minimum_threshold": 680, # Minimum eligible score
    "tier": str,              # Risk tier ("EXCELLENT", "GOOD", "ACCEPTABLE", "BELOW_MINIMUM")
    "eligible": bool,         # True if score >= 680
    "detail": str             # Formatted explanation (e.g., "FICO 750 — EXCELLENT")
}
```

## Callback Tracer

### UnderwritingTracer
**Purpose**: Callback handler that traces tool and LLM activity for underwriting runs, providing audit trails and debugging information.

**Tracked Events**:
- `tool_start`: When a tool execution begins (includes tool name and input)
- `tool_end`: When a tool execution completes (includes output)
- `llm_start`: When LLM inference begins (includes prompts)
- `agent_finish`: When agent execution completes (includes final output)

**Event Structure**:
Each trace entry includes:
- `event`: Event type string
- `timestamp`: ISO format timestamp
- Additional event-specific fields (input, output, prompts, etc.)

**Methods**:
- `get_trace_summary()`: Returns human-readable timeline of all events with numbered entries and formatted details

**Usage**: Instantiate `UnderwritingTracer()`, pass to agent execution, call `get_trace_summary()` after completion for audit logs.