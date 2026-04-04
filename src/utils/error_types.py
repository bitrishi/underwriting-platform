"""Structured error types and categorisation for the underwriting pipeline.

Error categories
----------------
RECOVERABLE — transient, safe to retry (network blip, throttling, timeout).
DEGRADED    — dependency partially available; pipeline continues with reduced
              data quality (e.g. credit bureau returned a cached score).
FATAL       — unrecoverable; pipeline must abort or route to an error report
              (e.g. borrower record not found, schema validation failed).

Integration
-----------
Use :func:`StructuredError.to_state_string` to append to the ``errors`` list
in ``UnderwritingState``.  Call :func:`categorize_pipeline_errors` inside
``final_decision_node`` to group errors by category for the audit report.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Category enum ─────────────────────────────────────────────────────────────


class ErrorCategory(str, Enum):
    RECOVERABLE = "RECOVERABLE"
    DEGRADED = "DEGRADED"
    FATAL = "FATAL"


# ── Structured error model ────────────────────────────────────────────────────


class StructuredError(BaseModel):
    """Canonical error record attached to pipeline state.

    Attributes:
        category: Severity / recoverability tier.
        source: Node or tool that raised the error, e.g. ``"fetch_data_node"``.
        message: Human-readable description of the failure.
        timestamp: UTC ISO-8601 timestamp when the error was created.
        retry_count: How many times the operation was retried before giving up.
        original_exception: ``str(exc)`` from the caught exception, if any.
    """

    category: ErrorCategory
    source: str = Field(description="Node or tool that raised the error")
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    retry_count: int = Field(default=0, ge=0)
    original_exception: str | None = None

    # ── Convenience constructors ──────────────────────────────────────────────

    @classmethod
    def recoverable(
        cls,
        source: str,
        message: str,
        retry_count: int = 0,
        exc: Exception | None = None,
    ) -> "StructuredError":
        """Transient failure — safe to retry."""
        return cls(
            category=ErrorCategory.RECOVERABLE,
            source=source,
            message=message,
            retry_count=retry_count,
            original_exception=str(exc) if exc is not None else None,
        )

    @classmethod
    def degraded(
        cls,
        source: str,
        message: str,
        exc: Exception | None = None,
    ) -> "StructuredError":
        """Service returned partial / stale data; pipeline continues degraded."""
        return cls(
            category=ErrorCategory.DEGRADED,
            source=source,
            message=message,
            original_exception=str(exc) if exc is not None else None,
        )

    @classmethod
    def fatal(
        cls,
        source: str,
        message: str,
        exc: Exception | None = None,
    ) -> "StructuredError":
        """Unrecoverable failure; pipeline should abort or route to error report."""
        return cls(
            category=ErrorCategory.FATAL,
            source=source,
            message=message,
            original_exception=str(exc) if exc is not None else None,
        )

    # ── State integration ─────────────────────────────────────────────────────

    def to_state_string(self) -> str:
        """Compact representation for the ``errors`` list in ``UnderwritingState``.

        Format: ``[CATEGORY] source: message``
        """
        return f"[{self.category.value}] {self.source}: {self.message}"


# ── Pipeline-level grouping ───────────────────────────────────────────────────


def categorize_pipeline_errors(
    errors: list[str | dict[str, Any]],
) -> dict[str, list[str]]:
    """Group a flat error list by :class:`ErrorCategory`.

    Accepts both plain strings (legacy format) and dicts / StructuredError
    dicts so the function works across existing and new code paths.

    Used by ``final_decision_node`` to surface errors by severity in the
    audit report.

    Args:
        errors: Entries from ``UnderwritingState["errors"]``.

    Returns:
        Dict mapping category name → list of error strings.
        Empty categories are omitted.

    Example::

        {
            "RECOVERABLE": ["[RECOVERABLE] fetch_data_node: credit timeout"],
            "FATAL": ["[FATAL] fetch_data_node: borrower APP-999 not found"],
        }
    """
    groups: dict[str, list[str]] = {
        ErrorCategory.RECOVERABLE.value: [],
        ErrorCategory.DEGRADED.value: [],
        ErrorCategory.FATAL.value: [],
        "UNCATEGORIZED": [],
    }

    for err in errors:
        if isinstance(err, dict):
            cat = str(err.get("category", "")).upper()
            msg = str(err.get("message", "")) or str(err)
        else:
            text = str(err)
            # Detect the structured prefix written by to_state_string().
            if text.startswith("[RECOVERABLE]"):
                cat, msg = ErrorCategory.RECOVERABLE.value, text
            elif text.startswith("[DEGRADED]"):
                cat, msg = ErrorCategory.DEGRADED.value, text
            elif text.startswith("[FATAL]"):
                cat, msg = ErrorCategory.FATAL.value, text
            else:
                cat, msg = "UNCATEGORIZED", text

        if cat in groups:
            groups[cat].append(msg)
        else:
            groups["UNCATEGORIZED"].append(msg)

    return {k: v for k, v in groups.items() if v}
