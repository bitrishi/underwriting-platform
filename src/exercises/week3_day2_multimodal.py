import os
import sys
from pathlib import Path

# Ensure repository root imports work when running directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.tools.document_tools import extract_document_data


SAMPLE_DIR = Path("data/sample_documents")


def run_extraction(document_path: Path, document_type: str) -> dict:
    result = extract_document_data.invoke(
        {
            "document_path": str(document_path),
            "document_type": document_type,
        }
    )

    print("\n" + "=" * 90)
    print(f"Document: {document_path.name} ({document_type})")
    print("=" * 90)
    print(result)

    if "error" in result:
        raise RuntimeError(result["error"])

    extracted = result["extracted_data"]
    assert extracted["confidence"] in {"HIGH", "MEDIUM", "LOW"}
    assert isinstance(extracted["unclear_fields"], list)

    return result


def main() -> None:
    docs = [
        (SAMPLE_DIR / "w2_sample.txt", "w2"),
        (SAMPLE_DIR / "tax_return_1040_sample.pdf", "1040"),
        (SAMPLE_DIR / "paystub_sample.png", "paystub"),
    ]

    outputs = [run_extraction(path, doc_type) for path, doc_type in docs]

    # Smart-routing verification: digital PDF should use text processing.
    pdf_output = next(item for item in outputs if item["document_type"] == "1040")
    assert pdf_output["metadata"]["processing_method"] == "text"

    print("\nSmart routing check passed: tax_return_1040_sample.pdf used text extraction.")


if __name__ == "__main__":
    main()
