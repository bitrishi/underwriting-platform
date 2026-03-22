"""Week 3 Day 4 graph traversal exercise."""

from __future__ import annotations

from pprint import pformat

from src.config.settings import settings
from src.graph.knowledge_graph import UnderwritingGraph
from src.graph.seed_data import seed_graph


def main() -> None:
    graph = UnderwritingGraph(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
    )
    try:
        if not graph.verify_connection():
            raise RuntimeError("Neo4j connection failed")

        seed_graph(graph)

        print("=" * 78)
        print("GRAPH TRAVERSAL: Borrower -> Employer -> Industry -> Risk")
        print("=" * 78)
        context = graph.get_borrower_risk_context("1003")
        print(pformat(context, indent=2, width=100))

        print("\n" + "=" * 78)
        print("SIMILAR PAST LOANS IN INDUSTRY")
        print("=" * 78)
        similar = graph.find_similar_loans("cryptocurrency", min_fico=600, limit=10)
        print(pformat(similar, indent=2, width=100))

        print("\n" + "=" * 78)
        print("STATE + FEDERAL REGULATIONS")
        print("=" * 78)
        regs = graph.get_state_regulations("Texas")
        print(pformat(regs, indent=2, width=100))
    finally:
        graph.close()


if __name__ == "__main__":
    main()
