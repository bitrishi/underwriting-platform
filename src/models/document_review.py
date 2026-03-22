"""Models for document review classification, extraction, and package reporting."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from src.models.documents import (
    DocumentExtractionData,
    W2Extraction,
    TaxReturn1040Extraction,
    PayStubExtraction,
)


class DocumentClassification(BaseModel):
    """Result of classifying a single document."""
    file_path: str = Field(
        ..., description="Path to the classified document."
    )
    document_type: Literal[
        "W2", "1040", "PAYSTUB", "BANK_STATEMENT",
        "APPRAISAL", "EMPLOYMENT_LETTER", "OTHER", "UNREADABLE"
    ] = Field(..., description="Best-effort document class for downstream processing.")
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Confidence in the classification result."
    )
    page_count: int = Field(ge=1, description="Total pages detected for the file.")


class ExtractionResult(BaseModel):
    """Data extracted from a single document."""
    file_path: str = Field(..., description="Path to the source document.")
    document_type: Literal["W2", "1040", "PAYSTUB"] = Field(
        ..., description="Normalized document type used for extraction."
    )
    extraction_method: Literal["TEXT", "VISION"] = Field(
        ..., description="Whether extraction used text parsing or vision analysis."
    )
    extracted_data: DocumentExtractionData = Field(
        ..., description="Typed extraction payload from the document model layer."
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ..., description="Overall confidence in the extracted payload."
    )
    unclear_fields: list[str] = Field(
        default_factory=list,
        description="Fields that were unreadable, ambiguous, or only partially visible.",
    )
    processing_time_ms: float = Field(
        ..., ge=0, description="Total extraction time in milliseconds."
    )


class CrossValidationResult(BaseModel):
    """Result of comparing data across documents."""
    check_name: str = Field(
        description="What was compared (e.g., 'W2 wages vs 1040 AGI')"
    )
    status: Literal["MATCH", "DISCREPANCY", "UNABLE_TO_VERIFY"]
    details: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]


class MissingDocument(BaseModel):
    """A required document that was not found."""
    document_type: Literal[
        "W2", "1040", "PAYSTUB", "BANK_STATEMENT", "APPRAISAL", "EMPLOYMENT_LETTER"
    ] = Field(..., description="Document type that was expected but not found.")
    reason_required: str = Field(
        ..., description="Why the missing document is required for underwriting or validation."
    )
    impact: str = Field(
        description="Impact on underwriting if not provided"
    )


class DocumentReviewPackage(BaseModel):
    """
    Complete document review output.
    
    This is what the Document Review agent produces
    and what the Risk Scoring agent consumes.
    """
    # What documents were provided
    documents_classified: list[DocumentClassification]
    
    # Extracted data from each document
    extractions: list[ExtractionResult]
    
    # Cross-document validation results
    validations: list[CrossValidationResult]
    
    # What's missing
    missing_documents: list[MissingDocument] = Field(default_factory=list)
    
    # Overall assessment
    document_quality: Literal["COMPLETE", "PARTIAL", "INSUFFICIENT"]
    total_documents: int
    total_issues: int = Field(
        description="Number of discrepancies + missing docs"
    )
    
    def has_critical_issues(self) -> bool:
        """Check if the review package contains blocking document problems."""
        return any(v.severity == "CRITICAL" for v in self.validations) or any(
            missing.document_type in {"W2", "1040", "PAYSTUB"}
            for missing in self.missing_documents
        )
    
    def format_report(self) -> str:
        """Human-readable document review summary."""
        lines = [
            f"📋 DOCUMENT REVIEW: {self.document_quality}",
            f"   Documents: {self.total_documents} provided, "
            f"{len(self.missing_documents)} missing, "
            f"{self.total_issues} issues",
            "",
        ]
        
        # Classifications
        lines.append("Documents Received:")
        for doc in self.documents_classified:
            lines.append(
                f"  📄 {doc.document_type} — {doc.file_path} "
                f"(confidence: {doc.confidence})"
            )

        if self.extractions:
            lines.append("\nExtractions:")
            for extraction in self.extractions:
                lines.append(
                    f"  🧾 {extraction.document_type} via {extraction.extraction_method} "
                    f"(confidence: {extraction.confidence}, unclear: {len(extraction.unclear_fields)})"
                )
        
        # Validations
        if self.validations:
            lines.append("\nCross-Document Validation:")
            for v in self.validations:
                icon = {"MATCH": "✅", "DISCREPANCY": "⚠️", "UNABLE_TO_VERIFY": "❓"}
                lines.append(
                    f"  {icon.get(v.status, '?')} {v.check_name}: "
                    f"{v.status} — {v.details}"
                )
        
        # Missing
        if self.missing_documents:
            lines.append("\n🚫 Missing Documents:")
            for m in self.missing_documents:
                lines.append(
                    f"  - {m.document_type}: {m.reason_required} (impact: {m.impact})"
                )

        if self.has_critical_issues():
            lines.append("\n⚠️  Critical issues present — human review required.")
        else:
            lines.append("\n✅ No critical document issues detected.")
        
        return "\n".join(lines)