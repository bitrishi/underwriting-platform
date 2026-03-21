"""Tests for underwriting tool functions."""

import pytest

from src.tools.underwriting_tools import calculate_dti, calculate_ltv, check_fico_eligibility


class TestCalculateDTI:
    def test_dti_normal_case(self):
        result = calculate_dti.run({"annual_income": 80000, "monthly_debt": 2000})
        assert pytest.approx(result["dti"], rel=1e-3) == 30.0
        assert result["threshold"] == 43
        assert result["pass"] is True
        assert "DTI" in result["detail"]

    def test_dti_edge_exact_threshold(self):
        annual_income = 100000
        monthly_debt = 0.43 * annual_income / 12
        result = calculate_dti.run({"annual_income": annual_income, "monthly_debt": monthly_debt})
        assert pytest.approx(result["dti"], rel=1e-3) == 43.0
        assert result["pass"] is True

    def test_dti_invalid_income_raises(self):
        with pytest.raises(ValueError):
            calculate_dti.run({"annual_income": 0, "monthly_debt": 2000})
        with pytest.raises(ValueError):
            calculate_dti.run({"annual_income": -10000, "monthly_debt": 2000})


class TestCalculateLTV:
    def test_ltv_normal_case(self):
        result = calculate_ltv.run({"loan_amount": 160000, "property_value": 200000})
        assert pytest.approx(result["ltv"], rel=1e-3) == 80.0
        assert result["threshold"] == 80.0
        assert result["requires_pmi"] is False
        assert result["pass"] is True

    def test_ltv_edge_exact_threshold(self):
        result = calculate_ltv.run({"loan_amount": 160000, "property_value": 200000})
        assert result["ltv"] == 80.0
        assert result["requires_pmi"] is False

    def test_ltv_zero_property_raises(self):
        with pytest.raises(ValueError):
            calculate_ltv.run({"loan_amount": 150000, "property_value": 0})


class TestCheckFicoEligibility:
    def test_fico_edge_minimum_threshold(self):
        result = check_fico_eligibility.run({"fico_score": 680})
        assert result["minimum_threshold"] == 680
        assert result["eligible"] is True
        assert result["tier"] == "ACCEPTABLE"

    def test_fico_exact_good_boundary(self):
        result = check_fico_eligibility.run({"fico_score": 700})
        assert result["tier"] == "GOOD"

    def test_fico_exact_excellent_boundary(self):
        result = check_fico_eligibility.run({"fico_score": 740})
        assert result["tier"] == "EXCELLENT"

    def test_fico_invalid_score_raises(self):
        with pytest.raises(ValueError):
            check_fico_eligibility.run({"fico_score": 299})
        with pytest.raises(ValueError):
            check_fico_eligibility.run({"fico_score": 851})
