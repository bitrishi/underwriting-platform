"""Chunking utilities for policy documents."""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

SECTION_HEADER_RE = re.compile(r"^[A-Z][A-Z0-9\s\-\(\)\/%&,:]{3,}$")


def _document_name(source: str) -> str:
    return Path(source).stem.replace("_", " ").title() if source else "Unknown Document"


def _iter_sections(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_header = "Introduction"
    current_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current_lines:
                current_lines.append("")
            continue

        if SECTION_HEADER_RE.match(line):
            if current_lines:
                sections.append((current_header, current_lines))
            current_header = line
            current_lines = []
            continue

        current_lines.append(line)

    if current_lines:
        sections.append((current_header, current_lines))

    return [
        (header, "\n".join(lines).strip())
        for header, lines in sections
        if "\n".join(lines).strip()
    ]


def split_by_sections(
    documents: list[Document],
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Split documents on section headers, then chunk within each section."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks: list[Document] = []

    for document in documents:
        source = str(document.metadata.get("source", ""))
        doc_name = _document_name(source)
        sections = _iter_sections(document.page_content)
        if not sections:
            sections = [("Introduction", document.page_content.strip())]

        for section_index, (section_name, section_text) in enumerate(sections, start=1):
            section_metadata = {
                **document.metadata,
                "document_name": doc_name,
                "section": section_name,
                "section_index": section_index,
            }
            section_doc = Document(page_content=section_text, metadata=section_metadata)
            section_chunks = splitter.split_documents([section_doc])
            for chunk_index, chunk in enumerate(section_chunks, start=1):
                chunk.metadata["chunk_index"] = chunk_index
                chunks.append(chunk)

    return chunks


def enrich_chunks(chunks: list[Document]) -> list[Document]:
    """Prepend document and section context to chunk text for better retrieval."""
    enriched: list[Document] = []

    for chunk in chunks:
        source = str(chunk.metadata.get("source", ""))
        doc_name = str(chunk.metadata.get("document_name") or _document_name(source))
        section_name = str(chunk.metadata.get("section", "Introduction"))
        prefix = f"Document: {doc_name}\nSection: {section_name}\nSource: {source}\n\n"
        enriched.append(
            Document(
                page_content=prefix + chunk.page_content,
                metadata={**chunk.metadata, "enriched": True},
            )
        )

    return enriched