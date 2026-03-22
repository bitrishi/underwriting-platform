# Week 3 — Day 2: Multi-Modal — Document Review Agent Vision

**Date:** Session 12  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete (all 5 components working)

---

## Topics Covered

1. Traditional document processing vs. multi-modal vision
2. Sending images to Claude on Bedrock (base64 encoding)
3. Structured extraction from documents (Pydantic + vision)
4. Handling PDFs (digital vs. scanned, smart routing)
5. Multi-page document processing
6. Textract vs. Vision tradeoffs and hybrid architecture

---

## What Was Built

```
Document Processing Pipeline
├── Tools:
│   ├── extract_document_data (smart routing: text vs vision)
│   └── compare_documents (cross-document validation)
│
├── Models:
│   ├── W2Extraction (W-2 form fields)
│   ├── TaxReturn1040Extraction (1040 fields)
│   └── PayStubExtraction (pay stub fields)
│
├── Smart Routing:
│   ├── Digital PDF → text extraction (Haiku, cheap)
│   ├── Scanned PDF → convert to image → vision (Sonnet)
│   └── Image file → vision directly (Sonnet)
│
└── Cross-Document Validation:
    └── Income consistency, employment match, YTD verification
```

---

## Core Pattern: Image + Text → Structured Output

```python
# Build message with BOTH image and text
message = HumanMessage(
    content=[
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64_encoded_image,
            },
        },
        {
            "type": "text",
            "text": "Extract all data from this W-2 form.",
        },
    ]
)

# Combined with structured output:
structured_llm = llm.with_structured_output(W2Extraction)
result = structured_llm.invoke([system_message, message])
# result is a validated W2Extraction Pydantic object
```

---

## Smart Routing

```python
def process_document(path: str, doc_type: str):
    if path.endswith((".png", ".jpg")):
        # Image file → vision directly
        return extract_from_image(path, doc_type)
    elif has_extractable_text(path):
        # Digital PDF → text extraction (cheap)
        return extract_from_text(path, doc_type)
    else:
        # Scanned PDF → convert to images → vision
        return extract_from_image_pdf(path, doc_type)
```

---

## Q&A from This Session

### Q: Why use vision instead of AWS Textract + LLM? Isn't it doing the same thing internally?

**No — different technology, different strengths.** 

Textract uses OCR algorithms → extracts raw text, tables, form fields. Deterministic. YOU then send text to LLM for reasoning.

Vision uses a neural network that "sees" the document holistically → extraction AND reasoning in one step. Non-deterministic.

**When Textract is BETTER:**

| Scenario | Why |
|----------|-----|
| Standard forms (W-2, 1040) | Cheaper ($0.0015 vs $0.005/page), deterministic, auditable |
| Tables and structured data | Dedicated table extraction, more reliable |
| High-volume batch processing | 3x cheaper at scale |
| 100+ page documents | No context window limit |

**When Vision is BETTER:**

| Scenario | Why |
|----------|-----|
| Handwritten documents | Textract OCR fails, Claude reads them |
| Foreign/unusual formats | Claude adapts, Textract needs standard layouts |
| Unstructured documents (letters) | Claude understands context, not just text |
| Photos, sketches, diagrams | Textract can't process non-text images |

### Q: What about 100+ page documents? Won't the LLM run out of context?

**Yes.** 100 images × 1,600 tokens = 160K tokens. Too expensive, too slow, LLM loses focus.

**Production solution for large documents:**

```
1. Textract extracts ALL text (cheap — $0.15 for 100 pages)
2. Keyword search identifies relevant sections (free — no LLM)
3. Send only relevant text to Haiku for reasoning (cheap)
4. Use vision ONLY on 2-3 pages with photos/sketches (targeted)

Cost: ~$0.17 for 100-page appraisal
vs. pure vision: $0.50 (3x more expensive)
```

### Q: What's the production architecture?

**Hybrid — Textract for standard forms, Vision for unstructured:**

```
Document arrives → Classify type (Haiku, $0.001)
  Standard form (W-2, 1040, pay stub) → Textract + Haiku ($0.002)
  Semi-structured (bank stmt, appraisal) → Textract + targeted vision ($0.17)
  Unstructured (letters, foreign docs) → Vision only ($0.005)
```

**Textract integration is planned for Week 5, Day 4.** Today we built with vision to learn the capability. The Pydantic models work with BOTH approaches — same output regardless of extraction method.

---

## Cost Summary

| Document Type | Approach | Cost/Page |
|---------------|----------|-----------|
| W-2 (standard) | Textract + Haiku | $0.002 |
| 1040 (standard) | Textract + Haiku | $0.002 |
| Pay stub | Textract + Haiku | $0.002 |
| Bank statement | Textract + Haiku | $0.003 |
| Appraisal (100 pg) | Textract + targeted vision | $0.17 total |
| Employment letter | Vision (Sonnet) | $0.005 |
| Foreign documents | Vision (Sonnet) | $0.005 |

---

## Assignments (Completed ✅)

- [x] Task 1: Document extraction Pydantic models (W2, 1040, PayStub)
- [x] Task 2: Document tools with smart routing
- [x] Task 3: Sample test documents
- [x] Task 4: Extraction tested with structured output from images ✅
- [x] Task 5: Tests for models, encoding, routing, comparison
- [x] Task 6: doc_review.txt prompt + SKILL.md updated