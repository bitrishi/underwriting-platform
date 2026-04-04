"""Thread-safe circuit breaker for external service calls.

States
------
CLOSED   — normal operation; calls pass through to the wrapped function.
OPEN     — failure threshold exceeded; calls are rejected immediately and
           routed to the configured fallback (if any).
HALF_OPEN — the timeout period has elapsed; one probe call is admitted to
            test whether the dependency has recovered.

Transition rules
----------------
CLOSED → OPEN     when consecutive failures reach ``failure_threshold``
OPEN   → HALF_OPEN when ``timeout_period`` seconds have passed since opening
HALF_OPEN → CLOSED  when the probe call succeeds
HALF_OPEN → OPEN    when the probe call fails (restarts the timeout)
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── State enum ────────────────────────────────────────────────────────────────


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpen(Exception):
    """Raised when a call is rejected because the circuit is OPEN and no
    fallback has been configured."""


# ── Core class ────────────────────────────────────────────────────────────────


class CircuitBreaker:
    """Thread-safe circuit breaker.

    Args:
        name: Human-readable identifier used in log messages.
        failure_threshold: Number of consecutive failures before opening.
        timeout_period: Seconds to stay OPEN before probing (HALF_OPEN).
        fallback: Optional callable invoked instead of raising when OPEN.
            Receives the same ``*args`` and ``**kwargs`` as the wrapped call.

    Usage as a decorator::

        @circuit_breaker
        def fetch_credit_report(ssn: str) -> dict:
            ...

    Usage via ``call``::

        result = circuit_breaker.call(fetch_credit_report, ssn="1234")

    Introspection::

        circuit_breaker.status()   # → dict with state, counts, etc.
        circuit_breaker.reset()    # manually restore to CLOSED
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_period: float = 60.0,
        fallback: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_period = timeout_period
        self.fallback = fallback

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._lock = threading.Lock()

    # ── Property ──────────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        return self._state

    # ── Internal state machine ────────────────────────────────────────────────

    def _transition(self, new_state: CircuitState) -> None:
        """Set new state and log the transition (must be called under lock)."""
        if new_state != self._state:
            logger.warning(
                "[circuit_breaker] '%s': %s → %s",
                self.name,
                self._state.value,
                new_state.value,
            )
            self._state = new_state

    def _allow_call(self) -> bool:
        """Decide whether to let a call through (must be called under lock)."""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.timeout_period:
                # Transition to HALF_OPEN and admit exactly one probe call.
                self._transition(CircuitState.HALF_OPEN)
                return True
            return False
        # HALF_OPEN: only one probe is allowed at a time; subsequent callers
        # are still blocked until the probe resolves.
        return False

    def _on_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._failure_count = 0
                self._transition(CircuitState.CLOSED)

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — reopen immediately and restart the timer.
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)
            elif self._failure_count >= self.failure_threshold:
                self._opened_at = time.monotonic()
                self._transition(CircuitState.OPEN)

    # ── Public interface ──────────────────────────────────────────────────────

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute ``func`` through this circuit breaker.

        Raises:
            CircuitBreakerOpen: if the circuit is OPEN and no fallback is set.
        """
        with self._lock:
            allowed = self._allow_call()

        if not allowed:
            logger.warning(
                "[circuit_breaker] '%s' is OPEN — rejecting call to '%s'.",
                self.name,
                getattr(func, "__qualname__", str(func)),
            )
            if self.fallback is not None:
                return self.fallback(*args, **kwargs)
            raise CircuitBreakerOpen(
                f"Circuit '{self.name}' is OPEN. "
                f"Retry after {self.timeout_period:.0f}s."
            )

        try:
            result = func(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Use as a plain decorator: ``@my_breaker``."""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(func, *args, **kwargs)

        return wrapper

    def reset(self) -> None:
        """Manually restore the circuit to CLOSED (useful in tests)."""
        with self._lock:
            self._failure_count = 0
            self._opened_at = 0.0
            self._transition(CircuitState.CLOSED)

    def status(self) -> dict[str, Any]:
        """Return a snapshot of the circuit's current state."""
        with self._lock:
            seconds_until_probe = (
                max(0.0, self.timeout_period - (time.monotonic() - self._opened_at))
                if self._state == CircuitState.OPEN
                else 0.0
            )
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "timeout_period_s": self.timeout_period,
                "seconds_until_probe": round(seconds_until_probe, 1),
            }


# ── Pre-built circuit breakers for each external dependency ───────────────────


def _bedrock_fallback(*_: Any, **__: Any) -> Any:
    return {"error": "bedrock_circuit_open", "degraded": True}


def _credit_bureau_fallback(*_: Any, **__: Any) -> Any:
    return {"error": "credit_bureau_circuit_open", "degraded": True}


def _employment_fallback(*_: Any, **__: Any) -> Any:
    return {"error": "employment_circuit_open", "degraded": True}


def _neo4j_fallback(*_: Any, **__: Any) -> Any:
    return {"error": "neo4j_circuit_open", "degraded": True}


def _opensearch_fallback(*_: Any, **__: Any) -> Any:
    return {"error": "opensearch_circuit_open", "degraded": True}


bedrock_breaker = CircuitBreaker(
    name="bedrock",
    failure_threshold=5,
    timeout_period=30.0,
    fallback=_bedrock_fallback,
)

credit_bureau_breaker = CircuitBreaker(
    name="credit_bureau",
    failure_threshold=3,
    timeout_period=60.0,
    fallback=_credit_bureau_fallback,
)

employment_breaker = CircuitBreaker(
    name="employment_verification",
    failure_threshold=3,
    timeout_period=60.0,
    fallback=_employment_fallback,
)

neo4j_breaker = CircuitBreaker(
    name="neo4j",
    failure_threshold=5,
    timeout_period=45.0,
    fallback=_neo4j_fallback,
)

opensearch_breaker = CircuitBreaker(
    name="opensearch",
    failure_threshold=5,
    timeout_period=45.0,
    fallback=_opensearch_fallback,
)

# Registry for bulk status inspection (e.g. health checks)
ALL_BREAKERS: dict[str, CircuitBreaker] = {
    "bedrock": bedrock_breaker,
    "credit_bureau": credit_bureau_breaker,
    "employment_verification": employment_breaker,
    "neo4j": neo4j_breaker,
    "opensearch": opensearch_breaker,
}
