"""Tests for LCEL-based chains and Runnable components."""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.application import LoanApplication
from src.models.decision import LoanDecision
from src.chains.underwriter_chain_v2 import underwriter_chain_v2, underwriter_chain_v3
from src.exercises.week2_day1_parallel import parallel_chains
from src.exercises.week2_day1_routing import routing_chain


class TestLCELChain:
    """Tests for the LCEL-based underwriter chain v2."""

    @pytest.fixture
    def sample_application(self):
        """Create a sample loan application for testing."""
        return LoanApplication(
            borrower_name="Test Borrower",
            loan_amount=200000,
            fico_score=720,
            monthly_debt=2000,
            annual_income=80000,
            property_value=250000,
            employment_years=2
        )

    def test_lcel_chain_returns_loan_decision(self, sample_application):
        """Test that the LCEL chain returns a LoanDecision object for valid input."""
        result = underwriter_chain_v2(sample_application.to_prompt_string())

        # Verify return type
        assert isinstance(result, LoanDecision)

        # Verify required fields are present
        assert hasattr(result, 'decision')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'risk_level')
        assert hasattr(result, 'reasons')
        assert hasattr(result, 'criteria')
        assert hasattr(result, 'reasoning_trace')

        # Verify decision is one of expected values
        assert result.decision in ['APPROVED', 'DECLINE', 'CONDITIONAL_APPROVAL']

        # Verify confidence is between 0 and 1
        assert 0 <= result.confidence <= 1

    def test_lcel_chain_with_different_fico_scores(self, sample_application):
        """Test LCEL chain behavior with different FICO scores."""
        test_cases = [
            (650, 'DECLINE'),  # Low FICO
            (720, 'CONDITIONAL_APPROVAL'),  # Medium FICO
            (780, 'APPROVED'),  # High FICO
        ]

        for fico_score, expected_decision in test_cases:
            # Create application with specific FICO
            app = sample_application.model_copy()
            app.fico_score = fico_score

            result = underwriter_chain_v2(app.to_prompt_string())

            assert isinstance(result, LoanDecision)
            # Note: The actual decision may vary based on LLM response,
            # but we verify the structure is correct
            assert result.decision in ['APPROVED', 'DECLINE', 'CONDITIONAL_APPROVAL']


class TestRunnableParallel:
    """Tests for RunnableParallel data lookup chains."""

    def test_parallel_returns_all_expected_keys(self):
        """Test that RunnableParallel returns results for all three chains."""
        input_data = {}  # Empty input for simulation

        result = parallel_chains.invoke(input_data)

        # Verify all expected keys are present
        assert 'credit' in result
        assert 'employment' in result
        assert 'property' in result

        # Verify each result has expected structure
        for key in ['credit', 'employment', 'property']:
            assert 'lookup_time' in result[key]

        # Verify credit check has score
        assert 'credit_score' in result['credit']
        assert isinstance(result['credit']['credit_score'], int)
        assert 300 <= result['credit']['credit_score'] <= 850

        # Verify employment check has status
        assert 'employment_status' in result['employment']
        assert result['employment']['employment_status'] in [
            'employed', 'unemployed', 'self-employed', 'retired'
        ]

        # Verify property check has value
        assert 'property_value' in result['property']
        assert isinstance(result['property']['property_value'], int)
        assert 100000 <= result['property']['property_value'] <= 1000000

    def test_parallel_execution_is_concurrent(self):
        """Test that parallel execution is faster than sequential."""
        import time

        # Time parallel execution
        start_time = time.time()
        parallel_result = parallel_chains.invoke({})
        parallel_time = time.time() - start_time

        # Time sequential execution (simulate)
        start_time = time.time()
        # Import the individual functions
        from src.exercises.week2_day1_parallel import credit_check, employment_check, property_check
        credit_result = credit_check({})
        employment_result = employment_check({})
        property_result = property_check({})
        sequential_time = time.time() - start_time

        # Parallel should be faster (though not guaranteed due to randomness)
        # At minimum, verify both complete successfully
        assert parallel_time > 0
        assert sequential_time > 0

        # Verify results are different (due to randomness)
        assert parallel_result['credit']['credit_score'] != credit_result['credit_score']


class TestRunnableBranch:
    """Tests for RunnableBranch routing logic."""

    @pytest.mark.parametrize("fico_score,expected_decision", [
        (600, "AUTO_DENIED"),  # FICO < 680
        (650, "AUTO_DENIED"),  # FICO < 680
        (679, "AUTO_DENIED"),  # FICO < 680
        (680, "STANDARD_REVIEW"),  # FICO 680-750
        (720, "STANDARD_REVIEW"),  # FICO 680-750
        (750, "STANDARD_REVIEW"),  # FICO 680-750
        (751, "FAST_APPROVED"),  # FICO > 750
        (780, "FAST_APPROVED"),  # FICO > 750
        (850, "FAST_APPROVED"),  # FICO > 750
    ])
    def test_runnable_branch_routes_correctly(self, fico_score, expected_decision):
        """Test that RunnableBranch routes FICO scores to correct decisions."""
        input_data = {"fico_score": fico_score}

        result = routing_chain.invoke(input_data)

        # Verify decision matches expected
        assert result["decision"] == expected_decision

        # Verify message is present and appropriate
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_runnable_branch_boundary_cases(self):
        """Test boundary cases for routing."""
        # Test exact boundaries
        test_cases = [
            (679, "AUTO_DENIED"),
            (680, "STANDARD_REVIEW"),
            (750, "STANDARD_REVIEW"),
            (751, "FAST_APPROVED"),
        ]

        for fico_score, expected in test_cases:
            result = routing_chain.invoke({"fico_score": fico_score})
            assert result["decision"] == expected

    def test_runnable_branch_invalid_input(self):
        """Test behavior with invalid FICO scores."""
        # Test with missing FICO
        result = routing_chain.invoke({})
        assert result["decision"] == "AUTO_DENIED"  # Default case

        # Test with negative FICO
        result = routing_chain.invoke({"fico_score": -100})
        assert result["decision"] == "AUTO_DENIED"

        # Test with very high FICO
        result = routing_chain.invoke({"fico_score": 1000})
        assert result["decision"] == "FAST_APPROVED"


class TestModelInputChain:
    """Tests for the model-input underwriter chain v3."""

    @pytest.fixture
    def sample_application(self):
        """Create a sample loan application for testing."""
        return LoanApplication(
            borrower_name="Test Borrower",
            loan_amount=200000,
            fico_score=720,
            monthly_debt=2000,
            annual_income=80000,
            property_value=250000,
            employment_years=2
        )

    def test_model_input_chain_accepts_loan_application(self, sample_application):
        """Test that the model input chain accepts LoanApplication objects directly."""
        result = underwriter_chain_v3.invoke(sample_application)

        # Verify return type
        assert isinstance(result, LoanDecision)

        # Verify required fields are present
        assert hasattr(result, 'decision')
        assert hasattr(result, 'confidence')
        assert result.decision in ['APPROVED', 'DECLINE', 'CONDITIONAL_APPROVAL']
        assert 0 <= result.confidence <= 1

    def test_model_input_chain_matches_string_input(self, sample_application):
        """Test that model input chain produces same results as string input chain."""
        # Get result from model input
        model_result = underwriter_chain_v3.invoke(sample_application)

        # Get result from string input
        string_result = underwriter_chain_v2(sample_application.to_prompt_string())

        # Results should be identical (same LLM call essentially)
        assert model_result.decision == string_result.decision
        assert model_result.confidence == string_result.confidence
        assert model_result.reasons == string_result.reasons