"""Week 5 Day 1: MCP client exercise using the policy server."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


def _default_policy_server_script() -> Path:
    return Path(__file__).resolve().parents[1] / "mcp" / "policy_server.py"


def _extract_text_result(tool_result: Any) -> str:
    content = getattr(tool_result, "content", None) or []
    text_chunks: list[str] = []

    for item in content:
        if isinstance(item, types.TextContent):
            text_chunks.append(item.text)

    if text_chunks:
        return "\n".join(text_chunks).strip()

    structured = getattr(tool_result, "structuredContent", None)
    if structured is not None:
        return str(structured)

    return str(tool_result)


@dataclass
class MCPPolicyAgent:
    """Minimal agent wrapper that uses MCP tool discovery and execution."""

    server_script: Path
    python_executable: str = sys.executable

    async def ask_policy(
        self,
        query: str,
        jurisdiction: str = "federal",
        loan_type: str = "all",
    ) -> dict[str, Any]:
        params = StdioServerParameters(
            command=self.python_executable,
            args=[str(self.server_script)],
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join(
                    [
                        str(self.server_script.parents[2]),
                        os.environ.get("PYTHONPATH", ""),
                    ]
                ).strip(os.pathsep),
            },
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools_response = await session.list_tools()
                tool_names = [tool.name for tool in tools_response.tools]
                if "search_lending_policies" not in tool_names:
                    raise RuntimeError(
                        "Expected search_lending_policies tool not found on MCP server"
                    )

                result = await session.call_tool(
                    "search_lending_policies",
                    {
                        "query": query,
                        "jurisdiction": jurisdiction,
                        "loan_type": loan_type,
                    },
                )

                return {
                    "tool_names": tool_names,
                    "result_text": _extract_text_result(result),
                    "is_error": bool(getattr(result, "isError", False)),
                }


def run_demo() -> dict[str, Any]:
    """Run a simple MCP call end-to-end and print a compact report."""
    agent = MCPPolicyAgent(server_script=_default_policy_server_script())
    payload = asyncio.run(
        agent.ask_policy(
            query="What are common DTI policy limits for conventional loans?",
            jurisdiction="federal",
            loan_type="conventional",
        )
    )

    print("Connected tools:", payload["tool_names"])
    print("MCP call error:", payload["is_error"])
    print("Policy result:\n", payload["result_text"])
    return payload


if __name__ == "__main__":
    run_demo()
