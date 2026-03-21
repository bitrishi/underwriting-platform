# tests/test_chain.py

import pytest
from src.models.application import LoanApplication
from src.models.decision import LoanDecision
from src.chains.underwriter_chain import UnderwriterChain


class TestUnderwriterChain:
    """Integration tests for the underwriting chain."""

    @pytest.fixture
    def chain(self):
        return UnderwriterChain()

    @pytest.fixture
    def strong_application(self):
        return LoanApplication(
            borrower_name="Test Strong",
            fico_score=740,
            annual_income=120000,
            monthly_debt=2400,
            loan_amount=350000,
            property_value=440000,
            employment_years=5
        )

    def test_returns_loan_decision(self, chain, strong_application):
        """Chain returns a typed LoanDecision object."""
        result = chain.evaluate_safe(strong_application)
        assert result is not None
        assert isinstance(result, LoanDecision)

    def test_decision_is_valid_literal(self, chain, strong_application):
        """Decision must be APPROVED, DENIED, or MANUAL_REVIEW."""
        result = chain.evaluate_safe(strong_application)
        assert result.decision in ["APPROVED", "DENIED", "MANUAL_REVIEW"]

    def test_confidence_in_range(self, chain, strong_application):
        """Confidence must be between 0 and 1."""
        result = chain.evaluate_safe(strong_application)
        assert 0.0 <= result.confidence <= 1.0

    def test_has_reasoning_trace(self, chain, strong_application):
        """Response must include step-by-step reasoning."""
        result = chain.evaluate_safe(strong_application)
        assert result.reasoning_trace.step_1_fico != ""

    def test_has_reasons(self, chain, strong_application):
        """Response must include at least one reason."""
        result = chain.evaluate_safe(strong_application)
        assert len(result.reasons) >= 1