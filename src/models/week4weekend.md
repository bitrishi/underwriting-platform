md_content = """# Week 4, Weekend BUILD: Complete Production Orchestrator

## Session Overview
**Date:** Week 4, Weekend
**Topic:** Assembling the complete multi-agent orchestrator — all four sub-agents wired through LangGraph with parallel execution, conditional routing, error handling, human-in-the-loop, checkpointing, and streaming.
**Prerequisites:** All Week 4 sessions (Days 1-5)

---

## What You Are Building

This is the culmination of four weeks of work. Every component you have built becomes a node in the final graph:

Week 1: Python + Bedrock + prompts + structured output → foundation for every agent
Week 2: LangChain + tools + RAG → FetchData agent (sub-agent #1)
Week 3: Agentic RAG + vision + knowledge graph → Document Review (#2) + Risk Scoring (#3)
Week 4: LangGraph + parallel + routing + compliance → Compliance (#4) + Orchestrator

The weekend build produces a single compiled LangGraph application that:

1. Accepts a loan application ID and optional document paths
2. Runs FetchData and Document Review in PARALLEL (saves 30-40% time)
3. Feeds both outputs into Risk Scoring (uses all three data sources)
4. Runs Compliance verification (can override the recommendation)
5. Conditionally routes to Human Review (for MANUAL_REVIEW cases)
6. Produces a complete underwriting decision with full audit trail
7. Checkpoints after every node (crash recovery)
8. Streams progress to the caller (real-time status updates)
9. Handles errors gracefully at every node (no silent failures)

---

## Assignment Tasks

### Task 1 — Finalize State Definition

Update `src/orchestrator/state.py` with the complete state:
- All fields from all four agents (borrower_package, document_review, risk_assessment, compliance_result)
- Control fields (has_documents, needs_manual_review, loan_type)
- Output fields (final_decision, final_report)
- Error tracking with Annotated list reducer
- Messages with Annotated add_messages reducer
- graph_version field for future versioning
- Timestamps for each node completion (for the audit trail)

### Task 2 — Finalize All Node Functions

Update `src/orchestrator/nodes.py`:
- fetch_data_node: calls FetchData agent, error handling, writes borrower_package
- doc_review_node: handles empty documents gracefully (SKIPPED status), calls Doc Review agent when documents exist
- risk_scoring_node: reads BOTH borrower_package and document_review, calls Risk Scoring agent with all three data sources
- compliance_node: reads risk_assessment, calls Compliance agent, can set needs_manual_review on violation
- human_review_node: uses interrupt() with detailed review summary, writes human decision on resume
- final_decision_node: combines all outputs into complete report with audit trail
- Every node has try/except with errors written to state

### Task 3 — Finalize Edge Functions

Update `src/orchestrator/edges.py`:
- should_continue_after_fetch: routes to fatal_error if borrower_package is None
- should_escalate: routes to human_review if needs_manual_review, otherwise final_decision
- Add any additional routing you need (e.g., loan_type based routing if you implemented dynamic routing from Day 5)

### Task 4 — Build the Complete Graph

Update `src/orchestrator/graph.py`:
- All six nodes registered
- Parallel edges from START to fetch_data and doc_review
- Convergence edges from both to risk_scoring
- Sequential edge from risk_scoring to compliance
- Conditional edge from compliance to human_review or final_decision
- Edge from human_review to final_decision
- Edge from final_decision to END
- Fatal error path from fetch_data to final_decision
- Compile with MemorySaver checkpointer (Redis in production)
- Export create_underwriting_graph() function

### Task 5 — Create the Runner

Create `src/exercises/week4_weekend_orchestrator.py`:
- Run the complete graph for three scenarios:
  - Scenario 1: Strong application with documents (should APPROVE, exercises parallel execution)
  - Scenario 2: Weak application without documents (should DENY, exercises doc_review skip and fatal conditions)
  - Scenario 3: Borderline application (should MANUAL_REVIEW, exercises human-in-the-loop)
- For Scenario 3: capture the interrupt, print the review message, resume with a human decision
- Use streaming mode to show node-by-node progress
- Print timing for each node
- Print the complete audit trail at the end
- Print total tool calls, total LLM calls, estimated cost

### Task 6 — Create the Report Formatter

Update `src/pipeline/report_formatter.py`:
- Takes the final state (all agent outputs + human decision if applicable)
- Produces a complete underwriting decision report:
  - Borrower summary (from FetchData)
  - Document review findings (from Doc Review)
  - Risk assessment with all criteria scores (from Risk Scoring)
  - Compliance verification results (from Compliance)
  - Human review decision and conditions (if applicable)
  - Full audit trail: which nodes ran, timing, tool calls, errors
  - Pipeline metadata: graph version, thread_id, total time, total cost

### Task 7 — Integration Tests

Create `tests/test_orchestrator.py`:
- Test complete happy path (all nodes succeed, no escalation)
- Test parallel execution (verify fetch_data and doc_review both run)
- Test doc_review skip (no documents provided)
- Test fatal error handling (fetch_data fails, pipeline routes to error report)
- Test compliance override (compliance finds violation, forces MANUAL_REVIEW)
- Test interrupt/resume cycle (borderline case, human responds)
- Test checkpoint persistence (verify state survives simulated restart)
- Test error accumulation (multiple nodes encounter non-fatal errors)

### Task 8 — Update Documentation

Update all SKILL.md files:
- src/orchestrator/SKILL.md: complete graph documentation with diagram
- src/agents/SKILL.md: all four agents with their tools and model assignments
- docs/architecture/orchestration_decision.md: why LangGraph, why these agent boundaries
- docs/architecture/deployment.md: Fargate service, Redis checkpointing, auto-scaling

### Task 9 — Git Commit
```bash
git add -A
git commit -m "Week 4: Complete production orchestrator

- LangGraph state machine with 6 nodes
- 4 sub-agents: FetchData, DocReview, RiskScoring, Compliance
- Parallel execution: FetchData + DocReview run simultaneously
- Conditional routing: doc skip, escalation, fatal error paths
- Human-in-the-loop: interrupt/resume for MANUAL_REVIEW
- Checkpointing: MemorySaver (Redis-ready for production)
- Streaming: node-by-node progress updates
- Error handling: per-node try/except, graceful degradation
- Complete audit trail with timing and cost tracking
- 20+ tools across 3 data sources (calc, RAG, graph)
- Integration tests for all execution paths"

git push
```

---

## What You Have After This Weekend

A complete, production-grade multi-agent underwriting system:

4 specialized sub-agents (FetchData, Document Review, Risk Scoring, Compliance)
20+ tools across 3 data sources (calculations, RAG vector DB, Neo4j knowledge graph)
LangGraph orchestrator with parallel execution, conditional routing, and human-in-the-loop
Checkpointing for crash recovery
Streaming for real-time progress
Error handling at every node with graceful degradation
Complete audit trail satisfying regulatory requirements
Multi-model architecture (Haiku for calculations, Sonnet for vision and legal reasoning)

This is the system. Weeks 5-6 add production hardening (MCP, guardrails, Textract, error handling) and deployment (eval testing, FastAPI, Streamlit UI). But the core intelligence — the agents, tools, data sources, and orchestration — is complete.

---

## Week 5 Preview

Week 5: Production Hardening
- Day 1: MCP (Model Context Protocol) — standardized tool connectivity
- Day 2: A2A (Agent-to-Agent Protocol) — cross-system agent communication
- Day 3: Bedrock Guardrails — content filtering, PII protection, topic blocking
- Day 4: AWS Textract integration — hybrid document processing (Textract for standard forms, vision for unstructured)
- Day 5: Error handling, retries, circuit breakers, observability
- Weekend: Full production hardening build

You are on track. Two weeks to go.
"""

with open("week4_weekend.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")