"""Field normalization and schema mapping for Textract outputs."""

from __future__ import annotations

import re
from typing import Any

from src.models.documents import PayStubExtraction, TaxReturn1040Extraction, W2Extraction

_FIELD_ALIASES: dict[str, dict[str, list[str]]] = {
    "w2": {
        "employer_name": ["employer name", "employer", "box c"],
        "employee_name": ["employee name", "employee", "box e"],
        "wages": ["wages", "box 1", "wages tips other compensation"],
        "federal_tax_withheld": ["federal tax withheld", "box 2", "income tax withheld"],
        "social_security_wages": ["social security wages", "box 3"],
        "tax_year": ["tax year", "year"],
    },
    "1040": {
        "tax_year": ["tax year", "year"],
        "filing_status": ["filing status", "status"],
        "adjusted_gross_income": ["adjusted gross income", "agi", "line 11"],
        "taxable_income": ["taxable income", "line 15"],
        "total_tax": ["total tax", "line 24"],
        "self_employment_income": ["self employment income", "schedule se"],
    },
    "paystub": {
        "employer_name": ["employer name", "employer"],
        "employee_name": ["employee name", "employee"],
        "pay_period_start": ["pay period start", "period start"],
        "pay_period_end": ["pay period end", "period end"],
        "gross_pay": ["gross pay", "gross"],
        "net_pay": ["net pay", "net"],
        "ytd_gross": ["ytd gross", "year to date gross", "ytd"],
        "pay_frequency": ["pay frequency", "frequency"],
    },
}

_FILING_STATUS_ALIASES = {
    "MARRIED FILING JOINTLY": "MARRIED_JOINT",
    "MARRIED JOINT": "MARRIED_JOINT",
    "MARRIED FILING SEPARATELY": "MARRIED_SEPARATE",
    "MARRIED SEPARATE": "MARRIED_SEPARATE",
    "HEAD OF HOUSEHOLD": "HEAD_OF_HOUSEHOLD",
    "QUALIFYING WIDOW": "QUALIFYING_WIDOW",
    "SINGLE": "SINGLE",
}


def _normalize_money(raw: str | None) -> float:
    if not raw:
        return 0.0
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _normalize_int(raw: str | None) -> int:
    if not raw:
        return 0
    match = re.search(r"\d+", raw)
    return int(match.group(0)) if match else 0


def _normalize_date(raw: str | None) -> str:
    if not raw:
        return "1970-01-01"

    raw = raw.strip()
    # YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw

    # MM/DD/YYYY
    mmddyyyy = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if mmddyyyy:
        mm, dd, yyyy = mmddyyyy.groups()
        return f"{int(yyyy):04d}-{int(mm):02d}-{int(dd):02d}"

    return "1970-01-01"


def _normalize_pay_frequency(raw: str | None) -> str:
    if not raw:
        return "MONTHLY"

    normalized = raw.strip().upper().replace(" ", "")
    aliases = {
        "WEEKLY": "WEEKLY",
        "BIWEEKLY": "BIWEEKLY",
        "SEMI-MONTHLY": "SEMIMONTHLY",
        "SEMIMONTHLY": "SEMIMONTHLY",
        "MONTHLY": "MONTHLY",
    }
    return aliases.get(normalized, "MONTHLY")


def _best_field_match(fields: list[dict[str, Any]], aliases: list[str]) -> tuple[str | None, float]:
    normalized_aliases = [alias.lower() for alias in aliases]
    candidate_value: str | None = None
    candidate_conf = -1.0

    for field in fields:
        key = str(field.get("key", "")).lower()
        value = str(field.get("value", "")).strip()
        confidence = float(field.get("confidence", 0.0) or 0.0)
        if not value:
            continue

        if any(alias in key for alias in normalized_aliases):
            if confidence > candidate_conf:
                candidate_value = value
                candidate_conf = confidence

    if candidate_conf < 0.0:
        return None, 0.0
    return candidate_value, candidate_conf


def _regex_fallback(text: str, canonical_field: str) -> str | None:
    patterns = {
        "employer_name": r"Employer Name:\s*(.+)",
        "employee_name": r"Employee Name:\s*(.+)",
        "wages": r"Wages:\s*([\d,\.]+)",
        "federal_tax_withheld": r"Federal Tax Withheld:\s*([\d,\.]+)",
        "social_security_wages": r"Social Security Wages:\s*([\d,\.]+)",
        "tax_year": r"Tax Year:\s*(\d{4})",
        "filing_status": r"Filing Status:\s*([A-Za-z_ ]+)",
        "adjusted_gross_income": r"Adjusted Gross Income:\s*([\d,\.]+)",
        "taxable_income": r"Taxable Income:\s*([\d,\.]+)",
        "total_tax": r"Total Tax:\s*([\d,\.]+)",
        "self_employment_income": r"Self Employment Income:\s*([\d,\.]+)",
        "pay_period_start": r"Pay Period Start:\s*([^\n]+)",
        "pay_period_end": r"Pay Period End:\s*([^\n]+)",
        "gross_pay": r"Gross Pay:\s*([\d,\.]+)",
        "net_pay": r"Net Pay:\s*([\d,\.]+)",
        "ytd_gross": r"YTD Gross:\s*([\d,\.]+)",
        "pay_frequency": r"Pay Frequency:\s*([A-Za-z\-_ ]+)",
    }

    pattern = patterns.get(canonical_field)
    if not pattern:
        return None

    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def map_textract_to_model(
    document_type: str,
    textract_payload: dict[str, Any],
    confidence_threshold: float = 80.0,
) -> W2Extraction | TaxReturn1040Extraction | PayStubExtraction:
    """Map Textract output fields into typed extraction models."""
    doc_type = document_type.lower()
    if doc_type not in _FIELD_ALIASES:
        raise ValueError(f"Unsupported document type for mappings: {document_type}")

    fields = textract_payload.get("fields", []) or []
    raw_text = str(textract_payload.get("raw_text", "") or "")
    aliases = _FIELD_ALIASES[doc_type]

    values: dict[str, str | None] = {}
    unclear_fields: list[str] = []

    for canonical_field, key_aliases in aliases.items():
        value, confidence = _best_field_match(fields, key_aliases)
        if value is None:
            value = _regex_fallback(raw_text, canonical_field)
            confidence = confidence if confidence > 0 else 79.0

        if value is None:
            unclear_fields.append(canonical_field)
            values[canonical_field] = None
            continue

        if confidence < confidence_threshold:
            unclear_fields.append(canonical_field)

        values[canonical_field] = value

    overall_conf = "HIGH" if len(unclear_fields) == 0 else "MEDIUM" if len(unclear_fields) <= 2 else "LOW"

    if doc_type == "w2":
        return W2Extraction(
            employer_name=str(values.get("employer_name") or "UNKNOWN"),
            employee_name=str(values.get("employee_name") or "UNKNOWN"),
            wages=_normalize_money(values.get("wages")),
            federal_tax_withheld=_normalize_money(values.get("federal_tax_withheld")),
            social_security_wages=_normalize_money(values.get("social_security_wages")),
            tax_year=_normalize_int(values.get("tax_year")),
            confidence=overall_conf,
            unclear_fields=unclear_fields,
        )

    if doc_type == "1040":
        status_raw = str(values.get("filing_status") or "SINGLE").upper().replace("_", " ").strip()
        filing_status = _FILING_STATUS_ALIASES.get(status_raw, "SINGLE")
        self_emp_value = values.get("self_employment_income")

        return TaxReturn1040Extraction(
            tax_year=_normalize_int(values.get("tax_year")),
            filing_status=filing_status,
            adjusted_gross_income=_normalize_money(values.get("adjusted_gross_income")),
            taxable_income=_normalize_money(values.get("taxable_income")),
            total_tax=_normalize_money(values.get("total_tax")),
            self_employment_income=(
                _normalize_money(self_emp_value) if self_emp_value is not None else None
            ),
            confidence=overall_conf,
            unclear_fields=unclear_fields,
        )

    return PayStubExtraction(
        employer_name=str(values.get("employer_name") or "UNKNOWN"),
        employee_name=str(values.get("employee_name") or "UNKNOWN"),
        pay_period_start=_normalize_date(values.get("pay_period_start")),
        pay_period_end=_normalize_date(values.get("pay_period_end")),
        gross_pay=_normalize_money(values.get("gross_pay")),
        net_pay=_normalize_money(values.get("net_pay")),
        ytd_gross=_normalize_money(values.get("ytd_gross")),
        pay_frequency=_normalize_pay_frequency(values.get("pay_frequency")),
        confidence=overall_conf,
        unclear_fields=unclear_fields,
    )
