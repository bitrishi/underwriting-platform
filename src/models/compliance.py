"""
Pydantic models for compliance answers.

ComplianceAnswer does grading + answering + self-verification
in a SINGLE LLM call instead of separate calls:
  - Old approach: 8 LLM calls (grade each doc + generate + verify)
  - New approach: 1 LLM call (combined ComplianceAnswer)

The LLM fills ALL fields in one response. Each Field(description=...)
tells the LLM what to put in that field. The field names (like
"all_claims_supported") are NOT magic keywords — the LLM reads
the description, not the Python field name.
"""

from pydantic import BaseModel, Field
from typing import Literal


class IrrelevantDocument(BaseModel):
    """A document that was retrieved but deemed not relevant to the question."""

    document_number: int = Field(
        description="The 1-indexed number of the document in the context list"
    )
    reason: str = Field(
        description="Brief explanation of why this document is not relevant "
                    "to the specific question being asked"
    )


class ComplianceAnswer(BaseModel):
    """
    Combined grading + answer + self-verification in ONE LLM response.

    This replaces three separate LLM calls:
    1. Retrieval grader → now: relevant_document_numbers + irrelevant_documents
    2. Answer generator → now: answer + sources + confidence
    3. Hallucination checker → now: all_claims_supported + unsupported_claims

    The LLM fills all fields in a single structured output call.
    """

    # ──────────────────────────────────────────────────────
    # CONTEXT ASSESSMENT (replaces separate retrieval grader)
    # ──────────────────────────────────────────────────────
    sufficient_context: bool = Field(
        description="Do the provided documents contain enough relevant "
                    "information to answer the question? Set false if "
                    "fewer than 2 documents are relevant."
    )
    relevant_document_numbers: list[int] = Field(
        default_factory=list,
        description="Which document numbers (1-indexed) from the context "
                    "are relevant to answering the question"
    )
    irrelevant_documents: list[IrrelevantDocument] = Field(
        default_factory=list,
        description="Documents that were provided but are NOT relevant, "
                    "with explanation of why each is irrelevant"
    )

    # ──────────────────────────────────────────────────────
    # ANSWER (generated from relevant documents only)
    # ──────────────────────────────────────────────────────
    answer: str | None = Field(
        default=None,
        description="Answer based ONLY on the relevant documents. "
                    "Must cite specific sources. "
                    "Set to null if sufficient_context is false."
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Source citations for each claim in the answer. "
                    "Format: 'document_name.pdf, Page X, Section Y'"
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW", "NONE"] = Field(
        description="HIGH: multiple docs clearly support answer. "
                    "MEDIUM: one doc supports, or partial support. "
                    "LOW: answer is inferred, not directly stated. "
                    "NONE: insufficient context, no answer provided."
    )

    # ──────────────────────────────────────────────────────
    # SELF-VERIFICATION (replaces separate hallucination check)
    # ──────────────────────────────────────────────────────
    all_claims_supported: bool = Field(
        description="After writing the answer, verify: are ALL claims "
                    "in the answer directly supported by the provided "
                    "documents? If answer is null, set to true."
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="List any specific claims in the answer that are "
                    "NOT directly stated in the provided documents. "
                    "Empty list if all claims are supported."
    )

    # ──────────────────────────────────────────────────────
    # HELPER METHODS
    # ──────────────────────────────────────────────────────
    def is_trustworthy(self) -> bool:
        """
        Quick check: is this answer reliable enough to use?

        An answer is trustworthy if:
        - Context was sufficient
        - All claims are supported by documents
        - No hallucinated claims detected
        - Confidence is at least MEDIUM
        """
        return (
            self.sufficient_context
            and self.all_claims_supported
            and len(self.unsupported_claims) == 0
            and self.confidence in ("HIGH", "MEDIUM")
        )

    def format_report(self) -> str:
        """
        Format as a human-readable compliance report.

        Used for:
        - Console output during development
        - Audit trail in production
        - UI display in Streamlit (Week 6)
        """
        lines = []

        # Handle insufficient context
        if not self.sufficient_context:
            lines.append("⚠️  INSUFFICIENT DOCUMENTATION")
            lines.append(
                "The retrieved documents do not adequately "
                "answer this question."
            )
            if self.irrelevant_documents:
                lines.append("\nDocuments retrieved but not relevant:")
                for doc in self.irrelevant_documents:
                    lines.append(
                        f"  - Doc {doc.document_number}: {doc.reason}"
                    )
            return "\n".join(lines)

        # Main answer
        lines.append(f"📋 Answer (Confidence: {self.confidence}):")
        lines.append(self.answer or "No answer generated.")

        # Sources
        if self.sources:
            lines.append(f"\n📚 Sources:")
            for source in self.sources:
                lines.append(f"  - {source}")

        # Relevant docs used
        if self.relevant_document_numbers:
            lines.append(
                f"\n📄 Used documents: "
                f"{self.relevant_document_numbers}"
            )

        # Irrelevant docs filtered
        if self.irrelevant_documents:
            lines.append(f"\n🚫 Filtered out:")
            for doc in self.irrelevant_documents:
                lines.append(
                    f"  - Doc {doc.document_number}: {doc.reason}"
                )

        # Verification status
        if self.all_claims_supported:
            lines.append("\n✅ All claims verified against source documents.")
        else:
            lines.append("\n⚠️  UNSUPPORTED CLAIMS DETECTED:")
            for claim in self.unsupported_claims:
                lines.append(f"  - {claim}")

        return "\n".join(lines)