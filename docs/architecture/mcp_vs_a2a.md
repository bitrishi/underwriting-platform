# MCP vs A2A In This Underwriting System

## Short Answer

- Use **MCP** for agent-to-tool connectivity.
- Use **A2A** for agent-to-agent connectivity across system boundaries.

They are complementary, not competing.

## 1. Current Repo Mapping

### MCP-aligned interactions (tool access)

Examples from this codebase:
- `search_lending_policies` exposed via MCP server (`src/mcp/policy_server.py`)
- Future MCP candidates from `src/tools/`: borrower data fetch, graph retrieval, compliance lookups

Why MCP here:
- Standardized tool schema and invocation
- Good fit for connecting one agent to many data/tool providers

### A2A-aligned interactions (external agent collaboration)

Potential external interactions:
- Underwriting agent delegates appraisal completion to valuation agent
- Underwriting agent requests title remediation from title agent
- Underwriting agent sends boarding package to servicing agent

Why A2A here:
- Discovery via Agent Card
- Long-running task lifecycle and asynchronous updates
- Opaque execution across independent agent systems

## 2. Concrete Scenarios

### Scenario A: Internal policy lookup during risk scoring

- Need: `risk_scoring` node needs regulation snippets.
- Best fit: MCP tool call (`search_lending_policies`) from underwriting system.
- Why: This is agent-to-tool retrieval, not delegation to another autonomous agent.

### Scenario B: Request appraisal from external valuation provider

- Need: Ask external appraisal system to produce a report and revision updates.
- Best fit: A2A task (`sendMessage`) with streaming/push updates.
- Why: This is agent-to-agent delegation with independent lifecycle.

### Scenario C: Final decision event broadcast to many downstream systems

- Need: fan-out notification to analytics, servicing, and monitoring.
- Best fit: EventBridge event publication (can coexist with A2A/MCP).
- Why: This is pub/sub distribution, not capability discovery or tool invocation.

## 3. Decision Matrix

| Question | Choose MCP when... | Choose A2A when... |
|---|---|---|
| Who are you talking to? | A tool/data provider | Another autonomous agent system |
| Interaction style | Function-like call with tool schema | Task-oriented collaboration with agent semantics |
| Discovery mechanism | Tool listing from MCP server | Agent Card discovery |
| Async model | Tool call/response (some streaming support via client runtime) | Native task lifecycle, streaming, polling, push notifications |
| Ownership boundary | Usually same org platform/tool teams | Often cross-team or cross-organization agent boundaries |

## 4. Integration Pattern For This Repo

1. Keep LangGraph as internal orchestrator.
2. Use MCP for tool adapters (policy, data, graph tools).
3. Introduce A2A for cross-system agent delegation only.
4. Emit enterprise events (for observability/choreography) via EventBridge alongside either approach.

## 5. Practical Rule

If you need a calculator/API/query, use MCP.
If you need another agent to reason, negotiate, and own a long-running task, use A2A.
