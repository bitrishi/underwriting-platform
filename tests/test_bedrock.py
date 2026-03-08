"""Tests for Bedrock LLM configuration and setup."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_aws import ChatBedrock

from src.config.bedrock import create_llm
from src.config.settings import settings


class TestCreateLLM:
    """Test suite for create_llm() function."""
    
    def test_create_llm_returns_chat_bedrock_instance(self) -> None:
        """Test that create_llm() returns a ChatBedrock instance."""
        # We mock the actual Bedrock API call to avoid AWS costs
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            llm = create_llm()
            
            # Verify ChatBedrock was instantiated
            assert mock_bedrock.called, "ChatBedrock should be instantiated"
            # The return value should be the mock instance
            assert isinstance(mock_bedrock.return_value, MagicMock)
    
    def test_create_llm_uses_correct_model_id(self) -> None:
        """Test that create_llm() uses the model ID from settings."""
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            create_llm()
            
            # Verify ChatBedrock was called with the correct model_id
            call_kwargs = mock_bedrock.call_args.kwargs
            assert call_kwargs['model_id'] == settings.bedrock_model_id, \
                f"Expected model_id={settings.bedrock_model_id}, got {call_kwargs['model_id']}"
    
    def test_create_llm_uses_correct_region(self) -> None:
        """Test that create_llm() uses the AWS region from settings."""
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            create_llm()
            
            # Verify ChatBedrock was called with the correct region_name
            call_kwargs = mock_bedrock.call_args.kwargs
            assert call_kwargs['region_name'] == settings.aws_region, \
                f"Expected region_name={settings.aws_region}, got {call_kwargs['region_name']}"
    
    def test_create_llm_default_temperature(self) -> None:
        """Test that create_llm() uses temperature=0 by default."""
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            create_llm()
            
            # Check model_kwargs for temperature
            call_kwargs = mock_bedrock.call_args.kwargs
            model_kwargs = call_kwargs['model_kwargs']
            assert model_kwargs['temperature'] == 0, \
                f"Expected temperature=0, got {model_kwargs['temperature']}"
    
    def test_create_llm_default_max_tokens(self) -> None:
        """Test that create_llm() uses max_tokens=1024 by default."""
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            create_llm()
            
            # Check model_kwargs for max_tokens
            call_kwargs = mock_bedrock.call_args.kwargs
            model_kwargs = call_kwargs['model_kwargs']
            assert model_kwargs['max_tokens'] == 1024, \
                f"Expected max_tokens=1024, got {model_kwargs['max_tokens']}"
    
    def test_create_llm_custom_temperature(self) -> None:
        """Test that create_llm() accepts custom temperature."""
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            custom_temp = 0.7
            create_llm(temperature=custom_temp)
            
            call_kwargs = mock_bedrock.call_args.kwargs
            model_kwargs = call_kwargs['model_kwargs']
            assert model_kwargs['temperature'] == custom_temp, \
                f"Expected temperature={custom_temp}, got {model_kwargs['temperature']}"
    
    def test_create_llm_custom_max_tokens(self) -> None:
        """Test that create_llm() accepts custom max_tokens."""
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            custom_tokens = 2048
            create_llm(max_tokens=custom_tokens)
            
            call_kwargs = mock_bedrock.call_args.kwargs
            model_kwargs = call_kwargs['model_kwargs']
            assert model_kwargs['max_tokens'] == custom_tokens, \
                f"Expected max_tokens={custom_tokens}, got {model_kwargs['max_tokens']}"
    
    def test_create_llm_all_custom_parameters(self) -> None:
        """Test that create_llm() respects all custom parameters."""
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            create_llm(temperature=0.5, max_tokens=512)
            
            call_kwargs = mock_bedrock.call_args.kwargs
            
            # Verify all parameters
            assert call_kwargs['model_id'] == settings.bedrock_model_id
            assert call_kwargs['region_name'] == settings.aws_region
            assert call_kwargs['model_kwargs']['temperature'] == 0.5
            assert call_kwargs['model_kwargs']['max_tokens'] == 512


class TestSettingsIntegration:
    """Test that create_llm() correctly uses settings module."""
    
    def test_settings_has_required_fields(self) -> None:
        """Test that settings contains all required fields."""
        assert hasattr(settings, 'aws_region'), "settings should have aws_region"
        assert hasattr(settings, 'bedrock_model_id'), "settings should have bedrock_model_id"
        assert isinstance(settings.aws_region, str), "aws_region should be a string"
        assert isinstance(settings.bedrock_model_id, str), "bedrock_model_id should be a string"
    
    def test_settings_values_non_empty(self) -> None:
        """Test that settings values are not empty."""
        assert settings.aws_region, "aws_region should not be empty"
        assert settings.bedrock_model_id, "bedrock_model_id should not be empty"
    
    def test_bedrock_model_id_is_valid_format(self) -> None:
        """Test that bedrock_model_id is in valid Bedrock model format."""
        # Valid formats: "provider.model-name-v1:0"
        assert ":" in settings.bedrock_model_id, \
            "bedrock_model_id should include model version indicator (:)"
        assert any(provider in settings.bedrock_model_id.lower() 
                   for provider in ["anthropic", "amazon", "meta", "cohere"]), \
            "bedrock_model_id should reference a known provider"


class TestCreateLLMIntegration:
    """Integration tests for create_llm with settings."""
    
    def test_create_llm_respects_environment_settings(self) -> None:
        """Test that create_llm() reads from correct settings."""
        # This test verifies the actual settings are loaded correctly
        # (not mocked, but doesn't call AWS)
        with patch('src.config.bedrock.ChatBedrock') as mock_bedrock:
            mock_bedrock.return_value = MagicMock(spec=ChatBedrock)
            
            create_llm()
            
            call_kwargs = mock_bedrock.call_args.kwargs
            
            # Verify the settings values are passed
            assert call_kwargs['model_id'] == settings.bedrock_model_id
            assert call_kwargs['region_name'] == settings.aws_region
            
            # Verify they match expected patterns
            assert "us-" in settings.aws_region or "eu-" in settings.aws_region, \
                "aws_region should be a valid AWS region"
