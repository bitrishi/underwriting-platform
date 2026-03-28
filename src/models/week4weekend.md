md_content = """# Week 4, Weekend BUILD: Complete Production Orchestrator

## Session Overview
**Date:** Week 4, Weekend  
**Topic:** Assembling the complete multi-agent orchestrator — architectural rationale for the graph structure, end-to-end data flow design, production considerations, and the final build.  
**Prerequisites:** All Week 4 sessions (Days 1-5), all sub-agents from Weeks 2-3

---

## 1. Why This Architecture: The Design Decisions

### 1.1 Four Agents, Not One — The Rationale Revisited

You asked in Day 2 why not build one agent with all tools. The weekend build is where that decision becomes concrete. Here is exactly what each agent boundary buys you in the final system.

The FetchData agent runs on Haiku and calls external APIs (borrower system, credit bureau, employment verification, policy search). Its failure mode is API timeouts and external service unavailability. If the credit bureau is down, FetchData fails partially — it still has borrower profile and employment data. The rest of the pipeline can work with partial data because FetchData's boundary isolates the external API risk.

The Document Review agent runs on Sonnet because it needs vision capabilities. It processes images and PDFs. Its failure mode is document quality — blurry scans, unreadable handwriting, corrupted files. If one document fails to extract, the others still succeed. The agent boundary means a document processing failure does not crash the data fetching or risk scoring.

The Risk Scoring agent runs on Haiku and combines three data sources (calculations, RAG, knowledge graph). It is the most tool-heavy agent (8 tools) but its tools are clearly differentiated — math functions, policy search, and graph queries have zero docstring overlap. Its failure mode is knowledge graph unavailability or RAG retrieval quality. If the graph is down, it still scores using calculations and RAG — graceful degradation within its boundary.

The Compliance agent runs on Sonnet because legal reasoning requires stronger model capabilities. It has veto power — it can override Risk Scoring's APPROVE to MANUAL_REVIEW if it finds a regulatory violation. This separation is not just technical but organizational — at Goldman, the compliance function is deliberately independent from the risk function. The agent boundary enforces this separation of concerns.

### 1.2 Parallel Execution: Where the Time Savings Come From

Your sequential pipeline from Week 3 ran: FetchData (3s) → DocReview (5s) → RiskScoring (3s) → total 11s. The graph runs FetchData and DocReview in parallel, cutting total to: max(3s, 5s) + 3s = 8s. That is a 27% reduction.

But the real savings in production are larger. FetchData calls three external APIs sequentially within its agent (borrower, credit, employment). If you later optimize FetchData to call those APIs concurrently (using asyncio.gather inside the agent), FetchData drops from 3s to 1.5s. Now the pipeline is: max(1.5s, 5s) + 3s = 8s. DocReview is the bottleneck because Sonnet vision is slow.

This reveals an important principle: parallelism at the GRAPH level (between nodes) and parallelism at the AGENT level (within nodes, using asyncio.gather for tool calls) are independent optimizations. You get both. The graph handles inter-agent parallelism. The agent handles intra-agent parallelism. Together they minimize total pipeline time.

### 1.3 The State Object: Designing for All Consumers

The UnderwritingState TypedDict must serve every node in the graph. Designing it well prevents friction later. The key design principles:

Each node writes to its OWN fields. fetch_data writes borrower_package. doc_review writes document_review. risk_scoring writes risk_assessment. compliance writes compliance_result. No node overwrites another node's fields. This eliminates the need for reducers on agent output fields (reducers only needed for shared fields like errors and messages).

Downstream nodes read from upstream fields. risk_scoring reads borrower_package AND document_review. compliance reads risk_assessment. final_decision reads EVERYTHING. The data flows forward through state — each node adds its contribution and later nodes consume accumulated data.

Control fields drive routing. has_documents determines whether doc_review does real work or returns SKIPPED. needs_manual_review determines whether the pipeline routes to human_review or final_decision. These are simple booleans set by nodes and read by edge functions.

Error fields accumulate. The errors list uses an add reducer so every node can append its failures without overwriting others. At the end, final_decision checks the errors list to determine if the evaluation is complete or partial.

### 1.4 Error Handling Philosophy: Partial Results Are Better Than No Results

The design philosophy for error handling in this orchestrator is: produce the best possible assessment with whatever data is available, and explicitly document what is missing.

If FetchData cannot pull the credit report (bureau timeout), it still has borrower profile and employment data. Risk Scoring receives partial data, calculates what it can (employment stability, income analysis), and flags "FICO: UNABLE TO VERIFY — credit bureau unavailable." The final decision is MANUAL_REVIEW with a note explaining what data is missing.

If Document Review fails entirely (no documents or all extractions fail), Risk Scoring still runs on the FetchData output. The document quality flags show "INSUFFICIENT — no verified documents." The risk score is lower (missing verification) and the recommendation is more conservative.

If Risk Scoring fails (Bedrock timeout, graph connection error), Compliance cannot run (nothing to verify). The pipeline routes to final_decision with an error report: "Risk assessment failed. Manual underwriting required."

Only a COMPLETE failure of FetchData (cannot even identify the borrower) triggers the fatal error path — skip everything and produce an error report. Every other failure mode produces partial results.

This philosophy matches real underwriting. A human underwriter does not stop working because one piece of data is unavailable. They work with what they have, note the gaps, and adjust their confidence accordingly. Your orchestrator does the same.

---

## 2. End-to-End Data Flow

### 2.1 The Complete Flow for a Typical Application

A senior underwriter submits application APP-001 through the Camelot UI with two uploaded documents (W-2 and pay stub). Here is exactly what happens:

**Initial state created:** app_id="APP-001", document_paths=["w2.png", "paystub.png"], all other fields null, errors empty.

**Parallel phase begins.** LangGraph starts both fetch_data and doc_review simultaneously.

**fetch_data executes (3 seconds).** The FetchData agent calls pull_borrower_data → gets name, income, debt, property info. Calls pull_credit_report → gets FICO 710, no delinquencies. Calls pull_employment_history → gets employer CryptoStartup, 2 years tenure. Calls search_lending_policies → gets applicable Texas regulations. Writes borrower_package to state. Checkpoint #1 saved.

**doc_review executes (5 seconds, in parallel).** The Doc Review agent calls classify_document on w2.png → identifies as W-2. Calls classify_document on paystub.png → identifies as pay stub. Calls extract_document_data on both → extracts wages, employer name, YTD income. Calls validate_document_package → checks W-2 employer matches pay stub employer (MATCH), flags missing 1040. Writes document_review to state. Checkpoint #2 saved.

**Parallel phase completes (5 seconds total, not 8).** Both checkpoints exist. risk_scoring can now execute.

**risk_scoring executes (3 seconds).** Reads borrower_package AND document_review from state. Calls calculate_dti → 40.4%. Calls calculate_ltv → 84.9%. Calls check_fico → 710, GOOD tier. Calls check_employment_stability → 2 years, MODERATE. Calls get_borrower_risk_context → cryptocurrency industry, 8% default rate. Calls find_similar_past_loans → 25% default rate for similar borrowers. Calls search_lending_policies → DTI 38-43% needs compensating factors. Calls verify_compliance_requirement → Texas LTV max 80%. Synthesizes: score 46/100, HIGH risk, MANUAL_REVIEW. Writes risk_assessment to state. Sets needs_manual_review=True. Checkpoint #3 saved.

**compliance executes (2 seconds).** Reads risk_assessment. Calls verify_compliance_requirement → Texas Section 50(a)(6) LTV violation confirmed. Calls check_disclosure_requirements → Adverse Action Notice not needed yet (not denied), Loan Estimate required. Calls verify_audit_trail → all required citations present. Writes compliance_result to state. LTV violation confirms needs_manual_review stays True. Checkpoint #4 saved.

**Conditional edge evaluates.** should_escalate reads needs_manual_review=True → routes to human_review.

**human_review interrupts.** Builds review summary from risk_assessment and compliance_result. Calls interrupt() with the summary. State saved to checkpoint store. Graph pauses. API returns pending_review status.

**Time passes.** Senior underwriter reviews in Camelot UI.

**Human responds.** "APPROVE WITH CONDITIONS — restructure to 80% LTV, require 6 months reserves documentation." API resumes graph with same thread_id.

**human_review completes.** Writes human decision to state. Checkpoint #5 saved.

**final_decision executes.** Reads ALL state fields. Produces complete report combining automated assessment + human override + audit trail. Writes final_report to state. Checkpoint #6 saved. Graph reaches END.

**Total time:** 5s (parallel) + 3s (risk) + 2s (compliance) + interrupt + 0.5s (final) = ~10.5s automated + human review time.

### 2.2 The Complete Flow for an Auto-Approved Application

Application APP-002: FICO 780, DTI 22%, LTV 72%, technology industry, 8 years employment, all documents provided.

Same parallel phase. FetchData and DocReview run simultaneously. Risk Scoring scores 92/100, LOW risk, APPROVE. Compliance finds no violations, all disclosures identified. should_escalate reads needs_manual_review=False → routes directly to final_decision. No human review. No interrupt.

Total time: ~10s automated, no human delay. Complete approval with full audit trail.

### 2.3 The Complete Flow for an Auto-Denied Application

Application APP-003: FICO 580, DTI 52%, no documents provided.

FetchData runs. DocReview runs in parallel but returns SKIPPED (no documents). Risk Scoring scores 15/100, CRITICAL risk, DENY. Multiple policy violations (FICO below 680, DTI above 43%). Compliance confirms violations, triggers Adverse Action Notice requirement. should_escalate reads needs_manual_review=False (DENY is clear-cut). final_decision produces denial report with specific reasons for each failed criterion.

Note: even for clear denials, the full pipeline runs. The audit trail must show that every criterion was checked and the denial is based on documented financial factors — this is the fair lending requirement.

---

## 3. Production Considerations for the Complete System

### 3.1 Cost Per Evaluation

The complete pipeline makes approximately 15-20 LLM calls per evaluation:

FetchData agent: 4-5 tool calls (Haiku) = ~$0.0015
DocReview agent: 3-4 tool calls (Sonnet, vision) = ~$0.015
RiskScoring agent: 7-8 tool calls (Haiku) = ~$0.003  
Compliance agent: 3-4 tool calls (Sonnet) = ~$0.010
Agent reasoning between tools: ~$0.002

Total per evaluation: approximately $0.025-0.035

At 1,000 evaluations per day: $25-35/day = $750-1,050/month

Document Review (Sonnet vision) is the most expensive component, accounting for roughly 50% of the cost. The Textract optimization in Week 5 Day 4 will reduce this significantly for standard form documents.

### 3.2 Latency Budget

Target: complete evaluation in under 15 seconds (excluding human review).

Parallel phase (fetch + doc): 5 seconds (the slower branch)
Risk Scoring: 3 seconds
Compliance: 2 seconds
Final decision formatting: 0.5 seconds
Graph overhead (state management, checkpointing): 0.5 seconds
Total: ~11 seconds

This is well within the 15-second target. The primary bottleneck is Document Review with Sonnet vision. If latency becomes an issue, the first optimization is switching standard form documents to Textract (Week 5).

### 3.3 Reliability Targets

For Goldman production, the system should handle:

Node failures: graceful degradation, partial results with explicit gap documentation
External API failures: retry with exponential backoff within each agent, fallback to cached data if available
LLM API failures: retry up to 3 times, then flag as error and continue with available data
Complete pipeline failure: checkpoint recovery, resume from last successful node
Human review timeout: 7-day TTL on checkpoints, auto-escalation after 5 business days

### 3.4 The Audit Trail: What Regulators Need

Every evaluation must produce a record containing:

What data was used: specific values for every financial metric
Where data came from: which APIs called, which documents processed, which policies retrieved
What was checked: every criterion evaluated with pass/fail and score
What could NOT be checked: missing data, failed tools, unavailable services
What the automated recommendation was: score, level, reasoning
Whether human review occurred: who reviewed, when, what they decided
What disclosures are required: TRID timing, state-specific requirements
The complete tool call history: every tool invocation with inputs and outputs

This audit trail is not a nice-to-have — it is a regulatory requirement. The RiskAssessment model, ComplianceResult model, and callback tracer together produce this record. The final_decision_node assembles it into the format that gets persisted to DocumentDB.

---

## 4. What Differentiates This From a Demo

Many AI agent tutorials produce demos that look impressive but would fail in production. Here is what makes your system production-grade:

**Typed state throughout.** Data flows as Pydantic-validated typed dictionaries, not strings. DTI is a float, not "about 40%." FICO is an integer, not "around 710." Downstream consumers can rely on data types and field presence.

**Deterministic where possible.** Tool calculations are pure Python — calculate_dti returns the same result every time. Routing edges are Python functions — should_escalate always returns the same result for the same state. The LLM is used for reasoning and judgment, not for math or routing.

**Isolated failures.** Each node handles its own errors. A credit bureau timeout does not crash document review. A graph database failure does not prevent basic risk scoring. The system degrades gracefully rather than failing completely.

**Auditability.** Every decision has a traceable path: which data was used, which tools were called, which policies were cited, what the reasoning was. This is not just logging — it is structured data that satisfies regulatory examination.

**Human oversight.** The system recommends, it does not decide unilaterally for borderline cases. MANUAL_REVIEW escalation with persistent human-in-the-loop ensures that uncertain decisions get human judgment.

**Cost predictability.** Each evaluation has a bounded cost ($0.025-0.035). No runaway LLM calls, no infinite loops, no unbounded token consumption. max_iterations on every agent, focused tool sets, and deterministic routing keep costs predictable.

**Resumability.** Checkpointing after every node means no work is lost on failure. A crashed evaluation resumes from the last checkpoint, not from scratch. Human reviews that take days do not require keeping processes alive.

---

## 5. Q&A

### Q: How does the final_decision_node know what happened in every other node?

It reads the complete state. Every prior node has written its output to a specific state field. final_decision reads borrower_package, document_review, risk_assessment, compliance_result, errors, and the human decision (if applicable). The state IS the communication mechanism — final_decision does not call any other node, it reads what they all produced.

### Q: What if I want to add a fifth agent later (e.g., fraud detection)?

Add a new node to the graph, add an edge connecting it to the appropriate point (probably after fetch_data, in parallel with doc_review and risk_scoring), add a new state field for its output, and update final_decision to read the new field. Existing nodes do not change. This is the benefit of the graph architecture — adding a node is adding a box and an arrow, not rewriting the pipeline.

### Q: How do I monitor this system in production?

Three layers. Layer 1: LangSmith tracing captures every LLM call, tool invocation, and agent reasoning across all nodes. Layer 2: CloudWatch metrics from ECS Fargate track container health, memory, CPU. Layer 3: custom metrics written by your nodes — evaluation count, success/failure rates, average latency per node, cost per evaluation, human review rate. Week 5 Day 5 covers observability in detail.

### Q: Can this system handle 10,000 evaluations per day?

Yes. Each evaluation is independent — no shared state between evaluations. Horizontal scaling: add more Fargate tasks. Bottleneck is LLM API throughput (Bedrock has rate limits per account). At 10,000/day with 15-second average, you need approximately 2 concurrent evaluations per second. A single Fargate task handles this. For burst capacity, auto-scale to 3-5 tasks.

### Q: The graph has 6 checkpoints per evaluation. At 10,000/day that is 60,000 checkpoints. Is Redis okay?

Yes. At 10 KB per checkpoint, 60,000 checkpoints = 600 MB. With 7-day TTL, maximum storage is 4.2 GB. A standard Redis instance (r6g.large) has 13 GB memory. Plenty of headroom. Completed evaluation checkpoints can be deleted immediately (only interrupted evaluations need persistence), further reducing storage.

### Q: What happens if Bedrock has an outage during peak hours?

Every node has retry logic (3 attempts with exponential backoff). If retries fail, the node writes an error to state and sets its output to None. Downstream nodes handle None gracefully. The pipeline produces a partial result with explicit error documentation. Checkpointing ensures that completed nodes do not need to re-run when Bedrock recovers. For critical outages, the system automatically routes all evaluations to MANUAL_REVIEW since automated assessment is unavailable.

---

## 6. Summary

### What You Have After This Weekend

| Component | Details |
|-----------|---------|
| Sub-agents | 4 (FetchData, DocReview, RiskScoring, Compliance) |
| Total tools | 20+ across all agents |
| Data sources | 3 (calculations, RAG vector DB, Neo4j graph) |
| LLM models | 2 (Haiku for calc/fetch, Sonnet for vision/legal) |
| Graph nodes | 6 (4 agents + human_review + final_decision) |
| Parallel branches | 2 (fetch_data + doc_review simultaneously) |
| Conditional edges | 2+ (doc skip, escalation, optional loan type routing) |
| Checkpoint store | MemorySaver dev, Redis production |
| Error handling | Per-node try/except, fatal error routing, graceful degradation |
| Human-in-the-loop | interrupt/resume for MANUAL_REVIEW |
| Streaming | Node-by-node progress updates |
| Audit trail | Complete regulatory-grade documentation |
| Est. cost per eval | $0.025-0.035 |
| Est. time per eval | 10-15 seconds (excluding human review) |

### Week 5 Preview

| Day | Topic |
|-----|-------|
| Day 1 | MCP — Model Context Protocol |
| Day 2 | A2A — Agent-to-Agent Protocol |
| Day 3 | Bedrock Guardrails |
| Day 4 | AWS Textract hybrid integration |
| Day 5 | Error handling, retries, circuit breakers, observability |
| Weekend | Full production hardening build |

The core intelligence is complete. Weeks 5-6 harden it for production and deploy it.

---

## 7. Assignment Tasks

### Task 1 — Finalize State Definition
Update src/orchestrator/state.py with the complete state including all agent output fields, control fields, error tracking with reducers, timestamps per node, and graph_version.

### Task 2 — Finalize All Node Functions
Update src/orchestrator/nodes.py with all six nodes, each with try/except error handling. doc_review handles empty documents. human_review uses interrupt(). final_decision assembles complete report.

### Task 3 — Finalize Edge Functions
Update src/orchestrator/edges.py with fatal error routing (fetch failure), escalation routing (manual review), and any dynamic routing.

### Task 4 — Build the Complete Graph
Update src/orchestrator/graph.py with all nodes, parallel edges, conditional edges, checkpointing, and compile. Export create_underwriting_graph().

### Task 5 — Create Runner with Three Scenarios
Create src/exercises/week4_weekend_orchestrator.py testing: strong application (APPROVE), weak application (DENY), borderline (MANUAL_REVIEW with interrupt/resume). Use streaming. Print timing, tool calls, cost estimates.

### Task 6 — Create Report Formatter
Update src/pipeline/report_formatter.py to produce complete audit-ready underwriting decision report from final state.

### Task 7 — Integration Tests
Create tests/test_orchestrator.py with 8 test cases: happy path, parallel verification, doc skip, fatal error, compliance override, interrupt/resume, checkpoint persistence, error accumulation.

### Task 8 — Update Documentation
All SKILL.md files, architecture decisions doc, deployment doc.

### Task 9 — Git Commit
Comprehensive commit message covering the complete orchestrator.
"""

with open("week4_weekend.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")