# LangSmith Good vs Bad Evaluation Comparison

## Scope
Compared two traces in project `underwriting-dev`:

- Good case (clear approve):
  - thread: `compare-approve-1775319372`
  - root run: `019d5947-d231-7b43-b0f2-090a0553dc91`
  - nodes reached final decision directly

- Borderline bad case (manual review escalation):
  - thread: `compare-manual-1775319372`
  - root run: `019d5947-f579-7e52-a2ce-5ca4d044c18e`
  - escalated to `human_review`

## Side-by-Side Summary

| Aspect | Good (APPROVE) | Borderline (MANUAL_REVIEW path) |
|---|---|---|
| Root duration | ~9.03s | ~6.66s |
| Node sequence | `doc_review -> fetch_data -> risk_scoring -> compliance -> final_decision` | `doc_review -> fetch_data -> risk_scoring -> compliance -> human_review` |
| Risk reasoning | `95/100 -> APPROVE` | `0/100 -> DENY` then escalated to manual review |
| Compliance summary | `override=NONE` | `override=NONE` |
| RAG tool usage | `search_lending_policies` | `search_lending_policies` + `verify_compliance_requirement` |

## Which Tools Differed

### Shared tools (both traces)
- `fetch_data`: `pull_borrower_data`, `pull_credit_report`, `pull_employment_history`, `search_lending_policies`
- `risk_scoring`: `calculate_dti`, `calculate_ltv`
- `compliance`: `check_disclosure_requirements`, `verify_audit_trail`

### Differing tools
- `compliance` node:
  - Good case: no `verify_compliance_requirement`
  - Borderline case: includes `verify_compliance_requirement`

Why this happened:
- Borderline case had a deny/manual-review style recommendation, so compliance executed the critical legal verification branch.

## Which RAG Results Differed

### Good trace RAG output
- `search_lending_policies` returned Texas state policy context from:
  - `data/policies/texas_state_rules.txt`

### Borderline trace RAG output
- `search_lending_policies` returned broader conventional policy context from:
  - `data/policies/fannie_mae_guidelines.txt`
- `verify_compliance_requirement` returned:
  - `INSUFFICIENT DATA — Cannot verify from available documents`

Interpretation:
- In the borderline trace, the system attempted an additional compliance RAG verification and found insufficient grounding, which is a classic indicator for escalation and manual handling.

## Where Reasoning Diverged

### Good trace (`risk_scoring.reasoning`)
`Base score from criteria: 100/100. Penalty applied: 5 points. Final score: 95/100 -> APPROVE. Industry technology default rate 4.0% contributed 5 penalty points.`

### Borderline trace (`risk_scoring.reasoning`)
`Base score from criteria: 33/100. Penalty applied: 45 points. Final score: 0/100 -> DENY. Industry technology default rate 4.0% contributed 5 penalty points.`

Primary divergence drivers:
- Lower borrower quality in APP-002 inputs (credit/income/debt profile).
- Missing document coverage in borderline case (only W2 supplied), increasing penalty/risk friction.
- Additional compliance verification call in borderline path, with insufficient evidence from RAG.

## Debugging Workflow Learned (Production Practice)
When debugging production issues, compare a good and bad trace by this order:

1. Compare node path first (did one path escalate to human/manual?).
2. Compare tool set per node (which tool was called only in failing case?).
3. Compare RAG retrieval outputs and source docs (did context change or become insufficient?).
4. Compare reasoning fields (`risk_assessment.reasoning`, compliance summaries) to identify decision pivot points.

This pair of traces demonstrates exactly that pattern:
- the bad trace introduces an extra compliance verification step,
- returns insufficiently grounded RAG evidence,
- and diverges in risk reasoning from `APPROVE` to `DENY/MANUAL_REVIEW` path.
