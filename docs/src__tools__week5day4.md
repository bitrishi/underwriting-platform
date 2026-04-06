md_content = """# Week 5, Day 4: AWS Textract Hybrid Integration & RAG Strategies Deep Dive

## Session Overview
**Date:** Week 5, Day 4
**Topic:** AWS Textract for cost-optimized document processing, hybrid Textract+Vision architecture, and comprehensive RAG strategy reference with detailed explanations of all 8 strategies including when and how to combine them.
**Prerequisites:** Week 3 Document Review agent (vision-based), Week 2-3 RAG pipeline, Week 5 Day 3 Guardrails

---

## 1. The Cost Problem

### 1.1 Current State

Document Review uses Sonnet vision for EVERY document at $0.005/page. For 10-15 pages per loan application, that is $0.05-0.075 per evaluation — roughly 50% of total pipeline cost. Most documents are standard typed forms (W-2, 1040, pay stubs) with predictable layouts. Using a $0.005/page vision model for typed forms is like hiring a senior architect to hang a picture frame.

### 1.2 The Solution

AWS Textract extracts text and structured data at $0.0015/page — one-third the cost. For standard forms, Textract is actually MORE accurate than vision because it is purpose-built for document extraction. The hybrid approach: Textract for standard forms, Sonnet vision only for unstructured documents that Textract cannot handle.

### 1.3 Cost Savings

Typical application with 12 pages: without hybrid all Sonnet = $0.060. With hybrid (8 standard via Textract + 4 unstructured via Vision) = $0.032. Savings: 47%. At 1,000 evaluations/day: saves $840/month.

---

## 2. What Textract Is

### 2.1 Beyond Basic OCR

Textract goes beyond converting pixels to characters. It understands document STRUCTURE — tables, forms, key-value pairs. Three extraction modes:

DetectDocumentText is basic OCR returning raw text lines and words with confidence scores. Cheapest mode. Use when you just need text content.

AnalyzeDocument with Forms feature extracts key-value pairs. Understands that "Box 1: $120,000" means key is "Box 1" and value is "$120,000." This is what makes Textract powerful for standard forms — it understands form structure, not just text.

AnalyzeDocument with Tables feature extracts table structures with rows, columns, and cell values. Critical for bank statements and financial reports where data is in grids.

Java analogy: DetectDocumentText is reading a file as plain text. AnalyzeDocument Forms is parsing XML with a schema-aware parser. AnalyzeDocument Tables is parsing CSV with header detection.

### 2.2 Synchronous vs Asynchronous

Synchronous mode sends document and gets results immediately. Use for small documents (under 5 pages) — individual W-2s, pay stubs, single-page forms.

Asynchronous mode starts a job pointing to an S3 object. Textract processes in background. You poll or receive SNS notification. Use for large documents (over 5 pages) and batch processing.

---

## 3. Textract vs Vision: When Each Wins

### 3.1 Textract Wins

Standard forms with typed text (W-2, 1040, pay stub, bank statement). Faster, cheaper, more consistent. Extraction is DETERMINISTIC — same document always produces same output (important for audit).

Documents with tables (bank statements, amortization schedules). Textract's table extraction identifies rows, columns, and cells accurately. Vision sometimes misaligns table data.

Many pages processed quickly. Textract processes asynchronously and handles multi-page PDFs in batch. Vision requires separate LLM call per page.

### 3.2 Vision Wins

Handwritten documents (employment verification letters, signed disclosures). Textract OCR struggles with handwriting. Vision understands handwriting contextually.

Unusual formats (foreign tax documents, non-standard forms, property sketches). Textract expects standard layouts. Vision handles any visual content.

Documents with photos or diagrams (property photos in appraisals, floor plans). Textract extracts text only. Vision understands images.

When you need UNDERSTANDING not just extraction. "Does this appraisal show red flags?" requires reasoning about content. Vision reasons; Textract only extracts.

### 3.3 Scanned PDFs

You CAN use Textract on scanned PDFs. Textract handles both digital and scanned PDFs. The routing decision is about CONTENT TYPE (typed vs handwritten), not FILE FORMAT (digital vs scanned). A scanned PDF of a typed W-2 works great with Textract. A scanned PDF of a handwritten letter needs vision.

---

## 4. The Hybrid Architecture

### 4.1 Document Router

The router decides Textract vs vision using two signals. Signal 1: document classification from your existing classify_document tool tells you the type. W-2, 1040, pay stub, bank statement route to Textract. Employment letter, foreign doc, handwritten route to vision. Signal 2: for low classification confidence (below 80%), route to vision as safe default.

### 4.2 The Field Mapping Layer

Textract returns generic key names based on text it reads ("Wages, tips, other compensation"). You need to MAP these to your Pydantic model fields (wages, federal_tax_withheld). This mapping is document-type-specific and deterministic Python code — no LLM needed.

The mapping handles exact key matches, partial key matches, value cleaning (remove $ and commas, convert to float), and missing field handling (flag as unclear).

This means the Textract path is FULLY DETERMINISTIC: same document always produces same extraction. No temperature variation, no LLM inconsistency. Every extraction is reproducible — regulators value this.

### 4.3 Fallback Pattern

Try Textract first. If extraction confidence is low, fields are missing, or Pydantic validation fails, fall back to Sonnet vision for that document. Log the fallback reason for monitoring. If a document type frequently falls back, investigate and adjust mapping or classification.

### 4.4 Both Paths Produce Same Output

The Pydantic output models (W2Extraction, PayStubExtraction) are identical regardless of extraction method. Risk Scoring receives the same BorrowerPackage whether data came from Textract or vision. This is a pure optimization — same results, lower cost. The Adapter pattern: same interface, different implementations.

---

## 5. Scaling for Large Documents

### 5.1 The 5,000 Page Problem

Neither synchronous Textract nor vision handles 5,000 pages as a single request. Vision is completely impractical — 5,000 images at 1,600 tokens each = 8 million tokens (far beyond context limits). Even as individual calls: 5,000 calls at 3-5 seconds each = 4-7 hours.

### 5.2 The Right Design

Step 1: Split PDF into chunks (500-1000 pages each) using PyPDF2. Upload to S3.

Step 2: Start parallel Textract async jobs — one per chunk. All run concurrently on Textract infrastructure. 5 jobs of 1,000 pages.

Step 3: Wait for all jobs (SNS notifications or polling). Processing time approximately 10-15 minutes for 5,000 pages.

Step 4: Collect and merge results. Each job returns text, key-value pairs, tables. Merge into single document structure with page numbers preserved.

Step 5: Apply intelligent processing on extracted text. RAG pipeline identifies relevant sections. Classification finds specific document types. Agents reason about content.

Cost: 5,000 pages at $0.0015 = $7.50. Compare to vision: $25 AND hours of processing. For large documents, Textract is not just cheaper — it is the ONLY viable option.

### 5.3 Textract Limits

Maximum 3,000 pages per async job. For larger documents, split into multiple jobs and process in parallel. No limit on number of concurrent jobs (subject to account service quotas).

---

## 6. Textract Output and RAG Integration

### 6.1 Two Types of Output, Two Uses

Textract gives you TWO things from a document:

Structured data (key-value pairs, tables) — use DIRECTLY as structured data for known forms. Feed into Pydantic models via field mapping. No RAG needed. W-2 key-value pairs become W2Extraction directly.

Raw text (lines and paragraphs) — use for RAG when you need to SEARCH through unstructured content. Chunk, embed, store in vector DB. 100-page appraisal narrative goes through your RAG pipeline.

For standard forms: Textract key-values go straight to Pydantic models. No embedding, no vector DB, no semantic search.

For narrative documents: Textract raw text goes through your existing RAG pipeline — chunk with RecursiveCharacterTextSplitter, add metadata (page number, document type, source), embed into FAISS.

### 6.2 Preserving Document Structure

Textract returns text organized by page with reading order preserved. Chunks maintain paragraph structure. Metadata per chunk includes page number (from Textract page blocks), document type (from classification), source file, and section headers (if detected).

This metadata enables filtered search: "find property condition comments from the appraisal report, pages 40-60."

---

## 7. Complete RAG Strategy Reference

### 7.1 What Gets Stored in the Vector DB

Every record has THREE components stored together. The embedding (1024 floating point numbers from Titan Embed) is for FINDING via similarity search. The page_content (the actual text) is for READING — this is what the LLM receives as context. The metadata (structured tags like source, page, jurisdiction, topic) is for FILTERING before search. The embedding finds it. Metadata filters it. Page_content is read by the LLM. You keep the original document separately in S3 for regulatory requirements.

### 7.2 Strategy 1: Basic RAG

Embed documents. Embed query. Find top-k by cosine similarity. Send to LLM. One call. Good for general conceptual questions. Weakness: no quality checking, misses exact terms, returns closest results even if not relevant.

### 7.3 Strategy 2: Hybrid Search (Vector + BM25)

Combine semantic search (finds "debt-to-income" when you search "DTI") with keyword search (finds "Section 50(a)(6)" by exact match). EnsembleRetriever with configurable weights. Essential for regulatory content mixing concepts and specific references. Weakness: still no quality checking.

### 7.4 Strategy 3: Re-Ranking

Retrieve top-10 with broad search. Re-rank with cross-encoder that scores query+document TOGETHER (unlike embeddings which encode separately). The cross-encoder sees word-level interactions: "Texas" in query matches "Texas" in document, "44%" near "45%." Promoted the Texas-specific document from Rank 4 to Rank 1 in the example because it saw both texts simultaneously.

Cross-encoder is local model (FlashRank, 50MB, free, ~50ms for 10 docs). Not an LLM. Purpose-built for relevance scoring. Two-stage approach: fast broad filter (embedding, milliseconds) then precise careful evaluation (cross-encoder, 50ms). Same pattern as database query optimization.

### 7.5 Strategy 4: Metadata Filtering

Filter by structured metadata BEFORE semantic search. 500,000 chunks narrowed to 3,000 Texas conventional chunks. 99.4% eliminated before embedding search runs. Essential for jurisdiction-specific compliance. No extra cost — filtering is a database operation.

Different from Strategy 5 in that metadata filtering narrows the SEARCH SPACE. Strategy 5 uses predetermined QUERY STRINGS. They work together: Strategy 5 uses Strategy 4 as part of its approach.

### 7.6 Strategy 5: Smart RAG (Primary Approach)

Deterministic query templates for known topics (COMPLIANCE_QUERIES lookup table — you wrote queries knowing your document corpus). Synonym expansion for terminology mismatch (TERM_SYNONYMS adds "debt-to-income" when query has "DTI"). Metadata filtering for jurisdiction and loan type. Semantic search on filtered subset. ONE LLM call that grades relevance, answers, cites sources, and self-checks for hallucination — all in the ComplianceAnswer model.

Zero LLM calls for query formulation, expansion, or filtering. ONE call for reasoning. Cost approximately $0.001. Deterministic where possible, LLM only for the reasoning step.

### 7.7 Strategy 6: Agentic RAG (Critical Compliance)

Same retrieval as Strategy 5. Then SEPARATE LLM calls for each step: grade each document individually (3 calls — each has ONE job, no incentive to stretch relevance), check if enough relevant docs found (if not: rewrite query and re-retrieve), generate answer from ONLY the verified relevant docs (irrelevant docs excluded from context), and check hallucination with a SEPARATE critic (different prompt = different cognitive role, catches what self-check misses).

Query rewriting: a SEPARATE LLM call tries different terminology. It does NOT know your document corpus — it guesses based on general knowledge. Your deterministic COMPLIANCE_QUERIES often outperform LLM rewriting. The rewriter is a FALLBACK for when templates do not cover the question.

Total: 5-10 LLM calls. Cost approximately $0.005-0.010. Use when wrong answer has legal consequences.

### 7.8 Strategy 7: Parent-Child Chunking

Store small chunks (400 chars) for precise searching. Store large parent chunks (2000 chars) for context. Search hits small child chunk. LLM receives the full parent section. Best of both: precise matching AND complete context. Search "DTI compensating factors" hits small chunk but LLM sees the entire section with the limit, the factors, and the specifics.

### 7.9 Strategy 8: Context-Enriched Chunks

Prepend document name, section header, topic to each chunk before embedding. The embedding captures not just content but what document and section it is from. Improves retrieval precision when document identity matters.

### 7.10 Strategies COMBINE

Smart RAG (5) already uses Metadata Filtering (4) and Context-Enriched (8). Agentic RAG (6) uses everything in Strategy 5 plus separate grading and verification. For maximum precision on critical queries: Metadata (4) + Hybrid (2) + Re-ranking (3) + Parent-child (7) + Agentic verification (6). Every technique stacked.

### 7.11 Decision Tree

Known topic and not compliance-critical: Strategy 5 (Smart RAG). Known topic and compliance-critical: Strategy 6 (Agentic RAG). Searching large document with mixed concepts and exact refs: Strategy 2 (Hybrid) + Strategy 3 (Re-rank) + Strategy 7 (Parent-child). Simple general question: Strategy 1 (Basic RAG).

---

## 8. Q&A

### Q: Can I use Textract on scanned PDFs?

Yes. Textract handles both digital and scanned PDFs. The routing decision is about content type (typed vs handwritten), not file format. Scanned PDF of a typed W-2 works great with Textract. Scanned PDF of a handwritten letter needs vision.

### Q: 5,000 page scanned PDF — what should I use?

Textract async processing. Split into chunks of 500-1000 pages, upload to S3, start parallel Textract jobs. Processing time approximately 10-15 minutes. Cost $7.50. Vision is impractical — 8 million tokens far exceeds context limits, would take 4-7 hours as individual calls.

### Q: If classification already scans the document, why extract again separately?

Classification looks at page 1 for half a second and answers "what TYPE of document is this?" — reads the header, logo, layout. Costs $0.0003 (Haiku, 1 page). Extraction reads EVERY field on EVERY page and returns structured data. Different jobs: classification identifies the document, extraction reads its content. Classification cost is trivial compared to extraction savings it enables by routing to Textract vs vision.

### Q: Does Textract key-value extraction lose document meaning?

For structured forms (W-2, 1040): No. The meaning IS the key-value pairs. "Box 1: $120,000" has the same meaning whether read by Textract or vision. For narrative documents (appraisals, letters): Yes if you ONLY extract key-value pairs. Use Textract TEXT extraction (full paragraphs preserved) for narrative content, not form extraction. Then chunk and embed for RAG.

### Q: The pipeline is to get key-values from Textract and ingest into embeddings?

No — two separate paths. For standard forms: Textract key-values go DIRECTLY to Pydantic models via field mapping. No embeddings, no vector DB, no RAG. Direct structured data. For narrative documents: Textract FULL TEXT goes through RAG pipeline — chunk, embed, store in vector DB for semantic search.

### Q: Does the vector DB provide non-embedding search?

Depends on which DB. FAISS: embedding search only. OpenSearch Serverless: yes — provides embedding search AND keyword search (BM25) AND metadata filtering all in one service. This is why OpenSearch is recommended for production.

### Q: How is metadata filtering (Strategy 4) different from Smart RAG (Strategy 5)?

Strategy 4 filters the search SPACE by metadata fields (jurisdiction, loan_type). Strategy 5 uses predetermined query STRINGS for known topics. They work together: Strategy 5 USES Strategy 4 as part of its approach. Strategy 5 adds: deterministic queries, synonym expansion, and combined grading/answering on top of metadata filtering.

### Q: Re-ranking — how is encoding together better?

Separate encoding (embeddings): query and document each compressed into ONE vector independently. Comparing by distance. Loses word-level interactions. The model cannot see that "Texas" in query matches "Texas" in document. Joint encoding (cross-encoder): query AND document fed as SINGLE input. Model sees every word alongside every other word. "Texas" matches "Texas." "44%" is near "45%." Word-level interactions preserved. Same as the difference between two separate SQL SELECTs vs a JOIN.

### Q: Explain Strategy 5 with an example.

Topic "dti" identified. Deterministic query from COMPLIANCE_QUERIES lookup (no LLM). Synonym expansion adds "debt-to-income" and "borrower leverage" (no LLM). Metadata filter narrows to Texas conventional docs (no LLM). Semantic search on filtered subset returns top 3 chunks. ONE LLM call produces ComplianceAnswer with answer, relevance grading, source citations, confidence level, and hallucination self-check. Total: zero LLM calls for retrieval + one for reasoning = $0.001.

### Q: What is query rewriting and who does it?

A SEPARATE LLM call in Strategy 6. When initial retrieval returns irrelevant results, the rewriter LLM receives the original query and the failed documents. It tries different terminology — "seasoning requirements" becomes "minimum time between refinance transactions Section 50." It does NOT know your document corpus — guesses based on general knowledge. Sometimes helps, sometimes makes things worse. Your deterministic COMPLIANCE_QUERIES templates are more reliable for known topics. Rewriting is a FALLBACK for unpredictable questions.

### Q: Explain Strategy 6 again.

Same retrieval as Strategy 5. Then: 3 separate grading calls (each evaluates ONE document's relevance — no incentive to stretch). If fewer than 2 relevant: rewrite query, re-retrieve, re-grade (max 2 attempts). Generate answer from ONLY verified relevant docs (irrelevant excluded). Separate hallucination check by independent critic (different prompt, different cognitive role — author checking own work vs independent reviewer). Total 5-10 calls at $0.005-0.010. Use for compliance-critical questions where wrong answer has legal consequences.

### Q: How to deal with exact answers vs semantic answers?

Semantic search finds documents ABOUT a topic. Exact answers need a specific value from a specific document. For exact answers: metadata filter to narrow jurisdiction/topic, hybrid search (BM25 catches exact terms like "43%"), Smart RAG with confidence level (HIGH = exact answer found, LOW = only related content). If confidence LOW for compliance question, escalate — do not guess. Exact values also come from deterministic tools (calculate_dti returns EXACTLY 40.4%) — no search needed for calculated values.

---

## 9. Summary

| Concept | What It Does | When to Use |
|---------|-------------|-------------|
| Textract Forms | Extract key-value pairs from standard forms | W-2, 1040, pay stubs (typed) |
| Textract Tables | Extract table structures | Bank statements, financial reports |
| Textract Text | Extract raw text for RAG | Narrative documents for embedding |
| Textract Async | Process large docs in background | 5+ pages, batch processing |
| Document Router | Decide Textract vs Vision per document | Every document, before extraction |
| Field Mapping | Transform Textract keys to Pydantic fields | Standard forms only |
| Fallback Pattern | Textract fails → automatic Vision retry | Low confidence or validation failure |
| Hybrid cost savings | Textract for standard, Vision for unstructured | 47% savings on document processing |
| Strategy 5 Smart RAG | Deterministic queries + 1 LLM call | Primary approach, most queries |
| Strategy 6 Agentic RAG | Separate grading + verification | Critical compliance questions |
| Re-ranking | Cross-encoder scores query+doc together | Multi-concept precision queries |
| Parent-child chunks | Search small, read big | When context around match matters |
| Strategies combine | Stack multiple for maximum precision | Critical queries: all techniques |
"""

with open("week5_day4.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")