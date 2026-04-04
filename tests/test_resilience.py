"""Tests for resilience utilities: retry, circuit breaker, error types, metrics."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from src.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from src.utils.error_types import (
    ErrorCategory,
    StructuredError,
    categorize_pipeline_errors,
)
from src.utils.metrics import NodeMetrics, PipelineMetrics
from src.utils.retry import retry_with_backoff


# ── retry_with_backoff ────────────────────────────────────────────────────────


def test_retry_succeeds_on_first_attempt() -> None:
    call_count = 0

    @retry_with_backoff(max_retries=3, base_delay=0.0)
    def flaky() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    assert flaky() == "ok"
    assert call_count == 1


def test_retry_succeeds_after_transient_failures() -> None:
    call_count = 0

    @retry_with_backoff(
        max_retries=3,
        base_delay=0.0,
        retryable_exceptions=(ConnectionError,),
    )
    def flaky() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient")
        return "recovered"

    assert flaky() == "recovered"
    assert call_count == 3


def test_retry_raises_after_exhausting_retries() -> None:
    @retry_with_backoff(
        max_retries=2,
        base_delay=0.0,
        retryable_exceptions=(TimeoutError,),
    )
    def always_fails() -> None:
        raise TimeoutError("still down")

    with pytest.raises(TimeoutError, match="still down"):
        always_fails()


def test_retry_does_not_catch_non_retryable_exception() -> None:
    call_count = 0

    @retry_with_backoff(
        max_retries=3,
        base_delay=0.0,
        retryable_exceptions=(ConnectionError,),
    )
    def wrong_error() -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        wrong_error()

    # Should propagate immediately on the first attempt.
    assert call_count == 1


def test_retry_respects_max_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("src.utils.retry.time.sleep", lambda s: sleeps.append(s))

    @retry_with_backoff(
        max_retries=4,
        base_delay=100.0,
        max_delay=5.0,
        retryable_exceptions=(ConnectionError,),
        jitter=False,
    )
    def always_fails() -> None:
        raise ConnectionError()

    with pytest.raises(ConnectionError):
        always_fails()

    assert all(s <= 5.0 for s in sleeps), f"delay exceeded max_delay: {sleeps}"


def test_retry_logs_each_attempt(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    @retry_with_backoff(
        max_retries=2,
        base_delay=0.0,
        retryable_exceptions=(RuntimeError,),
    )
    def noisy() -> None:
        raise RuntimeError("boom")

    with caplog.at_level(logging.WARNING, logger="src.utils.retry"):
        with pytest.raises(RuntimeError):
            noisy()

    # Expect one WARNING per retry attempt (2) + final ERROR
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 2


# ── CircuitBreaker ────────────────────────────────────────────────────────────


def test_circuit_starts_closed() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=3, timeout_period=5.0)
    assert cb.state == CircuitState.CLOSED


def test_circuit_opens_after_threshold() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=3, timeout_period=60.0)

    def fail() -> None:
        raise ConnectionError("down")

    for _ in range(3):
        with pytest.raises(ConnectionError):
            cb.call(fail)

    assert cb.state == CircuitState.OPEN


def test_circuit_open_rejects_calls_immediately() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1, timeout_period=60.0)

    def fail() -> None:
        raise ConnectionError()

    with pytest.raises(ConnectionError):
        cb.call(fail)

    assert cb.state == CircuitState.OPEN

    with pytest.raises(CircuitBreakerOpen):
        cb.call(fail)


def test_circuit_fallback_returned_when_open() -> None:
    fallback_value = {"error": "circuit_open", "degraded": True}
    cb = CircuitBreaker(
        name="test",
        failure_threshold=1,
        timeout_period=60.0,
        fallback=lambda: fallback_value,
    )

    def fail() -> None:
        raise ConnectionError()

    with pytest.raises(ConnectionError):
        cb.call(fail)

    assert cb.state == CircuitState.OPEN
    result = cb.call(fail)
    assert result == fallback_value


def test_circuit_transitions_to_half_open_after_timeout() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1, timeout_period=0.05)

    def fail() -> None:
        raise ConnectionError()

    with pytest.raises(ConnectionError):
        cb.call(fail)

    assert cb.state == CircuitState.OPEN

    time.sleep(0.1)

    # After timeout a probe call is admitted → transitions to HALF_OPEN.
    # The probe fails here, returning to OPEN.
    with pytest.raises(ConnectionError):
        cb.call(fail)

    assert cb.state == CircuitState.OPEN


def test_circuit_closes_on_successful_probe() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1, timeout_period=0.05)

    def fail() -> None:
        raise ConnectionError()

    with pytest.raises(ConnectionError):
        cb.call(fail)

    time.sleep(0.1)

    def succeed() -> str:
        return "ok"

    result = cb.call(succeed)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED


def test_circuit_reset_restores_closed_state() -> None:
    cb = CircuitBreaker(name="test", failure_threshold=1, timeout_period=60.0)

    def fail() -> None:
        raise ConnectionError()

    with pytest.raises(ConnectionError):
        cb.call(fail)

    assert cb.state == CircuitState.OPEN
    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.status()["failure_count"] == 0


def test_circuit_status_snapshot() -> None:
    cb = CircuitBreaker(name="my-service", failure_threshold=5, timeout_period=30.0)
    s = cb.status()
    assert s["name"] == "my-service"
    assert s["state"] == "CLOSED"
    assert s["failure_count"] == 0
    assert s["failure_threshold"] == 5
    assert s["timeout_period_s"] == 30.0


def test_circuit_breaker_thread_safety() -> None:
    """Many threads hammering the same circuit should not deadlock or corrupt state."""
    cb = CircuitBreaker(name="threaded", failure_threshold=10, timeout_period=60.0)
    errors: list[Exception] = []

    def worker() -> None:
        try:
            cb.call(lambda: None)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)

    # No thread should be stuck; errors are fine (circuit may open).
    assert all(t.is_alive() is False for t in threads)


def test_circuit_decorator_usage() -> None:
    cb = CircuitBreaker(name="deco", failure_threshold=5, timeout_period=60.0)

    @cb
    def external_call(x: int) -> int:
        return x * 2

    assert external_call(3) == 6


# ── StructuredError ───────────────────────────────────────────────────────────


def test_structured_error_recoverable() -> None:
    err = StructuredError.recoverable(
        source="fetch_data",
        message="credit timeout",
        retry_count=2,
        exc=TimeoutError("boom"),
    )
    assert err.category == ErrorCategory.RECOVERABLE
    assert err.retry_count == 2
    assert "boom" in (err.original_exception or "")
    assert err.to_state_string().startswith("[RECOVERABLE]")


def test_structured_error_degraded() -> None:
    err = StructuredError.degraded(source="risk_scoring", message="stale credit score")
    assert err.category == ErrorCategory.DEGRADED
    assert err.retry_count == 0
    assert "[DEGRADED]" in err.to_state_string()


def test_structured_error_fatal() -> None:
    err = StructuredError.fatal(source="fetch_data", message="app not found")
    assert err.category == ErrorCategory.FATAL
    assert "[FATAL]" in err.to_state_string()


def test_categorize_pipeline_errors_groups_by_prefix() -> None:
    errors: list[str] = [
        "[RECOVERABLE] fetch_data: transient timeout",
        "[FATAL] fetch_data: app not found",
        "[DEGRADED] risk_scoring: stale data",
        "legacy_bare_error_string",
    ]
    groups = categorize_pipeline_errors(errors)

    assert len(groups["RECOVERABLE"]) == 1
    assert len(groups["FATAL"]) == 1
    assert len(groups["DEGRADED"]) == 1
    assert len(groups["UNCATEGORIZED"]) == 1


def test_categorize_pipeline_errors_ignores_empty_categories() -> None:
    groups = categorize_pipeline_errors(["[FATAL] x: boom"])
    assert "RECOVERABLE" not in groups
    assert "DEGRADED" not in groups
    assert "UNCATEGORIZED" not in groups


def test_categorize_accepts_dict_errors() -> None:
    errors: list[Any] = [
        {"category": "FATAL", "message": "fatal problem"},
        {"category": "RECOVERABLE", "message": "transient"},
    ]
    groups = categorize_pipeline_errors(errors)
    assert "FATAL" in groups
    assert "RECOVERABLE" in groups


# ── PipelineMetrics ───────────────────────────────────────────────────────────


def test_metrics_start_end_node() -> None:
    m = PipelineMetrics(evaluation_id="test-001")
    m.start_node("fetch_data")
    time.sleep(0.01)
    m.end_node("fetch_data", status="success", llm_calls=1, tools_called=["pull_borrower_data"])

    s = m.summary()
    assert "fetch_data" in s["nodes_executed"]
    assert s["total_llm_calls"] == 1
    assert s["total_tools_called"] == 1
    assert s["node_metrics"]["fetch_data"]["duration_ms"] >= 0


def test_metrics_accumulates_retries() -> None:
    m = PipelineMetrics(evaluation_id="test-002")
    m.start_node("bedrock")
    m.end_node("bedrock", retries=3)
    m.start_node("credit")
    m.end_node("credit", retries=1)

    s = m.summary()
    assert s["total_retries"] == 4


def test_metrics_total_cost() -> None:
    m = PipelineMetrics(evaluation_id="test-003")
    m.start_node("a")
    m.end_node("a", cost_estimate_usd=0.001)
    m.start_node("b")
    m.end_node("b", cost_estimate_usd=0.002)

    s = m.summary()
    assert abs(s["total_cost_estimate_usd"] - 0.003) < 1e-9


def test_metrics_cloudwatch_records_shape() -> None:
    m = PipelineMetrics(evaluation_id="test-004")
    m.start_node("x")
    m.end_node("x")

    records = m.to_cloudwatch_metrics()
    names = {r["MetricName"] for r in records}
    assert "PipelineDurationMs" in names
    assert "LLMCalls" in names
    assert "TotalErrors" in names
    assert "TotalRetries" in names
    assert "EstimatedCostUSD" in names


def test_metrics_pipeline_error_counted() -> None:
    m = PipelineMetrics(evaluation_id="test-005")
    m.record_pipeline_error("something went wrong globally")

    s = m.summary()
    assert "something went wrong globally" in s["pipeline_errors"]
    assert s["total_errors"] == 1


def test_metrics_end_node_without_start_does_not_crash() -> None:
    m = PipelineMetrics(evaluation_id="test-006")
    # Calling end_node without a matching start_node should not raise.
    m.end_node("orphan_node", status="failed")
    s = m.summary()
    assert "orphan_node" in s["node_metrics"]
