"""Textract helpers for document OCR and key-value extraction."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pypdf import PdfReader

from src.config.settings import settings
from src.utils.retry import retry_with_backoff

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
PDF_EXTENSIONS = {".pdf"}


def _read_text_sidecar(document_path: Path) -> str:
    sidecar = document_path.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8")
    return ""


def _read_pdf_text(document_path: Path) -> str:
    try:
        reader = PdfReader(str(document_path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def _collect_text_lines(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("BlockType") != "LINE":
            continue
        lines.append(
            {
                "text": str(block.get("Text", "")),
                "confidence": float(block.get("Confidence", 0.0) or 0.0),
                "page": int(block.get("Page", 1) or 1),
            }
        )
    return lines


def _collect_kv_fields(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {block.get("Id"): block for block in blocks if block.get("Id")}
    fields: list[dict[str, Any]] = []

    for block in blocks:
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" not in block.get("EntityTypes", []):
            continue

        key_parts: list[str] = []
        value_parts: list[str] = []
        value_confidences: list[float] = []

        for rel in block.get("Relationships", []):
            rel_type = rel.get("Type")
            rel_ids = rel.get("Ids", [])

            if rel_type == "CHILD":
                for child_id in rel_ids:
                    child = by_id.get(child_id, {})
                    if child.get("BlockType") == "WORD":
                        key_parts.append(str(child.get("Text", "")))

            if rel_type == "VALUE":
                for value_id in rel_ids:
                    value_block = by_id.get(value_id, {})
                    value_confidences.append(float(value_block.get("Confidence", 0.0) or 0.0))
                    for value_rel in value_block.get("Relationships", []):
                        if value_rel.get("Type") != "CHILD":
                            continue
                        for value_child_id in value_rel.get("Ids", []):
                            word = by_id.get(value_child_id, {})
                            if word.get("BlockType") == "WORD":
                                value_parts.append(str(word.get("Text", "")))

        key_text = " ".join(part for part in key_parts if part).strip()
        value_text = " ".join(part for part in value_parts if part).strip()

        if not key_text and not value_text:
            continue

        confidence = sum(value_confidences) / len(value_confidences) if value_confidences else float(block.get("Confidence", 0.0) or 0.0)
        fields.append(
            {
                "key": key_text,
                "value": value_text,
                "confidence": round(confidence, 2),
                "page": int(block.get("Page", 1) or 1),
            }
        )

    return fields


def _fallback_from_local_text(document_path: Path) -> dict[str, Any]:
    if document_path.suffix.lower() in PDF_EXTENSIONS:
        text = _read_pdf_text(document_path)
    else:
        text = _read_text_sidecar(document_path)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    page_lines = [
        {
            "page_number": 1,
            "text": text,
            "line_count": len(lines),
        }
    ]
    fields: list[dict[str, Any]] = []

    for line in lines:
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        key = left.strip()
        value = right.strip()
        if not key:
            continue
        fields.append(
            {
                "key": key,
                "value": value,
                "confidence": 100.0,
                "page": 1,
            }
        )

    return {
        "raw_text": text,
        "fields": fields,
        "lines": [
            {
                "text": line,
                "confidence": 100.0,
                "page": 1,
            }
            for line in lines
        ],
        "pages": page_lines,
        "page_count": 1 if lines or text else 0,
        "average_confidence": 100.0 if lines else 0.0,
        "used_async_api": False,
        "provider": "local_fallback",
    }


@retry_with_backoff(
    max_retries=2,
    base_delay=0.5,
    max_delay=10.0,
    retryable_exceptions=(BotoCoreError,),
    jitter=True,
)
def detect_document_text(
    document_path: str,
    feature_types: list[str] | None = None,
) -> dict[str, Any]:
    """Extract OCR text and key-value fields using Textract when available.

    Retries up to 2 times on transient ``BotoCoreError`` failures with
    exponential backoff.  ``ClientError`` (e.g. invalid credentials) and
    ``RuntimeError`` / ``ValueError`` are not retried and fall through to
    the local-text fallback inside the function body.

    If Textract calls fail due to credentials/network constraints, this function
    degrades gracefully to local deterministic text extraction.
    """
    start = time.perf_counter()
    path = Path(document_path)

    if not path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")

    feature_types = feature_types or ["FORMS"]
    suffix = path.suffix.lower()
    used_async_api = False

    try:
        client = boto3.client("textract", region_name=settings.aws_region)
        if suffix in IMAGE_EXTENSIONS:
            payload = {"Bytes": path.read_bytes()}
            if feature_types:
                response = client.analyze_document(Document=payload, FeatureTypes=feature_types)
            else:
                response = client.detect_document_text(Document=payload)
        elif suffix in PDF_EXTENSIONS:
            # Keep PDFs on deterministic local parse in this project to avoid
            # requiring S3 async flow for multi-page documents.
            raise RuntimeError("pdf_local_fallback")
        else:
            raise ValueError(f"Unsupported format for Textract: {suffix}")

        blocks = response.get("Blocks", [])
        lines = _collect_text_lines(blocks)
        fields = _collect_kv_fields(blocks)

        raw_text = "\n".join(item["text"] for item in lines if item.get("text"))
        page_numbers = {item.get("page", 1) for item in lines}
        page_count = max(page_numbers) if page_numbers else 1
        pages: list[dict[str, Any]] = []

        for page_num in range(1, page_count + 1):
            page_lines = [line["text"] for line in lines if int(line.get("page", 1)) == page_num]
            pages.append(
                {
                    "page_number": page_num,
                    "text": "\n".join(page_lines),
                    "line_count": len(page_lines),
                }
            )

        confidences = [float(item.get("confidence", 0.0) or 0.0) for item in lines]
        average_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

        return {
            "raw_text": raw_text,
            "fields": fields,
            "lines": lines,
            "pages": pages,
            "page_count": page_count,
            "average_confidence": round(average_confidence, 2),
            "used_async_api": used_async_api,
            "provider": "textract",
            "processing_time_ms": round((time.perf_counter() - start) * 1000.0, 2),
        }
    except (ClientError, BotoCoreError, RuntimeError, ValueError):
        fallback = _fallback_from_local_text(path)
        fallback["processing_time_ms"] = round((time.perf_counter() - start) * 1000.0, 2)
        return fallback
