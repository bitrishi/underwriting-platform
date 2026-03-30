# Underwriting Agent Card Design

## Goal

Define how the underwriting system should present itself to external agents using an A2A Agent Card.

## 1. Capabilities to Advertise

External agents should see high-level business capabilities, not internal node names:

- `loan.eligibility.assess`
- `loan.risk.score`
- `loan.compliance.evaluate`
- `loan.decision.generate`
- `loan.decision.explain`
- `loan.documents.review`

Optional specialized capabilities:
- `loan.fha.compliance.evaluate`
- `loan.manual_review.request`
- `loan.audit.report.get`

## 2. Skill Catalog (Consumer-Facing)

| Skill ID | Description | Input Contract (summary) | Output Contract (summary) |
|---|---|---|---|
| `underwrite_application` | End-to-end underwriting evaluation | borrower profile, loan scenario, optional docs | task with final recommendation + audit trail |
| `score_risk` | Risk scoring only | normalized borrower + credit + employment + property metrics | risk level, score, rationale, supporting evidence |
| `check_compliance` | Compliance-only analysis | loan/product details + jurisdiction + disclosures | pass/fail flags, violations, required remediations |
| `review_documents` | Cross-document consistency checks | list of uploaded docs and metadata | extracted fields, mismatch findings, missing docs |
| `generate_decision_report` | Human-readable summary for downstream systems | task ID or underwriting input payload | structured report + text summary |

## 3. Security and Access Model

Recommended Agent Card declarations:

- Transport: HTTPS endpoint
- Auth: OAuth2 client credentials (service-to-service)
- Optional: mTLS for intra-enterprise high-trust environments
- Scopes:
  - `underwriting.read`
  - `underwriting.decision.write`
  - `underwriting.audit.read`

Access segmentation:
- Servicing agents: decision report + boarding fields
- Sales/origination assistants: eligibility summaries only
- Compliance/audit agents: full audit trail and violation details

## 4. Proposed Agent Card Shape (Example)

```json
{
  "name": "Goldman Underwriting Agent",
  "description": "Evaluates mortgage applications and returns risk, compliance, and decision outputs.",
  "url": "https://underwriting.goldman.internal/a2a",
  "version": "1.0.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true,
    "multiturn": true
  },
  "skills": [
    {
      "id": "underwrite_application",
      "name": "Underwrite Application",
      "description": "Run end-to-end underwriting and produce a final recommendation.",
      "tags": ["mortgage", "underwriting", "risk", "compliance"]
    },
    {
      "id": "review_documents",
      "name": "Review Documents",
      "description": "Validate and cross-check borrower document packages.",
      "tags": ["documents", "validation", "income"]
    }
  ],
  "securitySchemes": {
    "oauth2": {
      "type": "oauth2",
      "flows": {
        "clientCredentials": {
          "tokenUrl": "https://auth.goldman.internal/oauth/token",
          "scopes": {
            "underwriting.read": "Read underwriting outputs",
            "underwriting.decision.write": "Create decision tasks",
            "underwriting.audit.read": "Read audit evidence"
          }
        }
      }
    }
  },
  "security": [{ "oauth2": ["underwriting.read"] }]
}
```

## 5. Design Guidance

1. Keep capabilities stable and business-oriented; avoid exposing internal graph node names.
2. Version skill contracts explicitly; do not introduce breaking schema changes without version bumps.
3. Include async/streaming support in the card for long-running underwriting reviews.
4. Keep sensitive internals opaque; expose only required input/output contracts.
