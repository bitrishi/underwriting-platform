"""Integration-style tests for the FetchData agent wiring and behavior."""

from __future__ import annotations

import re

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from src.agents import fetch_data


class FakeAgentRuntime:
    """Deterministic runtime used to emulate create_agent execution."""

    def __init__(self, tools):
        self._tools = {t.name: t for t in tools}

    def _policy_tool(self):
        for name, tool_obj in self._tools.items():
            if "lending_policies" in name:
                return tool_obj
        raise KeyError("No lending policy search tool found in runtime tools")

    def invoke(self, payload: dict, config: dict | None = None) -> dict:
        messages = payload.get("messages", [])
        question = messages[0]["content"] if messages else ""
        match = re.search(r"(APP-\d+)", question)
        app_id = match.group(1) if match else "APP-UNKNOWN"

        borrower = self._tools["pull_borrower_data"].invoke({"app_id": app_id})
        if "error" in borrower:
            return {"messages": [AIMessage(content=f"Missing borrower data: {borrower['error']}")]}

        credit = self._tools["pull_credit_report"].invoke(
            {"ssn_last_four": borrower["ssn_last_four"]}
        )
        employment = self._tools["pull_employment_history"].invoke(
            {"ssn_last_four": borrower["ssn_last_four"]}
        )

        jurisdiction = f"state_{borrower.get('property_state', 'federal')}"
        policies = self._policy_tool().invoke(
            {
                "query": f"mortgage lending policies {borrower.get('property_state', '')}",
                "jurisdiction": jurisdiction,
                "loan_type": "conventional",
            }
        )

        summary = (
            f"app={app_id}; name={borrower['name']}; fico={credit.get('fico_score')}; "
            f"employer={employment.get('employer')}; policies={policies}"
        )
        return {"messages": [AIMessage(content=summary)]}


@pytest.fixture
def fake_policy_tool():
    @tool
    def fake_search_lending_policies(
        query: str,
        jurisdiction: str = "federal",
        loan_type: str = "all",
    ) -> str:
        """Fake policy lookup tool for tests."""
        return f"policy({jurisdiction},{loan_type})"

    return fake_search_lending_policies


def test_create_fetch_data_agent_wires_expected_tools(monkeypatch: pytest.MonkeyPatch, fake_policy_tool) -> None:
    captured: dict = {}

    def fake_create_agent(*, model, tools, system_prompt):
        captured["model"] = model
        captured["tools"] = tools
        captured["system_prompt"] = system_prompt
        return FakeAgentRuntime(tools)

    monkeypatch.setattr(fetch_data, "create_llm", lambda temperature=0: "fake-llm")
    monkeypatch.setattr(fetch_data, "load_prompt", lambda name: f"prompt:{name}")
    monkeypatch.setattr(fetch_data, "search_lending_policies", fake_policy_tool)
    monkeypatch.setattr(fetch_data, "create_agent", fake_create_agent)

    agent = fetch_data.create_fetch_data_agent()

    assert agent is not None
    assert captured["model"] == "fake-llm"
    assert captured["system_prompt"] == "prompt:fetch_data"

    tool_names = [tool.name for tool in captured["tools"]]
    assert tool_names == [
        "pull_borrower_data",
        "pull_credit_report",
        "pull_employment_history",
        "fake_search_lending_policies",
    ]


def test_fetch_data_agent_runs_end_to_end_with_tools(
    monkeypatch: pytest.MonkeyPatch,
    fake_policy_tool,
) -> None:
    monkeypatch.setattr(fetch_data, "create_llm", lambda temperature=0: "fake-llm")
    monkeypatch.setattr(fetch_data, "load_prompt", lambda name: f"prompt:{name}")
    monkeypatch.setattr(fetch_data, "search_lending_policies", fake_policy_tool)
    monkeypatch.setattr(fetch_data, "create_agent", lambda **kwargs: FakeAgentRuntime(kwargs["tools"]))

    agent = fetch_data.create_fetch_data_agent()

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "Gather all underwriting data for application APP-001",
                }
            ]
        }
    )

    assert "messages" in result
    output = result["messages"][-1].content
    assert "app=APP-001" in output
    assert "name=Alice Strong" in output
    assert "fico=740" in output
    assert "employer=TechCorp Inc" in output
    assert "policy(state_texas,conventional)" in output
