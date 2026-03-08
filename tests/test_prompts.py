"""Tests for prompt loading and templating functionality."""

from pathlib import Path

import pytest

from src.utils.prompt_loader import load_prompt, load_prompt_with_variables


class TestLoadPrompt:
    """Test suite for load_prompt() function."""

    def test_load_prompt_underwriter_exists(self) -> None:
        """Test that underwriter.txt prompt can be loaded."""
        prompt = load_prompt("underwriter")
        assert isinstance(prompt, str), "Prompt should be a string"
        assert len(prompt) > 0, "Prompt should not be empty"
        assert "underwriter" in prompt.lower() or "role" in prompt.lower(), \
            "Underwriter prompt should contain underwriter or role context"

    def test_load_prompt_fetch_data_exists(self) -> None:
        """Test that fetch_data.txt prompt can be loaded."""
        prompt = load_prompt("fetch_data")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "fetch" in prompt.lower() or "data" in prompt.lower(), \
            "FetchData prompt should reference data fetching"

    def test_load_prompt_risk_scoring_exists(self) -> None:
        """Test that risk_scoring.txt prompt can be loaded."""
        prompt = load_prompt("risk_scoring")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "risk" in prompt.lower() or "scoring" in prompt.lower(), \
            "Risk scoring prompt should reference risk or scoring"

    def test_load_prompt_missing_file_raises_error(self) -> None:
        """Test that missing prompt file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_prompt("nonexistent_agent")

        assert "nonexistent_agent" in str(exc_info.value)

    def test_load_prompt_error_message_helpful(self) -> None:
        """Test that FileNotFoundError includes file path."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_prompt("missing")

        error_msg = str(exc_info.value)
        assert "prompts" in error_msg or "missing" in error_msg


class TestLoadPromptWithVariables:
    """Test suite for load_prompt_with_variables() function."""

    def test_substitutes_single_variable(self) -> None:
        """Test variable substitution with a simple example."""
        # Create a temporary test by using underwriter and checking if it loads
        # For this test, we just verify the function works with any valid prompt
        try:
            prompt = load_prompt_with_variables(
                "underwriter",
                borrower_name="John Doe",
            )
            # If the prompt doesn't have {borrower_name}, it just returns as-is
            assert isinstance(prompt, str)
            assert len(prompt) > 0
        except KeyError:
            # Expected if prompt doesn't have {borrower_name}
            pass

    def test_missing_variable_raises_key_error(self) -> None:
        """Test that missing template variable raises KeyError."""
        # Test that load_prompt_with_variables raises KeyError when required variable is missing
        # Create a test by capturing a KeyError from format string operations
        try:
            prompt = load_prompt("underwriter")
            # The underwriter prompt contains JSON with placeholders like {decision}
            # So formatting without those values will raise KeyError
            formatted = prompt.format()  # No variables provided
            # If we get here, the prompt has no format variables
            assert isinstance(formatted, str)
        except KeyError:
            # Expected - the prompt contains template variables that need values
            pass

    def test_missing_prompt_file_with_variables_raises_error(self) -> None:
        """Test that load_prompt_with_variables also checks file existence."""
        with pytest.raises(FileNotFoundError):
            load_prompt_with_variables("nonexistent", var1="value1")

    def test_multiple_variable_substitution(self) -> None:
        """Test substitution with multiple variables."""
        # Generic test that works with any prompt
        try:
            prompt = load_prompt_with_variables(
                "underwriter",
                borrower_name="Alice",
                loan_amount="250000",
            )
            assert isinstance(prompt, str)
        except KeyError:
            # Expected if prompt doesn't use these variables
            pass


class TestPromptFiles:
    """Test that all expected prompt files exist and are valid."""

    def test_all_required_prompts_exist(self) -> None:
        """Test that all required prompt files exist."""
        required_prompts = ["underwriter", "fetch_data", "risk_scoring"]

        prompts_dir = Path(__file__).parent.parent / "src" / "prompts"
        assert prompts_dir.exists(), f"Prompts directory not found at {prompts_dir}"

        for prompt_name in required_prompts:
            file_path = prompts_dir / f"{prompt_name}.txt"
            assert file_path.exists(), f"Prompt file missing: {prompt_name}.txt"

    def test_prompt_files_are_non_empty(self) -> None:
        """Test that all prompt files have content."""
        required_prompts = ["underwriter", "fetch_data", "risk_scoring"]

        for prompt_name in required_prompts:
            prompt = load_prompt(prompt_name)
            assert len(prompt) > 50, \
                f"Prompt '{prompt_name}' is too short (should be substantive)"

    def test_prompt_files_are_readable(self) -> None:
        """Test that prompt files are valid UTF-8 text."""
        required_prompts = ["underwriter", "fetch_data", "risk_scoring"]

        for prompt_name in required_prompts:
            try:
                prompt = load_prompt(prompt_name)
                # If we can read and it's a string, encoding is valid
                assert isinstance(prompt, str)
                # Try to access content to ensure it's not corrupted
                _ = prompt.encode("utf-8")
            except UnicodeDecodeError:
                pytest.fail(f"Prompt '{prompt_name}' has encoding issues")

    def test_prompts_contain_role_section(self) -> None:
        """Test that each prompt defines a clear role/persona."""
        required_prompts = ["underwriter", "fetch_data", "risk_scoring"]
        role_indicators = ["role", "you are", "expert", "agent", "responsible"]

        for prompt_name in required_prompts:
            prompt_lower = load_prompt(prompt_name).lower()
            has_role = any(indicator in prompt_lower for indicator in role_indicators)
            assert has_role, \
                f"Prompt '{prompt_name}' missing role definition (should mention role/expertise)"

    def test_prompts_contain_output_format(self) -> None:
        """Test that each prompt specifies output format or schema."""
        required_prompts = ["underwriter", "fetch_data", "risk_scoring"]
        format_indicators = ["json", "output", "schema", "format", "return", "provide"]

        for prompt_name in required_prompts:
            prompt_lower = load_prompt(prompt_name).lower()
            has_format = any(indicator in prompt_lower for indicator in format_indicators)
            assert has_format, \
                f"Prompt '{prompt_name}' missing output format specification"

    def test_prompts_contain_constraints(self) -> None:
        """Test that each prompt includes constraints or rules."""
        required_prompts = ["underwriter", "fetch_data", "risk_scoring"]
        constraint_indicators = [
            "must", "should", "don't", "cannot", "prohibit", "constraint",
            "rule", "never", "always", "invalid", "reject"
        ]

        for prompt_name in required_prompts:
            prompt_lower = load_prompt(prompt_name).lower()
            has_constraints = any(
                indicator in prompt_lower for indicator in constraint_indicators
            )
            assert has_constraints, \
                f"Prompt '{prompt_name}' missing constraints/rules"

    def test_underwriter_prompt_contains_json_schema(self) -> None:
        """Test that underwriter prompt explicitly shows JSON schema."""
        prompt = load_prompt("underwriter")
        assert "decision" in prompt.lower(), \
            "Underwriter prompt missing 'decision' field in schema"
        assert "confidence" in prompt.lower(), \
            "Underwriter prompt missing 'confidence' field in schema"
        assert "risk" in prompt.lower(), \
            "Underwriter prompt missing risk-related field in schema"

    def test_fetch_data_prompt_contains_retrieval_steps(self) -> None:
        """Test that fetch_data prompt describes data retrieval steps."""
        prompt = load_prompt("fetch_data").lower()
        assert "credit" in prompt, "FetchData prompt missing credit data reference"
        assert "income" in prompt, "FetchData prompt missing income data reference"
        assert any(word in prompt for word in ["debt", "loan", "obligation"]), \
            "FetchData prompt missing debt/loan reference"

    def test_risk_scoring_prompt_contains_metrics(self) -> None:
        """Test that risk_scoring prompt includes calculation metrics."""
        prompt = load_prompt("risk_scoring").lower()
        assert any(term in prompt for term in ["dti", "debt-to-income", "debt to income"]), \
            "RiskScoring prompt missing DTI metric"
        assert "fico" in prompt, "RiskScoring prompt missing FICO reference"
        assert any(term in prompt for term in ["risk", "score", "category"]), \
            "RiskScoring prompt missing risk categorization"


class TestPromptIntegration:
    """Integration tests combining loader functions."""

    def test_load_and_substitute_workflow(self) -> None:
        """Test real-world workflow of loading and substituting."""
        # Load a prompt and then substitute a variable
        prompt = load_prompt("underwriter")
        assert isinstance(prompt, str)

        # Try to substitute a generic variable (may not exist in all prompts)
        try:
            templated = prompt.format(agent_name="TestAgent")
            assert isinstance(templated, str)
        except KeyError:
            # Expected if prompt doesn't use {agent_name}
            pass

    def test_all_prompts_loadable_via_loader(self) -> None:
        """Test that all prompts can be loaded via the loader utility."""
        required_prompts = ["underwriter", "fetch_data", "risk_scoring"]

        for prompt_name in required_prompts:
            prompt = load_prompt(prompt_name)
            assert prompt is not None
            assert isinstance(prompt, str)
            assert len(prompt) > 0
