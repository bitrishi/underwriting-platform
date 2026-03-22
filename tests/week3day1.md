# Week 3 — Day 1: Agentic RAG — Self-Correcting Retrieval

**Date:** Session 11  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete (all 5 components working)

---

## Topics Covered

1. The problem with basic RAG (blind trust in retrieved docs)
2. Agentic RAG components (grader, rewriter, answer grader)
3. Combined vs. separate LLM calls (production tradeoffs)
4. Deterministic query templates vs. LLM rewriting
5. Multi-model architecture (right model for right task)
6. SmartRAG hybrid pipeline (1 call routine, 2 calls critical)

---

## What Was Built

```
SmartRAG Hybrid Pipeline
├── Query Strategy (NO LLM calls):
│   ├── Deterministic templates for known topics (COMPLIANCE_QUERIES)
│   └── Synonym expansion for unknown topics (TERM_SYNONYMS)
│
├── Combined Grading + Answer (1 LLM call):
│   └── ComplianceAnswer model does grading + answer + self-verify
│
├── Multi-Model Routing:
│   ├── Haiku for routine lookups (cheap, fast)
│   └── Sonnet for critical compliance (expensive, precise)
│
└── Optional Verification (2nd call only when needed):
    └── Separate "critic" prompt for flagged answers
```

---

## Key Architecture Decision: Combined vs. Separate LLM Calls

| Approach | LLM Calls | Cost | When to Use |
|----------|-----------|------|-------------|
| Combined (ComplianceAnswer) | 1 | ~$0.001 | Routine policy lookups |
| Combined + verification | 2 | ~$0.005 | Critical queries when self-check flags issues |
| All separate (original approach) | 8 | ~$0.016 | Not recommended — overcomplicated |

---

## Files Created

| File | Purpose |
|------|---------|
| `src/config/bedrock.py` | Multi-model registry + TASK_MODEL_MAP |
| `src/rag/query_templates.py` | Deterministic queries + synonym expansion |
| `src/models/compliance.py` | ComplianceAnswer combined model |
| `src/rag/smart_rag.py` | SmartRAG hybrid pipeline |
| `src/tools/policy_tools_v2.py` | Two tools (routine + critical) |
| `tests/test_smart_rag.py` | Full test suite |

---

## Q&A from This Session

### Q: Why separate LLM calls? Can't the same prompt do grading + answering?

**Yes, combined is usually better.** The `ComplianceAnswer` Pydantic model does grading + answer + self-verification in ONE LLM call. Separate calls exist only for critical compliance queries where self-check flags potential issues.

**When combined fails:** The LLM has a bias toward generating answers. When asked to grade AND answer simultaneously, it may stretch document relevance to produce something. A separate "critic" call with a different prompt mindset catches this.

**Production approach:** Combined for 80% of queries. Separate verification only when `all_claims_supported=false` AND `critical=True`.

### Q: Can't the human write better queries instead of LLM rewriting?

**Yes, and they should.** Deterministic query templates (`COMPLIANCE_QUERIES`) are more reliable than LLM rewriting because:
- The LLM doesn't know what's in your vector store
- LLM rewriting can make results WORSE
- Templates are testable, predictable, and free

**Production approach:**
1. Known topics → predefined query templates (best)
2. Unknown topics → synonym expansion (good, no LLM)
3. LLM rewriting → NOT USED (unreliable, reserved for future chatbot)

### Q: How does the rewriter know document terminology? It doesn't know our docs.

**It doesn't.** The rewriter guesses from general knowledge. A deterministic synonym map (`TERM_SYNONYMS`) built from YOUR actual documents is more reliable. Analyze your document corpus, extract key terms, build the map once, use forever.

### Q: The `reasoning` field in Pydantic — is it a special keyword?

**No.** It's a regular Pydantic string field. The LLM reads `Field(description="...")` and generates appropriate content. The field name is for YOUR Python code. The description is what the LLM sees.

You could call it `reasoning`, `explanation`, `banana` — the LLM reads the description, not the Python name. Same for `hallucinated_claims`, `unsupported_claims`, etc.

### Q: Why separate hallucination check? Can't it be in the first call?

**It CAN be in the first call** — that's what `all_claims_supported` and `unsupported_claims` fields do in `ComplianceAnswer`. Separate checking is only for defense-in-depth when:
1. Query is marked critical (legal/regulatory consequences)
2. Self-check already flagged issues

The separate call uses a "critic" persona (skeptical) vs. the first call's "author" persona (helpful). Like asking someone else to review your code vs. reviewing your own.

### Q: Can we use different models based on their skill set?

**Yes — this is the multi-model architecture.** Route tasks to the optimal model:

```python
TASK_MODEL_MAP = {
    "orchestrator": "haiku",       # routing — needs tool calling
    "doc_review": "sonnet",        # vision — needs strong reasoning
    "compliance": "sonnet",        # legal — worth paying more
    "retrieval_grading": "haiku",  # yes/no — cheapest works
    "default": "haiku",            # fallback
}
```

One config change swaps models for any task. When specialized legal models become available, add them to the registry and update one line.

**Cost savings:** Multi-model saves ~56% vs. Sonnet for everything.

---

## Results

- ✅ Deterministic query templates worked better than LLM rewriting
- ✅ Combined ComplianceAnswer works in one LLM call
- ✅ Multi-model routing configured (Haiku/Sonnet)
- ✅ is_trustworthy() correctly flags bad answers
- ✅ All tests passing