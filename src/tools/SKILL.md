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

## MCP Integration Guidance (Week 5)

Use MCP for tools that are shared across teams or backed by external systems,
and keep deterministic math/validation local as `@tool`.

Current first MCP extraction:
- `search_lending_policies` via `src/mcp/policy_server.py`

Validation paths:
- Protocol roundtrip and server registration: `tests/test_mcp_policy_server.py`
- Agent-side MCP client flow: `src/exercises/week5_day1_mcp.py`

Decision rule:
- Keep local: low-latency deterministic calculators and simple compliance checks.
- Move to MCP: policy search, external data fetchers, graph-backed shared context.

## Textract Hybrid Extraction (Week 5 Day 4)

Use a hybrid route for underwriting document extraction:

- Standard forms (`W2`, `1040`, `paystub`) on image/PDF inputs:
  - Primary: Textract OCR + key-value mapping
  - Fallback: local text/vision parser
- Plain text files:
  - Primary: deterministic regex extraction
- Handwritten or irregular documents:
  - Primary: vision fallback

New modules:

- `src/tools/textract_tools.py`
  - `detect_document_text(document_path)`
  - Returns `raw_text`, per-line confidence, key-value fields, page slices.
- `src/tools/field_mappings.py`
  - `map_textract_to_model(document_type, textract_payload, confidence_threshold=80)`
  - Maps Textract output into Pydantic extraction models and marks low-confidence fields as unclear.
- `src/tools/document_router.py`
  - `route_document(document_path, declared_document_type=None)`
  - Chooses `text`, `vision`, or `textract` route using file/type heuristics.
- `src/tools/textract_to_rag.py`
  - `chunk_textract_pages(...)` and `ingest_textract_documents_to_faiss(...)`
  - Preserves page metadata while chunking and indexing extracted text.

`extract_document_data` now supports method override for comparisons:

- `preferred_method="auto"` (default)
- `preferred_method="text" | "vision" | "textract"`

Cost tracking:

- Per-document extraction metadata now includes `estimated_cost_usd`.
- Current estimates are lightweight heuristics for local exercises:
  - text: `$0.00`
  - textract: `~$0.0015/page`
  - vision: `~$0.01/page`
