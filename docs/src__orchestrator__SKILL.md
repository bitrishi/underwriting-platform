# Orchestrator SKILL

## Purpose
The orchestrator coordinates four underwriting agents in a production-style LangGraph flow with explicit state, routing, error handling, and human-in-the-loop support.

## Core Graph

```mermaid
flowchart TD
    S[START] --> F[fetch_data]
    S --> D[doc_review]
    F -->|continue| R[risk_scoring]
    F -->|fatal| Z[final_decision]
    D --> R
    R -->|fha| H[FHA_compliance]
    R -->|standard| C[compliance]
    H --> C
    C -->|needs_manual_review| M[human_review]
    C -->|no escalation| Z
    M --> Z
    Z --> E[END]
```

## Node Responsibilities
- `fetch_data`: build `borrower_package` and data-quality metadata.
- `doc_review`: classify/extract/validate docs or return `SKIPPED` when no docs.
- `risk_scoring`: combine borrower + doc review + policy/graph context into `risk_assessment`.
- `fha_compliance`: optional FHA-specific checks before standard compliance.
- `compliance`: legal/regulatory validation and escalation override.
- `human_review`: interrupt/resume for manual decision capture.
- `final_decision`: unified report + audit trail.

## State Requirements
- Shared state includes all agent outputs and control fields.
- `errors` uses `Annotated[list[str], add]`.
- `messages` uses `Annotated[list, add_messages]`.
- Audit fields must include per-node completion timestamps.
- `graph_version` must be set on every execution for future versioning.

## Routing Rules
- After `fetch_data`: route to final decision when borrower package is missing.
- After `compliance`: route to human review when `needs_manual_review` is true.
- `loan_type` may branch risk flow (for example `fha -> fha_compliance`).

## Reliability Rules
- Every node wraps work in try/except and writes failures to `errors`.
- Graph compiles with `MemorySaver` in development.
- Use persistent checkpoint backend (Redis) in production.

## Production Hardening (Week 5 Weekend)

### Structured Errors
- Node error handling should emit categorized errors using `StructuredError`:
    - `RECOVERABLE`: transient failures; continue with partial data
    - `DEGRADED`: service unavailable but pipeline remains operational
    - `FATAL`: pipeline cannot produce a trustworthy decision

`final_decision_node` groups errors via `categorize_pipeline_errors(...)` and
persists `error_categories` into state and report output.

### Metrics
- Every node records metrics into `metrics_summary`:
    - duration
    - llm/tool usage
    - retries
    - cost estimate
    - node success/degraded/failed status

Final report includes full metrics summary for audit and CloudWatch export.

### Guardrails + Bedrock Resilience
- Agent invocations in `_invoke_agent` are wrapped with retry + `bedrock_breaker`.
- Bedrock circuit-open conditions are surfaced and treated as degraded/fallback
    rather than silently ignored.

### Circuit Breaker Telemetry
- Final state includes `circuit_breaker_states` from `ALL_BREAKERS`.
- This is used by both the report and health endpoint for runtime diagnostics.

### Document Review Hybrid Routing
- `doc_review_node` uses `route_document` per file.
- Standard forms prefer Textract with fallback to Vision on low confidence.
- Unstructured documents follow Vision route.
- Per-document extraction method + estimated cost are stored in review payload.
