# Agents SKILL — Underwriting Agent Layer

## Overview

The `src/agents/` package defines agent entry points used in exercises and
runtime flows. Agents are built with LangChain's current `create_agent` API and
are invoked using a `messages` payload.

## Implemented Agents

### `create_underwriting_Agent()`
**File:** `src/agents/underwriting_agent.py`

Purpose:
- Evaluate underwriting scenarios using tool calls and policy lookup support.

Current tools:
- `calculate_dti`
- `calculate_ltv`
- `check_fico_eligibility`
- `search_lending_policies`

Input shape:
```python
{
    "messages": [
        {"role": "user", "content": "Evaluate this loan application ..."}
    ]
}
```

### `create_fetch_data_agent()`
**File:** `src/agents/fetch_data.py`

Purpose:
- Gather borrower, credit, employment, and policy context needed before
  downstream underwriting decisions.

Current tools:
- `pull_borrower_data`
- `pull_credit_report`
- `pull_employment_history`
- `search_lending_policies`

Execution flow expected by prompt:
1. Pull borrower profile by application id
2. Pull credit data using borrower SSN last four
3. Pull employment data using borrower SSN last four
4. Pull state-relevant policy snippets

Input shape:
```python
{
    "messages": [
        {"role": "user", "content": "Gather all underwriting data for APP-001"}
    ]
}
```

## Document Review Workflow

### `create_doc_review_agent()`
**File:** `src/agents/doc_review.py`

Purpose:
- Process uploaded loan documents end-to-end: classify, extract, cross-validate,
  and report missing documents.
- Uses Claude Sonnet (`task="doc_review"`) for its stronger visual reasoning.

Current tools (all four required):

| Tool | Purpose |
|------|---------|
| `classify_document` | Detect document type (W2, 1040, PAYSTUB, …) without a live LLM |
| `extract_document_data` | Parse structured fields, routing text-first then vision |
| `compare_documents` | Run named consistency checks across two extracted payloads |
| `validate_document_package` | Build a cross-validated `DocumentReviewPackage` |

Input shape (same `messages` contract as all agents):
```python
{
    "messages": [
        {
            "role": "user",
            "content": "Review these loan documents for application APP-001:\n- data/sample_documents/w2_sample.txt\n- data/sample_documents/paystub_sample.png"
        }
    ]
}
```

### Document Processing Flow

```
classify_document(path)          ->  DocumentClassification
        |
        v
extract_document_data(path, type)  ->  DocumentExtractionResult
        |
compare_documents(doc1, doc2, check)  ->  comparison metrics
        |
        v
validate_document_package([extractions])  ->  DocumentReviewPackage
        |
        v
DocumentReviewPackage.format_report()    ->  human-readable summary
```

Step-by-step rationale:
1. **Classify first** — determine document type before attempting typed extraction.
2. **Extract per type** — each schema (`W2Extraction`, `TaxReturn1040Extraction`,
   `PayStubExtraction`) enforces field-level validation and populates `unclear_fields`.
3. **Cross-validate** — `validate_document_package` internally calls `compare_documents`
   for every available document pair.
4. **Report** — `DocumentReviewPackage.format_report()` renders the full summary
   including classification, extraction confidence, validation results, and missing docs.

### Cross-Validation Checks

| Check | Documents needed | Tolerance | Severity on fail |
|-------|-----------------|-----------|-----------------|
| W-2 wages vs 1040 AGI | W2 + 1040 | < 10 % diff | CRITICAL |
| Pay stub employer vs W-2 employer | PAYSTUB + W2 | exact match | CRITICAL |
| Pay stub YTD gross vs W-2 wages | PAYSTUB + W2 | < 15 % diff | WARNING |

When a required document is absent the check status is `UNABLE_TO_VERIFY` (WARNING).

### Missing Document Detection

`validate_document_package` always checks for all three required document types.
Any absent type becomes a `MissingDocument` entry in the package.

```python
required = {"W2", "1040", "PAYSTUB"}
```

`DocumentReviewPackage.has_critical_issues()` returns `True` when:
- Any cross-validation result has `severity == "CRITICAL"`, **or**
- Any of the three required document types is listed in `missing_documents`.

### Exercise Entry Point
**File:** `src/exercises/week3_day3_doc_review.py`

Covers:
1. Classifying three sample documents (W-2 text, pay stub image, 1040 PDF).
2. Extracting data from each and verifying field values.
3. Running `validate_document_package` across all three.
4. Printing `format_report()` and asserting key verification steps.

### Testing Guidance
- Tests for model validation, `has_critical_issues()`, `format_report()`, and the
  `validate_document_package` tool are in `tests/test_doc_review.py`.
- Use direct `DocumentExtractionResult.model_dump()` payloads to test mismatched
  employer scenarios without hitting live files.
- `tests/test_documents.py` covers the lower-level extraction helpers
  (`encode_image`, `has_extractable_text`, `compare_documents`, `classify_document`).

## Risk Scoring Workflow

### `create_risk_scoring_agent()`
**File:** `src/agents/risk_scoring.py`

Purpose:
- Produce audit-ready risk decisions by combining deterministic calculations,
  policy retrieval, and graph context in a single reasoning loop.

Required tool set (8 total):

Calculation tools (4):
- `calculate_dti`
- `calculate_ltv`
- `check_fico_eligibility`
- `check_employment_stability`

RAG tools (2):
- `search_lending_policies`
- `verify_compliance_requirement`

Knowledge graph tools (2):
- `get_borrower_risk_context`
- `find_similar_past_loans`

### Three-Data-Source Architecture

1. Deterministic calculations:
   - Fast threshold checks on borrower metrics (DTI, LTV, FICO, tenure).
2. Vector retrieval (RAG):
   - Policy and compliance constraints for federal/state applicability.
3. Knowledge graph context:
   - Industry-level default history and similar-loan outcomes.

Risk decisions should never rely on only one source; agent output must cite all
three where possible.

### Scoring Guidelines

Overall score bands:
- `80-100` -> `LOW` risk -> `APPROVE`
- `60-79` -> `MEDIUM` risk -> `APPROVE`
- `40-59` -> `HIGH` risk -> `MANUAL_REVIEW`
- `0-39` -> `CRITICAL` risk -> `DENY`

Criterion guidance:
- DTI: `<= 36` best, `36-43` borderline, `> 43` weak.
- FICO: `>= 740` best, `680-739` moderate, `< 680` weak.
- LTV: `<= 80` best, `80-95` moderate, `> 95` weak.
- Employment: `>= 5y` best, `2-5y` moderate, `< 2y` weak.

### Risk Multipliers (Graph-Driven)

Apply industry default-rate penalty to base score:
- `< 3%`: `0`
- `3-5%`: `-5`
- `5-10%`: `-10`
- `> 10%`: `-20`

Policy violations and severe document issues can further reduce score and may
force a `MANUAL_REVIEW` even when numeric score is otherwise approvable.

## Compliance Workflow

### `create_compliance_agent()`
**File:** `src/agents/compliance.py`

Purpose:
- Perform final regulatory/compliance checks after risk scoring and provide an
  escalation override when legal or audit requirements are not satisfied.
- Uses Claude Sonnet (`task="compliance"`) for higher-quality legal reasoning.

Required tool set (4 total):

RAG tools (2):
- `verify_compliance_requirement`
- `search_lending_policies`

Deterministic tools (2):
- `check_disclosure_requirements`
- `verify_audit_trail`

Output expectations:
- Required disclosures list (TRID/ECOA/FCRA/state)

## Orchestration Framework Comparison

### LangGraph vs CrewAI (Practical Guidance)

- Use **LangGraph** for production underwriting orchestration where deterministic
  routing, typed shared state, and explicit error paths are mandatory.
- Use **CrewAI** for rapid, role-based prototyping when you want to iterate on
  agent collaboration quickly and strict topology is less important.

### Why LangGraph Is the Default Here

- Explicit graph topology for parallel fan-out and controlled convergence.
- Predictable conditional routing for manual review and fatal-failure shortcuts.
- Better audit traceability for compliance-focused decision pipelines.

### When CrewAI Is Better

- Early exploration of prompts, roles, and agent responsibilities.
- Small workflows with limited tool count and lower regulatory risk.
- Demo-oriented multi-agent interactions where speed matters more than rigid
  workflow guarantees.

### Decision Rule

- If the workflow is compliance-critical or must be reproducible, choose
  LangGraph.
- If the workflow is exploratory and fast-changing, start with CrewAI, then
  migrate to LangGraph for production hardening.

## Human-In-The-Loop Orchestration (Week 4 Day 4)

### Interrupt/Resume Pattern

- Use `interrupt()` inside `human_review_node` to pause execution and present a
  structured review payload to a human underwriter.
- Include borrower summary, risk assessment snapshot, and compliance outcome in
  the interrupt payload so the human can make a defensible decision.
- Resume execution with `Command(resume=...)` and persist the normalized human
  decision in graph state.

### Checkpointing Guidance

- Compile the graph with `MemorySaver` during development to enable pause and
  resume across invocations using `thread_id`.
- For restart simulation and multi-instance resume in local testing, share the
  same checkpointer object between graph instances.
- For production durability across process crashes, replace `MemorySaver` with
  a persistent checkpoint backend.
- Audit-trail completeness status
- Blocking violations list
- Recommendation override (`NONE` or `MANUAL_REVIEW` or `DENY`)

## Advanced Graph Patterns (Week 4 Day 5)

### Subgraph Extraction Heuristic

- Keep a node as-is while it remains linear and testable.
- Extract a node to a subgraph when it gains multiple internal branches,
  conditional lookups, or mixed responsibilities (for example deterministic
  metrics plus optional context enrichment plus synthesis).

### Streaming for Observability

- Prefer `graph.stream(...)` for operator-facing runs to surface node completion
  events and intermediate state growth in real time.
- Keep `graph.invoke(...)` for API paths that only need final output.

### Dynamic Routing by Loan Type

- Route from risk scoring to loan-type-specific checks using a deterministic
  router function (for example `route_by_loan_type`).
- Keep the default path (`conventional`) stable and insert specialty nodes
  (`fha_compliance`) only when needed.

### Human Review Loop Safety

- If a human requests additional data, allow a controlled loop back to data
  fetch/re-score.
- Enforce a hard max-iteration safety cap (for example 3) to prevent infinite
  cycles and force terminal output when exceeded.

Orchestrator interaction:
- The graph runs compliance after risk scoring.
- `should_escalate(...)` checks both risk recommendation and compliance
  `recommendation_override` before deciding on `human_review`.



## Agent Invocation Notes

- These agents return a LangGraph/LangChain state object that includes
  `messages`; exercise scripts should read the final message for display.
- Use callback handlers (for example `UnderwritingTracer`) via `config`:
```python
agent.invoke(payload, config={"callbacks": [tracer]})
```
- Prefer deterministic settings (`temperature=0`) for underwriting and compliance
  use cases.

## Compatibility Notes

- `create_tool_calling_agent`/`AgentExecutor` style setup has been migrated to
  `create_agent` for current LangChain compatibility.
- Agent prompts are loaded from `src/prompts/*.txt` through `load_prompt(...)`.

## Testing Guidance

- Integration tests for fetch-agent wiring and execution are in
  `tests/test_fetch_agent.py`.
- Keep tests deterministic by monkeypatching `create_agent` and policy search
  tools instead of invoking live Bedrock dependencies.
- Document model and multimodal extraction tests are in `tests/test_documents.py`.
