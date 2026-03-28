"""Deterministic compliance tools for disclosure and audit checks."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import tool


DecisionType = Literal["APPROVE", "DENY", "MANUAL_REVIEW"]


@tool
def check_disclosure_requirements(
    decision: DecisionType,
    state: str,
    is_new_application: bool,
) -> dict[str, Any]:
    """Determine required borrower disclosures from decision and jurisdiction.

    This deterministic check maps underwriting outcomes to TRID/ECOA/FCRA
    disclosure obligations plus a minimal set of state-specific notices.

    Args:
        decision: Final recommendation (`APPROVE`, `DENY`, `MANUAL_REVIEW`).
        state: Property state (for example `texas`).
        is_new_application: Whether this is a new application event.

    Returns:
        Dictionary containing required disclosures and a blocking-violations list.
        Returns an `error` key if inputs are invalid.
    """
    try:
        normalized_decision = decision.upper().strip()
        normalized_state = state.lower().strip()

        if normalized_decision not in {"APPROVE", "DENY", "MANUAL_REVIEW"}:
            raise ValueError("decision must be APPROVE, DENY, or MANUAL_REVIEW")
        if not normalized_state:
            raise ValueError("state must be a non-empty jurisdiction string")

        disclosures: list[dict[str, Any]] = []
        blocking_violations: list[str] = []

        if is_new_application:
            disclosures.append(
                {
                    "disclosure": "Loan Estimate",
                    "regulation": "TRID",
                    "timing": "Within 3 business days of application",
                    "required": True,
                }
            )

        if normalized_decision == "DENY":
            disclosures.extend(
                [
                    {
                        "disclosure": "Adverse Action Notice",
                        "regulation": "ECOA / Regulation B",
                        "timing": "Within 30 days of decision",
                        "required": True,
                    },
                    {
                        "disclosure": "Credit Score Disclosure",
                        "regulation": "FCRA",
                        "timing": "With adverse action notice",
                        "required": True,
                    },
                ]
            )

        if normalized_decision == "APPROVE":
            disclosures.append(
                {
                    "disclosure": "Closing Disclosure",
                    "regulation": "TRID",
                    "timing": "At least 3 business days before closing",
                    "required": True,
                }
            )

        if normalized_state == "texas":
            disclosures.append(
                {
                    "disclosure": "Texas Section 50(a)(6) Notice",
                    "regulation": "Texas Constitution",
                    "timing": "At least 12 days before closing",
                    "required": True,
                }
            )

        if normalized_decision == "DENY" and is_new_application is False:
            blocking_violations.append(
                "Denial decision recorded without new-application context; verify ECOA timing window."
            )

        return {
            "required_disclosures": disclosures,
            "blocking_violations": blocking_violations,
            "detail": f"Computed {len(disclosures)} disclosure requirement(s).",
        }
    except Exception as exc:
        return {
            "required_disclosures": [],
            "blocking_violations": [f"disclosure_check_error: {exc}"],
            "error": str(exc),
        }


@tool
def verify_audit_trail(risk_assessment: str) -> dict[str, Any]:
    """Check whether underwriting output contains a complete audit trail.

    The check is deterministic and keyword-based to ensure stable behavior in
    tests and orchestrator routing.

    Args:
        risk_assessment: Serialized risk assessment text or JSON string.

    Returns:
        Dictionary with completeness flag, per-check map, and missing elements.
        Returns an `error` key for invalid inputs.
    """
    try:
        if not isinstance(risk_assessment, str):
            raise TypeError("risk_assessment must be a string")

        lowered = risk_assessment.lower()
        checks = {
            "has_fico_citation": "fico" in lowered,
            "has_dti_citation": "dti" in lowered or "debt-to-income" in lowered,
            "has_ltv_citation": "ltv" in lowered or "loan-to-value" in lowered,
            "has_reasoning": "reason" in lowered or "because" in lowered,
            "has_recommendation": any(
                token in risk_assessment.upper()
                for token in ("APPROVE", "DENY", "MANUAL_REVIEW")
            ),
        }

        complete = all(checks.values())
        missing = [name for name, passed in checks.items() if not passed]

        return {
            "complete": complete,
            "checks": checks,
            "missing": missing,
            "detail": "Audit trail complete" if complete else f"Missing: {', '.join(missing)}",
        }
    except Exception as exc:
        return {
            "complete": False,
            "checks": {},
            "missing": ["audit_trail_unavailable"],
            "detail": f"Audit trail verification failed: {exc}",
            "error": str(exc),
        }