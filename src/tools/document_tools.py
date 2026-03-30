"""Document processing tools for multimodal underwriting extraction."""

from __future__ import annotations

import base64
import re
import time
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pypdf import PdfReader

from src.tools.document_router import route_document
from src.tools.field_mappings import map_textract_to_model
from src.tools.textract_tools import detect_document_text
from src.models.document_review import (
    CrossValidationResult,
    DocumentClassification,
    DocumentReviewPackage,
    ExtractionResult,
    MissingDocument,
)
from src.models.documents import (
    DocumentExtractionMetadata,
    DocumentExtractionResult,
    PayStubExtraction,
    TaxReturn1040Extraction,
    W2Extraction,
)

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}
SUPPORTED_DOCUMENT_TYPES = {"w2", "1040", "paystub"}


def _estimate_extraction_cost_usd(method: str, page_count: int) -> float:
    normalized = method.lower()
    if normalized == "textract":
        # Approximate for FORMS/TEXT extraction on standard underwriting docs.
        return round(page_count * 0.0015, 6)
    if normalized == "vision":
        # Approximate model invocation cost for image extraction.
        return round(page_count * 0.01, 6)
    if normalized == "hybrid":
        return round((page_count * 0.0015) + (page_count * 0.01), 6)
    return 0.0


def encode_image(image_path: str) -> str:
    """Encode an image file as a base64 string.

    Args:
        image_path: Path to a PNG or JPEG image file.

    Returns:
        Base64-encoded image payload suitable for multimodal model input.

    Raises:
        FileNotFoundError: If the image file does not exist.
        ValueError: If the file is not a supported image format.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise ValueError(f"Unsupported image format for encoding: {path.suffix}")

    return base64.b64encode(path.read_bytes()).decode("utf-8")


def has_extractable_text(document_path: str) -> bool:
    """Determine whether a document can be processed through text extraction.

    Args:
        document_path: Path to a text, PDF, or image document.

    Returns:
        True for text documents and parseable PDFs, False for image-only inputs.
    """
    path = Path(document_path)
    suffix = path.suffix.lower()

    if suffix == ".txt":
        return True

    if suffix == ".pdf":
        try:
            reader = PdfReader(str(path))
            extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
            return bool(extracted.strip()) or len(reader.pages) > 0
        except Exception:
            return False

    return False


def _read_text_for_extraction(document_path: str, processing_method: str) -> str:
    path = Path(document_path)
    if processing_method == "text":
        if path.suffix.lower() == ".txt":
            return path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join((page.extract_text() or "") for page in reader.pages)

    sidecar = path.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8")

    return ""


def _get_page_count(document_path: str) -> int:
    path = Path(document_path)
    if path.suffix.lower() == ".pdf":
        try:
            return len(PdfReader(str(path)).pages)
        except Exception:
            return 1
    return 1


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.replace(",", "").replace("$", "").strip()
    return float(normalized) if normalized else None


def _extract_w2(text: str) -> W2Extraction:
    mappings = {
        "employer_name": r"Employer Name:\s*(.+)",
        "employee_name": r"Employee Name:\s*(.+)",
        "wages": r"Wages:\s*([\d,\.]+)",
        "federal_tax_withheld": r"Federal Tax Withheld:\s*([\d,\.]+)",
        "social_security_wages": r"Social Security Wages:\s*([\d,\.]+)",
        "tax_year": r"Tax Year:\s*(\d{4})",
    }

    values: dict[str, object] = {}
    unclear: list[str] = []

    for key, pattern in mappings.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            unclear.append(key)
            continue
        raw = match.group(1).strip()
        if key in {"wages", "federal_tax_withheld", "social_security_wages"}:
            values[key] = _to_float(raw)
        elif key == "tax_year":
            values[key] = int(raw)
        else:
            values[key] = raw

    confidence = "HIGH" if len(unclear) == 0 else "MEDIUM" if len(unclear) <= 2 else "LOW"
    return W2Extraction(
        employer_name=str(values.get("employer_name", "UNKNOWN")),
        employee_name=str(values.get("employee_name", "UNKNOWN")),
        wages=float(values.get("wages") or 0.0),
        federal_tax_withheld=float(values.get("federal_tax_withheld") or 0.0),
        social_security_wages=float(values.get("social_security_wages") or 0.0),
        tax_year=int(values.get("tax_year") or 0),
        confidence=confidence,
        unclear_fields=unclear,
    )


def _extract_1040(text: str) -> TaxReturn1040Extraction:
    mappings = {
        "tax_year": r"Tax Year:\s*(\d{4})",
        "filing_status": r"Filing Status:\s*([A-Z_ ]+)",
        "adjusted_gross_income": r"Adjusted Gross Income:\s*([\d,\.]+)",
        "taxable_income": r"Taxable Income:\s*([\d,\.]+)",
        "total_tax": r"Total Tax:\s*([\d,\.]+)",
        "self_employment_income": r"Self Employment Income:\s*([\d,\.]+)",
    }

    values: dict[str, object] = {}
    unclear: list[str] = []

    for key, pattern in mappings.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            if key != "self_employment_income":
                unclear.append(key)
            continue
        raw = match.group(1).strip().upper()
        if key in {"adjusted_gross_income", "taxable_income", "total_tax", "self_employment_income"}:
            values[key] = _to_float(raw)
        elif key == "tax_year":
            values[key] = int(raw)
        else:
            normalized = raw.replace(" ", "_")
            aliases = {
                "MARRIED_FILING_JOINTLY": "MARRIED_JOINT",
                "MARRIED_JOINT": "MARRIED_JOINT",
                "MARRIED_SEPARATE": "MARRIED_SEPARATE",
                "HEAD_OF_HOUSEHOLD": "HEAD_OF_HOUSEHOLD",
                "QUALIFYING_WIDOW": "QUALIFYING_WIDOW",
                "SINGLE": "SINGLE",
            }
            values[key] = aliases.get(normalized, "SINGLE")

    confidence = "HIGH" if len(unclear) == 0 else "MEDIUM" if len(unclear) <= 2 else "LOW"
    return TaxReturn1040Extraction(
        tax_year=int(values.get("tax_year") or 0),
        filing_status=str(values.get("filing_status") or "SINGLE"),
        adjusted_gross_income=float(values.get("adjusted_gross_income") or 0.0),
        taxable_income=float(values.get("taxable_income") or 0.0),
        total_tax=float(values.get("total_tax") or 0.0),
        self_employment_income=(
            float(values["self_employment_income"])
            if values.get("self_employment_income") is not None
            else None
        ),
        confidence=confidence,
        unclear_fields=unclear,
    )


def _extract_paystub(text: str) -> PayStubExtraction:
    mappings = {
        "employer_name": r"Employer Name:\s*(.+)",
        "employee_name": r"Employee Name:\s*(.+)",
        "pay_period_start": r"Pay Period Start:\s*(\d{4}-\d{2}-\d{2})",
        "pay_period_end": r"Pay Period End:\s*(\d{4}-\d{2}-\d{2})",
        "gross_pay": r"Gross Pay:\s*([\d,\.]+)",
        "net_pay": r"Net Pay:\s*([\d,\.]+)",
        "ytd_gross": r"YTD Gross:\s*([\d,\.]+)",
        "pay_frequency": r"Pay Frequency:\s*([A-Z_]+)",
    }

    values: dict[str, object] = {}
    unclear: list[str] = []

    for key, pattern in mappings.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            unclear.append(key)
            continue
        raw = match.group(1).strip().upper()
        if key in {"gross_pay", "net_pay", "ytd_gross"}:
            values[key] = _to_float(raw)
        elif key == "pay_frequency":
            values[key] = raw
        else:
            values[key] = match.group(1).strip()

    confidence = "HIGH" if len(unclear) == 0 else "MEDIUM" if len(unclear) <= 2 else "LOW"
    return PayStubExtraction(
        employer_name=str(values.get("employer_name", "UNKNOWN")),
        employee_name=str(values.get("employee_name", "UNKNOWN")),
        pay_period_start=str(values.get("pay_period_start", "1970-01-01")),
        pay_period_end=str(values.get("pay_period_end", "1970-01-01")),
        gross_pay=float(values.get("gross_pay") or 0.0),
        net_pay=float(values.get("net_pay") or 0.0),
        ytd_gross=float(values.get("ytd_gross") or 0.0),
        pay_frequency=str(values.get("pay_frequency") or "MONTHLY"),
        confidence=confidence,
        unclear_fields=unclear,
    )


def _extract_by_type(document_type: str, text: str) -> W2Extraction | TaxReturn1040Extraction | PayStubExtraction:
    if document_type == "w2":
        return _extract_w2(text)
    if document_type == "1040":
        return _extract_1040(text)
    if document_type == "paystub":
        return _extract_paystub(text)
    raise ValueError(f"Unsupported document type: {document_type}")


def _classify_from_text_and_name(document_path: str, text: str) -> str:
    lowered_name = Path(document_path).name.lower()
    lowered_text = text.lower()

    if "w-2" in lowered_text or "w2" in lowered_name:
        return "W2"
    if "1040" in lowered_text or "tax_return" in lowered_name or "form 1040" in lowered_text:
        return "1040"
    if "pay stub" in lowered_text or "paystub" in lowered_name or "ytd gross" in lowered_text:
        return "PAYSTUB"
    if "appraisal" in lowered_text:
        return "APPRAISAL"
    if "bank statement" in lowered_text:
        return "BANK_STATEMENT"
    if "employment letter" in lowered_text:
        return "EMPLOYMENT_LETTER"
    return "OTHER" if text.strip() or Path(document_path).exists() else "UNREADABLE"


def _normalize_extraction_result(raw: dict[str, Any]) -> ExtractionResult:
    extracted_data = raw.get("extracted_data", {})
    document_type = str(raw.get("document_type", "")).upper()
    method = str(raw.get("metadata", {}).get("processing_method", "text")).upper()

    model_map = {
        "W2": W2Extraction,
        "1040": TaxReturn1040Extraction,
        "PAYSTUB": PayStubExtraction,
    }
    extraction_model = model_map[document_type]
    typed_payload = extraction_model.model_validate(extracted_data)

    return ExtractionResult(
        file_path=str(raw.get("metadata", {}).get("document_path", "")),
        document_type=document_type,
        extraction_method=method,
        extracted_data=typed_payload,
        confidence=typed_payload.confidence,
        unclear_fields=typed_payload.unclear_fields,
        processing_time_ms=float(raw.get("metadata", {}).get("processing_time_ms", 0.0)),
    )


@tool
def extract_document_data(
    document_path: str,
    document_type: str,
    preferred_method: str = "auto",
) -> dict:
    """Extract structured data from an underwriting document.

    The tool chooses text extraction for `.txt` and digital PDFs when possible,
    and falls back to a vision-style path for images or scanned documents. The
    returned payload is schema-validated and includes processing metadata.

    Args:
        document_path: Path to the source document.
        document_type: One of `w2`, `1040`, or `paystub`.
        preferred_method: `auto`, `text`, `vision`, or `textract`.

    Returns:
        Serialized `DocumentExtractionResult` on success, otherwise an error dict.
    """
    start = time.perf_counter()
    path = Path(document_path)

    try:
        if not path.exists():
            return {"error": f"Document not found: {document_path}"}
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {"error": f"Unsupported file format: {path.suffix}"}
        if document_type not in SUPPORTED_DOCUMENT_TYPES:
            return {"error": f"Unsupported document type: {document_type}"}
        if preferred_method not in {"auto", "text", "vision", "textract"}:
            return {"error": f"Unsupported preferred_method: {preferred_method}"}

        route = route_document(document_path, declared_document_type=document_type)
        method = route["primary_method"] if preferred_method == "auto" else preferred_method
        extraction_method = method

        if method == "textract":
            textract_payload = detect_document_text(document_path)
            extracted = map_textract_to_model(document_type, textract_payload)
        else:
            if method == "text" and not has_extractable_text(document_path):
                extraction_method = "vision"
            raw_text = _read_text_for_extraction(document_path, extraction_method)
            extracted = _extract_by_type(document_type, raw_text)

        page_count = _get_page_count(document_path)
        result = DocumentExtractionResult(
            document_type=document_type,
            extracted_data=extracted,
            metadata=DocumentExtractionMetadata(
                document_path=str(path),
                processing_method=extraction_method,
                processing_time_ms=(time.perf_counter() - start) * 1000.0,
                estimated_cost_usd=_estimate_extraction_cost_usd(extraction_method, page_count),
            ),
        )
        return result.model_dump()
    except Exception as exc:
        return {
            "error": f"Extraction failed: {exc}",
            "document_path": str(path),
            "document_type": document_type,
        }


@tool
def compare_documents(doc1_data: dict, doc2_data: dict, comparison_type: str) -> dict:
    """Compare extracted data across two documents for consistency checks.

    Supported comparison types:
    - `income_consistency`: W-2 wages vs 1040 AGI
    - `employment_match`: employer name comparison
    - `ytd_verification`: pay stub YTD gross vs W-2 wages

    Args:
        doc1_data: Extracted payload from document 1.
        doc2_data: Extracted payload from document 2.
        comparison_type: Named comparison rule to run.

    Returns:
        Comparison metrics and pass/fail status, or an error dict.
    """
    try:
        if comparison_type == "income_consistency":
            w2_wages = float(doc1_data.get("wages", 0) or 0)
            agi = float(doc2_data.get("adjusted_gross_income", 0) or 0)
            diff = abs(w2_wages - agi)
            diff_pct = (diff / max(w2_wages, 1)) * 100
            return {
                "match": diff_pct < 10,
                "w2_wages": w2_wages,
                "agi": agi,
                "difference": diff,
                "difference_pct": round(diff_pct, 2),
                "flag": "CONSISTENT" if diff_pct < 10 else "DISCREPANCY_DETECTED",
            }

        if comparison_type == "employment_match":
            left = str(doc1_data.get("employer_name", "")).strip().lower()
            right = str(doc2_data.get("employer_name", "")).strip().lower()
            match = bool(left and right and left == right)
            return {
                "match": match,
                "employer_doc1": doc1_data.get("employer_name"),
                "employer_doc2": doc2_data.get("employer_name"),
                "flag": "CONSISTENT" if match else "MISMATCH",
            }

        if comparison_type == "ytd_verification":
            ytd = float(doc1_data.get("ytd_gross", 0) or 0)
            wages = float(doc2_data.get("wages", 0) or 0)
            diff = abs(ytd - wages)
            diff_pct = (diff / max(wages, 1)) * 100
            return {
                "match": diff_pct < 15,
                "paystub_ytd": ytd,
                "w2_wages": wages,
                "difference": diff,
                "difference_pct": round(diff_pct, 2),
                "flag": "CONSISTENT" if diff_pct < 15 else "DISCREPANCY_DETECTED",
            }

        return {"error": f"Unknown comparison type: {comparison_type}"}
    except Exception as exc:
        return {"error": f"Comparison failed: {exc}"}


@tool
def classify_document(document_path: str) -> dict:
    """Classify an underwriting document using deterministic file/text heuristics.

    This tool is intentionally robust for local development: it inspects the file
    name and any extractable text to infer the most likely document type without
    requiring a vision model.

    Args:
        document_path: Path to the document to classify.

    Returns:
        Serialized `DocumentClassification` on success, otherwise an error dict.
    """
    path = Path(document_path)
    try:
        if not path.exists():
            return {"error": f"Document not found: {document_path}"}
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return {"error": f"Unsupported file format: {path.suffix}"}

        method = "text" if has_extractable_text(document_path) else "vision"
        text = _read_text_for_extraction(document_path, method)
        document_type = _classify_from_text_and_name(document_path, text)
        confidence = "HIGH" if document_type in {"W2", "1040", "PAYSTUB"} else "MEDIUM" if document_type == "OTHER" else "LOW"

        result = DocumentClassification(
            file_path=str(path),
            document_type=document_type,
            confidence=confidence,
            page_count=_get_page_count(document_path),
        )
        return result.model_dump()
    except Exception as exc:
        return {"error": f"Classification failed: {exc}", "document_path": document_path}


@tool
def validate_document_package(extractions: list[dict]) -> dict:
    """Validate a set of extracted documents and build a review package.

    The tool normalizes extraction payloads, runs cross-document consistency
    checks, identifies missing core documents, and returns a serialized
    `DocumentReviewPackage`.

    Args:
        extractions: A list of serialized outputs from `extract_document_data`.

    Returns:
        Serialized `DocumentReviewPackage` on success, otherwise an error dict.
    """
    try:
        normalized_extractions: list[ExtractionResult] = []
        classifications: list[DocumentClassification] = []
        validations: list[CrossValidationResult] = []
        missing_documents: list[MissingDocument] = []

        for raw in extractions:
            if raw.get("error"):
                continue
            normalized = _normalize_extraction_result(raw)
            normalized_extractions.append(normalized)
            classifications.append(
                DocumentClassification(
                    file_path=normalized.file_path,
                    document_type=normalized.document_type,
                    confidence=normalized.confidence,
                    page_count=_get_page_count(normalized.file_path),
                )
            )

        extracted_by_type = {item.document_type: item for item in normalized_extractions}

        w2_item = extracted_by_type.get("W2")
        tax_item = extracted_by_type.get("1040")
        paystub_item = extracted_by_type.get("PAYSTUB")

        if w2_item and tax_item:
            comparison = compare_documents.invoke(
                {
                    "doc1_data": w2_item.extracted_data.model_dump(),
                    "doc2_data": tax_item.extracted_data.model_dump(),
                    "comparison_type": "income_consistency",
                }
            )
            validations.append(
                CrossValidationResult(
                    check_name="W-2 wages vs 1040 AGI",
                    status="MATCH" if comparison.get("match") else "DISCREPANCY",
                    details=(
                        f"W-2: ${comparison.get('w2_wages', 0):,.0f}, "
                        f"AGI: ${comparison.get('agi', 0):,.0f} "
                        f"(diff: {comparison.get('difference_pct', 0):.1f}%)"
                    ),
                    severity=(
                        "INFO" if comparison.get("difference_pct", 0) < 5
                        else "WARNING" if comparison.get("difference_pct", 0) < 10
                        else "CRITICAL"
                    ),
                )
            )
        else:
            validations.append(
                CrossValidationResult(
                    check_name="W-2 wages vs 1040 AGI",
                    status="UNABLE_TO_VERIFY",
                    details="Required W-2 and/or 1040 document not available.",
                    severity="WARNING",
                )
            )

        if w2_item and paystub_item:
            comparison = compare_documents.invoke(
                {
                    "doc1_data": paystub_item.extracted_data.model_dump(),
                    "doc2_data": w2_item.extracted_data.model_dump(),
                    "comparison_type": "employment_match",
                }
            )
            validations.append(
                CrossValidationResult(
                    check_name="Pay stub employer vs W-2 employer",
                    status="MATCH" if comparison.get("match") else "DISCREPANCY",
                    details=(
                        f"Pay stub: {comparison.get('employer_doc1')}, "
                        f"W-2: {comparison.get('employer_doc2')}"
                    ),
                    severity="INFO" if comparison.get("match") else "CRITICAL",
                )
            )

            ytd_comparison = compare_documents.invoke(
                {
                    "doc1_data": paystub_item.extracted_data.model_dump(),
                    "doc2_data": w2_item.extracted_data.model_dump(),
                    "comparison_type": "ytd_verification",
                }
            )
            validations.append(
                CrossValidationResult(
                    check_name="Pay stub YTD vs W-2 wages",
                    status="MATCH" if ytd_comparison.get("match") else "DISCREPANCY",
                    details=(
                        f"Pay stub YTD: ${ytd_comparison.get('paystub_ytd', 0):,.0f}, "
                        f"W-2 wages: ${ytd_comparison.get('w2_wages', 0):,.0f} "
                        f"(diff: {ytd_comparison.get('difference_pct', 0):.1f}%)"
                    ),
                    severity="INFO" if ytd_comparison.get("match") else "WARNING",
                )
            )
        else:
            validations.append(
                CrossValidationResult(
                    check_name="Pay stub cross-checks",
                    status="UNABLE_TO_VERIFY",
                    details="Required pay stub and/or W-2 document not available.",
                    severity="WARNING",
                )
            )

        required_documents = {
            "W2": ("Income verification", "Cannot verify annual wage income."),
            "1040": ("Tax filing verification", "Cannot verify AGI or filing status."),
            "PAYSTUB": ("Current income verification", "Cannot confirm recent payroll continuity."),
        }
        for doc_type, (reason, impact) in required_documents.items():
            if doc_type not in extracted_by_type:
                missing_documents.append(
                    MissingDocument(
                        document_type=doc_type,
                        reason_required=reason,
                        impact=impact,
                    )
                )

        total_issues = (
            len([item for item in validations if item.status != "MATCH"])
            + len(missing_documents)
        )
        if not missing_documents and not any(v.severity == "CRITICAL" for v in validations):
            document_quality = "COMPLETE"
        elif normalized_extractions:
            document_quality = "PARTIAL"
        else:
            document_quality = "INSUFFICIENT"

        package = DocumentReviewPackage(
            documents_classified=classifications,
            extractions=normalized_extractions,
            validations=validations,
            missing_documents=missing_documents,
            document_quality=document_quality,
            total_documents=len(classifications),
            total_issues=total_issues,
        )
        return package.model_dump()
    except Exception as exc:
        return {"error": f"Document package validation failed: {exc}"}
