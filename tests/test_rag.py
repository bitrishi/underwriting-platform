"""Tests for RAG chains and PolicyAnswer model behavior."""

from __future__ import annotations

import re
from typing import Any

import pytest
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from src.models.policy import PolicyAnswer
from src.rag import rag_chain


class FakeVectorStore:
    """Minimal in-memory vector store fake with metadata filtering support."""

    def __init__(self, docs: list[Document]):
        self.docs = docs

    def _apply_filter(self, docs: list[Document], metadata_filter: Any) -> list[Document]:
        if metadata_filter is None:
            return docs
        if callable(metadata_filter):
            return [doc for doc in docs if metadata_filter(doc.metadata)]
        if isinstance(metadata_filter, dict):
            filtered: list[Document] = []
            for doc in docs:
                if all(doc.metadata.get(k) == v for k, v in metadata_filter.items()):
                    filtered.append(doc)
            return filtered
        return docs

    def _rank_docs(self, query: str) -> list[Document]:
        lowered = query.lower()
        if "texas" in lowered:
            preferred = [d for d in self.docs if "texas" in d.metadata.get("source", "").lower()]
            others = [d for d in self.docs if d not in preferred]
            return preferred + others
        if "loan estimate" in lowered or "trid" in lowered:
            preferred = [d for d in self.docs if "trid" in d.metadata.get("source", "").lower()]
            others = [d for d in self.docs if d not in preferred]
            return preferred + others
        if "credit" in lowered or "fico" in lowered or "dti" in lowered:
            preferred = [d for d in self.docs if "fannie" in d.metadata.get("source", "").lower()]
            others = [d for d in self.docs if d not in preferred]
            return preferred + others
        return self.docs

    def similarity_search(self, query: str, k: int = 3, filter: Any = None) -> list[Document]:
        ranked = self._rank_docs(query)
        filtered = self._apply_filter(ranked, filter)
        return filtered[:k]

    def as_retriever(self, search_kwargs: dict | None = None):
        kwargs = search_kwargs or {}
        k = kwargs.get("k", 3)
        metadata_filter = kwargs.get("filter")

        def retrieve(query: str) -> list[Document]:
            return self.similarity_search(query, k=k, filter=metadata_filter)

        return RunnableLambda(retrieve)


class FakeLLM:
    """Callable LLM fake that supports both string and structured outputs."""

    def _to_text(self, prompt_value: Any) -> str:
        return prompt_value.to_string() if hasattr(prompt_value, "to_string") else str(prompt_value)

    def __call__(self, prompt_value: Any) -> str:
        text = self._to_text(prompt_value)
        sources = re.findall(r"Source: ([^,\n]+)", text)
        if "mars colony" in text.lower() or "usda rural development subsidy" in text.lower():
            return "Insufficient documentation to answer this question. Sources: none"
        if sources:
            return f"Answer based on context. Sources: {', '.join(sorted(set(sources)))}"
        return "Insufficient documentation to answer this question. Sources: none"

    def with_structured_output(self, model_cls):
        def run(prompt_value: Any):
            text = self._to_text(prompt_value)
            sources = sorted(set(re.findall(r"Source: ([^,\n]+)", text)))
            quotes = re.findall(r"Content: (.+)", text)
            out_of_scope = (
                "mars colony" in text.lower()
                or "usda rural development subsidy" in text.lower()
            )
            return model_cls(
                answer=(
                    "Insufficient documentation to answer this question"
                    if out_of_scope
                    else "Policy answer generated from retrieved context"
                ),
                confidence=("LOW" if out_of_scope else "HIGH"),
                sources=sources,
                relevant_quotes=quotes[:2],
                sufficient_context=not out_of_scope,
            )

        return RunnableLambda(run)


@pytest.fixture
def fake_docs() -> list[Document]:
    return [
        Document(
            page_content="Texas home equity loans are capped at 80% LTV.",
            metadata={"source": "data/policies/texas_state_rules.txt", "jurisdiction": "state_texas"},
        ),
        Document(
            page_content="Loan Estimate must be provided within 3 business days.",
            metadata={"source": "data/policies/trid_regulations.txt", "jurisdiction": "federal"},
        ),
        Document(
            page_content="Minimum representative credit score is 620 for standard loans.",
            metadata={"source": "data/policies/fannie_mae_guidelines.txt", "jurisdiction": "federal"},
        ),
    ]


@pytest.fixture
def patch_rag_dependencies(monkeypatch: pytest.MonkeyPatch, fake_docs: list[Document]) -> None:
    monkeypatch.setattr(rag_chain, "load_vectorstore", lambda: FakeVectorStore(fake_docs))
    monkeypatch.setattr(rag_chain, "create_llm", lambda temperature=0: FakeLLM())


def test_rag_chain_returns_answers_with_citations(patch_rag_dependencies: None) -> None:
    chain = rag_chain.create_rag_chain()
    answer = chain.invoke("When must the Loan Estimate be provided?")

    assert "Sources:" in answer
    assert "trid_regulations" in answer


def test_metadata_filtering_texas_query_only_gets_texas_docs(
    patch_rag_dependencies: None,
) -> None:
    chain = rag_chain.create_structured_rag_chain(
        metadata_filter={"jurisdiction": "state_texas"}
    )
    result = chain.invoke("What is the maximum LTV for Texas loans?")

    assert isinstance(result, PolicyAnswer)
    assert result.sources
    assert all("texas" in source.lower() for source in result.sources)


def test_sufficient_context_false_for_out_of_scope_questions(
    patch_rag_dependencies: None,
) -> None:
    chain = rag_chain.create_structured_rag_chain()
    result = chain.invoke("What are USDA rural development subsidy percentages by county in 2026?")

    assert isinstance(result, PolicyAnswer)
    assert result.sufficient_context is False
    assert "Insufficient documentation" in result.answer


def test_policy_answer_validation() -> None:
    valid = PolicyAnswer(
        answer="DTI cap is 45% in this context.",
        confidence="MEDIUM",
        sources=["data/policies/fannie_mae_guidelines.txt"],
        relevant_quotes=["Maximum DTI Ratio is 45% for manually underwritten loans."],
        sufficient_context=True,
    )
    assert valid.confidence == "MEDIUM"

    with pytest.raises(ValidationError):
        PolicyAnswer(
            answer="Missing confidence enum",
            confidence="CERTAIN",  # invalid enum
            sources=[],
            relevant_quotes=[],
            sufficient_context=True,
        )
