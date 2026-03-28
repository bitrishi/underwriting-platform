"""Compliance agent for final legal/regulatory validation."""

from __future__ import annotations

from langchain.agents import create_agent

from src.config.bedrock import create_llm
from src.tools.compliance_tools import (
    check_disclosure_requirements,
    verify_audit_trail,
)
from src.tools.policy_tools_v2 import (
    search_lending_policies,
    verify_compliance_requirement,
)
from src.utils.prompt_loader import load_prompt


def create_compliance_agent():
    """Create compliance agent with 2 RAG + 2 deterministic tools.

    Uses Sonnet (`task="compliance"`) for legal reasoning and policy synthesis.
    """
    llm = create_llm(task="compliance")

    tools = [
        verify_compliance_requirement,
        search_lending_policies,
        check_disclosure_requirements,
        verify_audit_trail,
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=load_prompt("compliance"),
    )
