# Bedrock Guardrails Configuration

## Created Guardrail

- Guardrail name: `underwriting-guardrail-20260329-052008`
- Guardrail ID: `hissb9w0wpbg`
- Guardrail version: `1`
- Region: `us-east-1`

## Why These Guardrail Settings

### Content filters

Configured categories:
- `SEXUAL`: `HIGH`
- `VIOLENCE`: `HIGH`
- `HATE`: `HIGH`
- `INSULTS`: `HIGH`
- `MISCONDUCT`: `HIGH`
- `PROMPT_ATTACK`: `HIGH` for input, `NONE` for output

Rationale:
- Underwriting workflows are enterprise and compliance-sensitive, so high blocking thresholds are appropriate.
- Bedrock currently requires `PROMPT_ATTACK` output strength to be `NONE`; this is a platform constraint, not a policy preference.

### Denied topics

Configured deny topics:
1. `NoPersonalFinancialAdvice`
2. `NoOffTopicRequests`
3. `NoLendingDiscrimination`

Rationale:
- Prevents regulated advice beyond underwriting scope.
- Keeps system within intended domain boundaries.
- Explicitly blocks discriminatory decision patterns and policy violations.

### PII filters (REDACT behavior)

Configured PII entities with `ANONYMIZE` (redact-like behavior):
- `US_SOCIAL_SECURITY_NUMBER`
- `CREDIT_DEBIT_CARD_NUMBER`
- `PHONE`

Rationale:
- These are common sensitive inputs in loan workflows.
- Anonymization preserves utility while preventing direct exposure of raw identifiers.

### Word filters

Configured blocked terms:
- `guaranteed approval`
- `skip income verification`
- `racial quota lending`

Rationale:
- Blocks unsafe or non-compliant phrasing tied to policy bypass and discrimination risk.

### Contextual grounding policy

Configured filters:
- `GROUNDING` threshold `0.85`, action `BLOCK`
- `RELEVANCE` threshold `0.80`, action `BLOCK`

Rationale:
- Forces responses to stay tied to supplied evidence and user query context.
- Helps reduce unsupported claims in high-risk underwriting decisions.

## Per-Agent Guardrail Configurations

Implemented in `src/config/bedrock.py` using per-role guardrail resolution:

- `fetch` role: strict on PII and denied-topic inputs from ingestion pipelines
- `doc_review` role: strict safety + PII controls while processing borrower docs
- `risk` role: strict policy controls to prevent unsafe scoring narratives
- `compliance` role: strictest governance path for regulatory reasoning outputs

Current deployment pins each role to the same guardrail (`hissb9w0wpbg`, version `1`) but keeps separate configuration keys so teams can split role-specific guardrails later without code refactors.

## What Guardrails Cannot Catch Alone

Guardrails are necessary but not sufficient. Additional controls are required:

1. Business-rule validation
- Guardrails do not replace deterministic underwriting rules (DTI/LTV/FICO thresholds, disclosure timing).

2. Model/prompt drift and policy interpretation errors
- Guardrails can block categories and topics, but they cannot guarantee legal correctness of all compliant-looking outputs.

3. Data quality and provenance issues
- Grounding checks help, but cannot fully validate source document correctness or upstream extraction errors.

4. Access control and audit requirements
- Need IAM scoping, request authentication, and immutable audit logs beyond runtime content filtering.

5. Human oversight
- Manual review remains required for borderline/high-risk cases and exception handling.
