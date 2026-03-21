"""Pydantic models for policy retrieval responses."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class PolicyAnswer(BaseModel):
    """Structured answer returned by the policy RAG chain."""

    answer: str = Field(
        ...,
        min_length=1,
        description="Direct answer to the user's policy/compliance question.",
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ...,
        description="Confidence level based strictly on provided retrieval context.",
    )
    sources: List[str] = Field(
        default_factory=list,
        description="Source citations used to support the answer.",
    )
    relevant_quotes: List[str] = Field(
        default_factory=list,
        description="Key direct quotes from source documents supporting the answer.",
    )
    sufficient_context: bool = Field(
        ...,
        description="Whether retrieved documents were sufficient to answer reliably.",
    )

    def format_report(self) -> str:
        """Return a readable answer report with citations and supporting quotes."""
        lines: list[str] = []
        lines.append("Policy Retrieval Report")
        lines.append("=" * 24)
        lines.append(f"Answer: {self.answer}")
        lines.append(f"Confidence: {self.confidence}")
        lines.append(
            f"Sufficient Context: {'Yes' if self.sufficient_context else 'No'}"
        )

        lines.append("")
        lines.append("Sources:")
        if self.sources:
            for index, source in enumerate(self.sources, start=1):
                lines.append(f"{index}. {source}")
        else:
            lines.append("1. None provided")

        lines.append("")
        lines.append("Relevant Quotes:")
        if self.relevant_quotes:
            for index, quote in enumerate(self.relevant_quotes, start=1):
                lines.append(f"{index}. \"{quote}\"")
        else:
            lines.append("1. None provided")

        return "\n".join(lines)
