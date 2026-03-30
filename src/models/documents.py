"""Structured models for multimodal document extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class W2Extraction(BaseModel):
    """Data extracted from a W-2 Wage and Tax Statement."""
    employer_name: str = Field(
        description="Employer name from box (c)"
    )
    employee_name: str = Field(
        description="Employee name from box (e)"
    )
    wages: float = Field(
        description="Wages, tips, other compensation from box 1"
    )
    federal_tax_withheld: float = Field(
        description="Federal income tax withheld from box 2"
    )
    social_security_wages: float = Field(
        description="Social security wages from box 3"
    )
    tax_year: int = Field(
        description="Tax year from the form header"
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description="How confident you are in the extraction accuracy"
    )
    unclear_fields: list[str] = Field(
        default_factory=list,
        description="Any fields that were blurry, unclear, or partially visible"
    )


class TaxReturn1040Extraction(BaseModel):
    """Data extracted from IRS Form 1040."""
    tax_year: int
    filing_status: Literal[
        "SINGLE", "MARRIED_JOINT", "MARRIED_SEPARATE",
        "HEAD_OF_HOUSEHOLD", "QUALIFYING_WIDOW"
    ]
    adjusted_gross_income: float = Field(
        description="AGI from line 11"
    )
    taxable_income: float = Field(
        description="Taxable income from line 15"
    )
    total_tax: float = Field(
        description="Total tax from line 24"
    )
    self_employment_income: float | None = Field(
        default=None,
        description="Schedule SE income, if present"
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    unclear_fields: list[str] = Field(default_factory=list)


class PayStubExtraction(BaseModel):
    """Data extracted from a pay stub."""
    employer_name: str
    employee_name: str
    pay_period_start: str = Field(
        description="Pay period start date (YYYY-MM-DD)"
    )
    pay_period_end: str = Field(
        description="Pay period end date (YYYY-MM-DD)"
    )
    gross_pay: float
    net_pay: float
    ytd_gross: float = Field(
        description="Year-to-date gross earnings"
    )
    pay_frequency: Literal[
        "WEEKLY", "BIWEEKLY", "SEMIMONTHLY", "MONTHLY"
    ]
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    unclear_fields: list[str] = Field(default_factory=list)


DocumentExtractionData = W2Extraction | TaxReturn1040Extraction | PayStubExtraction


class DocumentExtractionMetadata(BaseModel):
    """Operational metadata describing how extraction was performed."""

    document_path: str = Field(
        ..., description="Absolute or relative path to the processed document."
    )
    processing_method: Literal["text", "vision", "textract", "hybrid"] = Field(
        ..., description="Whether extraction used text parsing or vision fallback."
    )
    processing_time_ms: float = Field(
        ..., ge=0, description="Total extraction processing time in milliseconds."
    )
    estimated_cost_usd: float = Field(
        default=0.0,
        ge=0,
        description="Estimated per-document extraction cost in USD.",
    )


class DocumentExtractionResult(BaseModel):
    """Unified extraction result with parsed data and operational metadata."""

    document_type: Literal["w2", "1040", "paystub"] = Field(
        ..., description="Document classifier used for extraction schema selection."
    )
    extracted_data: DocumentExtractionData = Field(
        ..., description="Schema-validated extracted document payload."
    )
    metadata: DocumentExtractionMetadata = Field(
        ..., description="Processing metadata including method and elapsed time."
    )