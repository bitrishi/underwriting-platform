"""Bridge utilities from Textract output into FAISS ingestion."""

from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.rag.vectorstore import _create_embeddings
from src.tools.textract_tools import detect_document_text


def chunk_textract_pages(
    textract_payload: dict,
    source_path: str,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> list[Document]:
    """Create page-preserving chunks from Textract extraction payload."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    pages = textract_payload.get("pages") or []
    if not pages:
        pages = [
            {
                "page_number": 1,
                "text": textract_payload.get("raw_text", ""),
            }
        ]

    chunks: list[Document] = []
    for page in pages:
        page_num = int(page.get("page_number", 1) or 1)
        text = str(page.get("text", "") or "")
        if not text.strip():
            continue

        source_doc = Document(
            page_content=text,
            metadata={
                "source": source_path,
                "page_number": page_num,
                "extraction_method": "textract",
            },
        )
        page_chunks = splitter.split_documents([source_doc])
        for chunk_idx, chunk in enumerate(page_chunks, start=1):
            chunk.metadata["chunk_index"] = chunk_idx
            chunks.append(chunk)

    return chunks


def ingest_textract_documents_to_faiss(
    document_paths: list[str],
    persist_path: str | Path = "data/vectorstore/textract",
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> dict:
    """Extract text via Textract pipeline, chunk it, and persist FAISS index."""
    all_chunks: list[Document] = []
    processed_sources: list[str] = []

    for document_path in document_paths:
        payload = detect_document_text(document_path)
        chunks = chunk_textract_pages(
            payload,
            source_path=document_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if chunks:
            all_chunks.extend(chunks)
            processed_sources.append(document_path)

    if not all_chunks:
        raise ValueError("No chunks were generated from provided documents.")

    embeddings = _create_embeddings()
    vectorstore = FAISS.from_documents(all_chunks, embeddings)

    persist_dir = Path(persist_path)
    persist_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(persist_dir))

    return {
        "persist_path": str(persist_dir),
        "documents_processed": len(processed_sources),
        "chunks_created": len(all_chunks),
        "sources": processed_sources,
    }
