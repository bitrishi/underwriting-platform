"""Week 4 Day 5: graph streaming demonstration with timing."""

from __future__ import annotations

import time
import uuid
from typing import Any

from src.orchestrator.graph import create_underwriting_graph


def _summarize_state(state: dict[str, Any]) -> str:
    keys = sorted(state.keys())
    return f"keys={keys}, errors={len(state.get('errors', []))}"


def run_streaming_demo() -> None:
    graph = create_underwriting_graph()

    initial_state = {
        "app_id": "APP-001",
        "loan_type": "conventional",
        "document_paths": [
            "data/sample_documents/w2_sample.txt",
            "data/sample_documents/1040_sample.txt",
            "data/sample_documents/paystub_sample.txt",
        ],
        "errors": [],
        "messages": [],
        "review_iterations": 0,
    }

    stream_config = {"configurable": {"thread_id": f"stream-{uuid.uuid4().hex[:8]}"}}
    invoke_config = {"configurable": {"thread_id": f"invoke-{uuid.uuid4().hex[:8]}"}}

    print("\n=== Streaming (graph.stream) ===")
    stream_start = time.perf_counter()
    first_result_seconds: float | None = None
    accumulated_state: dict[str, Any] = {}

    for event in graph.stream(initial_state, config=stream_config):
        for node_name, update in event.items():
            now = time.perf_counter()
            elapsed = now - stream_start
            if first_result_seconds is None:
                first_result_seconds = elapsed

            if isinstance(update, dict):
                accumulated_state.update(update)

            print(f"[{elapsed:0.3f}s] Node completed: {node_name}")
            print(f"State growth: {_summarize_state(accumulated_state)}")

    stream_total = time.perf_counter() - stream_start

    print("\n=== Invoke (graph.invoke) ===")
    invoke_start = time.perf_counter()
    invoke_result = graph.invoke(initial_state, config=invoke_config)
    invoke_total = time.perf_counter() - invoke_start

    print(f"Invoke finished in: {invoke_total:0.3f}s")
    print(f"Invoke final state: {_summarize_state(invoke_result)}")

    first_result = first_result_seconds if first_result_seconds is not None else stream_total
    print("\n=== Timing Comparison ===")
    print(f"First streaming result appeared at: {first_result:0.3f}s")
    print(f"Invoke returned final result at: {invoke_total:0.3f}s")
    print(f"First-result advantage (invoke - stream_first): {invoke_total - first_result:0.3f}s")


if __name__ == "__main__":
    run_streaming_demo()
