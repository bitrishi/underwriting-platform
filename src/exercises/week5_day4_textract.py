"""Week 5 Day 4: Textract hybrid extraction comparison exercise."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools.document_tools import extract_document_data

SAMPLE_DOCS = [
    ("data/sample_documents/w2_sample.txt", "w2"),
    ("data/sample_documents/tax_return_1040_sample.pdf", "1040"),
    ("data/sample_documents/paystub_sample.png", "paystub"),
]


def _safe_extract(path: str, doc_type: str, method: str) -> dict[str, Any]:
    payload = extract_document_data.invoke(
        {
            "document_path": path,
            "document_type": doc_type,
            "preferred_method": method,
        }
    )
    if "error" in payload:
        return {
            "method": method,
            "error": payload["error"],
        }

    return {
        "method": method,
        "confidence": payload["extracted_data"].get("confidence"),
        "unclear_fields": payload["extracted_data"].get("unclear_fields", []),
        "processing_method": payload["metadata"].get("processing_method"),
        "processing_time_ms": round(payload["metadata"].get("processing_time_ms", 0.0), 2),
        "estimated_cost_usd": payload["metadata"].get("estimated_cost_usd", 0.0),
    }


def compare_methods_for_document(path: str, doc_type: str) -> dict[str, Any]:
    methods = ["text", "vision", "textract", "auto"]
    comparisons = [_safe_extract(path, doc_type, method) for method in methods]

    return {
        "document_path": path,
        "document_type": doc_type,
        "exists": Path(path).exists(),
        "comparisons": comparisons,
    }


def run_week5_day4_exercise() -> list[dict[str, Any]]:
    """Run method comparisons over standard underwriting sample documents."""
    return [compare_methods_for_document(path, doc_type) for path, doc_type in SAMPLE_DOCS]


if __name__ == "__main__":
    print(json.dumps(run_week5_day4_exercise(), indent=2))
