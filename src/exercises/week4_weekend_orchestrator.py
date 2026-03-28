"""Week 4 weekend orchestrator runner with streaming and interrupt/resume demos."""

from __future__ import annotations

import time
import uuid
from typing import Any

from langgraph.types import Command

from src.orchestrator.graph import create_underwriting_graph


def _base_state(
    app_id: str,
    docs: list[str],
    loan_type: str = "conventional",
    thread_id: str = "",
) -> dict[str, Any]:
    return {
        "app_id": app_id,
        "document_paths": docs,
        "loan_type": loan_type,
        "graph_version": "v1",
        "thread_id": thread_id,
        "errors": [],
        "messages": [],
        "review_iterations": 0,
    }


def _print_event(node_name: str, update: dict[str, Any], elapsed: float) -> None:
    keys = sorted(update.keys()) if isinstance(update, dict) else []
    print(f"[{elapsed:0.3f}s] node={node_name} update_keys={keys}")


def _run_streaming(graph: Any, initial_state: dict[str, Any], thread_id: str) -> dict[str, Any]:
    config = {"configurable": {"thread_id": thread_id}}
    start = time.perf_counter()
    state_accum: dict[str, Any] = {}

    for event in graph.stream(initial_state, config=config):
        for node_name, update in event.items():
            elapsed = time.perf_counter() - start
            if isinstance(update, dict):
                state_accum.update(update)
            _print_event(node_name, update, elapsed)

    return state_accum


def _print_summary(title: str, state: dict[str, Any]) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)
    print(f"tool_calls={state.get('total_tool_calls', 0)}")
    print(f"llm_calls={state.get('total_llm_calls', 0)}")
    print(f"estimated_cost_usd={state.get('estimated_cost_usd', 0.0)}")
    report = state.get("final_report") or state.get("final_decision") or "No final report"
    print(report)


def scenario_1_strong_application(graph: Any) -> None:
    print("\n--- Scenario 1: Strong application with documents (expected APPROVE path) ---")
    thread_id = f"weekend-s1-{uuid.uuid4().hex[:8]}"
    state = _base_state(
        app_id="APP-001",
        docs=[
            "data/sample_documents/w2_sample.txt",
            "data/sample_documents/1040_sample.txt",
            "data/sample_documents/paystub_sample.txt",
        ],
        thread_id=thread_id,
    )
    out = _run_streaming(graph, state, thread_id=thread_id)
    _print_summary("Scenario 1 Final Report", out)


def scenario_2_weak_without_documents(graph: Any) -> None:
    print("\n--- Scenario 2: Weak application without documents (expected DENY/fatal path) ---")
    thread_id = f"weekend-s2-{uuid.uuid4().hex[:8]}"
    state = _base_state(app_id="APP-999", docs=[], thread_id=thread_id)
    out = _run_streaming(graph, state, thread_id=thread_id)
    _print_summary("Scenario 2 Final Report", out)


def scenario_3_borderline_with_human_review(graph: Any) -> None:
    print("\n--- Scenario 3: Borderline application with human-in-the-loop ---")
    thread_id = f"weekend-s3-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    state = _base_state(
        app_id="APP-002",
        docs=["data/sample_documents/w2_sample.txt"],
        thread_id=thread_id,
    )

    paused = graph.invoke(state, config=config)
    interrupts = paused.get("__interrupt__", []) if isinstance(paused, dict) else []
    if interrupts:
        payload = getattr(interrupts[0], "value", interrupts[0])
        print("\nHuman review message:")
        print(payload)

    resumed = graph.invoke(Command(resume="APPROVED with conditions"), config=config)
    _print_summary("Scenario 3 Final Report", resumed)


def main() -> None:
    graph = create_underwriting_graph()
    scenario_1_strong_application(graph)
    scenario_2_weak_without_documents(graph)
    scenario_3_borderline_with_human_review(graph)


if __name__ == "__main__":
    main()
