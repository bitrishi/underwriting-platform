# RAG Skill — Policy Retrieval Pipeline

## Overview

The `src/rag/` module provides retrieval-augmented generation support for underwriting policy lookup. Its current implementation focuses on local text policy documents stored under `data/policies/` and uses FAISS for semantic search.

Primary implementation files:
- `src/rag/vectorstore.py`
- `src/rag/chunking.py`
- `src/rag/retriever.py`

Primary data locations:
- `data/policies/` for source policy documents
- `data/vectorstore/` for the persisted FAISS index

## RAG Pipeline

The retrieval pipeline follows this sequence:

1. **Load**
   - `build_vectorstore()` reads all `.txt` files under `data/policies/`
   - It uses `DirectoryLoader` with `TextLoader`
   - Each loaded document keeps source metadata such as the file path in `metadata["source"]`

2. **Chunk**
   - The raw policy text is split with `RecursiveCharacterTextSplitter`
   - Current configuration:
     - `chunk_size=800`
     - `chunk_overlap=200`
   - This turns long policy documents into overlapping retrieval units that are small enough to search efficiently and large enough to preserve underwriting context

3. **Embed**
   - Each chunk is embedded with Amazon Bedrock embeddings via `BedrockEmbeddings`
   - Current embedding model:
     - `amazon.titan-embed-text-v2:0`
   - These embeddings convert policy text into vectors so semantically similar questions can match even when wording differs

4. **Store**
   - The embedded chunks are indexed in a FAISS vector store
   - The built store is saved locally to `data/vectorstore/`
   - This avoids recomputing embeddings on every query once the store has been built

5. **Search**
   - `search_policies(query, top_k=5, metadata_filter=None)` loads the stored FAISS index
   - The query is embedded with the same embeddings model
   - FAISS returns the most similar chunks for the query
   - Optional metadata filters can narrow results to a specific source document

## Retrieval Strategies

The codebase now supports multiple retrieval modes depending on the query style and reliability requirements.

### 1. Basic Vector Retrieval

Implemented with:
- FAISS similarity search
- standard recursive chunking

Use when:
- queries are natural language and semantically close to the source wording
- you want the simplest and fastest retrieval path
- exact statutory citations are not the primary retrieval problem

Good examples:
- `What is the minimum credit score?`
- `When must the Loan Estimate be provided?`

### 2. Hybrid Retrieval

Implemented with:
- FAISS vector search for semantic matching
- BM25 keyword scoring via `rank-bm25`
- score fusion in `ProductionRetriever`

Use when:
- queries mix statute names, section numbers, and legal phrases
- the source text contains exact identifiers such as `50(a)(6)` or `TRID`
- semantic retrieval alone may miss exact regulatory strings

Good examples:
- `Section 50(a)(6) requirements`
- `What are the rules for Texas cash-out refinance?`

### 3. Re-ranked Retrieval

Implemented as an optional final step in `ProductionRetriever` using `flashrank`.

Use when:
- top-k retrieval is mostly correct but ordering still matters
- multiple candidate chunks are relevant and you need the best few promoted
- legal/compliance answers benefit from prioritizing the most directly responsive passage

Re-ranking is most useful after hybrid retrieval, not as a replacement for it.

### 4. Thresholded Retrieval

Implemented with `search_with_threshold()` in `ProductionRetriever`.

Use when:
- you would rather return no documents than weak or misleading matches
- the downstream chain must explicitly say `Insufficient documentation`
- the query may be out of scope for the indexed corpus

Good example:
- `What are USDA rural development subsidy percentages by county in 2026?`

## Current Functions

### `build_vectorstore(source_dir="data/policies")`
Builds the FAISS index from `.txt` policy files and persists it to `data/vectorstore/`.

### `load_vectorstore()`
Loads the existing FAISS index from `data/vectorstore/`.

### `search_policies(query, top_k=5, metadata_filter=None)`
Runs semantic retrieval over stored policy chunks and returns the most relevant documents.

### `split_by_sections(documents, chunk_size=800, chunk_overlap=200)`
Splits policy documents at uppercase section headers, then chunks inside each section.

### `enrich_chunks(chunks)`
Prepends document title, section name, and source path to the chunk body before embedding.

### `ProductionRetriever`
Combines vector retrieval, BM25 keyword search, optional reranking, metadata filtering, and score-threshold gating.

## Chunking Strategies

The project now supports two chunking modes.

### 1. Basic Recursive Chunking

Uses:
- `RecursiveCharacterTextSplitter`
- `chunk_size=800`
- `chunk_overlap=200`

Use when:
- the document is mostly narrative text
- sections are short and semantically self-contained
- you need a simple baseline index

### 2. Section-Aware Enriched Chunking

Uses:
- header detection in `split_by_sections()`
- recursive chunking inside each section
- `enrich_chunks()` to prepend document/section/source context

Use when:
- documents have strong heading structure
- queries mention a policy domain rather than quoting the source exactly
- you want section names to influence embeddings and retrieval ranking

This works especially well for policy files that contain distinct sections like:
- `DEBT-TO-INCOME REQUIREMENTS`
- `FICO CREDIT SCORE REQUIREMENTS`
- `LOAN ESTIMATE DELIVERY REQUIREMENTS`
- `MANDATORY WAITING PERIODS AND BORROWER RIGHTS`

### Why `800` characters

`800` is a practical middle ground for policy and compliance text:
- It is large enough to keep a full rule, threshold, or disclosure requirement together in many cases
- It is small enough to avoid stuffing unrelated sections into the same chunk
- It improves retrieval precision when policy files contain multiple topics like DTI, FICO, LTV, PMI, and disclosure timing

For this project, policy documents are dense but mostly paragraph-structured. A chunk size around `800` keeps enough semantic context to answer queries such as:
- DTI limits
- minimum credit score
- Loan Estimate timing
- Texas-specific restrictions

### Why `200` overlap

`200` characters of overlap reduces boundary loss:
- A rule that begins near the end of one chunk is likely to continue into the next
- Overlap helps preserve context for headings, thresholds, and exceptions that span chunk boundaries
- Retrieval remains more stable when users ask for details that sit across adjacent paragraphs

Without overlap, semantic search tends to miss partial rules or return incomplete policy language. With too much overlap, the store grows unnecessarily and produces more duplicate hits. `200` is a reasonable balance for these source documents.

## How To Add New Policy Documents

Use this process when adding new policies, overlays, or compliance guidance.

1. Add the new document as a UTF-8 `.txt` file under `data/policies/`
   - Example file names:
     - `freddie_mac_guidelines.txt`
     - `california_state_rules.txt`
     - `closing_disclosure_updates.txt`

2. Keep the content structured and searchable
   - Use clear section headers
   - Put topic names in plain language such as `DTI REQUIREMENTS`, `MINIMUM CREDIT SCORE`, or `DISCLOSURE TIMING`
   - Prefer complete sentences and paragraphs over fragmented notes

3. Rebuild the vector store
   - Run code that calls `build_vectorstore()`
   - This reloads all policy documents, rechunks them, re-embeds them, and overwrites the stored FAISS index under `data/vectorstore/`

4. Verify retrieval
   - Run a few semantic queries that should hit the new document
   - Confirm returned results include the correct `metadata["source"]`
   - If results are weak, inspect the document wording and section structure before changing embedding or chunking settings

## Authoring Guidance For New Documents

To improve retrieval quality:
- Use explicit underwriting terminology such as `DTI`, `debt-to-income`, `LTV`, `FICO`, `Loan Estimate`, and `Closing Disclosure`
- Include common synonym pairs when useful, for example `DTI` and `debt-to-income`
- Keep unrelated policy areas in separate sections with descriptive headings
- Avoid tables or formatting that loses meaning when converted to plain text
- Prefer one policy source per file so metadata filtering remains useful

## Operational Notes

- `search_policies()` depends on a previously built store in `data/vectorstore/`
- If `data/vectorstore/` does not exist, build the index first with `build_vectorstore()`
- `DirectoryLoader` is configured with `show_progress=False` so the pipeline does not require `tqdm` in minimal environments
- Metadata filtering works best when filtering on exact stored metadata values such as the full `source` path

## Typical Workflow

```python
from src.rag.vectorstore import build_vectorstore, search_policies

build_vectorstore("data/policies")
results = search_policies("When must the Loan Estimate be provided?", top_k=3)

for doc in results:
    print(doc.metadata.get("source"))
    print(doc.page_content)
```

## Observed Comparison Results

The live comparison in `src/exercises/week2_day5_advanced_rag.py` rebuilt:
- a basic vector store with standard recursive chunking
- an advanced vector store with section-aware enriched chunks

It then compared basic RAG vs advanced RAG on these five queries:
- `Section 50(a)(6) requirements`
- `income documentation requirements`
- `What are the rules for Texas cash-out refinance?`
- `When must the Loan Estimate be provided?`
- `What is the minimum credit score?`

Observed outcomes from that run:
- `Section 50(a)(6) requirements`: advanced retrieval improved because BM25 helped match the exact statutory reference
- `income documentation requirements`: advanced retrieval improved because section-aware chunks surfaced the employment/income section more directly
- `What are the rules for Texas cash-out refinance?`: advanced retrieval returned richer citations, including both Texas and Fannie Mae context
- `When must the Loan Estimate be provided?`: no material difference between basic and advanced retrieval in that run
- `What is the minimum credit score?`: no material difference between basic and advanced retrieval in that run

Threshold demonstration from the same run:
- for `What are USDA rural development subsidy percentages by county in 2026?`, thresholded retrieval returned no documents, and the structured RAG chain responded with insufficient context rather than forcing irrelevant citations

## When To Use What

- Use basic vector retrieval for straightforward policy questions already well-covered by a single paragraph or section.
- Use hybrid retrieval for exact citations, section numbers, constitutional references, and mixed keyword-plus-semantic questions.
- Use reranking when multiple plausible chunks are retrieved and answer precision matters.
- Use thresholded retrieval when false positives are more dangerous than no answer.

## Future Improvements

Likely next enhancements for this RAG layer:
- tune the vector distance threshold per corpus instead of using one static value
- support incremental refresh instead of rebuilding the full FAISS index
- add document normalization and metadata enrichment during ingestion
- expose score diagnostics to help tune hybrid weighting and threshold values

## Query Strategy (Priority Order)

1. **Deterministic templates** — `COMPLIANCE_QUERIES` in `query_templates.py`
   Best for known topics. Most reliable. No LLM call.

2. **Synonym expansion** — `TERM_SYNONYMS` in `query_templates.py`
   For unknown topics. Catches terminology mismatches. No LLM call.

3. **LLM rewriting** — NOT USED in production.
   Unreliable (doesn't know our docs). Reserved for future chatbot interface.

## Multi-Model Strategy

| Task | Model | Reason |
|------|-------|--------|
| Routine RAG | Haiku | Cheap, fast, good enough |
| Critical RAG | Sonnet | Strongest reasoning for legal text |
| Retrieval grading | Haiku | Simple yes/no task |
| Hallucination check | Haiku | Verification task |

## Cost Analysis

| Mode | LLM Calls | Cost/Query | Use When |
|------|-----------|-----------|----------|
| Routine | 1 (Haiku) | ~$0.001 | General policy lookups |
| Critical | 1 (Sonnet) | ~$0.003 | Regulatory compliance |
| Critical + verify | 2 (Sonnet + Haiku) | ~$0.005 | When self-check flags issues |