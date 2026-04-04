# Production Readiness Checklist

## Guardrails
- [x] Agent-facing Bedrock tasks use guardrails by default.
- [x] Role-specific guardrail IDs/versions configured for:
  - fetch_data
  - doc_review
  - risk_scoring
  - compliance
- [x] Internal RAG grading/check tasks bypass guardrails by default:
  - retrieval_grading
  - hallucination_check
- [x] Validated expected behavior:
  - normal underwriting prompts pass
  - personal financial-advice prompt is blocked
  - discriminatory language prompt is blocked
  - PII/SSN leakage content is blocked/redacted

## Retry Configuration
- [x] Exponential backoff with jitter implemented in `src/utils/retry.py`.
- [x] Retry coverage added to external dependency paths:
  - Bedrock agent invocation boundary
  - credit bureau calls
  - employment verification calls
  - Neo4j graph query helpers
  - policy retrieval search / SmartRAG retrieval
  - Textract OCR helper
- [x] Retry attempt logs include wait-time details.

## Circuit Breaker Thresholds
- [x] Circuit breaker implementation with `CLOSED/OPEN/HALF_OPEN` states.
- [x] Transition logging enabled.
- [x] Service breakers configured:
  - Bedrock: threshold=5, timeout=30s
  - Credit bureau: threshold=3, timeout=60s
  - Employment verification: threshold=3, timeout=60s
  - Neo4j: threshold=5, timeout=45s
  - OpenSearch: threshold=5, timeout=45s
- [x] Fallback behavior defined:
  - Bedrock: degraded signal (manual underwriting route)
  - Credit bureau: unverified/cached-style degraded payload
  - Employment: degraded payload with `verified=false`
  - Neo4j: empty/degraded context
  - OpenSearch/FAISS: empty retrieval result

## Structured Error Categories
- [x] Categories implemented: `RECOVERABLE`, `DEGRADED`, `FATAL`.
- [x] Structured error model includes:
  - category
  - source
  - message
  - timestamp
  - retry_count
- [x] Orchestrator nodes use categorized errors for node-level failures.
- [x] Final report includes grouped error categories.

## Metrics Collected
- [x] Per-node metrics:
  - duration
  - llm_calls
  - tokens_in / tokens_out
  - tools_called
  - errors
  - retries
  - cost_estimate_usd
- [x] Per-evaluation aggregate metrics:
  - total duration
  - total llm/tool usage
  - total retries
  - total errors
  - total cost estimate
- [x] Metrics emitted in structured dict form for CloudWatch and audit trail.
- [x] Final state persists `metrics_summary`.

## Textract Hybrid Document Review
- [x] `doc_review_node` routes each document via `document_router`.
- [x] Standard forms (`W2`, `1040`, `paystub`) prefer Textract.
- [x] Unstructured documents use Vision path.
- [x] Textract low-confidence fallback to Vision implemented.
- [x] Per-document extraction method and cost logged.

## Health Check Dependencies
- [x] Bedrock runtime invoke probe.
- [x] Neo4j simple query probe.
- [x] FAISS search probe.
- [x] OpenSearch cluster health probe.
- [x] Redis ping probe.
- [x] Circuit breaker state snapshot included.
- [x] Endpoint-friendly status output: `healthy/degraded/unhealthy`.

## Suggested Alert Thresholds
- [ ] Error rate > 2% (5-minute window)
- [ ] Bedrock breaker OPEN for > 2 minutes
- [ ] Neo4j breaker OPEN for > 5 minutes
- [ ] Total retries > 3 per evaluation (p95)
- [ ] Guardrail interventions spike above baseline
- [ ] Health status `unhealthy` for 2 consecutive probes
- [ ] Estimated cost per evaluation exceeds configured budget threshold
