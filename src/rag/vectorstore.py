"""Vector store utilities for policy retrieval."""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_aws import BedrockEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config.settings import settings
from src.rag.chunking import enrich_chunks, split_by_sections

logger = logging.getLogger(__name__)

POLICY_DIR = Path("data/policies")
VECTORSTORE_DIR = Path("data/vectorstore")


def _create_embeddings() -> BedrockEmbeddings:
    """Create a Bedrock embeddings client for FAISS indexing/search."""
    return BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0",
        region_name=settings.aws_region,
    )


def load_policy_documents(source_dir: str | Path = POLICY_DIR) -> list[Document]:
    """Load raw policy documents from disk."""
    source_path = Path(source_dir)
    loader = DirectoryLoader(
        str(source_path),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"autodetect_encoding": True},
        show_progress=False,
    )
    documents = loader.load()

    if not documents:
        raise ValueError(f"No policy documents found in: {source_path}")

    return documents


def build_chunks(
    documents: list[Document],
    chunking_strategy: str = "basic",
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Build document chunks using the requested strategy."""
    if chunking_strategy == "basic":
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return splitter.split_documents(documents)

    if chunking_strategy == "section_enriched":
        section_chunks = split_by_sections(
            documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return enrich_chunks(section_chunks)

    raise ValueError(
        "Unsupported chunking_strategy. Expected 'basic' or 'section_enriched'."
    )


def build_vectorstore(
    source_dir: str | Path = POLICY_DIR,
    persist_path: str | Path | None = None,
    chunking_strategy: str = "basic",
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> FAISS:
    """Build and persist a FAISS vector store from local policy .txt files."""
    documents = load_policy_documents(source_dir)
    chunks = build_chunks(
        documents,
        chunking_strategy=chunking_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    embeddings = _create_embeddings()
    vectorstore = FAISS.from_documents(chunks, embeddings)

    persist_dir = Path(persist_path or VECTORSTORE_DIR)
    persist_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(persist_dir))
    logger.info("Saved vector store to %s using %s chunking", persist_dir, chunking_strategy)

    return vectorstore


def load_vectorstore(persist_path: str | Path | None = None) -> FAISS:
    """Load the persisted FAISS vector store from disk."""
    persist_dir = Path(persist_path or VECTORSTORE_DIR)
    if not persist_dir.exists():
        raise FileNotFoundError(
            f"Vector store not found at {persist_dir}. Run build_vectorstore() first."
        )

    embeddings = _create_embeddings()
    return FAISS.load_local(
        str(persist_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def search_policies(
    query: str,
    top_k: int = 5,
    metadata_filter: dict | None = None,
    persist_path: str | Path | None = None,
) -> list[Document]:
    """Return the top-k most relevant policy chunks for a user query."""
    vectorstore = load_vectorstore(persist_path=persist_path)
    return vectorstore.similarity_search(query, k=top_k, filter=metadata_filter)


# Backward-compatible aliases if older imports still exist in exercises.
build_vector_store = build_vectorstore
load_vector_store = load_vectorstore
