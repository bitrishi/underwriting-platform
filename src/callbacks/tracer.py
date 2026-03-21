from langchain_core.callbacks import BaseCallbackHandler
from datetime import datetime


class UnderwritingTracer(BaseCallbackHandler):
    """Callback handler that traces tool + LLM activity for underwriting runs.

    Tracks:
    - tool starts / ends
    - LLM starts
    - agent finish

    Each event includes an ISO timestamp.
    """

    def __init__(self):
        self.trace = []

    def _now(self) -> str:
        return datetime.now().isoformat()

    def on_tool_start(self, tool_name, tool_input, **kwargs):
        self.trace.append({
            "event": "tool_start",
            "tool": tool_name,
            "input": tool_input,
            "timestamp": self._now(),
        })

    def on_tool_end(self, output, **kwargs):
        self.trace.append({
            "event": "tool_end",
            "output": output,
            "timestamp": self._now(),
        })

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.trace.append({
            "event": "llm_start",
            "prompts": prompts,
            "timestamp": self._now(),
        })

    def on_agent_finish(self, finish, **kwargs):
        self.trace.append({
            "event": "agent_finish",
            "output": finish.return_values,
            "timestamp": self._now(),
        })

    def get_trace_summary(self) -> str:
        """Return a human-readable trace timeline."""
        lines = []
        for idx, entry in enumerate(self.trace, start=1):
            ts = entry.get("timestamp")
            ev = entry.get("event")
            if ev == "tool_start":
                lines.append(
                    f"{idx:02d}. [{ts}] TOOL START  - {entry.get('tool')} input={entry.get('input')}"
                )
            elif ev == "tool_end":
                lines.append(f"{idx:02d}. [{ts}] TOOL END    - output={entry.get('output')}")
            elif ev == "llm_start":
                lines.append(f"{idx:02d}. [{ts}] LLM START")
            elif ev == "agent_finish":
                lines.append(f"{idx:02d}. [{ts}] AGENT FINISH - output={entry.get('output')}")
            else:
                lines.append(f"{idx:02d}. [{ts}] {ev} - {entry}")
        return "\n".join(lines)
