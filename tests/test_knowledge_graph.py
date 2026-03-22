"""Tests for Neo4j underwriting knowledge graph and graph tools."""

from __future__ import annotations

import pytest

from src.config.settings import settings
from src.graph.knowledge_graph import UnderwritingGraph
from src.graph.seed_data import seed_graph
from src.tools.graph_tools import (
    find_similar_past_loans,
    get_borrower_risk_context,
    get_state_regulations,
)


@pytest.fixture(scope="module")
def graph_available() -> bool:
    graph = UnderwritingGraph(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    try:
        return graph.verify_connection()
    except Exception:
        return False
    finally:
        graph.close()


@pytest.fixture(scope="module")
def seeded_graph(graph_available: bool) -> UnderwritingGraph:
    if not graph_available:
        pytest.skip("Neo4j unavailable; skipping graph integration tests")
    graph = UnderwritingGraph(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    seed_graph(graph)
    yield graph
    graph.close()


def test_get_borrower_risk_context_traversal(seeded_graph: UnderwritingGraph) -> None:
    context = seeded_graph.get_borrower_risk_context("1003")
    assert context["borrower"]["name"] == "Carmen Ruiz"
    assert context["employer"]["name"] == "BlockNova Labs"
    assert context["industry"]["name"] == "cryptocurrency"
    assert context["industry_risk_profile"] == "HIGH"
    assert context["loan_summary"]["total_loans"] >= 1


def test_find_similar_past_loans_in_industry(seeded_graph: UnderwritingGraph) -> None:
    results = seeded_graph.find_similar_loans("cryptocurrency", min_fico=600, limit=10)
    assert results["industry"] == "cryptocurrency"
    assert results["count"] >= 2
    outcomes = {item["outcome"] for item in results["loans"]}
    assert "defaulted" in outcomes


def test_get_state_regulations_includes_texas_and_federal(seeded_graph: UnderwritingGraph) -> None:
    result = seeded_graph.get_state_regulations("Texas")
    assert result["state"] == "Texas"
    jurisdictions = {item["jurisdiction"] for item in result["regulations"]}
    assert "federal" in jurisdictions
    assert "texas" in jurisdictions


def test_graph_tools_get_borrower_risk_context(graph_available: bool) -> None:
    if not graph_available:
        pytest.skip("Neo4j unavailable; skipping graph tool tests")
    result = get_borrower_risk_context.invoke({"ssn_last4": "1003"})
    assert "error" not in result
    assert result["borrower"]["ssn_last4"] == "1003"


def test_graph_tools_find_similar_past_loans(graph_available: bool) -> None:
    if not graph_available:
        pytest.skip("Neo4j unavailable; skipping graph tool tests")
    result = find_similar_past_loans.invoke(
        {"industry": "healthcare", "min_fico": 680, "limit": 10}
    )
    assert "error" not in result
    assert result["industry"] == "healthcare"


def test_graph_tools_get_state_regulations(graph_available: bool) -> None:
    if not graph_available:
        pytest.skip("Neo4j unavailable; skipping graph tool tests")
    result = get_state_regulations.invoke({"state": "Texas"})
    assert "error" not in result
    assert result["count"] >= 2
