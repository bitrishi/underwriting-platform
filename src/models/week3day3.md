# Week 3 — Day 3: Document Review Agent — Sub-Agent #2

**Date:** Session 13  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. Document Review agent architecture (classify → extract → validate)
2. DocumentReviewPackage output model
3. Classification tool (LLM vision identifies document type)
4. Validation tool (pure Python cross-document checks)
5. Agent tool ordering via system prompt
6. What uses LLM vs. what's pure Python

---

## What Was Built

```
Document Review Agent (Sub-Agent #2)
├── Tools:
│   ├── classify_document (LLM vision — identifies doc type)
│   ├── extract_document_data (LLM vision/text — structured extraction)
│   ├── compare_documents (Python — math comparison)
│   └── validate_document_package (Python — cross-validation + missing check)
│
├── Models:
│   ├── DocumentClassification
│   ├── ExtractionResult
│   ├── CrossValidationResult
│   ├── MissingDocument
│   └── DocumentReviewPackage (complete output)
│
├── Agent: create_doc_review_agent() using Sonnet for vision
│
└── Output: DocumentReviewPackage → ready for Risk Scoring agent
```

---

## Agent Flow

```
Agent receives: "Review these docs: w2.png, paystub.png"

  🔧 classify_document("w2.png")          [LLM VISION]
  ✅ → {"document_type": "W2", "confidence": "HIGH"}

  🔧 classify_document("paystub.png")     [LLM VISION]
  ✅ → {"document_type": "PAYSTUB", "confidence": "HIGH"}

  🔧 extract_document_data("w2.png", "w2")   [LLM VISION]
  ✅ → {"wages": 120000, "employer_name": "TechCorp", ...}

  🔧 extract_document_data("paystub.png", "paystub")  [LLM VISION]
  ✅ → {"gross_pay": 5000, "employer_name": "TechCorp", ...}

  🔧 validate_document_package([...])     [PURE PYTHON — no LLM]
  ✅ → {"validations": [employer MATCH], "missing": ["1040"]}

  📋 Final: PARTIAL — 2 docs, 1 missing, employer names match
```

Agent followed correct order autonomously based on system prompt guidance.

---

## Q&A from This Session

### Q: How does the agent identify documents? Is it asking the LLM?

**Yes — Claude vision "looks" at the document.** The classify_document tool sends the first page image to Claude Sonnet. Claude recognizes document types by visual cues: headers, form numbers, layout, logos — the same way a human glances at a document and knows it's a W-2.

The LLM doesn't need to be told what a W-2 looks like. It learned from training data (millions of document images). It recognizes W-2s, 1040s, pay stubs, bank statements by visual appearance.

### Q: How does validate_document_package work? Is the LLM classifying missing docs?

**No — validation is pure Python.** No LLM involved:

```python
# Find docs by type (Python dict lookup)
w2 = next((e for e in extractions if e["type"] == "W2"), None)
tax = next((e for e in extractions if e["type"] == "1040"), None)

# Compare values (math, not LLM)
diff_pct = abs(w2_wages - agi) / w2_wages * 100

# Check missing (null check, not LLM)
if not tax:
    missing.append("1040 — needed for AGI verification")
```

### Q: What uses LLM vs. what's pure Python?

| Component | Uses LLM? | What It Does |
|-----------|-----------|-------------|
| Agent reasoning (between tools) | ✅ Yes | Decides which tool to call next |
| classify_document | ✅ Yes (vision) | Claude LOOKS at image, recognizes type |
| extract_document_data | ✅ Yes (vision/text) | Claude reads document, extracts fields |
| validate_document_package | ❌ No (Python) | Compares values, checks missing |
| compare_documents | ❌ No (Python) | Math: wages match? employer match? |
| Pydantic validation | ❌ No (Python) | Type checking, field constraints |
| Agent final response | ✅ Yes (text) | Combines results into report |

**Rule:** LLM for understanding and reasoning. Python for validation and comparison.

### Q: Using Copilot to write code — is this okay?

For this stage of learning, yes. You're learning AI/agent architecture, not Python syntax. Your questions prove deep understanding ("Why would the LLM rewriter get better? It doesn't know my docs"). The value is in architecture decisions, not typing code.

**Caveat for Week 4+:** When wiring LangGraph with multiple agents, write the graph definition yourself. When debugging production failures, trace through the code yourself before asking Copilot to fix it.

---

## Underwriting System Progress

```
  ✅ FetchData Agent (Week 2)        — tools + RAG + structured output
  ✅ Document Review Agent (Week 3)   — vision + classification + validation
  📍 Risk Scoring Agent (Week 3)      — calculations + knowledge graph
  📍 Compliance Agent (Week 4)        — regulatory verification
  📍 Orchestrator (Week 4)            — LangGraph, connects everything
```

---

## Assignments (Completed ✅)

- [x] Task 1: DocumentReviewPackage and related models
- [x] Task 2: classify_document and validate_document_package tools
- [x] Task 3: Document Review agent with Sonnet
- [x] Task 4: Agent tested — correct classify → extract → validate order ✅
- [x] Task 5: Tests for models and validation
- [x] Task 6: SKILL.md updated