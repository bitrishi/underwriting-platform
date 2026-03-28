"""Week 4 Day 1 exercise: run and inspect the underwriting StateGraph."""

from __future__ import annotations

from pprint import pformat

from src.orchestrator.graph import create_underwriting_graph


def run_case(name: str, app_id: str, document_paths: list[str]) -> None:
    graph = create_underwriting_graph()

    initial_state = {
        "app_id": app_id,
        "document_paths": document_paths,
        "errors": [],
        "messages": [],
    }

    print("\n" + "=" * 90)
    print(f"CASE: {name} | app_id={app_id} | docs={len(document_paths)}")
    print("=" * 90)

    executed_nodes: list[str] = []
    final_state: dict = {}

    for event in graph.stream(initial_state):
        for node_name, updates in event.items():
            executed_nodes.append(node_name)
            final_state.update(updates)
            print(f"\n[NODE] {node_name}")
            print(pformat(updates, sort_dicts=False))

    print("\nExecuted nodes:", " -> ".join(executed_nodes))
    print("\nFinal decision report:\n")
    print(final_state.get("final_decision", "No final decision generated."))


if __name__ == "__main__":
    run_case(
        name="Complete application (with documents)",
        app_id="APP-001",
        document_paths=[
            "data/sample_documents/w2_sample.txt",
            "data/sample_documents/1040_sample.txt",
            "data/sample_documents/paystub_sample.txt",
        ],
    )

    run_case(
        name="No documents (skip doc review)",
        app_id="APP-002",
        document_paths=[],
    )
