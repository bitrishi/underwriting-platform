"""Week 4 Day 2: full underwriting graph scenarios with compliance and fatal routing."""

from __future__ import annotations

from pprint import pformat

from src.orchestrator.graph import create_underwriting_graph


def run_case(name: str, state: dict) -> None:
    graph = create_underwriting_graph()
    print("\n" + "=" * 92)
    print(f"CASE: {name}")
    print("=" * 92)

    executed_nodes: list[str] = []
    final_state: dict = {}

    for event in graph.stream(state):
        for node_name, updates in event.items():
            executed_nodes.append(node_name)
            final_state.update(updates)
            print(f"\n[NODE] {node_name}")
            print(pformat(updates, sort_dicts=False))

    print("\nExecuted nodes:", " -> ".join(executed_nodes))
    print("\nErrors:")
    print(pformat(final_state.get("errors", []), sort_dicts=False))
    print("\nFinal decision:\n")
    print(final_state.get("final_decision", "No final decision generated."))


if __name__ == "__main__":
    def init_state(**kwargs):
        return {"errors": [], "messages": [], **kwargs}

    run_case(
        "Normal flow (no escalation)",
        init_state(
            app_id="APP-001",
            document_paths=[
                "data/sample_documents/w2_sample.txt",
                "data/sample_documents/1040_sample.txt",
                "data/sample_documents/paystub_sample.txt",
            ],
        ),
    )

    run_case(
        "Empty documents (doc_review skips)",
        init_state(
            app_id="APP-001",
            document_paths=[],
        ),
    )

    run_case(
        "Compliance violation (manual escalation)",
        init_state(
            app_id="APP-002",
            document_paths=["data/sample_documents/w2_sample.txt"],
            simulate_existing_application=True,
        ),
    )

    run_case(
        "Fetch data failure (fatal route)",
        init_state(
            app_id="APP-999",
            document_paths=["data/sample_documents/w2_sample.txt"],
        ),
    )
