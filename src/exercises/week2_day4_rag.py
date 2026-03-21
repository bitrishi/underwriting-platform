import os
import sys

# Ensure repository root imports work when running directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.policy import PolicyAnswer
from src.rag.rag_chain import create_rag_chain, create_structured_rag_chain


def print_unstructured_result(question: str, answer: str) -> None:
    print("\n" + "=" * 90)
    print(f"Question: {question}")
    print("-" * 90)
    print(answer)


def print_structured_result(question: str, result: PolicyAnswer) -> None:
    print("\n" + "=" * 90)
    print(f"Question: {question}")
    print("-" * 90)
    print(result.format_report())


def test_unstructured_chain() -> None:
    print("\nRunning unstructured RAG chain tests...")
    chain = create_rag_chain()

    questions = [
        "What are the DTI limits?",
        "When must the Loan Estimate be provided?",
        "What is the minimum credit score?",
    ]

    for question in questions:
        answer = chain.invoke(question)
        print_unstructured_result(question, answer)


def test_structured_chain() -> None:
    print("\nRunning structured RAG chain tests...")
    chain = create_structured_rag_chain()

    question = "What are Texas loan restrictions for LTV?"
    result = chain.invoke(question)

    # Verify required PolicyAnswer fields are populated.
    assert isinstance(result, PolicyAnswer)
    assert result.answer.strip()
    assert result.confidence in {"HIGH", "MEDIUM", "LOW"}
    assert isinstance(result.sources, list)
    assert isinstance(result.relevant_quotes, list)
    assert isinstance(result.sufficient_context, bool)

    print_structured_result(question, result)


def test_structured_chain_with_metadata_filter() -> None:
    print("\nRunning structured RAG chain with metadata filter (Texas)...")
    texas_filter = lambda metadata: "texas" in str(metadata.get("source", "")).lower()
    chain = create_structured_rag_chain(metadata_filter=texas_filter)

    question = "What is the maximum LTV for Texas home equity loans?"
    result = chain.invoke(question)
    print_structured_result(question, result)


def test_out_of_scope_question() -> None:
    print("\nRunning out-of-scope sufficiency test...")
    chain = create_structured_rag_chain()

    question = "What are USDA rural development subsidy percentages by county in 2026?"
    result = chain.invoke(question)
    print_structured_result(question, result)

    # Required check for this exercise.
    assert result.sufficient_context is False, (
        "Expected sufficient_context=False for out-of-scope question. "
        "Review prompt instructions or retrieval behavior if this fails."
    )


def main() -> None:
    test_unstructured_chain()
    test_structured_chain()
    test_structured_chain_with_metadata_filter()
    test_out_of_scope_question()


if __name__ == "__main__":
    main()
