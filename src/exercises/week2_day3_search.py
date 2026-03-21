import os
import sys

# Ensure repository root is importable when run directly as a script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.rag.vectorstore import build_vectorstore, search_policies


def print_search_results(query: str, top_k: int = 3) -> None:
    """Run a semantic search and print metadata + content for each hit."""
    print("\n" + "=" * 90)
    print(f"Query: {query}")
    print("=" * 90)

    results = search_policies(query=query, top_k=top_k)

    if not results:
        print("No results found.")
        return

    for idx, doc in enumerate(results, start=1):
        source = doc.metadata.get("source", "unknown")
        print(f"\nResult #{idx}")
        print(f"Source: {source}")
        print("Content:")
        print(doc.page_content.strip())
        print("-" * 90)


def main() -> None:
    """Build vector store once, then run five semantic policy searches."""
    print("Building vector store from policy documents...")
    build_vectorstore("data/policies")
    print("Vector store ready at data/vectorstore/.")

    queries = [
        "What are the DTI limits?",
        "debt-to-income requirements",
        "When must the Loan Estimate be provided?",
        "Texas loan restrictions",
        "What is the minimum credit score?",
    ]

    for q in queries:
        print_search_results(q, top_k=3)


if __name__ == "__main__":
    main()
