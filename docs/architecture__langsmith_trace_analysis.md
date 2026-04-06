# LangSmith Trace Analysis

## Run Context
- Project: `underwriting-dev`
- Target scenario: evaluation that escalates to `MANUAL_REVIEW`
- Input used:
  - `app_id=APP-002`
  - `document_paths=['data/sample_documents/w2_sample.txt']`
  - `loan_type=conventional`
  - `thread_id=manual-review-trace-1775318851`
- Root trace:
  - `run_id=019d593f-e005-7f01-b96c-df9ca7b18c12`
  - `name=LangGraph`
  - `start=2026-04-04T16:07:31.589242`
  - `end=2026-04-04T16:07:38.523068`

## Top-Level Metrics
- Total duration: `6933.83 ms`
- Total tokens (LangSmith usage metadata):
  - input tokens: `0`
  - output tokens: `0`
  - total tokens: `0`
- Total cost (LangSmith): `$0.001904`

Notes:
- Bedrock calls hit legacy-model access errors in this environment, so token usage was not populated on LLM spans.
- Cost still appears in run metadata for parts of the traced execution.

## Which Nodes Ran
Top-level chain children under the `LangGraph` run:
- `fetch_data`
- `doc_review`
- `risk_scoring`
- `compliance`
- `human_review`

This confirms escalation reached `human_review`, i.e., a `MANUAL_REVIEW` path was produced.

## Tools Called Per Node (Agent/Node-Level)
Grouped by nearest node-chain ancestor:

- `fetch_data`
  - `pull_borrower_data`
  - `pull_borrower_data` (second call from deterministic fallback path)
  - `pull_credit_report`
  - `pull_employment_history`
  - `search_lending_policies`

- `doc_review`
  - `classify_document`
  - `extract_document_data`

- `risk_scoring`
  - `calculate_dti`
  - `calculate_ltv`

- `compliance`
  - `check_disclosure_requirements`
  - `verify_audit_trail`
  - `verify_compliance_requirement`

## RAG Retrieval Observations
RAG-related tool outputs captured in trace:

- `search_lending_policies`
  - Returned policy snippets including PMI / LTV content from:
    - `data/policies/fannie_mae_guidelines.txt`
  - This is expected behavior for borrower/policy context enrichment.

- `verify_compliance_requirement`
  - Returned: `INSUFFICIENT DATA — Cannot verify from available documents`
  - Indicates compliance verifier could not fully ground the critical query with retrieved context.

## Final Reasoning Observed
From `risk_scoring` chain output:

- Reasoning text:
  - `Base score from criteria: 33/100. Penalty applied: 45 points. Final score: 0/100 -> DENY. Industry technology default rate 4.0% contributed 5 penalty points.`

From `compliance` chain output:

- Summary:
  - `Compliance complete. override=NONE. blocking_violations=0.`

Interpretation:
- Risk scoring produced a deny-level recommendation with explicit quantitative rationale.
- The orchestration still entered `human_review`, and trace scanning confirms `MANUAL_REVIEW` appears in outputs, so the run followed manual-escalation governance flow.

## Trace Drilldown Example
A representative drilldown path in LangSmith for this run:

1. `LangGraph` (root chain)
2. `risk_scoring` (child chain)
3. Tool spans:
   - `calculate_dti`
   - `calculate_ltv`
4. LLM span(s): `ChatBedrock` (where available)

Similarly for compliance:

1. `LangGraph`
2. `compliance`
3. Tool spans:
   - `check_disclosure_requirements`
   - `verify_audit_trail`
   - `verify_compliance_requirement`
4. RAG verifier output shows insufficient grounding for the critical compliance query.

## Conclusion
This trace demonstrates a full manual-escalation-style underwriting path with auditable node execution, tool-level provenance, and reasoning artifacts. Even with constrained Bedrock access in this environment, LangSmith captured the critical orchestration structure needed for debugging and governance review.
