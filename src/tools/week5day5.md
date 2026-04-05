md_content = """# Week 5, Day 5: Error Handling, Retries, Circuit Breakers & Observability

## Session Overview
**Date:** Week 5, Day 5
**Topic:** Production resilience — three layers of error handling (retry, circuit breaker, graceful degradation), structured observability (metrics, logs, traces, alerts), and the production readiness checklist.
**Prerequisites:** Week 4 complete orchestrator, Week 5 Days 1-4 (MCP, A2A, Guardrails, Textract)

---

## 1. Why This Matters

### 1.1 The Math of Failure

Your pipeline makes 15-20 external calls per evaluation — Bedrock API (multiple models), credit bureau, employment verification, Neo4j, OpenSearch, Redis. At 99.9% reliability per call: 20 calls × 1,000 evaluations × 0.1% failure = 20 failures per day.

Without error handling: 20 crashed evaluations producing zero results. With error handling: 20 partial results with documented gaps — still useful, still auditable.

The difference between demo and production is not the AI — it is how the system behaves when things go wrong.

---

## 2. Three Layers of Error Handling

### 2.1 Layer 1: Individual API Call — Retry with Exponential Backoff

A single call to Bedrock, credit bureau, or Neo4j fails. Most failures are transient — network blip, momentary overload. The right response is retry with increasing wait times.

Exponential backoff formula: wait_time = base_delay × (2 to the power of attempt_number) + random_jitter. First retry waits 1 second. Second retry waits 2 seconds. Third retry waits 4 seconds. The jitter (random 0-500ms) prevents thundering herd — 100 evaluations all retrying at exactly the same moment would slam the recovering service again.

Which errors to retry: timeout errors (service was slow), 429 Too Many Requests (rate limited, wait and try again), 500 Internal Server Error (service hiccup), 503 Service Unavailable (service restarting), network connection errors (network blip).

Which errors NOT to retry: 400 Bad Request (your input is wrong, same input will fail again), 401/403 Unauthorized (credentials wrong, retrying will not fix auth), 404 Not Found (resource does not exist), validation errors (data is invalid).

Java analogy: Spring Retry with @Retryable. Annotate method with retry policy, specify retryable exceptions, set backoff parameters. Same concept.

### 2.2 Layer 2: Tool/Agent Level — Circuit Breaker

If the credit bureau has been failing for 5 minutes, retrying every call 3 times wastes time and money. A circuit breaker detects sustained failures and STOPS trying.

Three states. CLOSED is normal operation — all requests go through. The breaker monitors failure rate. If failures exceed threshold (5 failures in 60 seconds), circuit OPENS. OPEN means all requests immediately fail WITHOUT calling the external service. Returns cached result or structured error instantly. After timeout (30 seconds), circuit moves to HALF-OPEN. HALF-OPEN allows ONE request through to test recovery. Success closes the circuit (back to normal). Failure opens it again.

Why circuit breakers matter: without one, credit bureau down means every evaluation retries 3 times, creating 3x the API calls, hitting rate limits on OTHER services, everything slows down. With circuit breaker: credit bureau down, circuit opens after 5 failures, subsequent evaluations skip credit bureau instantly, other services unaffected, partial results produced quickly.

Each external service gets its own circuit breaker: Bedrock, credit bureau, employment verification, Neo4j, OpenSearch. They fail independently.

Java analogy: Resilience4j CircuitBreaker or Netflix Hystrix. Same pattern you use in Kuber.

### 2.3 Layer 3: Pipeline/Graph Level — Graceful Degradation

Already built in Week 4. Each LangGraph node has try/except. Errors accumulate via add reducer. Downstream nodes check for None. Pipeline produces best result with available data.

Day 5 adds STRUCTURED error categorization. ERROR_RECOVERABLE means evaluation continues with reduced confidence (credit bureau timeout — score without FICO, flag as unverified). ERROR_DEGRADED means evaluation continues but significantly less reliable (Neo4j down — no industry context, all documents failed — no verified data). ERROR_FATAL means evaluation cannot continue (cannot identify borrower, Bedrock completely unavailable). Route to manual underwriting immediately.

### 2.4 How the Three Layers Work Together

Layer 1 handles transient blips — retry fixes it, the evaluation never knows there was a problem. Layer 2 handles sustained outages — stop wasting time, skip the failing service, let the evaluation proceed with what is available. Layer 3 handles the impact — produce partial results, categorize what is missing, route to human review if too degraded.

Example: Credit bureau has intermittent issues. First evaluation: call fails, Layer 1 retries, second attempt succeeds. Normal result. Third evaluation: call fails, retry fails, retry fails — Layer 1 exhausted. Tool returns error. Layer 3 records RECOVERABLE error, pipeline continues without FICO. Fifth through tenth evaluations: Layer 2 circuit breaker opens after 5 failures. All subsequent calls skip credit bureau instantly (0ms instead of 3×4s retry waits). Layer 3 flags all as "FICO unverified." Thirtieth second later: circuit breaker goes HALF-OPEN, one test call succeeds, circuit closes, normal operation resumes.

---

## 3. Observability: The Four Pillars

### 3.1 Metrics — Numbers Over Time

Numerical measurements tracked continuously. Evaluation count per hour. Success/failure rate. Average latency per node. Cost per evaluation. Circuit breaker state per service. Error count by category. Human review rate.

These go to CloudWatch as custom metrics. Build dashboards showing trends. Set alarms for anomalies. Same CloudWatch infrastructure the company uses for Kuber.

### 3.2 Logs — Structured Event Records

Every tool call logged with tool name, input parameters (PII redacted), output summary, duration, success/failure, error details. Every node completion logged. Every guardrail intervention logged. Every circuit breaker state change logged.

Structured JSON logs are essential — not print statements. Structured logs can be queried and aggregated. "Show me all credit bureau failures in the last hour" is a log query in CloudWatch Logs Insights.

### 3.3 Traces — End-to-End Request Tracking

One evaluation generates 15-20 tool calls across 4 agents. A trace connects all into a single timeline with a unique trace_id. When an evaluation produces a bad result, pull the trace: which tools called, what returned, how long each took, where errors occurred.

Two tracing systems work together. LangSmith captures AI-layer traces — every LLM call, tool invocation, agent reasoning across the LangGraph pipeline. CloudWatch X-Ray captures infra-layer traces — Bedrock API calls, S3 access, DynamoDB queries. Together they give complete end-to-end visibility.

LangSmith in detail will be covered in Week 6 Day 1.

### 3.4 Alerts — Automated Problem Detection

Error rate exceeds 5% → page on-call engineer. Average latency exceeds 30 seconds → investigate bottleneck. Circuit breaker opens for any service → notify team. Cost per evaluation exceeds $0.05 → possible runaway LLM calls. Zero evaluations in last hour → system might be down.

CloudWatch Alarms → SNS → PagerDuty/Slack. Same alerting infrastructure as Kuber.

---

## 4. What to Measure Per Evaluation

### 4.1 Pipeline Metrics

Total duration, success/failure, recommendation (approve/deny/manual), error count, error categories, total cost estimate.

### 4.2 Per-Node Metrics

Node name, duration, LLM calls made, tokens used (input + output by model), tools called, errors encountered, fallbacks triggered, circuit breaker hits.

### 4.3 Per-Tool Metrics

Tool name, duration, success/failure, retry count, input size, output size.

### 4.4 Cost Metrics

LLM tokens by model (Haiku and Sonnet separately), Textract pages processed, embedding calls, total estimated cost. Critical for budget monitoring — detect cost anomalies before monthly bill arrives.

### 4.5 Quality Metrics

RAG retrieval confidence, grounding check results, guardrail interventions, human review rate, Smart RAG vs Agentic RAG usage ratio.

### 4.6 Where Metrics Go

Real-time: CloudWatch custom metrics for operations dashboards. Per-evaluation: DocumentDB alongside loan decision as part of audit trail ("this evaluation used 18,432 tokens, cost $0.028, took 11.3s, with 1 credit bureau retry"). Aggregated: weekly/monthly reports showing trends.

---

## 5. The Production Readiness Checklist

### 5.1 Retry

Every external call has retry with exponential backoff. Transient errors retried (timeout, 429, 500, 503). Permanent errors not retried (400, 401, 404). Maximum 3 retries with 1s/2s/4s backoff plus jitter.

### 5.2 Circuit Breaker

Each external service has its own circuit breaker. Opens after 5 failures in 60 seconds. Half-open after 30 seconds. Fallback behavior defined (cached data or structured error). State changes logged and alerted.

### 5.3 Graceful Degradation

Every node has try/except. Errors categorized (recoverable/degraded/fatal). Fatal routes to immediate final_decision. Recoverable produces partial results with flags.

### 5.4 Logging

Structured JSON for every tool call, node completion, error, guardrail intervention. PII redacted. Log level configurable (DEBUG for dev, INFO for prod).

### 5.5 Metrics

CloudWatch custom metrics for success rate, latency per node, cost per evaluation, error rate by category, circuit breaker state, human review rate.

### 5.6 Tracing

LangSmith for AI-layer (LLM calls, tool invocations, agent reasoning). X-Ray for infra-layer (AWS API calls). Trace ID propagated across all calls.

### 5.7 Alerts

Thresholds for error rate (above 5%), latency (above 30s), circuit breaker open, cost anomaly, zero throughput.

### 5.8 Health Check

Endpoint verifying connectivity to all dependencies (Bedrock, Neo4j, OpenSearch, Redis, DocumentDB). Used by ECS for container health. Returns degraded status if any dependency unreachable.

---

## 6. Q&A

### Q: Are we covering LangSmith in detail later?

Yes. Week 6 Day 1 covers LangSmith in depth: enabling tracing across the entire LangGraph pipeline, debugging failed evaluations with complete traces, monitoring production costs per model and agent, building test datasets for regression testing, and tracking quality over time. Today builds infrastructure-level observability. LangSmith adds AI-specific observability on top.

### Q: How does retry interact with circuit breaker?

They layer. First attempt fails → retry handles it (Layer 1). All retries fail → tool reports failure → if this is the Nth failure in the window, circuit breaker opens (Layer 2). Next calls skip the service entirely (circuit open). Circuit breaker wraps around retry — the circuit breaker decides WHETHER to allow the call, retry decides HOW MANY TIMES to try if allowed.

### Q: What is the fallback when circuit is open?

Depends on the service. Credit bureau: return cached credit data from Redis if recent (last 30 days), otherwise return structured error with fico=None. Neo4j: return empty industry context, risk scoring proceeds without graph data. Bedrock: no fallback — if LLM is unavailable, the agent cannot function. Route entire evaluation to manual underwriting.

### Q: How do I know which errors are transient vs permanent?

HTTP status codes are the primary signal. 4xx errors (client errors) are permanent — your request is wrong. 5xx errors (server errors) are transient — the server had a problem. Timeouts are transient. Connection refused might be transient (service restarting) or permanent (wrong URL). When uncertain, retry once — if same error, treat as permanent.

### Q: Cost anomaly detection — what counts as anomalous?

Set baseline from normal operation. If average evaluation costs $0.028, alert if any single evaluation exceeds $0.05 (possible infinite tool loop) or if hourly average exceeds $0.040 (systematic cost increase — maybe a prompt change caused more tool calls, or a model version change increased token usage).

---

## 7. Summary

| Concept | What It Does | Java / AWS Equivalent |
|---------|-------------|----------------------|
| Exponential backoff | Increasing wait between retries | Spring Retry @Retryable |
| Jitter | Random delay preventing thundering herd | Random backoff in retry policy |
| Retryable errors | Transient: timeout, 429, 500, 503 | Same classification |
| Non-retryable | Permanent: 400, 401, 404 | Same classification |
| Circuit breaker | Stops calling failing services | Resilience4j / Hystrix |
| CLOSED state | Normal operation, monitoring failures | Circuit closed |
| OPEN state | Blocking all calls, returning fallback | Circuit open |
| HALF-OPEN state | Testing recovery with one call | Circuit half-open |
| Error categorization | RECOVERABLE / DEGRADED / FATAL | Exception hierarchy |
| Graceful degradation | Partial results with documented gaps | Fallback responses |
| Structured logs | JSON format, queryable, PII-redacted | CloudWatch Logs |
| Metrics | Counters, gauges, histograms to CloudWatch | CloudWatch Custom Metrics |
| Traces (LangSmith) | AI-layer end-to-end tracking | Application tracing |
| Traces (X-Ray) | Infra-layer AWS service tracking | AWS X-Ray |
| Alerts | Automated notification on anomalies | CloudWatch Alarms → SNS |
| Health check | Dependency connectivity verification | ECS health check |
| Production checklist | All resilience patterns verified | Deployment readiness review |
"""

with open("week5_day5.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")