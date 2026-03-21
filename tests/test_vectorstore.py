"""Tests for vector store build/load/search behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.rag import vectorstore


class DummyEmbeddings(Embeddings):
    """Deterministic local embedding model for tests (no network calls)."""

    _vocab = [
        "dti",
        "debt",
        "income",
        "loan estimate",
        "trid",
        "texas",
        "restriction",
        "credit",
        "score",
        "fico",
    ]

    def _embed(self, text: str) -> list[float]:
        lowered = text.lower()
        # Include a bias dimension so vectors are never all-zero.
        return [1.0] + [float(lowered.count(term)) for term in self._vocab]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@pytest.fixture
def sample_policy_dir(tmp_path: Path) -> Path:
    """Create local policy documents with known semantics for testing."""
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)

    # Long repeated content to force multiple chunks for at least one document.
    dti_body = (
        "Debt-to-income requirements and DTI limits are key underwriting factors. "
        "DTI is computed from monthly debt obligations divided by gross income. "
    ) * 40
    (policy_dir / "fannie_mae_guidelines.txt").write_text(
        "Fannie Mae policy\n" + dti_body + "Minimum credit score requirement is 620 FICO.",
        encoding="utf-8",
    )

    (policy_dir / "trid_regulations.txt").write_text(
        (
            "TRID rules\n"
            "The Loan Estimate must be provided within three business days after "
            "a completed application is received."
        ),
        encoding="utf-8",
    )

    (policy_dir / "texas_state_rules.txt").write_text(
        (
            "Texas restrictions\n"
            "Texas loan restrictions include an 80% LTV cap for certain home equity loans "
            "and additional constitutional limitations."
        ),
        encoding="utf-8",
    )

    return policy_dir


@pytest.fixture
def patch_vectorstore_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Patch persistence path and embeddings for isolated deterministic tests."""
    test_vectorstore_path = tmp_path / "vectorstore"
    monkeypatch.setattr(vectorstore, "VECTORSTORE_DIR", test_vectorstore_path)
    monkeypatch.setattr(vectorstore, "_create_embeddings", lambda: DummyEmbeddings())
    return test_vectorstore_path


def test_build_vectorstore_creates_expected_number_of_chunks(
    sample_policy_dir: Path,
    patch_vectorstore_env: Path,
) -> None:
    """build_vectorstore should persist FAISS with chunk count matching splitter output."""
    built_store = vectorstore.build_vectorstore(sample_policy_dir)

    loader = DirectoryLoader(
        str(sample_policy_dir),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"autodetect_encoding": True},
    )
    docs = loader.load()
    expected_chunks = len(
        RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=200).split_documents(docs)
    )

    assert built_store.index.ntotal == expected_chunks
    assert (patch_vectorstore_env / "index.faiss").exists()
    assert (patch_vectorstore_env / "index.pkl").exists()


def test_search_policies_returns_relevant_results_for_known_queries(
    sample_policy_dir: Path,
    patch_vectorstore_env: Path,
) -> None:
    """Known queries should retrieve chunks from the expected policy files."""
    vectorstore.build_vectorstore(sample_policy_dir)

    query_to_expected_file = {
        "What are the DTI limits?": "fannie_mae_guidelines.txt",
        "When must the Loan Estimate be provided?": "trid_regulations.txt",
        "Texas loan restrictions": "texas_state_rules.txt",
        "What is the minimum credit score?": "fannie_mae_guidelines.txt",
    }

    for query, expected_file in query_to_expected_file.items():
        results = vectorstore.search_policies(query, top_k=3)
        assert results, f"No search results returned for query: {query}"
        assert any(
            result.metadata.get("source", "").endswith(expected_file) for result in results
        ), f"Expected to find {expected_file} in search results for query: {query}"


def test_search_policies_metadata_filtering(
    sample_policy_dir: Path,
    patch_vectorstore_env: Path,
) -> None:
    """metadata_filter should constrain results to the requested source document."""
    vectorstore.build_vectorstore(sample_policy_dir)

    loader = DirectoryLoader(
        str(sample_policy_dir),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"autodetect_encoding": True},
    )
    docs = loader.load()
    texas_source = next(
        doc.metadata["source"]
        for doc in docs
        if doc.metadata.get("source", "").endswith("texas_state_rules.txt")
    )

    filtered = vectorstore.search_policies(
        query="loan restrictions",
        top_k=5,
        metadata_filter={"source": texas_source},
    )

    assert filtered, "Expected filtered search to return at least one result"
    assert all(doc.metadata.get("source") == texas_source for doc in filtered)
