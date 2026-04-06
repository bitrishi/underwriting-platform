# Week 2 — Day 5: Advanced RAG — Chunking, Hybrid Search & Re-Ranking

**Date:** Session 10  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. Three problems with basic RAG (bad chunks, semantic misses, irrelevant top results)
2. Section-aware chunking and context enrichment
3. Parent-child chunking (precise search, full context)
4. Hybrid search (vector + BM25 keyword)
5. Re-ranking with cross-encoders
6. Similarity score thresholds
7. ProductionRetriever combining all strategies

---

## Three Problems With Basic RAG

| Problem | Example | Solution |
|---------|---------|----------|
| Bad chunks | Regulation split mid-sentence | Section-aware chunking |
| Semantic misses | "Section 50(a)(6)" not found by meaning | Hybrid search (BM25 + vector) |
| Irrelevant top results | 1 great + 2 mediocre results | Re-ranking with cross-encoder |

---

## Smarter Chunking

### Section-Aware Chunking

```python
def split_by_sections(text: str, source: str) -> list[Document]:
    """Split at section headers, not arbitrary character counts."""
    pattern = r'((?:Section|Article)\s+[\d.]+[:\s\-]+[^\n]+)'
    parts = re.split(pattern, text)
    # Each chunk = complete section with metadata
```

### Context-Enriched Chunks

```python
def enrich_chunks(chunks):
    """Prepend document/section info to each chunk."""
    for chunk in chunks:
        chunk.page_content = (
            f"Document: {chunk.metadata['source']}\n"
            f"Section: {chunk.metadata['section']}\n"
            f"Content: {chunk.page_content}"
        )
    # Now embedding captures WHAT document and WHICH section
```

### Parent-Child Chunking

```python
# Small chunks for precise search
# But retrieve parent (large chunk) for LLM context
child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000)

# Search hits child → return parent content
```

---

## Hybrid Search

Combines semantic (FAISS) + keyword (BM25):

```python
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

hybrid = EnsembleRetriever(
    retrievers=[
        vectorstore.as_retriever(search_kwargs={"k": 5}),
        BM25Retriever.from_documents(documents, k=5),
    ],
    weights=[0.5, 0.5],
)
```

- FAISS finds: "debt-to-income" when you search "DTI" (meaning)
- BM25 finds: "Section 50(a)(6)" when you search that exact term (keywords)
- Together: best of both worlds ✅

Weight tuning:
- Legal/exact terms: `[0.3, 0.7]` (favor keyword)
- Conceptual queries: `[0.7, 0.3]` (favor semantic)
- Balanced: `[0.5, 0.5]`

---

## Re-Ranking

Two-stage retrieval: fast broad search → precise re-scoring.

```python
# Stage 1: FAISS returns top 10 (fast, milliseconds)
# Stage 2: Cross-encoder scores each against query (precise)
# Return top 3 after re-ranking

from langchain_community.document_compressors import FlashrankRerank

compressor = FlashrankRerank(top_n=3)
reranked = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=vectorstore.as_retriever(search_kwargs={"k": 10}),
)
```

---

## Score Threshold

```python
def search_with_threshold(vectorstore, query, k=5, threshold=0.7):
    results_with_scores = vectorstore.similarity_search_with_score(query, k=k)
    filtered = [(doc, s) for doc, s in results_with_scores if s <= threshold]
    return [doc for doc, s in filtered] if filtered else []
    # Returns empty if nothing is relevant enough
```

---

## Q&A from This Session

### Q: How does re-ranking actually work? Is the re-ranker an LLM?

**No, it's NOT an LLM.** A re-ranker is a cross-encoder — a much smaller, specialized model:

| Aspect | LLM (Claude) | Re-Ranker (FlashRank) |
|--------|-------------|----------------------|
| Size | 7B-200B params | 22M-300M params |
| Output | Text | Single number (0.0-1.0) |
| Cost | $$$ per API call | Free, runs locally |
| Speed | 1-5 seconds | 5-50ms per document |
| Runs where | Bedrock (cloud) | Your machine (local) |

**How it works:**

```
Embedding (bi-encoder):
  Query → [vector]  }  compared SEPARATELY
  Doc   → [vector]  }  by distance

Cross-encoder (re-ranker):
  [Query + Doc TOGETHER] → relevance score
  Sees BOTH simultaneously, reasons about the match
```

**The algorithm:**
1. FAISS returns top 10 by vector distance (fast, broad)
2. Cross-encoder scores each of the 10 as [query + doc] pairs (precise)
3. Sort by cross-encoder score, return top 3

Java analogy: Phase 1 = fast index scan returns candidates. Phase 2 = detailed evaluation of each candidate.

### Q: In embeddings, I embed all docs first, then the query, then find shortest distance. But if Document B has "Texas" and the query has "Texas", shouldn't it return as closest?

**No, and here's why:** Embeddings capture OVERALL meaning, not individual keywords. A single vector represents the ENTIRE paragraph's meaning.

**The core problem:**

```
Query: "Can a Texas borrower with DTI 44% get approved?"
  → Query embedding is dominated by "DTI limits for mortgages"

Document A: "Maximum DTI for qualified mortgages is 43%..."
  → Embedding: densely about DTI limits
  → Distance to query: 0.11 (VERY close — pure DTI match)

Document B: "Texas Section 50(a)(6) loans have DTI exceptions..."
  → Embedding: spread across Texas + legal reference + DTI + exceptions
  → Distance to query: 0.16 (further — embedding pulled in multiple directions)
```

Document A wins because it's a DENSE match on the query's dominant concept (DTI limits). Document B is the BETTER answer but its embedding is spread across multiple concepts (Texas, legal codes, DTI, exceptions).

**This is exactly what re-ranking fixes.** The cross-encoder sees query + document B together and recognizes "Texas + DTI 44% + allows up to 45% = PERFECT match."

**Mitigations without re-ranking:**
1. **Metadata filtering** — `filter={"jurisdiction": "state_texas"}` forces Texas docs only. Then Document B IS #1 within that filtered set.
2. **Hybrid search** — BM25 keyword search catches "Texas" as a keyword match, boosting Document B.
3. **Focused queries from agent** — instead of one broad query, agent makes focused searches: "Texas DTI exceptions" 

**Best production approach:** Metadata filtering + hybrid search handles 90% of cases. Add re-ranking for the remaining 10% precision-critical queries.

---

## Summary

| Technique | What It Solves | When to Use |
|-----------|---------------|-------------|
| Section-aware chunking | Splits mid-regulation | Structured docs (policies) |
| Context enrichment | Chunks lack doc context | Always — cheap improvement |
| Parent-child chunking | Small chunks lose context | Need precise search + full context |
| Hybrid search (BM25+vector) | Exact terms missed | Legal references, section numbers |
| Re-ranking | Top-k includes irrelevant | Large collections, precision-critical |
| Score threshold | Returning garbage | Production (prevent bad answers) |

---

## Assignments (Completed ✅)

- [x] Task 1: Section-aware chunking + context enrichment
- [x] Task 2: Hybrid retriever (FAISS + BM25) — found results vector missed ✅
- [x] Task 3: Similarity threshold (empty results for irrelevant queries)
- [x] Task 4: Advanced vs. basic RAG comparison
- [x] Task 5: Retriever tests
- [x] Task 6: Updated rag/SKILL.md with strategies