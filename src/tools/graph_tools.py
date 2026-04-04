"""LangChain tools for underwriting knowledge-graph queries."""

from __future__ import annotations

from langchain_core.tools import tool
from neo4j.exceptions import ServiceUnavailable, TransientError  # type: ignore[import]

from src.config.settings import settings
from src.graph.knowledge_graph import UnderwritingGraph
from src.utils.retry import retry_with_backoff
from src.utils.circuit_breaker import neo4j_breaker


def _graph() -> UnderwritingGraph:
    return UnderwritingGraph(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
    )


@retry_with_backoff(
    max_retries=2,
    base_delay=0.5,
    max_delay=15.0,
    retryable_exceptions=(ServiceUnavailable, TransientError),
    jitter=True,
)
def _query_borrower_risk(ssn_last4: str) -> dict:
    """Internal retry-wrapped helper for the Neo4j borrower-risk traversal."""
    graph = _graph()
    try:
        return graph.get_borrower_risk_context(ssn_last4)
    finally:
        graph.close()


@retry_with_backoff(
    max_retries=2,
    base_delay=0.5,
    max_delay=15.0,
    retryable_exceptions=(ServiceUnavailable, TransientError),
    jitter=True,
)
def _query_similar_loans(industry: str, min_fico: int, limit: int) -> dict:
    """Internal retry-wrapped helper for the Neo4j similar-loans query."""
    graph = _graph()
    try:
        return graph.find_similar_loans(industry=industry, min_fico=min_fico, limit=limit)
    finally:
        graph.close()


@tool
def get_borrower_risk_context(ssn_last4: str) -> dict:
    """Get full borrower risk context from relationship traversal.

    Traversal path:
    Borrower -> Company -> Industry
    Borrower -> Loan -> Property -> State -> Regulation

    Args:
        ssn_last4: Last 4 digits of borrower SSN.

    Returns:
        Structured borrower risk context and related entities.
    """
    try:
        return neo4j_breaker.call(_query_borrower_risk, ssn_last4)
    except Exception as exc:
        return {"error": f"Graph query failed: {exc}", "ssn_last4": ssn_last4}


@tool
def find_similar_past_loans(industry: str, min_fico: int = 0, limit: int = 10) -> dict:
    """Find historical loans in the same industry.

    Args:
        industry: Industry name (for example, "energy" or "healthcare").
        min_fico: Optional lower bound for borrower FICO.
        limit: Max rows to return.

    Returns:
        Industry-level historical loan outcomes and summary stats.
    """
    try:
        return neo4j_breaker.call(_query_similar_loans, industry, min_fico, limit)
    except Exception as exc:
        return {"error": f"Graph query failed: {exc}", "industry": industry}


@retry_with_backoff(
    max_retries=2,
    base_delay=0.5,
    max_delay=15.0,
    retryable_exceptions=(ServiceUnavailable, TransientError),
    jitter=True,
)
def _query_state_regulations(state: str) -> dict:
    """Internal retry-wrapped helper for the Neo4j state-regulations query."""
    graph = _graph()
    try:
        return graph.get_state_regulations(state)
    finally:
        graph.close()


@tool
def get_state_regulations(state: str) -> dict:
    """Fetch state plus federal regulations applicable to a state.

    Args:
        state: State node name (for example, "Texas").

    Returns:
        Regulations list with jurisdiction, severity, and descriptions.
    """
    try:
        return neo4j_breaker.call(_query_state_regulations, state)
    except Exception as exc:
        return {"error": f"Graph query failed: {exc}", "state": state}
