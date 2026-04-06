# Utils SKILL

## Purpose
Utilities in `src/utils/` provide production-hardening primitives shared across tools, agents, and orchestrator nodes.

## Retry
- Module: `src/utils/retry.py`
- API: `retry_with_backoff(...)`
- Features:
  - exponential backoff (`base_delay * 2^attempt`)
  - optional jitter
  - configurable retryable exception types
  - per-attempt wait logging

Use for transient external failures (timeouts, temporary network errors).

## Circuit Breaker
- Module: `src/utils/circuit_breaker.py`
- API: `CircuitBreaker`, `ALL_BREAKERS`
- States:
  - `CLOSED` -> normal
  - `OPEN` -> fail-fast/fallback
  - `HALF_OPEN` -> probe recovery

Configured breakers:
- `bedrock_breaker`
- `credit_bureau_breaker`
- `employment_breaker`
- `neo4j_breaker`
- `opensearch_breaker`

## Structured Errors
- Module: `src/utils/error_types.py`
- Categories:
  - `RECOVERABLE`
  - `DEGRADED`
  - `FATAL`
- API:
  - `StructuredError.recoverable(...)`
  - `StructuredError.degraded(...)`
  - `StructuredError.fatal(...)`
  - `categorize_pipeline_errors(...)`

Use `to_state_string()` when appending to orchestrator `state["errors"]`.

## Metrics
- Module: `src/utils/metrics.py`
- API: `PipelineMetrics`
- Captures per-node and total metrics:
  - duration
  - LLM calls / token counts
  - tools called
  - errors
  - retries
  - cost estimate

Persist summary into orchestrator state key: `metrics_summary`.

## Health Checks
- Module: `src/utils/health_check.py`
- API: `check_all_dependencies()`
- Dependency probes:
  - Bedrock runtime invoke
  - Neo4j query
  - FAISS search
  - OpenSearch cluster health
  - Redis ping
  - circuit-breaker state snapshot

Top-level status: `healthy | degraded | unhealthy`.
