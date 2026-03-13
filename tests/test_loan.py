"""Tests for LoanApplication model."""

import pytest
from src.models.application import LoanApplication


class TestLoanApplicationCalculateDTI:
    """Test suite for DTI property and calculation."""    
    def test_calculate_dti_with_known_values(self) -> None:
        """Test DTI calculation with known values."""
        # expected DTI = 0.20 for given inputs
        app = LoanApplication(
            borrower_name="John Doe",
            loan_amount=300000,
            fico_score=750,
            monthly_debt=2000,
            annual_income=120000,
            property_value=350000,
            employment_years=5,
        )
        
        dti = app.dti
        assert dti == pytest.approx(0.2), "DTI should be 0.2 (20%)"
    
    def test_calculate_dti_high_debt(self) -> None:
        """Test DTI with high monthly debt."""
        # annual_income=100000 (8333/month), monthly_debt=3000
        # DTI = 3000 / 8333 ≈ 0.36 (36%)
        app = LoanApplication(
            borrower_name="Jane Smith",
            loan_amount=200000,
            fico_score=720,
            monthly_debt=3000,
            annual_income=100000,
            property_value=250000,
            employment_years=3,
        )
        
        dti = app.dti
        assert dti == pytest.approx(3000 / (100000 / 12)), "DTI calculation incorrect"
        assert dti > 0.35, "DTI should be above 35%"
    
    def test_calculate_dti_zero_income_validation_error(self) -> None:
        """Annual income must be >0; zero income should raise validation error."""
        with pytest.raises(Exception) as exc_info:
            LoanApplication(
                borrower_name="No Income",
                loan_amount=100000,
                fico_score=600,
                monthly_debt=1000,
                annual_income=0,
                property_value=100000,
                employment_years=0,
            )
        assert "annual_income" in str(exc_info.value), "Zero income should trigger validation error"    
    def test_calculate_dti_zero_debt(self) -> None:
        """Test DTI calculation with no monthly debt."""
        app = LoanApplication(
            borrower_name="No Debt",
            loan_amount=150000,
            fico_score=800,
            monthly_debt=0,
            annual_income=80000,
            property_value=200000,
            employment_years=2,
        )
        
        dti = app.dti
        assert dti == 0.0, "DTI should be 0 with no debt"


class TestLoanApplicationIsEligible:
    """Test suite for is_eligible() method."""
    
    def test_is_eligible_excellent_profile(self) -> None:
        """Test eligibility with excellent credit profile."""
        app = LoanApplication(
            borrower_name="Excellent Borrower",
            loan_amount=300000,
            fico_score=800,
            monthly_debt=1000,
            annual_income=150000,
            property_value=400000,
            employment_years=10,
        )
        
        assert app.is_eligible() is True, "Should be eligible with excellent FICO and low DTI"
    
    def test_is_eligible_borderline_fico_680(self) -> None:
        """Test eligibility at borderline FICO of 680 (below 700 threshold)."""
        app = LoanApplication(
            borrower_name="Borderline FICO",
            loan_amount=200000,
            fico_score=680,  # Just below 700 threshold
            monthly_debt=2000,
            annual_income=120000,  # DTI ≈ 0.2 (good)
            property_value=220000,
            employment_years=4,
        )
        
        dti = app.dti
        assert dti < 0.36, "DTI should be acceptable"
        assert app.is_eligible() is False, "Should NOT be eligible with FICO < 700"
    
    def test_is_eligible_exactly_700_fico(self) -> None:
        """Test eligibility at exact FICO threshold of 700."""
        app = LoanApplication(
            borrower_name="Threshold FICO",
            loan_amount=250000,
            fico_score=700,  # Exactly at 700 threshold
            monthly_debt=2500,
            annual_income=120000,  # DTI ≈ 0.25 (good)
            property_value=300000,
            employment_years=6,
        )
        
        assert app.is_eligible() is True, "Should be eligible with FICO >= 700"
    
    def test_is_eligible_high_dti_43_percent(self) -> None:
        """Test eligibility with DTI at 43% (above 36% threshold)."""
        # To get DTI ≈ 0.43, we need monthly_debt/monthly_income = 0.43
        # Example: annual_income=100000 (8333/month), monthly_debt=3583
        # DTI = 3583 / 8333 ≈ 0.43 (43%)
        app = LoanApplication(
            borrower_name="High DTI",
            loan_amount=400000,
            fico_score=750,  # Good FICO
            monthly_debt=3583,
            annual_income=100000,  # DTI ≈ 0.43 (43%)
            property_value=450000,
            employment_years=2,
        )
        
        dti = app.dti
        assert dti > 0.36, "DTI should exceed 36% threshold"
        assert app.is_eligible() is False, "Should NOT be eligible with DTI > 36%"
    
    def test_is_eligible_exactly_36_dti(self) -> None:
        """Test eligibility at exact DTI threshold of 36%."""
        # annual_income=100000 (8333/month), monthly_debt=3000
        # DTI = 3000 / 8333 ≈ 0.36 (exactly 36%)
        app = LoanApplication(
            borrower_name="Threshold DTI",
            loan_amount=300000,
            fico_score=750,
            monthly_debt=3000,
            annual_income=100000,  # DTI ≈ 0.36
            property_value=325000,
            employment_years=5,
        )
        
        dti = app.dti
        assert dti == pytest.approx(0.36, abs=0.001), "DTI should be ~36%"
        # Note: is_eligible() uses strict < 0.36, so at exactly 0.36 it's NOT eligible
        assert app.is_eligible() is False, "Should NOT be eligible with DTI >= 36%"
    
    def test_is_eligible_low_fico_low_dti(self) -> None:
        """Test eligibility when FICO is low but DTI is good."""
        app = LoanApplication(
            borrower_name="Low FICO Good DTI",
            loan_amount=200000,
            fico_score=650,  # Below threshold
            monthly_debt=1500,
            annual_income=120000,  # DTI ≈ 0.15 (excellent)
            property_value=210000,
            employment_years=2,
        )
        
        assert app.is_eligible() is False, "Should NOT be eligible regardless of DTI if FICO < 700"
    
    def test_is_eligible_high_fico_high_dti(self) -> None:
        """Test eligibility when FICO is excellent but DTI is high."""
        app = LoanApplication(
            borrower_name="High FICO Bad DTI",
            loan_amount=500000,
            fico_score=800,  # Excellent
            monthly_debt=4000,
            annual_income=100000,  # DTI ≈ 0.48 (too high)
            property_value=600000,
            employment_years=8,
        )
        
        dti = app.dti
        assert dti > 0.36, "DTI should exceed threshold"
        assert app.is_eligible() is False, "Should NOT be eligible regardless of FICO if DTI >= 36%"
    
    def test_is_eligible_both_edge_cases_fail(self) -> None:
        """Test eligibility when BOTH FICO and DTI fail at edge cases."""
        app = LoanApplication(
            borrower_name="Both Failed",
            loan_amount=400000,
            fico_score=699,  # Just below 700
            monthly_debt=3600,
            annual_income=100000,  # DTI ≈ 0.43 (above 0.36)
            property_value=420000,
            employment_years=1,
        )
        
        assert app.is_eligible() is False, "Should NOT be eligible when either condition fails"


class TestLoanApplicationIntegration:
    """Integration tests for LoanApplication."""
    
    def test_application_lifecycle(self) -> None:
        """Test the complete lifecycle of a loan application."""
        app = LoanApplication(
            borrower_name="Complete Tester",
            loan_amount=250000,
            fico_score=750,
            monthly_debt=2000,
            annual_income=120000,
            property_value=300000,
            employment_years=3,
        )
        
        # Calculate DTI
        dti = app.dti
        assert isinstance(dti, float), "DTI should be a float"
        
        # Check eligibility
        eligible = app.is_eligible()
        assert isinstance(eligible, bool), "is_eligible() should return bool"
        
        # Verify logic consistency
        if app.fico_score >= 700 and dti < 0.36:
            assert eligible is True, "Logic should be consistent"
        else:
            assert eligible is False, "Logic should be consistent"
