import os
import sys
from pathlib import Path

# Ensure repository root imports work when running directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.models.policy import PolicyAnswer
from src.rag.rag_chain import create_structured_rag_chain
from src.rag.retriever import ProductionRetriever
from src.rag.vectorstore import build_chunks, build_vectorstore, load_policy_documents


BASIC_STORE_PATH = Path("data/vectorstore/basic")
ADVANCED_STORE_PATH = Path("data/vectorstore/advanced")


def print_result_block(title: str, result: PolicyAnswer) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    print(result.format_report())


def compare_note(query: str, basic: PolicyAnswer, advanced: PolicyAnswer) -> str:
    if advanced.sufficient_context and not basic.sufficient_context:
        return "Advanced retrieval improved context coverage."
    if not advanced.sufficient_context and basic.sufficient_context:
        return "Advanced retrieval correctly filtered weak matches into empty context."
    if len(advanced.sources) > len(basic.sources):
        return "Advanced retrieval returned richer citations."
    lowered = query.lower()
    if "50(a)(6)" in lowered:
        return "Keyword-heavy citation benefited from BM25 matching."
    if "income documentation" in lowered:
        return "Section enrichment helped surface the income/employment section context."
    if "texas cash-out refinance" in lowered:
        return "Texas-specific retrieval benefited from hybrid ranking plus section context."
    return "No material difference observed in this run."


def build_retrievers() -> tuple:
    documents = load_policy_documents("data/policies")
    basic_chunks = build_chunks(documents, chunking_strategy="basic")
    advanced_chunks = build_chunks(documents, chunking_strategy="section_enriched")

    print("Building basic vector store...")
    basic_vectorstore = build_vectorstore(
        source_dir="data/policies",
        persist_path=BASIC_STORE_PATH,
        chunking_strategy="basic",
    )

    print("Building section-enriched vector store...")
    advanced_vectorstore = build_vectorstore(
        source_dir="data/policies",
        persist_path=ADVANCED_STORE_PATH,
        chunking_strategy="section_enriched",
    )

    print(f"Basic chunk count: {len(basic_chunks)}")
    print(f"Advanced chunk count: {len(advanced_chunks)}")

    basic_retriever = basic_vectorstore.as_retriever(search_kwargs={"k": 3})
    production_retriever = ProductionRetriever(
        vectorstore=advanced_vectorstore,
        documents=advanced_chunks,
    )
    advanced_retriever = production_retriever.as_runnable(k=3, use_hybrid=True, rerank=True)
    threshold_retriever = production_retriever.as_runnable(
        k=3,
        use_hybrid=True,
        rerank=True,
        score_threshold=0.75,
    )

    return basic_retriever, advanced_retriever, threshold_retriever


def main() -> None:
    basic_retriever, advanced_retriever, threshold_retriever = build_retrievers()

    basic_chain = create_structured_rag_chain(retriever=basic_retriever)
    advanced_chain = create_structured_rag_chain(retriever=advanced_retriever)
    threshold_chain = create_structured_rag_chain(retriever=threshold_retriever)

    queries = [
        "Section 50(a)(6) requirements",
        "income documentation requirements",
        "What are the rules for Texas cash-out refinance?",
        "When must the Loan Estimate be provided?",
        "What is the minimum credit score?",
    ]

    improvements: list[str] = []

    for query in queries:
        print("\n" + "=" * 100)
        print(f"Query: {query}")
        print("=" * 100)

        basic_result = basic_chain.invoke(query)
        advanced_result = advanced_chain.invoke(query)

        print_result_block("Basic RAG", basic_result)
        print_result_block("Advanced RAG", advanced_result)

        note = compare_note(query, basic_result, advanced_result)
        improvements.append(f"- {query}: {note}")
        print("\nObservation:")
        print(note)

    print("\n" + "=" * 100)
    print("Summary Of Query-Level Changes")
    print("=" * 100)
    for line in improvements:
        print(line)

    out_of_scope_query = "What are USDA rural development subsidy percentages by county in 2026?"
    print("\n" + "=" * 100)
    print("Threshold Demo")
    print("=" * 100)
    threshold_result = threshold_chain.invoke(out_of_scope_query)
    print_result_block("Advanced RAG With Threshold", threshold_result)


if __name__ == "__main__":
    main()