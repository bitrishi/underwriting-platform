"""Routing heuristics for document extraction method selection."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

STANDARD_FORMS = {"w2", "1040", "paystub"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
TEXT_EXTENSIONS = {".txt"}
PDF_EXTENSIONS = {".pdf"}


def _pdf_has_text(path: Path) -> bool:
    try:
        reader = PdfReader(str(path))
        extracted = "\n".join((page.extract_text() or "") for page in reader.pages)
        return bool(extracted.strip())
    except Exception:
        return False


def _detect_type_from_filename(path: Path) -> str | None:
    name = path.name.lower()
    if "w2" in name or "w-2" in name:
        return "w2"
    if "1040" in name or "tax_return" in name:
        return "1040"
    if "paystub" in name or "pay_stub" in name:
        return "paystub"
    return None


def route_document(document_path: str, declared_document_type: str | None = None) -> dict:
    """Return extraction route metadata for a document.

    Strategy:
    - Standard forms on image/pdf: prefer Textract, fallback to vision.
    - Typed text files: use deterministic text parsing.
    - Non-standard handwritten-like images: use vision.
    """
    path = Path(document_path)
    suffix = path.suffix.lower()
    inferred_type = _detect_type_from_filename(path)
    doc_type = (declared_document_type or inferred_type or "").lower()
    handwritten_hint = "handwritten" in path.name.lower()

    if suffix in TEXT_EXTENSIONS:
        return {
            "primary_method": "text",
            "fallback_method": "vision",
            "document_type": doc_type or inferred_type,
            "reason": "plain_text_document",
            "use_textract": False,
        }

    if handwritten_hint:
        return {
            "primary_method": "vision",
            "fallback_method": "textract",
            "document_type": doc_type or inferred_type,
            "reason": "handwritten_hint",
            "use_textract": False,
        }

    if suffix in IMAGE_EXTENSIONS | PDF_EXTENSIONS and doc_type in STANDARD_FORMS:
        return {
            "primary_method": "textract",
            "fallback_method": "vision",
            "document_type": doc_type,
            "reason": "standard_form_detected",
            "use_textract": True,
        }

    if suffix in PDF_EXTENSIONS and _pdf_has_text(path):
        return {
            "primary_method": "text",
            "fallback_method": "textract",
            "document_type": doc_type or inferred_type,
            "reason": "pdf_has_embedded_text",
            "use_textract": False,
        }

    return {
        "primary_method": "vision",
        "fallback_method": "text",
        "document_type": doc_type or inferred_type,
        "reason": "default_vision_route",
        "use_textract": False,
    }
