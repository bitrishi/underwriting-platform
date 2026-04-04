md_content = """# Week 5, Weekend BUILD: Production Hardening

## Session Overview
**Date:** Week 5, Weekend
**Topic:** Integrating all Week 5 components into the orchestrator — guardrails, Textract hybrid, retry/circuit breaker, structured errors, metrics, and health checks. Transforming the working orchestrator into a production-hardened system.
**Prerequisites:** Week 5 Days 1-5 (MCP, A2A, Guardrails, Textract, Error Handling)

---

## 1. What You Are Hardening

### 1.1 The Gap Between Working and Production

The Week 4 orchestrator WORKS — it evaluates loans correctly with 4 agents, parallel execution, conditional routing, and human-in-the-loop. But it is fragile. External calls have no retry. Sustained outages cascade. No content filtering. All documents use expensive Vision. No cost or performance tracking. No health monitoring.

Production means: the system handles failures gracefully, protects against content safety issues, optimizes costs, reports operational metrics, and recovers from outages — automatically, without human intervention.

### 1.2 The Hardening Layers

Six layers of hardening applied to the existing orchestrator:

Guardrails sit between agent code and Bedrock LLM. Content filtering, PII redaction, denied topics, word filters. Per-agent configuration. Blocks harmful content without blocking legitimate underwriting.

Textract hybrid replaces all-Vision document processing. Router classifies document type. Standard forms go to Textract at one-third the cost. Unstructured documents continue to Vision. Automatic fallback if Textract fails.

Retry wraps every external call. Exponential backoff with jitter. Maximum 3 attempts. Transient errors retried, permanent errors not.

Circuit breaker per external service. Detects sustained outages. Stops retrying failing services. Returns fallback immediately. Tests recovery periodically.

Structured errors replace plain strings. RECOVERABLE, DEGRADED, FATAL categories. Pipeline behavior changes based on category. Audit trail shows what failed and what impact it had.

Metrics collection at every node. Duration, tokens, cost, errors, retries, circuit breaker hits. Stored per-evaluation for audit. Aggregated for operational dashboards.

---

## 2. Architecture After Hardening

### 2.1 The Call Chain

Every external call now passes through multiple protection layers. Agent code calls through Guardrails (content check), which calls through Retry wrapper (exponential backoff), which calls through Circuit breaker (skip if service down), which calls the actual external service.

If the service responds normally: result flows back through all layers unchanged. If the service fails transiently: retry handles it transparently. If the service is down: circuit breaker returns fallback immediately. If the LLM generates harmful content: guardrail catches it. Each layer handles a different failure mode.

### 2.2 Document Processing After Hybrid

Document arrives. Router classifies type using Haiku (fast, cheap). Standard forms (W-2, 1040, pay stub, bank statement) go to Textract at $0.0015/page, through field mapping to Pydantic models. Unstructured documents (letters, handwritten, unusual) go to Vision at $0.005/page. If Textract extraction confidence is low or Pydantic validation fails, automatic fallback to Vision. Both paths produce identical Pydantic output models. Downstream agents cannot tell the difference.

### 2.3 Error Flow

Tool fails → retry wrapper retries up to 3 times → if all retries fail, tool returns structured error → node catches error, categorizes as RECOVERABLE/DEGRADED/FATAL → error appended to state errors list → if FATAL, conditional edge routes to final_decision immediately → if RECOVERABLE/DEGRADED, pipeline continues with partial data → final_decision reports all errors by category in audit trail → if any DEGRADED or FATAL errors, evaluation flagged for human review.

---

## 3. Production Impact

### 3.1 Cost Optimization

Document processing: $0.060/eval (all Vision) drops to $0.032/eval (Textract hybrid). Savings: 47% on document costs, $840/month at 1,000 evals/day.

Guardrails skip on internal calls: retrieval grading and internal classification do not pass through guardrails, saving 100-300ms per skipped call. Only agent-facing and user-facing calls are filtered.

Circuit breaker prevents wasted retries: when a service is down, calls skip instantly instead of waiting through 3 retry attempts (up to 7 seconds saved per call during outages).

### 3.2 Reliability Improvement

Without hardening: any external failure crashes the evaluation. 20 failures/day at 99.9% per-call reliability = 20 crashed evaluations.

With hardening: transient failures recovered by retry (invisible to the evaluation). Sustained failures handled by circuit breaker (fast fallback). Remaining impact produces partial results with documented gaps. Fatal failures routed to manual underwriting immediately.

Effective reliability improves from 98% (20 crashes in 1,000) to 99.8% (2 fatal failures in 1,000 where even partial results were impossible).

### 3.3 Operational Visibility

Before: no idea how the system is performing until someone complains. After: real-time metrics showing evaluation throughput, latency distribution, cost per evaluation, error rates by service, circuit breaker states. Problems detected in minutes, not days.

---

## 4. What Each Component Adds

| Component | What It Prevents | Cost | Latency Impact |
|-----------|-----------------|------|----------------|
| Guardrails | PII leaks, harmful content, off-topic | $0.004/eval | +100-300ms per filtered call |
| Textract hybrid | Overpaying for standard form extraction | Saves $0.028/eval | Neutral (Textract is fast) |
| Retry | Transient failures crashing evaluations | None | +1-7s per retried call |
| Circuit breaker | Sustained outages cascading | None | Saves 7s per skipped call |
| Error categorization | Silent failures with no documentation | None | None |
| Metrics | Invisible performance and cost issues | None | Negligible |
| Health check | Undetected dependency failures | None | None (runs on demand) |

### Net impact on cost: SAVES approximately $0.024/eval ($24/day at 1K evals)
### Net impact on reliability: 98% → 99.8% effective reliability
### Net impact on latency: approximately neutral (Textract saves time, guardrails add time)

---

## 5. Testing Strategy

### 5.1 Four Scenarios

Scenario 1 (Normal): everything works. Verify guardrails do not block legitimate work. Verify Textract used for standard docs. Verify metrics collected. This is the MOST IMPORTANT test — hardening must not break normal operation.

Scenario 2 (Partial failure): one service times out. Verify retry recovers or produces partial result. Verify RECOVERABLE error documented. Verify downstream agents handle missing data.

Scenario 3 (Sustained failure): one service down for all calls. Verify circuit opens after threshold. Verify subsequent calls skip instantly. Verify DEGRADED results produced. Verify circuit tests recovery after timeout.

Scenario 4 (Content safety): adversarial input attempts discriminatory output. Verify guardrail blocks harmful content. Verify evaluation still produces a result for the legitimate parts.

### 5.2 What Success Looks Like

Scenario 1: complete evaluation, zero errors, metrics show Textract used for standard docs, guardrails did not intervene.

Scenario 2: partial evaluation, one RECOVERABLE error, missing data flagged, everything else normal, total time only slightly increased by retries.

Scenario 3: degraded evaluation, DEGRADED errors documented, circuit breaker OPEN logged, subsequent calls instant (no retry delays), partial result with explicit gaps.

Scenario 4: guardrail intervention logged, harmful content blocked, evaluation completed for legitimate content, human review triggered if guardrail affected the decision output.

---

## 6. What You Have After This Weekend

The complete system with production hardening:

4 sub-agents with focused tool sets and optimal model selection. 20+ tools across calculations, RAG, knowledge graph, document processing. LangGraph orchestrator with parallel execution, conditional routing, human-in-the-loop. Checkpointing for crash recovery. Textract hybrid for cost-optimized document processing. Bedrock Guardrails for content safety and PII protection. Retry with exponential backoff on all external calls. Circuit breakers per external service. Structured error categorization with graceful degradation. Metrics collection for operational visibility. Health check for container monitoring.

Estimated production metrics: cost per evaluation $0.025-0.035. Latency 10-15 seconds automated. Effective reliability 99.8%. Document processing cost reduced 47%.

---

## 7. Week 6 Preview

| Day | Topic |
|-----|-------|
| 1 | LangSmith — tracing, debugging, production monitoring |
| 2 | Ragas — automated RAG quality and agent accuracy evaluation |
| 3 | Fine-tuning on Bedrock — custom model on underwriting data |
| 4 | FastAPI — production API layer for the orchestrator |
| 5 | Streamlit — UI for agent progress, audit trails, human review |
| Weekend | Final deployment and integration build |

The system is complete and hardened. Week 6 adds evaluation (prove it works), deployment (make it accessible), and UI (make it usable). One week to go.
"""

with open("week5_weekend.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")