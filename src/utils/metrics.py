"""Pipeline and per-node metrics collection.

Designed to produce structured output compatible with:
- AWS CloudWatch PutMetricData
- The underwriting audit trail / ``final_decision_node`` report
- Local experiment logging during development

Usage
-----
::

    metrics = PipelineMetrics(evaluation_id="APP-001-run-1")

    metrics.start_node("fetch_data")
    # … run fetch_data_node …
    metrics.end_node(
        "fetch_data",
        status="success",
        llm_calls=1,
        tools_called=["pull_borrower_data", "pull_credit_report"],
        cost_estimate_usd=0.0012,
    )

    summary = metrics.summary()          # → dict (CloudWatch + audit)
    cw_records = metrics.to_cloudwatch_metrics()  # → list[dict]
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Per-node record ───────────────────────────────────────────────────────────


class NodeMetrics(BaseModel):
    """Metrics captured for a single node execution."""

    node_name: str
    started_at: str

    duration_ms: float = 0.0
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tools_called: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    retries: int = 0
    cost_estimate_usd: float = 0.0
    status: str = "pending"  # pending | success | degraded | failed


# ── Pipeline-level collector ──────────────────────────────────────────────────


class PipelineMetrics:
    """Accumulates per-node and pipeline-wide metrics over one evaluation run.

    Args:
        evaluation_id: Unique run identifier (e.g. ``"APP-001"``) used as a
            CloudWatch dimension and audit trail key.
    """

    def __init__(self, evaluation_id: str) -> None:
        self.evaluation_id = evaluation_id
        self.started_at = datetime.now(UTC).isoformat()
        self._wall_start = time.perf_counter()
        self._nodes: dict[str, NodeMetrics] = {}
        self._node_timers: dict[str, float] = {}
        self._pipeline_errors: list[str] = []
        self._total_retries: int = 0

    # ── Node lifecycle ────────────────────────────────────────────────────────

    def start_node(self, node_name: str) -> None:
        """Record that a node has started execution."""
        self._node_timers[node_name] = time.perf_counter()
        self._nodes[node_name] = NodeMetrics(
            node_name=node_name,
            started_at=datetime.now(UTC).isoformat(),
        )

    def end_node(
        self,
        node_name: str,
        *,
        status: str = "success",
        llm_calls: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        tools_called: list[str] | None = None,
        errors: list[str] | None = None,
        retries: int = 0,
        cost_estimate_usd: float = 0.0,
    ) -> None:
        """Record that a node has finished and populate its metrics.

        Args:
            node_name: Must match the name passed to :meth:`start_node`.
            status: ``"success"``, ``"degraded"``, or ``"failed"``.
            llm_calls: Number of Bedrock / LLM invocations in this node.
            tokens_in: Approximate input tokens consumed.
            tokens_out: Approximate output tokens produced.
            tools_called: Names of @tool functions invoked.
            errors: Error strings recorded during node execution.
            retries: How many retry attempts were made (from the retry decorator).
            cost_estimate_usd: Estimated USD cost for this node's API calls.
        """
        node = self._nodes.get(node_name)
        if node is None:
            # start_node was never called — create a placeholder.
            node = NodeMetrics(
                node_name=node_name,
                started_at=self.started_at,
            )
            self._nodes[node_name] = node

        timer_start = self._node_timers.get(node_name, time.perf_counter())
        node.duration_ms = round((time.perf_counter() - timer_start) * 1000.0, 2)
        node.status = status
        node.llm_calls = llm_calls
        node.tokens_in = tokens_in
        node.tokens_out = tokens_out
        node.tools_called = tools_called or []
        node.errors = errors or []
        node.retries = retries
        node.cost_estimate_usd = cost_estimate_usd
        self._total_retries += retries

    def record_pipeline_error(self, message: str) -> None:
        """Record an error that is not scoped to a single node."""
        self._pipeline_errors.append(message)

    # ── Aggregation ────────────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Return a structured summary suitable for CloudWatch and audit trail.

        Top-level keys:
        - ``evaluation_id``, ``started_at``, ``total_duration_ms``
        - ``nodes_executed`` (ordered list)
        - ``total_llm_calls``, ``total_tokens_in``, ``total_tokens_out``
        - ``total_tools_called``, ``total_errors``, ``total_retries``
        - ``total_cost_estimate_usd``
        - ``pipeline_errors`` — errors not scoped to a node
        - ``node_metrics`` — dict[node_name → per-node dict]
        - ``cloudwatch`` — CloudWatch-friendly dimension block
        """
        total_duration_ms = round((time.perf_counter() - self._wall_start) * 1000.0, 2)
        total_llm_calls = sum(n.llm_calls for n in self._nodes.values())
        total_tokens_in = sum(n.tokens_in for n in self._nodes.values())
        total_tokens_out = sum(n.tokens_out for n in self._nodes.values())
        total_tools = sum(len(n.tools_called) for n in self._nodes.values())
        total_node_errors = sum(len(n.errors) for n in self._nodes.values())
        total_errors = total_node_errors + len(self._pipeline_errors)
        total_cost = round(sum(n.cost_estimate_usd for n in self._nodes.values()), 6)

        node_summaries = {
            name: {
                "duration_ms": node.duration_ms,
                "status": node.status,
                "llm_calls": node.llm_calls,
                "tokens_in": node.tokens_in,
                "tokens_out": node.tokens_out,
                "tools_called": node.tools_called,
                "errors": node.errors,
                "retries": node.retries,
                "cost_estimate_usd": node.cost_estimate_usd,
            }
            for name, node in self._nodes.items()
        }

        return {
            "evaluation_id": self.evaluation_id,
            "started_at": self.started_at,
            "total_duration_ms": total_duration_ms,
            "nodes_executed": list(self._nodes.keys()),
            "total_llm_calls": total_llm_calls,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_tools_called": total_tools,
            "total_errors": total_errors,
            "total_retries": self._total_retries,
            "total_cost_estimate_usd": total_cost,
            "pipeline_errors": self._pipeline_errors,
            "node_metrics": node_summaries,
            # CloudWatch-friendly flat dimension block
            "cloudwatch": {
                "metric_name": "UnderwritingPipelineCompletion",
                "dimensions": {
                    "EvaluationId": self.evaluation_id,
                    "TotalLLMCalls": str(total_llm_calls),
                    "TotalErrors": str(total_errors),
                    "TotalRetries": str(self._total_retries),
                    "TotalCostUSD": str(total_cost),
                    "TotalDurationMs": str(total_duration_ms),
                },
            },
        }

    def to_cloudwatch_metrics(self) -> list[dict[str, Any]]:
        """Format as CloudWatch ``PutMetricData`` records.

        Each record has: ``MetricName``, ``Value``, ``Unit``, ``Timestamp``.
        """
        s = self.summary()
        ts = s["started_at"]
        return [
            {
                "MetricName": "PipelineDurationMs",
                "Value": s["total_duration_ms"],
                "Unit": "Milliseconds",
                "Timestamp": ts,
            },
            {
                "MetricName": "LLMCalls",
                "Value": s["total_llm_calls"],
                "Unit": "Count",
                "Timestamp": ts,
            },
            {
                "MetricName": "TotalErrors",
                "Value": s["total_errors"],
                "Unit": "Count",
                "Timestamp": ts,
            },
            {
                "MetricName": "TotalRetries",
                "Value": s["total_retries"],
                "Unit": "Count",
                "Timestamp": ts,
            },
            {
                "MetricName": "EstimatedCostUSD",
                "Value": s["total_cost_estimate_usd"],
                "Unit": "None",
                "Timestamp": ts,
            },
        ]
