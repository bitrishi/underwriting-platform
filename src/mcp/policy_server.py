"""MCP server exposing policy-search tools for underwriting agents."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Ensure local imports work when server is launched as a standalone stdio process.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tools.policy_tools import search_lending_policies as lc_search_lending_policies


mcp = FastMCP(
    name="Underwriting Policy Server",
    instructions=(
        "Provides policy and regulatory search tools for mortgage underwriting."
    ),
)


def run_policy_lookup(query: str, jurisdiction: str = "federal", loan_type: str = "all") -> str:
    """Execute the underlying local policy tool.

    Set MCP_POLICY_SERVER_FAKE_RESPONSE in tests to bypass FAISS/RAG dependencies.
    """
    fake_response = os.getenv("MCP_POLICY_SERVER_FAKE_RESPONSE")
    if fake_response:
        return fake_response

    return lc_search_lending_policies.invoke(
        {
            "query": query,
            "jurisdiction": jurisdiction,
            "loan_type": loan_type,
        }
    )


@mcp.tool()
def search_lending_policies(
    query: str,
    jurisdiction: str = "federal",
    loan_type: str = "all",
) -> str:
    """Search lending policy documents and return cited policy snippets."""
    return run_policy_lookup(
        query=query,
        jurisdiction=jurisdiction,
        loan_type=loan_type,
    )


def main() -> None:
    """Run the MCP server over stdio for local client connections."""
    mcp.run()


if __name__ == "__main__":
    main()
