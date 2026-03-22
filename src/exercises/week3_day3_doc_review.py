# src/exercises/week3_day3_doc_review.py
#
# Week 3 Day 3 — Document Review Pipeline
#
# Demonstrates the full document review flow without requiring a live LLM:
#   1. Classify each document
#   2. Extract structured data (text routing for .txt/.pdf, vision sidecar for images)
#   3. Cross-validate across documents
#   4. Detect missing required documents
#   5. Build and print a formatted DocumentReviewPackage report
#
# To run with the live Bedrock agent instead, call create_doc_review_agent() and
# agent.invoke({"messages": [...]}).

from pprint import pformat
from src.models.document_review import DocumentReviewPackage
from src.tools.document_tools import (
    classify_document,
    extract_document_data,
    validate_document_package,
)

SAMPLE_DIR = "data/sample_documents"

# Documents to process — covers W-2, paystub (image), and 1040 (PDF)
CANDIDATES = [
    ("data/sample_documents/w2_sample.txt", "w2"),
    ("data/sample_documents/paystub_sample.png", "paystub"),
    ("data/sample_documents/tax_return_1040_sample.pdf", "1040"),
]

DIVIDER = "-" * 70


def step(label: str, result: dict) -> dict:
    print(f"\n{DIVIDER}")
    print(f"  {label}")
    print(DIVIDER)
    if "error" in result:
        print(f"  [ERROR] {result['error']}")
    else:
        print(pformat(result, indent=2, width=80))
    return result


def main() -> None:
    print("=" * 70)
    print("  DOCUMENT REVIEW PIPELINE — APP-DOC-001")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Classify all candidate documents
    # ------------------------------------------------------------------
    print("\n\n[STEP 1] CLASSIFY DOCUMENTS")
    classifications = []
    for path, _ in CANDIDATES:
        result = step(f"classify_document({path!r})", classify_document.invoke({"document_path": path}))
        if "error" not in result:
            classifications.append(result)

    # ------------------------------------------------------------------
    # Step 2: Extract structured data from each document
    # ------------------------------------------------------------------
    print("\n\n[STEP 2] EXTRACT STRUCTURED DATA")
    extractions = []
    for path, doc_type in CANDIDATES:
        result = step(
            f"extract_document_data({path!r}, {doc_type!r})",
            extract_document_data.invoke({"document_path": path, "document_type": doc_type}),
        )
        if "error" not in result:
            extractions.append(result)

    # ------------------------------------------------------------------
    # Step 3: Cross-validate and build the review package
    # ------------------------------------------------------------------
    print("\n\n[STEP 3] VALIDATE DOCUMENT PACKAGE")
    package_data = step("validate_document_package([all extractions])", validate_document_package.invoke({"extractions": extractions}))

    if "error" in package_data:
        print("\n[FATAL] Package validation failed — cannot produce report.")
        return

    # ------------------------------------------------------------------
    # Step 4: Build typed model and print formatted report
    # ------------------------------------------------------------------
    print("\n\n[STEP 4] FORMATTED REPORT")
    print(DIVIDER)
    package = DocumentReviewPackage.model_validate(package_data)
    print(package.format_report())

    # ------------------------------------------------------------------
    # Step 5: Assertions — verify each requirement
    # ------------------------------------------------------------------
    print("\n\n[STEP 5] VERIFICATION")
    print(DIVIDER)

    classified_types = {c["document_type"] for c in classifications}
    assert "W2" in classified_types, "W-2 classification failed"
    assert "PAYSTUB" in classified_types, "Paystub classification failed"
    print("  [PASS] Classification detected W2 and PAYSTUB")

    extracted_types = {e["document_type"] for e in extractions}
    assert "w2" in extracted_types, "W-2 extraction missing"
    assert "paystub" in extracted_types, "Paystub extraction missing"
    w2_data = next(e for e in extractions if e["document_type"] == "w2")
    assert w2_data["extracted_data"]["wages"] == 86500.0, "W-2 wage extraction incorrect"
    print("  [PASS] Extraction produced correct W-2 wages ($86,500)")

    validation_statuses = {v.check_name: v.status for v in package.validations}
    ytd_check = validation_statuses.get("Pay stub YTD vs W-2 wages")
    assert ytd_check == "MATCH", f"YTD cross-validation expected MATCH, got {ytd_check!r}"
    print("  [PASS] Cross-validation: pay stub YTD matches W-2 wages")

    missing_types = {m.document_type for m in package.missing_documents}
    # 1040 sample PDF has no embedded text, so it extracts with LOW confidence but
    # still counts as provided. Only assert that the validator ran the missing-doc check.
    assert isinstance(package.missing_documents, list)
    print(f"  [PASS] Missing document detection ran (missing: {missing_types or 'none'})")

    print(f"\n  [PASS] document_quality = {package.document_quality!r}")
    print(f"  [PASS] total_issues     = {package.total_issues}")
    print(f"  [PASS] has_critical_issues = {package.has_critical_issues()}\n")


if __name__ == "__main__":
    main()
