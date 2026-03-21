# Week 2 — Weekend BUILD: FetchData Sub-Agent

**Date:** Weekend Session  
**Duration:** 2 hours hands-on  
**Status:** ✅ Complete (all 5 components working)

---

## What Was Built

The FetchData sub-agent — first production sub-agent for the underwriting system.

```
FetchData Sub-Agent
├── Tools:
│   ├── pull_borrower_data(app_id) → borrower profile
│   ├── pull_credit_report(ssn) → FICO, delinquencies
│   ├── pull_employment_history(ssn) → employer, tenure
│   └── search_lending_policies(query, jurisdiction) → RAG
│
├── Capabilities:
│   ├── Autonomous tool selection
│   ├── RAG-powered policy lookup (hybrid search)
│   ├── Structured output (BorrowerPackage)
│   ├── Callback tracing (audit trail)
│   └── Error handling
│
└── Output: BorrowerPackage → ready for Risk Scoring agent
```

---

## Files Created

| File | Purpose |
|------|---------|
| `src/models/borrower.py` | BorrowerProfile, CreditReport, EmploymentRecord, PolicyContext, BorrowerPackage |
| `src/tools/fetch_tools.py` | pull_borrower_data, pull_credit_report, pull_employment_history |
| `src/agents/fetch_data.py` | create_fetch_data_agent() with AgentExecutor |
| `src/prompts/fetch_data.txt` | System prompt with process steps and rules |
| `tests/test_fetch_agent.py` | Integration tests |

---

## Agent Behavior (Observed)

```
Agent receives: "Gather data for APP-001"

  🔧 Calling: pull_borrower_data("APP-001")
  ✅ Result: {name: "Alice Strong", ssn_last_four: "1234", ...}

  🔧 Calling: pull_credit_report("1234")     ← used SSN from step 1
  ✅ Result: {fico: 740, tier: "EXCELLENT", ...}

  🔧 Calling: pull_employment_history("1234")
  ✅ Result: {employer: "TechCorp", years: 5, ...}

  🔧 Calling: search_lending_policies("Texas lending requirements",
              jurisdiction="state_texas")      ← used state from step 1
  ✅ Result: [Texas Section 50(a)(6)..., TRID requirements...]

  📋 Final: Complete BorrowerPackage assembled
```

Agent autonomously decided order and used data from previous tool calls to inform subsequent ones.

---

## Q&A from This Session

### Q: How do the placeholders in ChatPromptTemplate get populated?

```python
prompt = ChatPromptTemplate.from_messages([
    ("system", load_prompt("fetch_data")),    # filled at creation time
    ("human", "{input}"),                      # filled from invoke() dict
    ("placeholder", "{agent_scratchpad}"),      # filled by AgentExecutor
])
```

| Placeholder | Filled By | When |
|-------------|-----------|------|
| `load_prompt(...)` | Your Python code (reads .txt) | At chain creation (once) |
| `{input}` | Your `invoke({"input": "..."})` call | At invocation (once per request) |
| `{agent_scratchpad}` | AgentExecutor (AUTOMATICALLY) | Every ReAct iteration (grows) |

**`{agent_scratchpad}` detail:**

You NEVER fill this. LangChain manages it. After each tool call, the AgentExecutor appends:
- `AIMessage(tool_calls=[{name, args, id}])` — the LLM's tool request
- `ToolMessage(content="result", tool_call_id="...")` — the tool's response

Each ReAct iteration, the full scratchpad (all previous tool calls + results) is re-sent to the LLM. This is how the stateless LLM "sees" what it already fetched.

**Why `"placeholder"` not `"human"`:**

The scratchpad is a LIST of messages (alternating AI + Tool messages), not a single message. `"placeholder"` tells LangChain to insert multiple messages. `"human"` would try to cram everything into one string, breaking the tool call protocol.

### Q: How does the cross-encoder re-ranker actually work? It seems like the same thing as embeddings?

**Fundamentally different.** The key is TOGETHER vs. APART.

**Bi-encoder (embeddings):** Encodes query ALONE → vector. Encodes document ALONE → vector. Compares vectors with math (cosine). The model NEVER sees both texts simultaneously.

**Cross-encoder (re-ranker):** Takes [query + document] as ONE input. The model sees both simultaneously with cross-attention — every word in the query interacts with every word in the document.

**Why this matters — concrete example:**

```
Query: "Can I prepay a Texas home equity loan?"

Document A: "Prepayment penalties are common in conventional mortgages"
Document B: "Texas Section 50(a)(6) prohibits prepayment penalties on home equity loans"
```

**Bi-encoder result:** Doc A wins (0.12 distance). "Prepayment" dominates both query and Doc A embeddings. Doc B's embedding is spread across Texas + legal + prepayment + home equity.

**Cross-encoder result:** Doc B wins (0.97 score). The model sees "Texas" ↔ "Texas", "prepay" ↔ "prepayment penalties", "home equity loan" ↔ "home equity loans", "Can I" ↔ "prohibits" (question ↔ answer relationship).

**The cross-encoder performs word-level interactions (cross-attention).** The bi-encoder compresses everything into one vector per text and compares vectors — no word-level interaction possible.

**Why not use cross-encoder for everything?**
- Bi-encoder: 500,000 docs in ~15ms (vector math)
- Cross-encoder: 500,000 docs = 500,000 model calls = 41 MINUTES
- Solution: bi-encoder gets top 10 fast → cross-encoder re-ranks 10 precisely

---

## Week 2 Complete Summary

| Day | Topic | Key Deliverable |
|-----|-------|----------------|
| Day 1 | LangChain deep dive | LCEL chains, RunnableParallel, RunnableBranch |
| Day 2 | Tools & function calling | Autonomous agent with tools + callback tracer |
| Day 3 | Embeddings & vector DB | FAISS vector store with semantic search |
| Day 4 | RAG pipeline | Retrieve → Augment → Generate with citations |
| Day 5 | Advanced RAG | Hybrid search, re-ranking, enriched chunks |
| Weekend | BUILD | FetchData sub-agent (tools + RAG + structured output) |

### Skills Acquired in Week 2
- LangChain LCEL pipe syntax for composing chains
- Tool/function calling with @tool decorator
- Understanding of API-level tool_use protocol
- Embedding models and vector databases (FAISS)
- RAG pipeline with source citations
- Advanced retrieval (hybrid BM25 + vector, re-ranking)
- Section-aware chunking and context enrichment
- Callback handlers for observability
- Production sub-agent with autonomous tool selection

### Next: Week 3 — Agentic RAG + Multi-Modal + Knowledge Graphs