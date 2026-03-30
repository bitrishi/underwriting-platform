"""Tests for Bedrock guardrail configuration and exercise helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.config.bedrock import create_llm, get_guardrail_for_task
from src.exercises.week5_day3_guardrails import summarize_result


def test_get_guardrail_for_task_returns_role_specific_config():
    fetch_cfg = get_guardrail_for_task("fetch_data")
    risk_cfg = get_guardrail_for_task("risk_scoring")
    compliance_cfg = get_guardrail_for_task("compliance")

    assert fetch_cfg is not None
    assert risk_cfg is not None
    assert compliance_cfg is not None

    assert fetch_cfg["guardrailIdentifier"]
    assert fetch_cfg["guardrailVersion"]


def test_create_llm_includes_guardrails_for_agent_task():
    with patch("src.config.bedrock.ChatBedrock") as mock_bedrock:
        mock_bedrock.return_value = MagicMock()

        create_llm(task="compliance", temperature=0)

        kwargs = mock_bedrock.call_args.kwargs
        assert "guardrails" in kwargs
        assert kwargs["guardrails"]["guardrailIdentifier"]
        assert kwargs["guardrails"]["guardrailVersion"]


def test_create_llm_allows_guardrail_override():
    with patch("src.config.bedrock.ChatBedrock") as mock_bedrock:
        mock_bedrock.return_value = MagicMock()

        create_llm(
            task="compliance",
            guardrail_id="override-id",
            guardrail_version="9",
        )

        kwargs = mock_bedrock.call_args.kwargs
        assert kwargs["guardrails"]["guardrailIdentifier"] == "override-id"
        assert kwargs["guardrails"]["guardrailVersion"] == "9"


def test_summarize_result_compacts_response_payload():
    payload = {
        "action": "GUARDRAIL_INTERVENED",
        "actionReason": "Denied topic",
        "outputs": [{"text": "[REDACTED]"}],
        "assessments": [{}, {}],
    }

    summary = summarize_result("pii_redaction", payload)

    assert summary["label"] == "pii_redaction"
    assert summary["action"] == "GUARDRAIL_INTERVENED"
    assert summary["outputs"] == ["[REDACTED]"]
    assert summary["assessmentCount"] == 2
