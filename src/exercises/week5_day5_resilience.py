"""Week 5 Day 5: Resilience patterns — retry, circuit breaker, error types, metrics.

Four simulation scenarios
--------------------------
1. Bedrock timeout → verify retry with exponential backoff
2. Credit bureau sustained failure → circuit breaker trips to OPEN
3. Partial borrower data → graceful degradation returns PARTIAL result
4. Fatal error → pipeline routes to a structured error report

Each scenario is exercised against lightweight mocks so no live AWS credentials
are required.  Metrics are collected and printed for each scenario.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from src.utils.error_types import ErrorCategory, StructuredError, categorize_pipeline_errors
from src.utils.metrics import PipelineMetrics
from src.utils.retry import retry_with_backoff


# ── Scenario helpers ──────────────────────────────────────────────────────────


def _print_section(title: str) -> None:
    border = "─" * 60
    print(f"\n{border}\n  {title}\n{border}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1: Bedrock timeout → retry with backoff
# ─────────────────────────────────────────────────────────────────────────────


def scenario_bedrock_timeout_retry() -> dict[str, Any]:
    """Simulate a Bedrock endpoint that times out twice then succeeds.

    Expected: two retries with logged wait times, final call succeeds.
    """
    _print_section("Scenario 1: Bedrock timeout → retry with backoff")

    metrics = PipelineMetrics(evaluation_id="scenario-1-bedrock-retry")
    metrics.start_node("bedrock_llm_call")

    call_count = 0
    retries_recorded = 0
    outcome = "unknown"

    @retry_with_backoff(
        max_retries=3,
        base_delay=0.05,   # short delay for the demo
        max_delay=1.0,
        retryable_exceptions=(TimeoutError,),
        jitter=False,
    )
    def call_bedrock_llm(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise TimeoutError(f"Bedrock endpoint timed out (attempt {call_count})")
        return "APPROVE — borrower profile meets all underwriting criteria."

    try:
        result = call_bedrock_llm("Evaluate APP-001")
        retries_recorded = call_count - 1
        outcome = "success"
        error = StructuredError.recoverable(
            source="bedrock_llm_call",
            message=f"Bedrock recovered after {retries_recorded} retries.",
            retry_count=retries_recorded,
        )
        print(f"  ✓ Succeeded on attempt {call_count}. Result: {result[:60]}")
        print(f"  Retries: {retries_recorded}")

    except TimeoutError as exc:
        outcome = "failed"
        error = StructuredError.fatal(
            source="bedrock_llm_call",
            message="Bedrock exhausted all retries.",
            exc=exc,
        )
        print(f"  ✗ All retries exhausted: {exc}")

    metrics.end_node(
        "bedrock_llm_call",
        status=outcome,
        llm_calls=1,
        retries=retries_recorded,
        errors=[error.to_state_string()],
        cost_estimate_usd=0.0012,
    )

    summary = metrics.summary()
    print(f"  Metrics → total_retries={summary['total_retries']}, "
          f"total_errors={summary['total_errors']}")
    return {"scenario": "bedrock_retry", "outcome": outcome, "metrics": summary}


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2: Sustained credit bureau failure → circuit breaker opens
# ─────────────────────────────────────────────────────────────────────────────


def scenario_credit_bureau_circuit_open() -> dict[str, Any]:
    """Drive the credit-bureau circuit breaker to OPEN through repeated failures.

    Expected:
    - First ``failure_threshold`` calls raise ``ConnectionError`` and are
      passed through (CLOSED state absorbs them).
    - On the (threshold+1)th call the circuit transitions to OPEN.
    - Subsequent calls are immediately rejected without touching the function.
    """
    _print_section("Scenario 2: Credit bureau failures → circuit breaker opens")

    metrics = PipelineMetrics(evaluation_id="scenario-2-circuit-open")

    breaker = CircuitBreaker(
        name="credit_bureau_demo",
        failure_threshold=3,
        timeout_period=60.0,
        fallback=lambda **kw: {"error": "credit_bureau_circuit_open", "degraded": True},
    )

    attempt_log: list[dict[str, Any]] = []

    def _always_fail_credit_api(ssn: str) -> dict:
        raise ConnectionError("credit bureau unreachable")

    for i in range(1, 7):
        metrics.start_node(f"credit_call_{i}")
        try:
            result = breaker.call(_always_fail_credit_api, ssn="1234")
            status_label = "fallback"
            err = StructuredError.degraded(
                source=f"credit_call_{i}",
                message=f"Circuit open — fallback returned: {result}",
            )
        except ConnectionError as exc:
            status_label = "failed"
            err = StructuredError.recoverable(
                source=f"credit_call_{i}",
                message=str(exc),
                retry_count=1,
                exc=exc,
            )
        except CircuitBreakerOpen as exc:
            status_label = "circuit_open_rejected"
            err = StructuredError.degraded(
                source=f"credit_call_{i}",
                message=str(exc),
            )
        else:
            status_label = "success"
            err = StructuredError.recoverable(source=f"credit_call_{i}", message="ok")

        metrics.end_node(
            f"credit_call_{i}",
            status=status_label,
            errors=[err.to_state_string()],
        )
        attempt_log.append({
            "attempt": i,
            "circuit_state": breaker.state.value,
            "status": status_label,
        })
        print(f"  Attempt {i}: state={breaker.state.value}, status={status_label}")

    summary = metrics.summary()
    final_state = breaker.state.value
    print(f"\n  Final circuit state: {final_state}")
    print(f"  Metrics → total_errors={summary['total_errors']}")
    return {
        "scenario": "credit_bureau_circuit_open",
        "final_circuit_state": final_state,
        "attempts": attempt_log,
        "metrics": summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3: Partial data → graceful degradation
# ─────────────────────────────────────────────────────────────────────────────


def scenario_partial_data_degradation() -> dict[str, Any]:
    """Simulate a fetch where employment data is unavailable.

    Expected:
    - borrower and credit data succeed
    - employment check fails and is recorded as DEGRADED
    - pipeline continues with data_quality=PARTIAL
    """
    _print_section("Scenario 3: Partial data → graceful degradation")

    metrics = PipelineMetrics(evaluation_id="scenario-3-partial-data")
    metrics.start_node("fetch_data")

    errors: list[str] = []
    missing: list[str] = []

    # Borrower and credit succeed
    borrower = {
        "name": "Alice Strong",
        "annual_income": 120_000,
        "monthly_debt": 2_400,
        "loan_amount": 350_000,
        "property_value": 440_000,
        "property_state": "texas",
    }
    credit = {"fico_score": 740, "delinquencies": 0, "tier": "EXCELLENT"}

    # Employment verification is unavailable (circuit breaker fallback)
    employment_result = {"error": "employment_circuit_open", "degraded": True}
    if employment_result.get("degraded"):
        missing.append("employment")
        err = StructuredError.degraded(
            source="fetch_data_node",
            message="Employment verification unavailable; circuit open.",
        )
        errors.append(err.to_state_string())

    data_quality = "PARTIAL" if missing else "COMPLETE"

    metrics.end_node(
        "fetch_data",
        status="degraded" if missing else "success",
        tools_called=["pull_borrower_data", "pull_credit_report"],
        errors=errors,
        cost_estimate_usd=0.0002,
    )

    package = {
        "borrower": borrower,
        "credit": credit,
        "employment": employment_result,
        "data_quality": data_quality,
        "missing_fields": missing,
    }

    summary = metrics.summary()
    print(f"  data_quality  : {data_quality}")
    print(f"  missing_fields: {missing}")
    print(f"  errors        : {errors}")
    print(f"  Metrics → status={summary['node_metrics']['fetch_data']['status']}")

    return {
        "scenario": "partial_data_degradation",
        "data_quality": data_quality,
        "missing_fields": missing,
        "errors": errors,
        "metrics": summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4: Fatal error → pipeline routes to error report
# ─────────────────────────────────────────────────────────────────────────────


def scenario_fatal_error_report() -> dict[str, Any]:
    """Simulate a borrower not found (fatal) error and build an error report.

    Expected:
    - ``fatal_error=True`` is set in state
    - ``final_decision`` is an error report
    - Errors are categorised and surfaced by category
    """
    _print_section("Scenario 4: Fatal error → pipeline routes to error report")

    metrics = PipelineMetrics(evaluation_id="scenario-4-fatal-error")
    metrics.start_node("fetch_data")

    fatal = StructuredError.fatal(
        source="fetch_data_node",
        message="Application APP-999 not found in loan origination system.",
    )
    state_errors = [fatal.to_state_string()]

    metrics.end_node(
        "fetch_data",
        status="failed",
        errors=state_errors,
    )

    # Simulate final_decision_node receiving a fatal state
    categorized = categorize_pipeline_errors(state_errors)
    error_report = (
        "==== UNDERWRITING ERROR REPORT ====\n"
        f"Application ID : APP-999\n"
        f"Fatal Errors   :\n"
        + "\n".join(f"  • {e}" for e in categorized.get(ErrorCategory.FATAL.value, []))
        + "\n"
        f"Recommendation : DENY (pipeline aborted)\n"
        "===="
    )

    summary = metrics.summary()
    print(f"  Categorized errors: {json.dumps(categorized, indent=4)}")
    print(f"  Error report preview:\n{error_report}")
    print(f"  Metrics → total_errors={summary['total_errors']}, "
          f"status={summary['node_metrics']['fetch_data']['status']}")

    return {
        "scenario": "fatal_error_report",
        "categorized_errors": categorized,
        "error_report": error_report,
        "fatal_error": True,
        "metrics": summary,
    }


# ── Main ──────────────────────────────────────────────────────────────────────


def run_week5_day5_exercise() -> list[dict[str, Any]]:
    """Run all four resilience scenarios and return their results."""
    return [
        scenario_bedrock_timeout_retry(),
        scenario_credit_bureau_circuit_open(),
        scenario_partial_data_degradation(),
        scenario_fatal_error_report(),
    ]


if __name__ == "__main__":
    results = run_week5_day5_exercise()
    _print_section("Metrics Summary (all scenarios)")
    for r in results:
        scenario = r["scenario"]
        m = r["metrics"]
        print(
            f"  {scenario}: duration={m['total_duration_ms']}ms, "
            f"errors={m['total_errors']}, retries={m['total_retries']}, "
            f"cost=${m['total_cost_estimate_usd']}"
        )
