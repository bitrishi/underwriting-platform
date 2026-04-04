"""Retry decorator with exponential backoff and jitter for transient failures."""

from __future__ import annotations

import functools
import logging
import random
import time
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
    jitter: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory: retry with exponential backoff on transient failures.

    Delay schedule (without jitter):
        attempt 0 → base_delay * 2^0 = base_delay
        attempt 1 → base_delay * 2^1
        attempt 2 → base_delay * 2^2
        …capped at max_delay

    When ``jitter=True`` a uniform random amount up to 20 % of the computed
    delay is added to spread retry storms across replicas.

    Args:
        max_retries: Number of *additional* attempts after the first call fails.
            A value of 3 means up to 4 total calls.
        base_delay: Seconds to wait before the first retry.
        max_delay: Hard cap on computed wait time.
        retryable_exceptions: Only these exception types trigger a retry.
            Anything else propagates immediately.
        jitter: Whether to add random jitter to the delay.

    Returns:
        A decorator that wraps the target function with retry logic.

    Example::

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.5,
            retryable_exceptions=(ConnectionError, TimeoutError),
        )
        def call_external_api(url: str) -> dict:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt >= max_retries:
                        logger.error(
                            "[retry] %s exhausted all %d retries. "
                            "Final error: %s: %s",
                            func.__qualname__,
                            max_retries,
                            type(exc).__name__,
                            exc,
                        )
                        raise

                    raw_delay = min(base_delay * (2.0 ** attempt), max_delay)
                    wait = raw_delay + (random.uniform(0.0, raw_delay * 0.2) if jitter else 0.0)

                    logger.warning(
                        "[retry] %s attempt %d/%d failed (%s: %s). "
                        "Waiting %.3fs before retry.",
                        func.__qualname__,
                        attempt + 1,
                        max_retries,
                        type(exc).__name__,
                        exc,
                        wait,
                    )
                    time.sleep(wait)

            # Unreachable — satisfies type checkers.
            raise last_exc  # type: ignore[possibly-undefined]

        return wrapper

    return decorator
