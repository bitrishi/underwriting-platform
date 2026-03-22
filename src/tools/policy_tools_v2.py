"""
RAG-powered policy search tools for the underwriting agents.

Two tools with distinct purposes:
1. search_lending_policies — fast routine lookups (1 LLM call)
2. verify_compliance_requirement — thorough verification (1-2 LLM calls)

The agent's LLM reads the docstrings to decide which tool to use.
Tool selection is based on the question's criticality:
- "What's the general DTI limit?" → search_lending_policies
- "Does this violate Section 50(a)(6)?" → verify_compliance_requirement
"""

from langchain_core.tools import tool
from src.rag.smart_rag import SmartRAG
from src.rag.query_templates import COMPLIANCE_QUERIES


@tool
def search_lending_policies(
    query: str,
    topic: str = "",
    jurisdiction: str = "federal",
) -> str:
    """Search lending policies for routine lookups.

    FAST — uses one LLM call. Use for straightforward policy questions
    where you need a quick reference, not a critical compliance decision.

    For best results, pass a known topic. Available topics:
    dti, fico, ltv, pmi, seasoning, trid, employment, income,
    appraisal, closing, cashout

    Args:
        query: Natural language question about lending policies
        topic: Known topic key for optimized search (e.g., "dti", "fico").
               Leave empty if the question doesn't match a known topic.
               Using a known topic gives more reliable results.
        jurisdiction: Filter by jurisdiction. Options:
                      "federal" (default), "state_texas",
                      "state_california", etc.

    Returns:
        Policy answer with source citations and confidence level.
        Includes which documents were relevant and which were filtered.
    """
    # Build metadata filter
    metadata_filter = None
    if jurisdiction and jurisdiction != "federal":
        metadata_filter = {"jurisdiction": jurisdiction}

    # Run the SmartRAG pipeline (routine mode — 1 LLM call)
    rag = SmartRAG(metadata_filter=metadata_filter)
    result = rag.query(
        question=query,
        topic=topic if topic else None,
        critical=False,  # routine — uses Haiku, no separate verification
    )

    return result.format_report()


@tool
def verify_compliance_requirement(
    query: str,
    jurisdiction: str = "federal",
) -> str:
    """Thorough compliance verification for critical regulatory questions.

    SLOWER but MORE ACCURATE — uses a stronger model and runs
    hallucination verification when needed.

    Use this tool when:
    - The question involves specific regulatory Section references
    - The answer could have legal or regulatory consequences
    - You need to verify compliance for a specific loan scenario
    - Accuracy matters more than speed

    Do NOT use this for general policy lookups — use
    search_lending_policies instead for those.

    Args:
        query: Specific compliance question requiring verification
        jurisdiction: Filter by jurisdiction. Options:
                      "federal" (default), "state_texas",
                      "state_california", etc.

    Returns:
        Verified answer with sources, confidence, hallucination check,
        and VERIFIED/NEEDS REVIEW status indicator.
    """
    # Build metadata filter
    metadata_filter = None
    if jurisdiction and jurisdiction != "federal":
        metadata_filter = {"jurisdiction": jurisdiction}

    # Run SmartRAG in critical mode (Sonnet + verification if needed)
    rag = SmartRAG(metadata_filter=metadata_filter)
    result = rag.query(
        question=query,
        topic=None,     # critical queries are usually specific, not templated
        critical=True,  # uses Sonnet, runs verification if self-check flags issues
    )

    # Add trust indicator
    if result.is_trustworthy():
        status = "✅ VERIFIED — All claims supported by source documents"
    elif result.sufficient_context:
        status = "⚠️ NEEDS REVIEW — Some claims may not be fully supported"
    else:
        status = "❌ INSUFFICIENT DATA — Cannot verify from available documents"

    return f"[{status}]\n\n{result.format_report()}"