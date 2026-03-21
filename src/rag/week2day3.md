# Week 2 — Day 3: Embeddings & Vector DB

**Date:** Session 8  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. What embeddings are (text → vector of numbers representing meaning)
2. Cosine similarity (measuring meaning distance)
3. Embedding models vs. LLMs (deterministic numbers vs. generative text)
4. FAISS vector database (local dev)
5. Document loading and chunking strategies
6. Metadata design and filtering
7. Production scaling (FAISS → OpenSearch → Bedrock Knowledge Bases)

---

## Core Concept: Embeddings

An embedding converts text into a list of numbers representing its MEANING.

```python
from langchain_aws import BedrockEmbeddings

embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region_name="us-east-1",
)

vector = embeddings.embed_query("What is the DTI requirement?")
# Returns [0.023, -0.041, 0.089, ...] — 1024 numbers
# Same input ALWAYS produces same output (deterministic)
```

Two sentences with similar meaning → similar vectors → high cosine similarity.

---

## Cosine Similarity Formula

```
cosine = dot(A, B) / (norm(A) × norm(B))

dot product:  multiply corresponding elements, sum them
              [1,2,3] · [4,5,6] = (1×4) + (2×5) + (3×6) = 32

norm:         length of vector = sqrt(sum of squares)
              norm([1,2,3]) = sqrt(1² + 2² + 3²) = sqrt(14) ≈ 3.74

Why divide:   removes effect of vector length
              only measures ANGLE (direction = meaning)

Result:       1.0 = identical meaning (0° angle)
              0.0 = completely unrelated (90° angle)
```

Java analogy: Like comparing percentages instead of absolute numbers. Normalizes for size, compares direction only.

---

## Embedding Models vs. LLMs

| Aspect | LLM (Claude) | Embedding Model (Titan) |
|--------|-------------|------------------------|
| Output | Variable-length text | Fixed-size number vector |
| Deterministic? | No (temperature) | **Yes, always same output** |
| Training goal | Predict next word | Learn semantic similarity |
| Size | 7B-200B+ params | 100M-1B params |
| Cost | $$$ | $ (50-100x cheaper) |
| Use case | Reasoning, generation | Search, comparison |

---

## FAISS Vector Database

```python
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

documents = [
    Document(
        page_content="The maximum DTI ratio for qualified mortgages is 43%...",
        metadata={"source": "fannie_mae.pdf", "page": 42, "topic": "dti"}
    ),
    # ... more documents
]

# Create vector store (embeds all documents)
vectorstore = FAISS.from_documents(documents, embeddings)

# Search by meaning
results = vectorstore.similarity_search(
    "debt-to-income requirements",  # different words!
    k=3
)
# Finds DTI documents even though query used different terminology

# Save / load
vectorstore.save_local("data/vectorstore")
vectorstore = FAISS.load_local("data/vectorstore", embeddings,
                                allow_dangerous_deserialization=True)
```

---

## Chunking

Split large documents into focused pieces for precise retrieval.

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,      # max chars per chunk
    chunk_overlap=200,   # overlap preserves context at boundaries
    separators=["\n\n", "\n", ". ", " "],
)

chunks = splitter.split_documents(documents)
```

| Chunk Size | Good For | Trade-off |
|-----------|----------|-----------|
| 200-500 | Precise facts | Loses broader context |
| 500-1000 | Balance (our choice) | Good default |
| 1000-2000 | Complex topics | Less precise matching |

Context preservation: overlap ensures boundary sentences appear in both chunks.

---

## Complete Pipeline

```python
# src/rag/vectorstore.py

def build_vectorstore(docs_path: str = "data/policies") -> FAISS:
    """Load → Chunk → Embed → Store"""
    loader = DirectoryLoader(docs_path, glob="**/*.txt")
    documents = loader.load()
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=200
    )
    chunks = splitter.split_documents(documents)
    
    vectorstore = FAISS.from_documents(chunks, create_embeddings())
    vectorstore.save_local("data/vectorstore")
    return vectorstore
```

---

## Q&A from This Session

### Q: Explain cosine similarity — why is 1 identical and 0 unrelated?

Cosine measures the ANGLE between two vectors. Same direction = 0° = cos(0°) = 1.0. Perpendicular = 90° = cos(90°) = 0.0.

Three parts of the formula:
- **Dot product:** multiply corresponding elements, sum them. Measures alignment.
- **Norm:** length of vector (sqrt of sum of squares). Used to normalize.
- **Division:** removes length effect, only measures angle (meaning similarity).

### Q: Different model for embeddings — how do they differ from LLMs?

Fundamentally different models. Embedding models are trained for semantic similarity (which texts mean similar things). They output fixed-size number vectors, are deterministic (same input = same output always), much smaller (100M vs 200B params), and 50-100x cheaper. LLMs are trained for text generation, non-deterministic, and output variable-length text.

Same input → same vector every time. This is critical because vector DB would break if embeddings changed between storage and query.

### Q: More examples of metadata? How is it useful?

Metadata is structured tags stored alongside the vector for filtering and citation:

```python
metadata = {
    "source": "fannie_mae_guide_2024.pdf",
    "page": 42,
    "section": "Section 3.4: DTI Requirements",
    "jurisdiction": "federal",          # filter: Texas loan gets Texas rules
    "loan_type": "conventional",        # filter: FHA loan gets FHA guidelines
    "topic": "dti",                     # filter: narrow by subject
    "effective_date": "2024-01-01",     # filter: only current regulations
    "status": "current",               # filter: exclude superseded rules
}
```

Use cases: jurisdiction filtering (Texas loan → Texas rules only), loan type filtering, recency filtering, and source citation in audit trails.

### Q: What if I don't know the document name?

You don't need to! Semantic search finds documents by MEANING. Metadata in the results tells you WHERE it came from. You search with a question, the vector DB finds relevant content, then you read metadata to see the source.

### Q: Is OpenSearch an AWS managed service? How does Bedrock help?

Yes, OpenSearch Serverless is fully managed. AWS provides multiple options:

| Service | What It Does | Best For |
|---------|-------------|----------|
| FAISS | In-memory, local | Development |
| OpenSearch Serverless | Managed vector search | Production |
| Bedrock Knowledge Bases | Zero-code RAG (upload to S3, done) | Fastest to production |
| Aurora pgvector | PostgreSQL + vectors | Teams already on Aurora |

Bedrock Knowledge Bases eliminates all RAG code — you upload PDFs to S3 and Bedrock handles chunking, embedding, storage, and retrieval automatically.

### Q: How does chunking keep context if only loading pieces?

Three strategies:
1. **Overlap** (our approach): 200-char overlap ensures boundary sentences appear in both chunks
2. **Parent-child**: Small chunks for search, retrieve parent (larger chunk) for LLM context
3. **Context prepending**: Add section headers and document info to each chunk

### Q: Scaling to 1000s of PDFs — what's the right mechanism?

Math: 1,000 PDFs × 100 pages × 5 chunks/page = 500K chunks. Embedding cost: ~$4 (one-time). Search latency: <100ms. FAISS handles this in memory (~2GB). OpenSearch auto-scales for larger datasets. For production, use batch ingestion pipeline or Bedrock Knowledge Bases (zero code).

### Q: Too many matches — will the LLM get confused?

Yes, too many results adds noise. Use k=3 to k=5 (sweet spot). Prompt: "Answer ONLY from provided context." LLM can still make mistakes — safeguards include citation requirements, faithfulness evaluation (Ragas in Week 6), confidence thresholding, and Agentic RAG self-correction (Week 3).

### Q: Metadata filtering — does embedding search first then filter, or filter first then search?

Depends on the database:
- **FAISS**: Post-filter (search all, then filter results). Works for small datasets.
- **OpenSearch**: Pre-filter (filter first, then search within subset). Better for production.
- **Hybrid**: Filter → vector search → keyword search → combine and re-rank. Best accuracy.

Best practices: Design metadata schema upfront like a DB schema. Validate with Pydantic at ingestion. Use hierarchical filters (jurisdiction → loan_type → topic). Auto-extract metadata with code or LLM during ingestion.

---

## Assignments (Completed ✅)

- [x] Task 1: Sample policy documents (fannie_mae, trid, texas)
- [x] Task 2: vectorstore.py with build, load, search functions
- [x] Task 3: 5 semantic searches — different wording found correct docs ✅
- [x] Task 4: Cosine similarity comparison (similar vs unrelated)
- [x] Task 5: Vectorstore tests
- [x] Task 6: rag/SKILL.md documentation