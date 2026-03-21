"""Tests for advanced retrieval and section-aware chunking."""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from src.models.policy import PolicyAnswer
from src.rag.chunking import enrich_chunks, split_by_sections
from src.rag.rag_chain import create_structured_rag_chain
from src.rag.retriever import ProductionRetriever


class FakeVectorStore:
    """Vector store stub with deterministic scored results."""

    def __init__(self, scored_results: dict[str, list[tuple[Document, float]]]):
        self.scored_results = scored_results
        self.embedding_function = None

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 3,
        filter: Any = None,
    ) -> list[tuple[Document, float]]:
        results = self.scored_results.get(query, self.scored_results.get("__default__", []))
        if filter is None:
            return results[:k]

        filtered: list[tuple[Document, float]] = []
        for doc, score in results:
            if callable(filter) and filter(doc.metadata):
                filtered.append((doc, score))
            elif isinstance(filter, dict) and all(doc.metadata.get(key) == value for key, value in filter.items()):
                filtered.append((doc, score))
        return filtered[:k]


class FakeStructuredLLM:
    def with_structured_output(self, model_cls):
        def run(prompt_value):
            text = prompt_value.to_string() if hasattr(prompt_value, "to_string") else str(prompt_value)
            no_context = "No matching policy documents found." in text
            sources = [] if no_context else ["data/policies/texas_state_rules.txt"]
            return model_cls(
                answer=(
                    "Insufficient documentation to answer this question"
                    if no_context
                    else "Structured answer from retrieved policy context"
                ),
                confidence=("LOW" if no_context else "HIGH"),
                sources=sources,
                relevant_quotes=[] if no_context else ["Texas home equity loans are capped at 80% LTV."],
                sufficient_context=not no_context,
            )

        return RunnableLambda(run)


def test_section_aware_chunking_produces_correct_metadata() -> None:
    doc = Document(
        page_content=(
            "FANNIE MAE GUIDE\n"
            "DEBT-TO-INCOME REQUIREMENTS\n"
            "Maximum DTI is 45% for manual underwriting.\n\n"
            "EMPLOYMENT AND INCOME REQUIREMENTS\n"
            "Borrowers must document two years of employment history."
        ),
        metadata={"source": "data/policies/fannie_mae_guidelines.txt"},
    )

    chunks = split_by_sections([doc], chunk_size=120, chunk_overlap=20)
    enriched = enrich_chunks(chunks)

    assert chunks
    assert all("section" in chunk.metadata for chunk in chunks)
    assert any(chunk.metadata["section"] == "DEBT-TO-INCOME REQUIREMENTS" for chunk in chunks)
    assert any(chunk.metadata["section"] == "EMPLOYMENT AND INCOME REQUIREMENTS" for chunk in chunks)
    assert enriched[0].page_content.startswith("Document: Fannie Mae Guidelines")


def test_hybrid_retriever_finds_result_vector_only_misses() -> None:
    texas_doc = Document(
        page_content="Section 50(a)(6) sets Texas home equity loan requirements.",
        metadata={"source": "data/policies/texas_state_rules.txt"},
    )
    income_doc = Document(
        page_content="Borrowers must document two years of employment and income.",
        metadata={"source": "data/policies/fannie_mae_guidelines.txt"},
    )
    trid_doc = Document(
        page_content="Loan Estimate must be delivered within three business days.",
        metadata={"source": "data/policies/trid_regulations.txt"},
    )

    store = FakeVectorStore(
        {
            "Section 50(a)(6) requirements": [
                (income_doc, 0.20),
                (texas_doc, 0.25),
                (trid_doc, 0.40),
            ],
            "__default__": [(income_doc, 0.30), (texas_doc, 0.50)],
        }
    )
    retriever = ProductionRetriever(store, [texas_doc, income_doc, trid_doc], reranker=None)

    pure_vector = retriever.search("Section 50(a)(6) requirements", k=1, use_hybrid=False)
    hybrid = retriever.search("Section 50(a)(6) requirements", k=1, use_hybrid=True)

    assert pure_vector[0].metadata["source"].endswith("fannie_mae_guidelines.txt")
    assert hybrid[0].metadata["source"].endswith("texas_state_rules.txt")


def test_score_threshold_returns_empty_for_irrelevant_query() -> None:
    irrelevant_doc = Document(
        page_content="Texas home equity loans are capped at 80% LTV.",
        metadata={"source": "data/policies/texas_state_rules.txt"},
    )
    store = FakeVectorStore(
        {
            "completely unrelated astronomy policy": [(irrelevant_doc, 1.8)],
            "__default__": [(irrelevant_doc, 1.8)],
        }
    )
    retriever = ProductionRetriever(store, [irrelevant_doc], reranker=None)

    results = retriever.search_with_threshold(
        "completely unrelated astronomy policy",
        k=3,
        max_vector_distance=0.5,
    )

    assert results == []


def test_threshold_empty_context_flows_into_rag_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    texas_doc = Document(
        page_content="Texas home equity loans are capped at 80% LTV.",
        metadata={"source": "data/policies/texas_state_rules.txt"},
    )
    store = FakeVectorStore(
        {
            "What are USDA subsidy percentages by county?": [(texas_doc, 1.7)],
            "__default__": [(texas_doc, 1.7)],
        }
    )
    retriever = ProductionRetriever(store, [texas_doc], reranker=None)
    runnable = retriever.as_runnable(k=3, score_threshold=0.5)

    monkeypatch.setattr("src.rag.rag_chain.create_llm", lambda temperature=0: FakeStructuredLLM())

    chain = create_structured_rag_chain(retriever=runnable)
    result = chain.invoke("What are USDA subsidy percentages by county?")

    assert isinstance(result, PolicyAnswer)
    assert result.sufficient_context is False
    assert result.sources == []
    assert "Insufficient documentation" in result.answer