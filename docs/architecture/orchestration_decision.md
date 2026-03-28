# Orchestration Decision: LangGraph vs CrewAI

## Decision
Choose **LangGraph** as the default orchestration framework for the underwriting system.

## Why LangGraph for This System
- Deterministic execution graph: underwriting requires explicit sequencing, joins, and branch control.
- Parallel-safe fan-out/fan-in: `fetch_data` and `doc_review` can run concurrently and converge predictably.
- Typed shared state: easier validation, testing, and audit traceability across node boundaries.
- Strong failure routing: node-level try/except and conditional paths support graceful degradation.
- Compliance-first behavior: escalation and manual review routing are first-class graph decisions.
- Better production operability: explicit topology is easier to inspect, replay, and monitor.

## When CrewAI Is a Better Fit
- Fast role-based prototypes where speed of iteration matters more than rigid control flow.
- Lightweight collaborative assistants with fewer tools and limited compliance risk.
- Exploratory workflows where natural-language task decomposition is preferred.

## Comparison Table (Week 4 Day 3 Observations)

| Factor | CrewAI | LangGraph |
|---|---|---|
| Authoring speed for linear flow | Faster | Moderate |
| Deterministic routing clarity | Medium | High |
| Structured state handling | Medium | High |
| Parallel branch semantics | Medium | High |
| Error isolation and recovery design | Medium | High |
| Compliance and audit suitability | Medium | High |
| Best use in this repo | Prototyping | Production orchestration |

## Final Guidance
Use LangGraph for production underwriting decisions. Use CrewAI for quick experiments, idea validation, and non-critical assistant-style tasks.
