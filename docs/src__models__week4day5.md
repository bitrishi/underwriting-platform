md_content = """# Week 4, Day 5: Advanced LangGraph — Subgraphs, Streaming & Dynamic Routing

## Session Overview
**Date:** Week 4, Day 5
**Topic:** Advanced LangGraph patterns — subgraphs for modular complexity, streaming for real-time progress, dynamic routing for different loan types, graph cycles for iterative workflows, and graph versioning for production deployment.
**Prerequisites:** Week 4 Day 1-4 (LangGraph fundamentals, parallel execution, error handling, human-in-the-loop)

---

## 1. Subgraphs: Graphs Inside Graphs

### 1.1 Why Subgraphs Exist

Your current orchestrator is a flat graph — all six nodes at the same level. As the system grows (more agents, more conditions, more loan types), this flat structure becomes hard to manage. Subgraphs solve this by nesting graphs inside nodes.

Think of your Kuber architecture. You do not have one giant service with 200 endpoints. You have separate services (core, sync, dependency evaluator), each with their own internal logic. The outer system calls a service; the service internally handles its own complexity. A subgraph is the same principle — your orchestrator calls "risk_scoring" as one node, but internally risk_scoring is its own graph with multiple steps and conditional logic.

### 1.2 When to Use Subgraphs

Use subgraphs when a single node's logic has its own conditional branching, error handling, or multi-step sequencing that benefits from graph-style orchestration. If Risk Scoring needs to "calculate metrics, then check if any are borderline, then selectively query knowledge graph only for borderline criteria, then synthesize" — that conditional internal flow is a subgraph candidate.

Use subgraphs for reusability. A "document processing" subgraph that classifies, extracts, and validates can be reused across different outer graphs — underwriting pipeline, refinance pipeline, HELOC pipeline.

Use subgraphs for team ownership. Risk team owns their subgraph, Compliance team owns theirs. Outer orchestrator calls subgraphs as nodes. Team boundaries map to subgraph boundaries — same principle as microservice team ownership.

### 1.3 When NOT to Use Subgraphs

Do not use subgraphs for simple nodes. If fetch_data just calls one agent and returns, wrapping it adds complexity with zero benefit. Do not use subgraphs prematurely. Start flat. When a node becomes complex enough that you write nested conditionals inside it, that is the signal to extract. Same as the microservices rule: start monolith, extract when complexity demands it.

### 1.4 State Mapping Between Parent and Subgraph

The subgraph has its own state type, potentially different from the parent. Data is mapped at the boundary: parent state fields to subgraph initial state on entry, subgraph output fields to parent state on exit. This mapping is explicit.

Java analogy: calling a downstream microservice. Your service has its own DTOs. The downstream service has its own. You map between them at the boundary — request DTO to downstream input, downstream response to your response DTO.

---

## 2. Streaming Through the Graph

### 2.1 Three Layers of Streaming

Layer 1 is token streaming from the LLM API. Individual words appearing as the model generates them. This is what you see in chat interfaces and Claude Code. Every LLM API supports this natively. LangGraph does not add or control this.

Layer 2 is tool call streaming at the agent level. The agent thinking, calling a tool, receiving a result. This is what verbose=True shows in AgentExecutor — the ReAct loop streamed as it happens.

Layer 3 is node completion streaming at the graph level. This is LangGraph-specific. It streams orchestration progress — which node completed, what state was produced, which node starts next. When you see Claude Code showing "Searching files... Reading main.py... Writing changes..." — that is the same pattern as Layer 3.

### 2.2 Why Streaming Matters

For the API and UI: instead of a loading spinner for 15 seconds, users see incremental progress. "Fetching borrower data... Done. Reviewing documents... Done." This significantly improves perceived performance.

For debugging: streaming shows exactly where failures occur. "fetch_data completed, doc_review completed, risk_scoring started... timeout." Immediate diagnosis without log diving.

For cost monitoring: each streamed event can include token usage. Costs visible in real-time as they accumulate across nodes.

### 2.3 Streaming Modes

LangGraph provides three streaming modes. "values" mode streams the complete accumulated state after each node. "updates" mode streams only the changes from each node. "events" mode streams fine-grained events including individual LLM tokens within nodes.

For production APIs, "updates" mode is most useful. The UI receives node completions with their outputs — each update is a partial result displayed immediately.

### 2.4 Streaming and Human-in-the-Loop

When the graph hits interrupt(), the stream yields an interrupt event. The caller explicitly knows the graph paused and receives the interrupt message. Cleaner than checking return values for interrupt markers.

---

## 3. Dynamic Routing

### 3.1 Data-Driven Routing

Instead of hardcoding node connections, load routing configuration based on input data. Different loan types need different pipelines: conventional goes through standard flow, FHA needs additional FHA compliance, jumbo needs enhanced risk scoring.

Build the graph dynamically based on loan type rather than building one giant graph with every possible node. Each graph instance is deterministic once constructed — the dynamism is in WHICH graph is built, not in how it executes.

Java analogy: Spring profiles. Application loads different bean configurations based on environment or request type. Wiring changes, but each configuration is deterministic once loaded.

### 3.2 Map-Reduce for Batch Processing

For portfolio review evaluating 50 loans simultaneously: a map node fans out to process each loan independently (parallel), a reduce node aggregates results into summary statistics. Each loan goes through the full pipeline independently.

### 3.3 LLM-Based Routing: When to Actually Use It

Most routing should be deterministic. Use LLM routing only when the decision genuinely requires judgment that cannot be encoded in simple rules. A triage node at the start that examines unusual document combinations and decides "standard flow" vs "complex flow" is a valid use of LLM routing. One LLM routing call at the pipeline start is acceptable. LLM routing at every edge would be slow and expensive.

The principle: LLM routing at decision points requiring human-like judgment. Deterministic routing everywhere else.

---

## 4. Graph Cycles

### 4.1 When Cycles Are Needed

Your current graph is acyclic. But the human review loop needs cycles: human says "get a more recent credit report," graph goes BACK to fetch_data, re-runs risk_scoring, returns to human_review.

LangGraph supports cycles. You add an edge from human_review back to fetch_data. The graph loops: fetch, risk, compliance, human_review, fetch, risk, compliance, human_review, final_decision. Each iteration has updated state (new credit report changes risk score).

### 4.2 Guarding Against Infinite Loops

A cycle without termination loops forever. Always include max_iterations as safety limit. For human review loop, set 3-5 maximum iterations. After 3 rounds of additional data requests, escalate to supervisor.

### 4.3 When Cycles Are Appropriate

Use cycles for iterative refinement — human requests more info, agent retries with different parameters, quality check fails triggering reprocessing. Cycles should be exception paths, not primary flow. A well-designed pipeline completes in one pass for the common case.

---

## 5. Graph Versioning

### 5.1 The Problem

You have 50 loans paused at human_review on graph v1. You deploy v2 which adds a new node. When the human responds to a v1 loan, the resume tries to load a v1 checkpoint into a v2 graph. The structure does not match.

### 5.2 The Solution

Version your graphs. Include graph_version in state and thread_id (e.g., "APP-001-v1"). Keep old graph definitions available until their checkpoints expire. New evaluations use v2. Old evaluations complete on v1. TTL-based expiry means no migration needed.

Same challenge as database migrations in microservices. Either migrate old data to new format, or maintain backward compatibility. For checkpoints, TTL-based expiry is the simplest approach.

---

## 6. Production Deployment: One Service vs Lambda Per Node

### 6.1 Why NOT Lambda Per Node

Cold start latency: 500ms-3s per Lambda invocation. With 5 nodes, that is 2.5-15s of pure overhead added to every evaluation. State transfer overhead: serialize to checkpoint store, invoke next Lambda, read state — adds 20-100ms per handoff. Dependency duplication: each Lambda needs the full LangChain package (200-500MB per function). LangGraph does not natively support distributed Lambda execution.

### 6.2 The Recommended Architecture

The entire LangGraph pipeline runs as ONE service on ECS Fargate. All nodes execute in the same process. Inter-node communication is in-memory (microseconds). Redis for checkpointing (crash recovery only, not in the hot path).

The Fargate container handles 100-200 concurrent evaluations. Auto-scale tasks based on queue depth. Zero cold start overhead. Zero serialization overhead between nodes.

This is exactly how Kuber services run — long-running containers on Fargate, not individual Lambdas per endpoint.

### 6.3 When Lambda Per Node Does Make Sense

If one node is dramatically more expensive (document review with Sonnet vision uses 10x compute), extract THAT ONE node as a separate service to scale independently. But do not split all nodes — just the bottleneck. If multiple pipelines share nodes, deploy shared nodes as independent services. But this is service architecture, not Lambda-per-node.

---

## 7. Q&A

### Q: Is Claude/Copilot streaming the same as LangGraph streaming?

Related but different layers. Claude's word-by-word text is token-level streaming from the LLM API (Layer 1). LangGraph adds node-level streaming on top (Layer 3) — which agent is running, when it finished, what it produced. Claude Code showing "Searching files... Writing changes..." is closest to Layer 3 — orchestration progress through a multi-step workflow.

### Q: Is "I tried but cannot" the infinite loop thing?

Partially. Three mechanisms cause agents to stop: max_iterations limit hit (safety guard against loops), the LLM genuinely reasoning it cannot help (legitimate conclusion, not a loop), and error accumulation after repeated tool failures (circuit breaker pattern). Your system handles this with try/except per node and conditional edges routing to final_decision on fatal failures.

### Q: Should each node be a Lambda?

No for most cases. Cold starts add 2-15s overhead. State transfer adds latency. Dependencies are duplicated. The recommended architecture: one ECS Fargate service running the full pipeline, all nodes in-process, Redis for crash recovery. Extract individual nodes as separate services only if they become bottlenecks. Same pattern as Kuber services.

### Q: When should I extract a subgraph?

When a node's internal logic has its own conditional branching or multi-step sequencing. If the node is a simple agent call, keep it flat. Same rule as microservices — extract when internal complexity justifies it, not before.

### Q: Does streaming add overhead?

Minimal. Event serialization and transmission are negligible compared to LLM call latency. Streaming improves perceived performance even if total time is unchanged because users see progress immediately.

### Q: Can cycles cause infinite loops?

Yes. Always include max_iterations as safety limit. For human review loops, 3-5 iterations maximum. After that, escalate to supervisor.

### Q: How do I handle graph versioning with pending human reviews?

Version your graphs. Include graph_version in thread_id. Keep old graph definitions until checkpoints expire via TTL. No migration needed.

---

## 8. Summary: Key Concepts

| Concept | What It Does | Java / AWS Equivalent |
|---------|-------------|----------------------|
| Subgraph | Graph nested inside a node | Microservice with internal logic |
| Subgraph state mapping | Maps parent state to/from subgraph state | DTO mapping at service boundary |
| Token streaming (Layer 1) | Words appear as LLM generates | HTTP chunked transfer |
| Node streaming (Layer 3) | Pipeline progress updates | Step Functions execution events |
| "updates" mode | Stream only changes per node | Event sourcing deltas |
| Dynamic routing | Build graph based on input data | Spring profiles |
| Map-reduce | Parallel batch processing with aggregation | Fork-join framework |
| LLM routing | Agent decides next node (use sparingly) | AI-based service mesh routing |
| Graph cycles | Edges that loop back for iteration | Retry/feedback loops |
| max_iterations | Safety limit on cycles | Circuit breaker max retries |
| Graph versioning | Version in thread_id, keep old definitions | Database migration strategy |
| Single Fargate service | Full pipeline in one process | Kuber service architecture |
| Lambda per node (avoid) | Separate function per step | Microfunction antipattern |
"""

with open("week4_day5.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")