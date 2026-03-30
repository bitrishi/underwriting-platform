# MCP Migration Plan For Underwriting Tools

## Goal

Adopt MCP where cross-team reuse, external integration, or runtime tool discovery is valuable, while keeping local deterministic tools as in-process `@tool` functions.

## Current Tool Inventory

From `src/tools/`, we currently expose these families:
- Underwriting calculators: `calculate_dti`, `calculate_ltv`, `check_fico_eligibility`, `check_employment_stability`
- Fetch/data access: `pull_borrower_data`, `pull_credit_report`, `pull_employment_history`
- Policy/compliance retrieval: `search_lending_policies`, `search_compliance_rules`, `verify_compliance_requirement`
- Document analysis: `classify_document`, `extract_document_data`, `compare_documents`, `validate_document_package`
- Knowledge graph: `get_borrower_risk_context`, `find_similar_past_loans`, `get_state_regulations`
- Compliance checks: `check_disclosure_requirements`, `verify_audit_trail`

## Classification: MCP Server Candidate vs Keep Local

### Strong MCP candidates (shared boundary)

These are high-value for sharing across agents/teams and likely to need independent deployment:
- Policy/compliance retrieval tools
  - `search_lending_policies`
  - `search_compliance_rules`
  - `verify_compliance_requirement`
- Data fetch tools backed by external systems
  - `pull_borrower_data`
  - `pull_credit_report`
  - `pull_employment_history`
- Knowledge graph query tools
  - `get_borrower_risk_context`
  - `find_similar_past_loans`
  - `get_state_regulations`

### Keep as local `@tool` (deterministic + low coupling)

These are fast, deterministic, and lightweight enough to keep in-process:
- `calculate_dti`
- `calculate_ltv`
- `check_fico_eligibility`
- `check_employment_stability`
- `check_disclosure_requirements`
- `verify_audit_trail`

### Conditional MCP candidates (phase later)

Document tools should move to MCP only if a dedicated document service is needed:
- `classify_document`
- `extract_document_data`
- `compare_documents`
- `validate_document_package`

Reason: these tools can become compute-heavy and model-dependent, but today they are tightly coupled to local exercise data and execution paths.

## Proposed MCP Server Boundaries

1. `policy-server`
- Exposes policy/compliance retrieval tools.
- First migration target (already implemented in `src/mcp/policy_server.py`).

2. `data-server`
- Exposes borrower/credit/employment fetch tools.
- Add auth and auditing per downstream system requirements.

3. `graph-server`
- Exposes graph traversal and similarity tools.
- Useful for sharing graph context with non-underwriting agents.

4. `document-server` (optional, later)
- Exposes document extraction and validation.
- Consider only when centralizing OCR/vision costs and model routing.

## Migration Order

1. Policy server (lowest risk, highest reuse)
- Move policy retrieval first.
- Keep local fallback paths during transition.

2. Data server (external dependency boundary)
- Move fetch tools behind MCP with standardized schemas.
- Add request/response trace IDs.

3. Graph server (shared intelligence boundary)
- Move graph tools once schema/versioning conventions are stable.

4. Document server (optional)
- Move only if scaling demands independent compute/runtime control.

## Coexistence Strategy

- Use hybrid tooling in each agent:
  - deterministic local `@tool` for simple numeric checks
  - MCP tools for shared/external context providers
- Keep tool names stable to avoid prompt and orchestration churn.
- Use capability checks (`tools/list`) during startup to fail fast if required MCP tools are missing.

## Risks and Controls

- Risk: schema drift across server versions
  - Control: versioned tool contracts and compatibility tests
- Risk: higher latency vs in-process `@tool`
  - Control: keep deterministic calculators local
- Risk: auth complexity for remote servers
  - Control: centralize auth in MCP client configuration and add smoke tests for `initialize` and `tools/call`
