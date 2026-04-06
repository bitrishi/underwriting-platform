# Graph Versioning Strategy

## Goal
Allow safe graph evolution (new nodes, changed routes, new policies) without breaking in-flight underwriting executions.

## Versioning Approach
- Use explicit graph versions (for example `v1`, `v2`, `v3`) in orchestrator code.
- Persist `graph_version` with each execution thread.
- Resume an interrupted thread with the same graph version that started it.

## Rules
1. Never change routing semantics for existing in-flight thread versions.
2. Introduce new behavior behind a new version entry point.
3. Keep old versions runnable until all in-flight executions complete or expire.
4. Record version metadata in final report/audit output.

## Compatibility Tiers
- Backward-compatible change:
  - Add non-routing state fields.
  - Add optional report sections.
- Version-required change:
  - Add/remove/reorder nodes in active path.
  - Change conditional edge logic.
  - Change human-loop semantics.

## Runtime Selection
- New execution: choose latest stable version unless caller pins a version.
- Resume execution: force previously stored version.

## Storage Recommendation
- Persist per-thread metadata:
  - `thread_id`
  - `graph_version`
  - `created_at`
  - `status` (`running|interrupted|completed|failed`)

## Deployment Pattern
1. Deploy `vN+1` alongside `vN`.
2. Route only new threads to `vN+1`.
3. Continue resuming `vN` threads on `vN`.
4. Retire `vN` after no active threads remain.

## Testing Matrix
- For each version, test:
  - conventional path
  - fha path
  - interrupt/resume path
  - loop safety limit

This strategy prevents checkpoint corruption and ensures reproducible audit trails across version transitions.
