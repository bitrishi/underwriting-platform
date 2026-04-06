# Deployment Architecture (Orchestrator)

## Target Runtime
- Deploy orchestrator as a containerized service on AWS Fargate.
- One service owns graph execution and exposes API endpoints for start/resume/status.

## Core Components
- Fargate service:
  - Runs LangGraph orchestrator process.
  - Handles streaming and interrupt/resume calls.
- Checkpoint store:
  - Development: `MemorySaver`.
  - Production: Redis-backed checkpointing.
- Data stores:
  - DocumentDB (or equivalent) for persisted underwriting outcomes and reports.
  - Vector store + graph store remain backing dependencies for RAG/knowledge lookups.

## Checkpointing Strategy
- Persist checkpoint state keyed by `thread_id`.
- Resume must reuse the same `thread_id`.
- Keep checkpoint TTL to prevent unbounded growth.

## Scaling Strategy
- Autoscale Fargate tasks on:
  - CPU/memory
  - request rate
  - queue depth (if asynchronous front-door queue is used)
- Ensure idempotent resume handling to avoid duplicate completions.

## Operational Guidance
- Emit per-node timing and routing decision logs.
- Persist `graph_version` with each execution for replay compatibility.
- Track costs via estimated tool/LLM counters in final report metadata.

## Failure Handling
- Node-level try/except captures non-fatal issues in state `errors`.
- Fatal fetch failures route directly to final decision report.
- Human-review interrupt uses checkpoint state for safe process restarts.

## Security
- Use IAM task roles for model/data access.
- Keep PII minimized in logs and messages.
- Encrypt data at rest for checkpoint and result stores.
