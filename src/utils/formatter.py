# src/utils/formatter.py

from src.models.decision import LoanDecision
from src.models.application import LoanApplication


def format_decision_report(
    application: LoanApplication,
    decision: LoanDecision
) -> str:
    """
    Format an underwriting decision as a human-readable report.

    This is the audit trail that regulators, senior reviewers,
    and the UI will display.

    Args:
        application: The original loan application
        decision: The validated decision from the chain

    Returns:
        Formatted string report
    """
    # Header
    lines = [
        "=" * 60,
        f"  UNDERWRITING DECISION: {decision.decision}",
        f"  Confidence: {decision.confidence:.0%}  |  Risk: {decision.risk_level}",
        "=" * 60,
        "",
        f"  Borrower: {application.borrower_name}",
        f"  FICO: {application.fico_score}  |  "
        f"DTI: {application.dti:.1f}%  |  "
        f"LTV: {application.ltv:.1f}%",
        "",
        "-" * 60,
        "  CRITERIA CHECKS",
        "-" * 60,
    ]

    # Criteria checks
    if decision.criteria:
        for check in decision.criteria:
            status = "PASS" if check.passed else "FAIL"
            icon = "✅" if check.passed else "❌"
            lines.append(f"  {icon} {check.name.upper()}: {status}")
    else:
        lines.append("  No detailed criteria checks available")

    # Reasoning trace
    lines.extend([
        "",
        "-" * 60,
        "  REASONING TRACE",
        "-" * 60,
    ])
    if decision.reasoning_trace and decision.reasoning_trace.steps:
        for i, step in enumerate(decision.reasoning_trace.steps, 1):
            lines.append(f"  {i}. {step}")
    else:
        lines.append("  No reasoning trace available")

    # Summary reasons
    lines.extend([
        "",
        "-" * 60,
        "  SUMMARY",
        "-" * 60,
    ])
    for reason in decision.reasons:
        lines.append(f"  • {reason}")

    lines.append("=" * 60)
    return "\n".join(lines)