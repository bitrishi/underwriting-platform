"""Tests for LoanDecision and LoanApplication models."""

import pytest
from pydantic import ValidationError

from src.models.application import LoanApplication
from src.models.decision import LoanDecision


class TestLoanDecisionValidation:
    """Test LoanDecision Pydantic model validation."""

    def test_valid_loan_decision(self):
        """Test that LoanDecision accepts valid data."""
        decision = LoanDecision(
            decision="APPROVED",
            confidence=0.85,
            risk_level="LOW",
            reasons=["Excellent credit score", "Low DTI"],
        )

        assert decision.decision == "APPROVED"
        assert decision.confidence == 0.85
        assert decision.risk_level == "LOW"
        assert decision.reasons == ["Excellent credit score", "Low DTI"]
        assert decision.conditions is None
        assert decision.criteria is None
        assert decision.reasoning_trace is None

    def test_valid_conditional_decision(self):
        """Test conditional approval with conditions."""
        decision = LoanDecision(
            decision="CONDITIONAL_APPROVAL",
            confidence=0.65,
            risk_level="MEDIUM",
            reasons=["Borderline FICO", "DTI acceptable"],
            conditions=["Provide additional documentation", "Verify employment"],
        )

        assert decision.decision == "CONDITIONAL_APPROVAL"
        assert decision.conditions == ["Provide additional documentation", "Verify employment"]

    def test_invalid_confidence_too_high(self):
        """Test that confidence > 1.0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoanDecision(
                decision="APPROVED",
                confidence=2.0,  # Invalid: > 1.0
                risk_level="LOW",
                reasons=["Good credit"],
            )

        assert "confidence" in str(exc_info.value)

    def test_invalid_confidence_negative(self):
        """Test that negative confidence is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoanDecision(
                decision="DECLINE",
                confidence=-0.1,  # Invalid: < 0
                risk_level="HIGH",
                reasons=["Poor credit"],
            )

        assert "confidence" in str(exc_info.value)

    def test_invalid_decision_value(self):
        """Test that invalid decision values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoanDecision(
                decision="MAYBE",  # Invalid: not in allowed values
                confidence=0.5,
                risk_level="MEDIUM",
                reasons=["Unsure"],
            )

        assert "decision" in str(exc_info.value)

    def test_invalid_risk_level(self):
        """Test that invalid risk level is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoanDecision(
                decision="DECLINE",
                confidence=0.3,
                risk_level="UNKNOWN",  # Invalid: not LOW/MEDIUM/HIGH
                reasons=["Bad credit"],
            )

        assert "risk_level" in str(exc_info.value)

    def test_empty_reasons_list(self):
        """Test that empty reasons list is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LoanDecision(
                decision="APPROVED",
                confidence=0.9,
                risk_level="LOW",
                reasons=[],  # Invalid: min_items=1
            )

        assert "reasons" in str(exc_info.value)


class TestLoanApplicationCalculations:
    """Test LoanApplication property calculations."""

    def test_dti_calculation(self):
        """Test DTI calculation with known values."""
        app = LoanApplication(
            borrower_name="Test Borrower",
            loan_amount=200000,
            fico_score=750,
            monthly_debt=2000,
            annual_income=100000,  # Monthly income = 8333.33
            property_value=250000,
            employment_years=3,
        )

        # DTI = 2000 / (100000/12) = 2000 / 8333.33 ≈ 0.24
        expected_dti = 2000 / (100000 / 12)
        assert app.dti == pytest.approx(expected_dti, rel=1e-3)

    def test_dti_zero_income(self):
        """Test DTI with very small income (should be high DTI)."""
        app = LoanApplication(
            borrower_name="Low Income",
            loan_amount=100000,
            fico_score=600,
            monthly_debt=1000,
            annual_income=1,  # Very small positive income
            property_value=100000,
            employment_years=0,
        )

        # With annual_income=1, monthly_income=1/12≈0.083, DTI=1000/0.083≈12000
        # But since income is very small, dti will be very high
        assert app.dti > 1000  # Very high DTI

    def test_ltv_calculation(self):
        """Test LTV calculation."""
        app = LoanApplication(
            borrower_name="Test Borrower",
            loan_amount=200000,
            fico_score=750,
            monthly_debt=2000,
            annual_income=100000,
            property_value=250000,  # LTV = 200000/250000 = 0.8
            employment_years=3,
        )

        assert app.ltv == pytest.approx(0.8, rel=1e-3)

    def test_ltv_zero_property_value(self):
        """Test LTV with very small property value (should be high LTV)."""
        app = LoanApplication(
            borrower_name="Tiny Property",
            loan_amount=100000,
            fico_score=600,
            monthly_debt=1000,
            annual_income=50000,
            property_value=1,  # Very small positive value
            employment_years=1,
        )

        # LTV = 100000/1 = 100000 (very high)
        assert app.ltv > 1000


class TestLoanApplicationPromptString:
    """Test LoanApplication.to_prompt_string() method."""

    def test_to_prompt_string_includes_all_fields(self):
        """Test that to_prompt_string includes all application fields."""
        app = LoanApplication(
            borrower_name="John Doe",
            loan_amount=300000,
            fico_score=780,
            monthly_debt=2500,
            annual_income=120000,
            property_value=400000,
            employment_years=5,
        )

        prompt_str = app.to_prompt_string()

        # Check that all fields are included
        assert "Borrower: John Doe" in prompt_str
        assert "FICO Score: 780" in prompt_str
        assert "Annual Income: $120,000" in prompt_str
        assert "Monthly Debt: $2,500" in prompt_str
        assert "Debt-to-Income Ratio: 25.00%" in prompt_str  # 2500/(120000/12) = 0.25
        assert "Requested Loan Amount: $300,000" in prompt_str
        assert "Property Value: $400,000" in prompt_str
        assert "Loan-to-Value Ratio: 75.00%" in prompt_str  # 300000/400000 = 0.75
        assert "Employment Years: 5" in prompt_str

    def test_to_prompt_string_formatting(self):
        """Test that to_prompt_string has correct multi-line format."""
        app = LoanApplication(
            borrower_name="Jane Smith",
            loan_amount=250000,
            fico_score=720,
            monthly_debt=2000,
            annual_income=100000,
            property_value=300000,
            employment_years=3,
        )

        prompt_str = app.to_prompt_string()

        # Should be multi-line with newlines
        lines = prompt_str.split('\n')
        assert len(lines) == 10  # 9 fields + empty line at end

        # Check specific formatting
        assert lines[0] == "Borrower: Jane Smith"
        assert lines[1] == "FICO Score: 720"
        assert lines[2] == "Annual Income: $100,000"
        assert lines[3] == "Monthly Debt: $2,000"
        assert "Debt-to-Income Ratio:" in lines[4]
        assert "Requested Loan Amount:" in lines[5]
        assert "Property Value:" in lines[6]
        assert "Loan-to-Value Ratio:" in lines[7]
        assert lines[8] == "Employment Years: 3.0"