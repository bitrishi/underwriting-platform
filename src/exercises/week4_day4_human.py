"""Week 4 Day 4: interrupt/resume and checkpoint persistence exercise."""

from __future__ import annotations

import json
import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.orchestrator.graph import create_underwriting_graph


def _extract_interrupt_value(result: Any) -> Any:
    if isinstance(result, dict) and "__interrupt__" in result:
        interrupts = result.get("__interrupt__") or []
        if interrupts:
            first = interrupts[0]
            return getattr(first, "value", first)
    return None


def run_interrupt_cycle(shared_saver: MemorySaver, resume_value: Any) -> dict[str, Any]:
    graph = create_underwriting_graph(checkpointer=shared_saver)
    thread_id = f"human-review-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "app_id": "APP-002",  # Borderline/risky profile, should escalate
        "document_paths": ["data/sample_documents/w2_sample.txt"],
        "errors": [],
        "messages": [],
    }

    paused = graph.invoke(initial_state, config=config)
    interrupt_value = _extract_interrupt_value(paused)
    print("\n=== Interrupt Captured ===")
    print(json.dumps(interrupt_value, indent=2, default=str))

    checkpoint_state = graph.get_state(config)
    checkpoint_keys = sorted((checkpoint_state.values or {}).keys())
    print("\nCheckpoint state keys before resume:")
    print(checkpoint_keys)

    # Simulate process restart: create a new graph instance with same saver.
    restarted_graph = create_underwriting_graph(checkpointer=shared_saver)
    resumed = restarted_graph.invoke(Command(resume=resume_value), config=config)

    final_decision = resumed.get("final_decision", "") if isinstance(resumed, dict) else ""
    print("\n=== Final Decision After Resume ===")
    print(final_decision)

    return {
        "thread_id": thread_id,
        "interrupt_value": interrupt_value,
        "checkpoint_keys": checkpoint_keys,
        "final_decision": final_decision,
    }


def main() -> None:
    saver = MemorySaver()

    print("\n##### Resume with: APPROVED with conditions #####")
    approved_result = run_interrupt_cycle(saver, "APPROVED with conditions")
    print(
        "Contains human decision?",
        "APPROVE_WITH_CONDITIONS" in approved_result["final_decision"],
    )

    print("\n##### Resume with: DENIED #####")
    denied_result = run_interrupt_cycle(saver, "DENIED")
    print("Contains human decision?", "DENY" in denied_result["final_decision"])


if __name__ == "__main__":
    main()
