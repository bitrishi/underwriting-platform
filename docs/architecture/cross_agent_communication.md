# Cross-Agent Communication Design

## Purpose

Define what stays internal to the current underwriting orchestrator (LangGraph shared state) and what should become external agent-to-agent interactions (A2A) if Goldman runs multiple independent agent systems.

## 1. Internal vs External Boundaries

### Internal interactions (today, inside one underwriting system)

These are best kept as in-process graph coordination because they share strongly coupled state and deterministic routing:

- `fetch_data -> risk_scoring`
- `doc_review -> risk_scoring`
- `risk_scoring -> compliance`
- `compliance -> human_review/final_decision`
- `human_review -> fetch_data` loop for additional data

Reasons to keep internal:
- Same trust boundary and codebase
- Tight shared `UnderwritingState` coupling
- Low-latency fan-out/fan-in orchestration
- Easier deterministic replay and audit in one graph execution

### External interactions (future multi-system Goldman architecture)

These are better represented as A2A when systems are independently owned/deployed:

- Underwriting system <-> Appraisal system
- Underwriting system <-> Title/closing system
- Underwriting system <-> Insurance verification system
- Underwriting system <-> Servicing boarding system
- Underwriting system <-> Fraud/KYC specialist agent platform

Reasons to use A2A:
- Cross-team or cross-organization agent boundaries
- Need for capability discovery (Agent Card)
- Long-running delegated tasks with asynchronous status
- Opaque execution requirements between systems

## 2. Mortgage Party Mapping (Goldman Workflow)

| Party | Typical Interaction | Internal (LangGraph state) or External (A2A) | Why |
|---|---|---|---|
| Lender underwriting core | Risk + compliance + decision synthesis | Internal | Core decision pipeline with tightly coupled state and deterministic policy gates |
| Servicer platform | Boarding package, payment setup, post-close handoff | External (A2A preferred) | Different platform ownership and asynchronous handoff lifecycle |
| Appraiser network/system | Order appraisal, receive valuation report/revisions | External (A2A preferred) | Long-running lifecycle with status updates and artifacts (reports) |
| Title company/system | Title search, lien resolution, commitment updates | External (A2A preferred) | Multi-step async process with document artifacts and legal state changes |
| Insurance provider/system | Hazard/flood verification and policy evidence | External (A2A preferred) | Independent provider APIs and asynchronous confirmation flow |

## 3. A2A vs EventBridge vs REST by Interaction Type

| Interaction Type | Best Default | Why | Concrete Underwriting Example |
|---|---|---|---|
| In-process agent collaboration with shared state | LangGraph internal state (not A2A/EventBridge/REST) | Lowest latency + strong deterministic control | `fetch_data` and `doc_review` converge into `risk_scoring` |
| Cross-system delegated agent task needing capability discovery | A2A | Agent Card + task lifecycle + streaming/push updates | Send appraisal request to external valuation agent and track task state |
| Event fan-out, pub/sub notifications, decoupled workflows | EventBridge | Event routing, retries, fan-out subscriptions, low coupling | Publish `loan.decision.finalized` for downstream servicing and analytics consumers |
| Synchronous CRUD/API call to a known service contract | REST | Simple request/response, mature tooling | Fetch static county tax rate or update a known servicing endpoint |
| Long-running external process with partial outputs | A2A (or EventBridge + REST fallback) | Native task model, streaming events, push configs | Title remediation task emits intermediate document artifacts before completion |
| Cross-domain compliance evidence/audit package handoff | A2A + EventBridge | A2A for task protocol, EventBridge for enterprise event distribution | Underwriting sends final compliance packet to servicing agent; event emitted for audit systems |

## 4. Recommended Decision Rules

1. Keep communication internal when all participants are nodes in one orchestrator and share one typed state model.
2. Use A2A when one agent system delegates to another independently owned agent system.
3. Use EventBridge for event broadcast and workflow choreography across many consumers.
4. Use REST for simple synchronous endpoint interactions without agent negotiation or task lifecycle semantics.
