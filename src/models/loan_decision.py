from dataclasses import dataclass


@dataclass
class LoanDecision:
    """Decision outcome for a loan application."""
    
    decision: bool
    confidence: float
    reasons: list[str]

    def __str__(self) -> str:
        """Return a human-readable decision summary."""
        status = "Approved" if self.decision else "Denied"
        reasons_str = ", ".join(self.reasons) if self.reasons else "No details provided"
        return f"Loan {status} (Confidence: {self.confidence:.2%})\nReasons: {reasons_str}"
        