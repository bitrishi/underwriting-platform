# The GenAI Reference — Kuber Edition

*A working compendium of agents, retrieval, memory, and evaluation — written for the engineers who build and the leaders who must explain.*

**Compiled for the Kuber underwriting platform · April 2026**

---

## Table of Contents

1. [Anatomy of an Agent](#-01--the-anatomy-of-an-agent)
2. [RAG, All Eight Strategies](#-02--rag-all-eight-strategies)
3. [Memory & Context Management](#-03--memory--context-management)
4. [Evaluating Agents](#-04--evaluating-agents)
5. [The Bedrock Toolkit](#-05--the-bedrock-toolkit)
6. [Decisions for Kuber](#-06--decisions-for-kuber)

---

## § 01 — The Anatomy of an Agent

*A definition that holds up under pressure — and the spectrum that separates real agents from clever scripts.*

An agent is the most overused word in the GenAI vocabulary. Vendors apply it to anything that calls a model. Frameworks apply it to anything they sell. The result is a word that means everything and therefore nothing. Strip it back to mechanics, and a precise definition emerges: an agent is an LLM that **decides** what to do next, **uses tools** to take actions, **observes** the results, and **repeats** until it reaches a goal.

Every word matters. Decides means autonomy — you do not hardcode the next step. Uses tools means it can affect the world beyond text generation. Observes means it reads the result of its actions. Repeats means there is a loop, not a single call. Together, these four properties form the ReAct pattern — Reason, Act, Observe — and that pattern is the litmus test.

> **If it has a tool-calling loop, it is an agent. If it is a single LLM call or a fixed sequence of calls, it is not.**

### The Spectrum, From Function to Agent

Most production systems contain a mix. In Kuber, here is how the components grade out:

| Component | Agent? | Why |
|-----------|--------|-----|
| `calculate_dti()` | No | Pure function. No autonomy, no model. |
| Single `model.invoke()` | No | One call, one response. No loop. |
| Sequential pipeline (Week 3) | No | Fixed order. The code chooses the next step, not the model. |
| FetchData with `create_react_agent` | **Yes** | Receives a goal, picks tools, loops until satisfied. |
| RiskScoring agent | **Yes** | 8 tools, decides which to call based on intermediate results. |
| LangGraph orchestrator | *Meta-agent* | Coordinates agents but does not loop tools itself. A state machine. |

### The Four Components of Every Agent

Whatever framework you use — LangGraph, CrewAI, the bare Anthropic SDK — every agent has the same four parts:

1. **An LLM** — the reasoning engine. For Kuber, this is Claude Haiku for routine work and Claude Sonnet for complex reasoning.
2. **A tool registry** — functions the model can call. Each tool has a name, a description, and a typed schema for inputs.
3. **A loop** — the ReAct cycle. Send messages and tools to the model, receive a response, execute any tool calls, append results, repeat until the model produces a final answer or hits a stopping condition.
4. **A stopping condition** — max iterations, a confidence threshold, an explicit "done" signal, or a token budget. Without one, an agent can loop forever.

### Why Four Agents in Kuber

The four-agent underwriting pipeline is not arbitrary. Each agent boundary corresponds to a real-world failure mode that should be isolated:

- **FetchData (Haiku)** isolates external API risk — credit bureau timeouts cannot crash the rest.
- **DocReview (Sonnet)** isolates document quality issues — a bad scan does not affect risk scoring.
- **RiskScoring (Haiku)** handles graceful degradation — if the knowledge graph is down, the agent still scores using calculations and RAG.
- **Compliance (Sonnet)** is deliberately independent and has veto power — separation of concerns matching the organizational structure of the underwriting function itself.

The agent boundary is where you want failures contained. The model boundary (Haiku vs Sonnet) is where you want cost optimized. These two boundaries do not have to align, but in Kuber they do.

---

## § 02 — RAG, All Eight Strategies

*Retrieval is not one technique. It is a stack of choices, and the right choice depends on the question being asked.*

Retrieval-Augmented Generation began as a simple idea — embed your documents, find the closest matches to a query, hand them to the model. That naive version works for prototypes and fails for production. Real systems combine multiple retrieval techniques layered on top of each other. By the end of Week 3, the Kuber pipeline used eight distinct strategies, and understanding when to apply each one is the difference between a system that hallucinates and one that is auditable.

### What Lives in the Vector Database

Before strategies, mechanics. Every record in the vector store has three components stored together:

- The **embedding** — a vector of floating-point numbers (1024 dimensions for Titan Embed). Used for similarity search. Never read by the LLM directly.
- The **page_content** — the actual text chunk. This is what the model reads as context.
- The **metadata** — structured tags like jurisdiction, document source, page number, topic. Used for filtering before the search runs.

The original document still lives in S3 for regulatory and audit purposes. The vector store is the working copy.

### The Eight Strategies

**Strategy 01 — Basic RAG**
- *1 LLM call · ~$0.001 · Prototyping*
- Embed documents, embed the query, return top-k by cosine similarity, send to the model. The simplest possible RAG. Good for general conceptual questions, fails on exact-term lookup and quality.

**Strategy 02 — Hybrid Search (Vector + BM25)**
- *1 LLM call · ~$0.001 · Mixed content*
- Combine semantic search (catches "debt-to-income" when the query says "DTI") with keyword search (catches "Section 50(a)(6)" by exact match). Essential for regulatory content where concepts and exact references both matter.

**Strategy 03 — Re-Ranking**
- *1 LLM + local cross-encoder · ~$0.001 · Precision-critical*
- Retrieve top-10 with broad search, then re-rank with a cross-encoder that scores query and document together. Promotes the most relevant document from rank 4 to rank 1. The cross-encoder is a small local model — 50ms, free.

**Strategy 04 — Metadata Filtering**
- *1 LLM call · ~$0.001 · Jurisdiction lookup*
- Filter by structured metadata *before* semantic search runs. Narrow 500,000 chunks down to 3,000 Texas conventional chunks first, then embed-search the subset. 99.4% of the corpus eliminated in a database operation, free.

**Strategy 05 — Smart RAG** ⭐ *Kuber Primary*
- *1 LLM call · ~$0.001 · Production default*
- Deterministic query templates for known topics, synonym expansion, metadata filtering, and a single LLM call that grades relevance, answers, cites sources, and self-checks for hallucination — all in one structured response. Combines strategies 2, 4, and 8 into one production-ready approach.

**Strategy 06 — Agentic RAG** 🟡 *Critical Compliance*
- *5–10 LLM calls · $0.005–$0.010 · Highest confidence*
- Separate LLM calls for grading each retrieved document, optional query rewriting, generation from verified documents only, and an independent hallucination check. Slow and expensive — reserved for compliance-critical questions where a wrong answer carries legal consequences.

**Strategy 07 — Parent-Child Chunks**
- *1 LLM call · ~$0.001 · Context preservation*
- Embed small child chunks for precise matching, but return the larger parent chunk as context to the model. Solves the tradeoff between precision (small chunks find specific facts) and context (large chunks preserve meaning).

**Strategy 08 — Context-Enriched Chunks**
- *1 LLM call · ~$0.001 · Document identity*
- Each chunk's text is prefixed with "From document X, section Y." This ensures the embedding captures not just the chunk content but its provenance — useful when the same fact appears in multiple sources and you need to know which one.

### Strategies Combine — They Are Not Mutually Exclusive

The eight strategies are not a menu where you pick one. Real systems stack them. Smart RAG (Strategy 5) already includes metadata filtering (Strategy 4) and context-enriched chunks (Strategy 8). Agentic RAG (Strategy 6) builds on Smart RAG with separate verification. For maximum precision on a critical query, you stack everything:

```
Maximum-precision stack:
  Strategy 4 (metadata filter)
    + Strategy 2 (hybrid search)
    + Strategy 3 (re-ranking)
    + Strategy 7 (parent-child)
    + Strategy 6 (separate grading + verification)
  = Every technique layered. Expensive. Maximum confidence.
```

### The Decision Tree

```
Is this a KNOWN topic (DTI, FICO, LTV)?
│
├── YES — Is it compliance-CRITICAL (legal consequences)?
│   │
│   ├── YES → Strategy 6 (Agentic RAG)
│   │         Separate grading + verification
│   │         ~$0.005–$0.010, highest confidence
│   │
│   └── NO  → Strategy 5 (Smart RAG)  ← PRIMARY
│             Deterministic query + 1 LLM call
│             ~$0.001, good enough for most queries
│
└── NO  — Is it searching a LARGE document?
    │
    ├── YES — Mixes concepts and exact references?
    │   │
    │   ├── YES → Strategies 2 + 3 + 7 stacked
    │   └── NO  → Strategies 2 + 4
    │
    └── NO  → Strategy 1 (Basic RAG)
```

### What RAG Cannot Do

A note on the limits of retrieval: RAG is designed to answer specific questions about a known corpus. It is not designed for general questions. If a borrower asks "what is the housing market like in Austin," RAG over your lending policy documents will return policy text — useless. That is a question for the model alone, not for retrieval. Knowing when not to use RAG is as important as knowing how to use it.

---

## § 03 — Memory & Context Management

*Three layers of state, each with a different purpose, lifetime, and storage backend.*

LLMs are stateless. Every API call is independent. The model has no memory of yesterday's conversation, no awareness of the previous request, no persistent state. Everything the model "knows" must arrive in the current message. This single fact governs everything about agent memory: there is no memory, only the engineering you do to simulate it.

Production systems organize this engineering into three distinct layers, each solving a different problem with a different mechanism.

### Layer One: Within a Single Agent Invocation

This is the agent scratchpad — the message list that accumulates during one ReAct loop. The agent sends a prompt, gets a tool call, executes the tool, appends the result, sends the updated message list back to the model, and so on. The scratchpad lives in memory *during* the invocation and is gone the moment the invocation completes.

> **Java analogy:** Local variables in a method call. They exist on the stack while the method runs and are gone when the method returns. You do not persist method-local variables. The agent scratchpad is the same — short-lived working memory for one invocation.

For Kuber, a single agent invocation lasts 3–10 seconds and involves 5–15 tool calls. The scratchpad never exceeds context limits. No special handling required.

### Layer Two: Between Nodes in a Pipeline (Checkpointing)

This is where LangGraph's checkpointer earns its keep. After each node executes, the entire pipeline state is serialized to a persistent store. If the system crashes between nodes, the next instance loads the state from the checkpoint and resumes exactly where the previous instance stopped.

```
Node 1 (FetchData) executes  → state saved to Redis
                                (borrower_package populated)
Node 2 (DocReview) executes  → state saved to Redis
                                (document_review populated)
[CONTAINER CRASHES]
Node 3 (RiskScoring) never ran
[NEW CONTAINER STARTS]
                              → load state from Redis
                              → resume at Node 3 with prior state intact
```

#### Checkpoint Storage Options

| Backend | Persistence | Use For |
|---------|-------------|---------|
| **MemorySaver** | None (in-memory) | Local development only |
| **SqliteSaver** | File-based | Local dev with restart survival |
| **Redis** | Production-grade | **Kuber's choice.** Sub-millisecond, TTL support, already in the stack. |
| **PostgreSQL** | Production-grade | When you need to query checkpoint data for analytics |
| **DynamoDB** | Production-grade | AWS-native, fully managed, pay-per-request |

### Layer Three: Long-Term Conversation History

If your system has a chat interface where a user converses with the agent across hours or days, that conversation history needs persistent storage. This is *your* responsibility — LangGraph manages pipeline state, not chat history. For Kuber, this layer stores final loan decisions, audit trails, and human review notes in DocumentDB.

### Context Window Management

Even with all three layers, you eventually face a more fundamental problem: context windows are finite. Claude Sonnet has 200,000 tokens. If a conversation grows past that limit, something must be dropped. Four strategies:

1. **Summarization** — periodically replace older messages with an LLM-generated summary. Preserves key facts, drops verbose tool results. LangChain's `ConversationSummaryBufferMemory` automates this.
2. **Trimming** — drop the oldest messages, keep the most recent N. Cheap (no LLM call), lossy (you may lose important early context).
3. **Selective retention** — keep system prompt, keep tool results, drop intermediate reasoning. More sophisticated, preserves the most useful context per token.
4. **External fact storage** — extract facts from conversations and store them as structured data outside the conversation. The conversation gets compressed; the facts persist forever. This is how Claude.ai's memory feature works.

For Kuber's pipeline, none of this applies. Each loan evaluation is a self-contained graph execution with maybe 10,000 tokens total. Compression only matters for long-running chat sessions.

### The Critical Distinction

> **Facts persist indefinitely. Conversation history gets compressed or dropped.**

Production memory systems separate *what the user is* (facts: name, role, preferences, project context) from *what was said* (conversation: the literal back-and-forth). Facts are stored in a structured database and retrieved on every conversation. Conversation history gets summarized when it grows too long. This separation is the difference between an assistant that "remembers" you and a chatbot that forgets everything between sessions.

---

## § 04 — Evaluating Agents

*How to prove that an AI system actually works — and to whom you have to prove it.*

An agent that works in development is not the same as an agent that works in production. The gap between "the demo passes" and "we can defend this to the risk committee" is filled with evaluation. Without it, you are shipping a search engine with a language model bolted on and hoping for the best. With it, you can quantify quality, catch regressions, and produce evidence — the kind a regulator can read.

### The Two Categories of Evaluation

**Offline Evaluation** — Run a fixed dataset of test cases (ideally 500+) through the system. Compare outputs to known-good answers verified by humans. Track scores over time. This is how you prove the system works before deployment and after every prompt change.

**Online Evaluation** — Sample production traffic, score it asynchronously, push the scores back to your observability platform. This is how you detect quality degradation in production before users notice — prompt drift, model version changes, retrieval regression.

### The Four Core RAG Metrics

For any RAG-based system, four metrics matter. Two evaluate retrieval quality, two evaluate generation quality. Together they form the standard developed by the Ragas framework and adopted across the industry.

| Metric | Layer | Question | Diagnoses |
|--------|-------|----------|-----------|
| **Faithfulness** | Generation | Is the answer grounded in retrieved context? | Hallucination, fabricated facts |
| **Answer Relevancy** | Generation | Does the answer address the question asked? | Off-topic, wrong tool selected |
| **Context Precision** | Retrieval | Are the retrieved docs actually relevant? | Bad metadata, embedding drift |
| **Context Recall** | Retrieval | Did we retrieve *all* relevant info? | Top-k too low, bad chunking |

### Faithfulness — A Worked Example

Faithfulness is the most important metric for compliance work. It measures hallucination directly. Here is how it works:

**Question:** What is the maximum DTI for a Texas conventional QM?

**Retrieved context:** "For Texas conventional qualified mortgages, the maximum DTI ratio is 43%. Compensating factors may be considered for DTIs between 38% and 43%."

**Generated answer:** "The maximum DTI is 43%, with compensating factors above 38%. The borrower must also have a minimum FICO of 680."

**Claims extracted from the answer:**
- Maximum DTI is 43% — supported by context ✓
- Compensating factors above 38% — supported ✓
- Minimum FICO of 680 — **NOT in context — fabricated** ✗

**Faithfulness = 2 supported / 3 total = 0.67**

For compliance work, anything below 0.95 is unacceptable. A single fabricated claim could expose the company to regulatory risk.

### The Tooling Landscape

Five tools matter, each with a different role:

| Tool | What It Does | When to Use |
|------|-------------|-------------|
| **Ragas** | Open-source RAG-specific metrics (the four above plus 20 more) | Development analysis, exploratory evaluation, synthetic test generation |
| **DeepEval** | Pytest-style LLM testing for CI/CD pipelines | Quality gates before merge — every PR must pass |
| **LangSmith** | Tracing + evaluation datasets + trajectory checks | Development debugging, dataset management |
| **Bedrock Evaluations** | Three levels: Model Eval, Knowledge Base Eval, AgentCore Eval | **Production** — stays in AWS VPC, no data exfiltration |
| **Manual / human** | The gold standard, slow and expensive | Final validation before shipping, edge cases, risk committee sign-off |

### Trajectory Evaluation — The Underrated Metric

For agents specifically, output correctness is not enough. You also need to verify *how* the agent got there. A trajectory evaluator checks whether the agent called the right tools in the right order. Example rule for the Risk Scoring agent:

```python
# Trajectory check
required_tools = [
    "pull_borrower_data",
    "calculate_dti",
    "search_lending_policies"
]
missing = [t for t in required_tools if t not in actual_tool_calls]
score = 1.0 if not missing else 0.0
```

This catches the scenario where the agent produces a reasonable-looking answer but skipped a critical step. Output checks alone would miss it. Trajectory checks catch it every time.

### The Kuber Evaluation Stack

The right combination depends on the phase:

- **DEVELOPMENT — LangSmith + Ragas.** LangSmith Cloud free tier for tracing and dataset management. Ragas for deeper RAG-specific metrics and synthetic test data generation. Iterate fast, debug aggressively.
- **CI/CD — DeepEval Quality Gates.** Every pull request that touches a prompt or agent must pass a pytest suite of evaluation tests. Faithfulness threshold 0.95. Trajectory checks for each agent. No merge without green builds.
- **PRODUCTION — Bedrock Evaluations + Langfuse.** Bedrock AgentCore Evaluations with code-based Lambda evaluators for deterministic compliance checks. Langfuse self-hosted in the company's VPC for tracing. Sample 5–10% of production traffic for quality monitoring.

---

## § 05 — The Bedrock Toolkit

*What AWS provides natively, and why you might still need everything else.*

Most of the GenAI ecosystem treats AWS Bedrock as a simple model-hosting service — a way to call Claude or Llama without managing your own infrastructure. That undersells it. Bedrock is a layered platform: inference, evaluation, safety, customization, and agent orchestration are all native services. Knowing what Bedrock provides is the difference between buying tools you do not need and reinventing tools you already have.

### The Five Pillars of Bedrock

| Service | What It Does | Kuber Use |
|---------|-------------|-------------|
| **Bedrock Runtime** | Inference API — invoke models, including streaming and tool use. Unified API across providers via Converse. | Every Claude call in the pipeline |
| **Bedrock Knowledge Bases** | Managed RAG — connect S3 documents, auto-chunk and embed, query via API. | Optional alternative to OpenSearch RAG. Limited control. |
| **Bedrock Guardrails** | Content filtering, PII redaction, denied topics, prompt injection detection. | Wraps every agent call. the company compliance requirement. |
| **Bedrock Evaluations** | Model Eval, Knowledge Base Eval, AgentCore Eval — three levels of quality measurement. | Production evaluation. Stays in VPC. |
| **Bedrock AgentCore** | Managed agent runtime with memory, identity, gateway, browser tools, observability. | Alternative to LangGraph for managed orchestration. |

### What Bedrock Does Not Do (Well)

Bedrock is strong but not universal. Three notable gaps:

- **Claude fine-tuning is not available.** Bedrock supports fine-tuning for Titan, Llama, Cohere, and Nova models. Claude is excluded. If you need to customize a Claude model, you cannot — your only options are prompt engineering, distillation to a fine-tunable model, or working with Anthropic directly.
- **Knowledge Bases are opaque.** Bedrock's managed RAG locks you into specific chunking strategies and vector stores. Teams often start with Knowledge Bases, hit a wall, and rebuild on OpenSearch or Pinecone for control over retrieval logic.
- **No semantic caching.** Bedrock has no built-in semantic cache. If 100 users ask the same question, you pay for 100 inferences. You can build your own cache layer (Redis + embedding similarity) but it is not provided.

### Three Bedrock Features Worth Knowing

**Prompt Caching** — Bedrock can cache the KV (key-value) computations from processing your prompt prefix. The first call computes everything. Subsequent calls with the same prefix skip the computation and load the cached result, billing those tokens at a 90% discount. For Kuber's compliance agent processing batches of similar loans, this saves 84% on input costs. The cache is invoked via a `cache_control` marker on the system prompt and policy context.

**Extended Thinking** — Claude Sonnet 3.7 and newer support extended thinking — a private scratchpad where the model reasons through a problem before producing the final answer. Thinking tokens are billed as output tokens. For complex multi-step reasoning (like checking whether a loan violates three different Texas regulations simultaneously), extended thinking catches nuances the standard mode misses. Use it on the Compliance agent. Skip it on FetchData.

**AgentCore Evaluations with Lambda Graders** — The newest and most relevant Bedrock feature for Kuber. AgentCore Evaluations launched GA in March 2026 with thirteen built-in evaluators plus support for custom Lambda-based graders. The Lambda graders are critical because they are deterministic — an LLM-as-judge cannot reliably verify "did the response include the exact DTI value of 40.4 percent," but a Python function in Lambda can. For compliance checks, deterministic evaluation is non-negotiable.

### The Bedrock Cost Map

Cost varies by 100× across Bedrock models. The single largest optimization is choosing the right model per task:

| Model | Input ($/1M tok) | Output ($/1M tok) | Use For |
|-------|------------------|-------------------|---------|
| Nova Micro | $0.035 | $0.14 | Simple classification, routing |
| Claude Haiku | $1.00 | $5.00 | FetchData, RiskScoring (Kuber) |
| Claude Sonnet | $3.00 | $15.00 | DocReview, Compliance (Kuber) |
| Claude Opus | $15.00 | $75.00 | Most complex reasoning, rarely needed |

Routing simple tasks to Nova Micro instead of Claude Sonnet is an 85× cost reduction with no quality loss for the right tasks. Most teams overspend by defaulting to premium models for work that smaller models handle perfectly.

---

## § 06 — Decisions for Kuber

*A consolidated record of every architectural choice made over six weeks — and the reasoning behind it.*

Six weeks of construction produced a system. They also produced dozens of architectural decisions, each with tradeoffs, each defended at the time, each worth recording for the next engineer who has to explain them. This is that record.

### Orchestration

| Decision | Choice | Why |
|----------|--------|-----|
| Framework | LangGraph | Typed state, parallel execution, checkpointing, human-in-the-loop. CrewAI is simpler but less control. AutoGen is for research, not pipelines. |
| Execution model | Single ECS Fargate service | Persistent Redis connections, no Lambda cold starts, 15-min timeout limit avoided. |
| Checkpointing | Redis | Already in the stack. Sub-millisecond. Right access pattern (key-value with TTL). |

### Models

| Agent | Model | Why |
|-------|-------|-----|
| FetchData | Claude Haiku | Simple structured extraction. Cost optimized. |
| DocReview | Claude Sonnet | Complex document understanding. Vision capability needed. |
| RiskScoring | Claude Haiku | Calculation-heavy with deterministic rules. Haiku sufficient. |
| Compliance | Claude Sonnet + Extended Thinking | Regulatory reasoning has legal consequences. Frontier model justified. |

### Retrieval

| Component | Choice | Why |
|-----------|--------|-----|
| Vector store | OpenSearch (production), FAISS (dev) | OpenSearch supports hybrid search natively. FAISS is fine for local iteration. |
| Embedding model | Titan Embed v2 (1024-dim) | Native to Bedrock, no extra service. |
| Primary RAG strategy | Smart RAG (Strategy 5) | One LLM call. Combines metadata filtering, hybrid search, structured output, self-check. |
| Critical compliance RAG | Agentic RAG (Strategy 6) | Separate grading and verification. Higher cost justified by legal risk. |

### Production Hardening

| Concern | Solution |
|---------|----------|
| Content safety | Bedrock Guardrails on every agent call |
| Document processing cost | Textract hybrid — standard forms via Textract, narrative via Vision. 47% cost reduction. |
| External API resilience | Retry with exponential backoff + circuit breaker per service |
| Crash recovery | LangGraph checkpointing to Redis after every node |
| Cost optimization | Prompt caching on system prompt and policy context. 84% input savings. |

### Deployment

| Component | Choice |
|-----------|--------|
| API layer | FastAPI with async submit/poll pattern (HTTP 202) |
| UI | Streamlit for internal underwriter dashboard |
| Container runtime | ECS Fargate (separate services for FastAPI and Streamlit) |
| Auto-scaling | 2–8 tasks based on CPU (60% scale up, 30% scale down) |
| Observability | LangSmith Cloud (dev), Langfuse self-hosted (production) |

### The Things That Did Not Make the Cut

Equally important: what was considered and rejected.

- **Fine-tuning Claude.** Not supported on Bedrock. Even if it were, the cost of training data preparation and ongoing retraining would exceed the inference savings at Kuber's volume.
- **LangServe.** Auto-generated FastAPI from LangGraph code. Fast for prototyping, too opaque for a the company API contract that the Java team needs to consume.
- **Bedrock Knowledge Bases.** Managed RAG that locks you into specific chunking and retrieval. Custom OpenSearch + Smart RAG gives more control.
- **Bedrock AgentCore.** Promising but newer than LangGraph. Revisit in 12 months.
- **React for the UI.** Overkill for an internal dashboard built by a Python + Java team. Streamlit is sufficient. Rebuild later if the UI ever goes external-facing.

### What Remains to Be Done

The system is architecturally complete. The remaining work is organizational, not technical — coordinating with the company's AI platform team for ECS Fargate deployment, IAM roles, Secrets Manager integration, CloudWatch alerting, and the production readiness checklist. The hard part — turning a six-week learning sprint into a defensible production architecture — is done.

> **The model is commodity. The orchestration, evaluation, and integration are where the value lives.**

---

*Compiled in April 2026 from six weeks of construction, conversation, and revision. For internal the company reference. Kuber underwriting platform.*