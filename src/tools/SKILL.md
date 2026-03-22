# Tools SKILL — Underwriting And Policy Tooling

## Overview

The `src/tools/` package provides agent-callable tools for:
- underwriting calculations (`DTI`, `LTV`, `FICO`)
- data-fetch simulation for borrower pipelines
- policy and compliance retrieval via RAG-backed search

All tools are exposed with `@tool` and are designed for deterministic, structured
outputs that agents can reason over.

## Underwriting Calculation Tools

### `calculate_dti`
- Input: `annual_income`, `monthly_debt`
- Output: `dti`, threshold, pass/fail, detail
- Validation: income must be positive

### `calculate_ltv`
- Input: `loan_amount`, `property_value`
- Output: `ltv`, PMI requirement, pass/fail, detail
- Validation: property value must be positive

### `check_fico_eligibility`
- Input: `fico_score`
- Output: minimum threshold, risk tier, eligibility, detail
- Validation: FICO range 300-850

## Fetch Pipeline Tools

### `pull_borrower_data`
- Input: `app_id`
- Output: borrower profile dictionary from simulated application store

### `pull_credit_report`
- Input: `ssn_last_four`
- Output: simulated bureau report including FICO and delinquency summary

### `pull_employment_history`
- Input: `ssn_last_four`
- Output: simulated employment verification record

## Policy And Compliance Retrieval Tools

### `search_lending_policies`
- Inputs:
  - `query: str`
  - `jurisdiction: str` (for example `federal`, `state_texas`)
  - `loan_type: str` (for example `conventional`, `fha`, `va`, `all`)
- Behavior:
  - Runs semantic policy search over FAISS vector store
  - Applies jurisdiction-aware source filtering
  - Incorporates loan type into semantic query context
  - If FAISS index is stale/mismatched, auto-rebuilds from `data/policies`
- Output:
  - formatted document snippets with source citations

### `search_compliance_rules`
- Inputs:
  - `query: str`
  - `regulation_type: str` (for example `TRID`, `RESPA`, `TILA`)
- Behavior:
  - Uses regulation aliases to narrow retrieval focus
  - Returns formatted citations from matching policy/compliance docs

## Knowledge Graph Tools

### Overview

Graph tools expose relationship-aware context that retrieval alone cannot produce.
The backing graph schema links:

- `Borrower -> WORKS_AT -> Company -> IN_INDUSTRY -> Industry`
- `Borrower -> HAS_LOAN -> Loan -> SECURED_BY -> Property -> LOCATED_IN -> State`
- `State -> GOVERNED_BY -> Regulation`

### `get_borrower_risk_context`

- Input: `ssn_last4`
- Output:
  - borrower profile
  - employer and industry risk metadata
  - prior loans and default ratio
  - related properties, states, and regulations

Use case:
- Explain borrower risk with a full entity traversal (not just text matches).

### `find_similar_past_loans`

- Inputs: `industry`, optional `min_fico`, optional `limit`
- Output:
  - matching historical loans
  - outcomes summary (`approved`, `defaulted`, `default_ratio`)

Use case:
- Compare current application to historical outcomes in the same industry.

### `get_state_regulations`

- Input: `state`
- Output:
  - state-specific and federal regulations attached to that state node

Use case:
- Inject jurisdiction-aware rules into compliance and decisioning prompts.

### Cross-Validation Guidance

When using graph tools with document review outputs:

1. Pull borrower risk context by SSN.
2. Compare extracted employment data to graph employer/industry.
3. Compare industry default rate to model confidence/risk tier.
4. Fetch state regulations and cross-check policy constraints.

This creates a multi-source risk picture combining document, graph, and policy data.

## Design Rules

- Keep each tool focused on one responsibility.
- Validate inputs and fail fast for invalid values.
- Return machine-friendly structures for non-RAG calculators.
- For retrieval tools, always include source-oriented output context.

## Testing Guidance

- Unit tests for underwriting calculators: `tests/test_tools.py`
- Integration-style fetch agent + tool wiring tests: `tests/test_fetch_agent.py`
- RAG and retrieval behavior tests: `tests/test_rag.py`, `tests/test_retriever.py`,
  `tests/test_vectorstore.py`
