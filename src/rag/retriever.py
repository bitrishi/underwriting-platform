"""Advanced retrieval strategies for policy search."""

from __future__ import annotations

import re
from typing import Any, Iterable

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from rank_bm25 import BM25Okapi

try:
    from flashrank import Ranker, RerankRequest
except ImportError:  # pragma: no cover - handled at runtime when dependency missing
    Ranker = None
    RerankRequest = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_\-\(\)\.]+", text.lower())


def _matches_metadata(metadata: dict[str, Any], metadata_filter: Any) -> bool:
    if metadata_filter is None:
        return True
    if callable(metadata_filter):
        return bool(metadata_filter(metadata))
    if isinstance(metadata_filter, dict):
        return all(metadata.get(key) == value for key, value in metadata_filter.items())
    return True


class ProductionRetriever:
    """Retriever that combines vector search, BM25, thresholding, and reranking."""

    def __init__(
        self,
        vectorstore: Any,
        documents: list[Document],
        reranker: Any | None = None,
    ) -> None:
        self.vectorstore = vectorstore
        self.documents = documents
        self.embedding_function = getattr(vectorstore, "embedding_function", None)
        self._tokenized_corpus = [_tokenize(doc.page_content) for doc in documents]
        self.bm25 = BM25Okapi(self._tokenized_corpus)
        self.reranker = reranker or self._create_default_reranker()

    def _create_default_reranker(self) -> Any | None:
        if Ranker is None:
            return None
        try:
            return Ranker(model_name="ms-marco-MiniLM-L-12-v2")
        except Exception:
            return None

    def _filter_documents(
        self,
        documents: Iterable[Document],
        metadata_filter: Any = None,
    ) -> list[Document]:
        return [doc for doc in documents if _matches_metadata(doc.metadata, metadata_filter)]

    def _vector_results(
        self,
        query: str,
        k: int,
        metadata_filter: Any = None,
    ) -> list[tuple[Document, float]]:
        raw_results = self.vectorstore.similarity_search_with_score(
            query,
            k=max(k, 8),
            filter=metadata_filter,
        )
        return [(doc, float(score)) for doc, score in raw_results]

    def _bm25_results(
        self,
        query: str,
        k: int,
        metadata_filter: Any = None,
    ) -> list[tuple[Document, float]]:
        filtered_docs = self._filter_documents(self.documents, metadata_filter)
        if not filtered_docs:
            return []

        scores = self.bm25.get_scores(_tokenize(query))
        doc_scores: list[tuple[Document, float]] = []
        for index, document in enumerate(self.documents):
            if document in filtered_docs:
                doc_scores.append((document, float(scores[index])))

        doc_scores.sort(key=lambda item: item[1], reverse=True)
        return doc_scores[: max(k, 8)]

    def _merge_results(
        self,
        vector_results: list[tuple[Document, float]],
        bm25_results: list[tuple[Document, float]],
        k: int,
    ) -> list[Document]:
        score_map: dict[tuple[str, tuple[tuple[str, Any], ...]], dict[str, Any]] = {}

        for rank, (doc, score) in enumerate(vector_results, start=1):
            key = (doc.page_content, tuple(sorted(doc.metadata.items())))
            score_map.setdefault(key, {"doc": doc, "score": 0.0})
            score_map[key]["score"] += 1.0 / (rank + 1) + 1.0 / (1.0 + score)

        for rank, (doc, score) in enumerate(bm25_results, start=1):
            key = (doc.page_content, tuple(sorted(doc.metadata.items())))
            score_map.setdefault(key, {"doc": doc, "score": 0.0})
            score_map[key]["score"] += 1.0 / (rank + 1) + max(score, 0.0)

        merged = sorted(score_map.values(), key=lambda item: item["score"], reverse=True)
        return [item["doc"] for item in merged[:k]]

    def _rerank(self, query: str, documents: list[Document], k: int) -> list[Document]:
        if not documents or self.reranker is None or RerankRequest is None:
            return documents[:k]

        passages = [
            {
                "id": str(index),
                "text": doc.page_content,
                "meta": doc.metadata,
            }
            for index, doc in enumerate(documents)
        ]
        try:
            request = RerankRequest(query=query, passages=passages)
            ranked = self.reranker.rerank(request)
        except Exception:
            return documents[:k]

        reranked_docs: list[Document] = []
        for item in ranked[:k]:
            original = documents[int(item["id"])]
            reranked_docs.append(original)
        return reranked_docs

    def search(
        self,
        query: str,
        k: int = 3,
        metadata_filter: Any = None,
        use_hybrid: bool = True,
        rerank: bool = False,
    ) -> list[Document]:
        """Search via vector-only or hybrid retrieval."""
        vector_results = self._vector_results(query, k=k, metadata_filter=metadata_filter)
        if not use_hybrid:
            docs = [doc for doc, _ in vector_results[:k]]
            return self._rerank(query, docs, k) if rerank else docs

        bm25_results = self._bm25_results(query, k=k, metadata_filter=metadata_filter)
        merged = self._merge_results(vector_results, bm25_results, k=max(k, 8))
        return self._rerank(query, merged, k) if rerank else merged[:k]

    def search_with_threshold(
        self,
        query: str,
        k: int = 3,
        metadata_filter: Any = None,
        max_vector_distance: float = 0.75,
    ) -> list[Document]:
        """Return only documents whose vector distance is below the supplied threshold."""
        vector_results = self._vector_results(query, k=k, metadata_filter=metadata_filter)
        kept = [doc for doc, score in vector_results if score <= max_vector_distance]
        return kept[:k]

    def as_runnable(
        self,
        *,
        k: int = 3,
        metadata_filter: Any = None,
        use_hybrid: bool = True,
        rerank: bool = False,
        score_threshold: float | None = None,
    ) -> RunnableLambda:
        """Expose this retriever as an LCEL-compatible runnable."""

        def run(query: str) -> list[Document]:
            if score_threshold is not None:
                return self.search_with_threshold(
                    query,
                    k=k,
                    metadata_filter=metadata_filter,
                    max_vector_distance=score_threshold,
                )
            return self.search(
                query,
                k=k,
                metadata_filter=metadata_filter,
                use_hybrid=use_hybrid,
                rerank=rerank,
            )

        return RunnableLambda(run)