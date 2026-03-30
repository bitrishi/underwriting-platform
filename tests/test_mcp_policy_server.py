"""Tests for MCP policy server integration."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from src.exercises.week5_day1_mcp import MCPPolicyAgent
from src.mcp.policy_server import run_policy_lookup


def _extract_text(result) -> str:
    chunks: list[str] = []
    for item in getattr(result, "content", []) or []:
        if isinstance(item, types.TextContent):
            chunks.append(item.text)
    return "\n".join(chunks)


def test_run_policy_lookup_uses_fake_response(monkeypatch):
    monkeypatch.setenv("MCP_POLICY_SERVER_FAKE_RESPONSE", "FAKE POLICY RESPONSE")
    output = run_policy_lookup("Any question")
    assert output == "FAKE POLICY RESPONSE"


def test_mcp_stdio_roundtrip_for_policy_tool(monkeypatch):
    monkeypatch.setenv("MCP_POLICY_SERVER_FAKE_RESPONSE", "ROUNDTRIP POLICY RESULT")
    server_script = Path("src/mcp/policy_server.py").resolve()

    async def _run_roundtrip() -> str:
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_script)],
            env={
                **os.environ,
                "MCP_POLICY_SERVER_FAKE_RESPONSE": "ROUNDTRIP POLICY RESULT",
            },
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert any(t.name == "search_lending_policies" for t in tools.tools)

                result = await session.call_tool(
                    "search_lending_policies",
                    {"query": "DTI rules", "jurisdiction": "federal", "loan_type": "all"},
                )
                return _extract_text(result)

    text = asyncio.run(_run_roundtrip())
    assert "ROUNDTRIP POLICY RESULT" in text


def test_week5_agent_calls_mcp_policy_server():
    server_script = Path("src/mcp/policy_server.py").resolve()
    agent = MCPPolicyAgent(server_script=server_script, python_executable=sys.executable)

    original = os.environ.get("MCP_POLICY_SERVER_FAKE_RESPONSE")
    os.environ["MCP_POLICY_SERVER_FAKE_RESPONSE"] = "AGENT MCP RESULT"
    try:
        response = asyncio.run(agent.ask_policy("What are FHA policy requirements?"))
    finally:
        if original is None:
            os.environ.pop("MCP_POLICY_SERVER_FAKE_RESPONSE", None)
        else:
            os.environ["MCP_POLICY_SERVER_FAKE_RESPONSE"] = original

    assert "search_lending_policies" in response["tool_names"]
    assert response["is_error"] is False
    assert "AGENT MCP RESULT" in response["result_text"]
