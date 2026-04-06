# Week 6, Day 3: Fine-Tuning on Bedrock — When It Makes Sense, Prompt Caching & Extended Thinking

**Date:** April 5, 2026  
**Module:** Model Customization  
**Platform:** Kuber Loan Origination System  

---

## 1. Session Overview

**Topic:** Fine-tuning on Bedrock — the three customization approaches (fine-tuning, reinforcement fine-tuning, distillation), the critical reality that Claude models do NOT support fine-tuning on Bedrock, prompt caching as a cost optimization alternative, extended thinking for reasoning quality, and the honest decision framework for whether Kuber needs fine-tuning at all.

**Prerequisites:** Week 6 Days 1–2 complete (LangSmith tracing, Ragas evaluation). Four-agent pipeline with Ragas quality scores established.

**Key Deliverable:** A justified decision on Kuber's customization strategy — prompt engineering + RAG + prompt caching is the right answer for now.

---

## 2. Three Ways to Customize Model Behavior on Bedrock

### 2.1 Level 1: Prompt Engineering + RAG (Current Approach)

Craft system prompts, provide context through RAG, use structured output. Zero training cost. Instant iteration. This is what your four agents currently use — carefully designed prompts with tool definitions, Smart RAG for compliance lookups, and Pydantic-typed outputs.

### 2.2 Level 2: Fine-Tuning (Supervised)

Provide labeled training data (input/output JSONL pairs) and Bedrock trains a custom version of a base model. The model's weights are modified to specialize on your task.

- **Supported models:** Amazon Titan, Meta Llama (3.2, 3.1, 3), Cohere Command
- **NOT supported:** Claude (Haiku, Sonnet, Opus)
- **Cost:** Per token processed during training (tokens × epochs) + monthly storage ($0.02–$0.10/GB). Inference requires Provisioned Throughput (committed capacity, not on-demand).

### 2.3 Level 3: Reinforcement Fine-Tuning (RFT) — GA December 2025

Instead of labeled data, you provide a reward function (a Lambda that scores outputs). Bedrock generates responses, your Lambda grades them, and the model learns from feedback. AWS reports 66% accuracy gains on average over base models.

- **Supported:** Amazon Nova, open-weight models (GPT OSS 20B, Qwen 3 32B as of February 2026)
- **NOT supported:** Claude

### 2.4 Distillation

Use an expensive teacher model (Claude Sonnet) to generate high-quality responses for your prompts. Then fine-tune a cheaper student model (Nova Micro, Llama) to replicate that behavior. Available on Bedrock. This is the most relevant customization technique for Kuber.

### 2.5 Continued Pre-Training

Feed the model raw, unlabeled domain text (lending regulations, the company policies, underwriting manuals). The model absorbs domain knowledge without learning specific input/output patterns.

---

## 3. The Claude Fine-Tuning Reality

**Critical fact:** Claude models (Haiku, Sonnet, Opus) do NOT support fine-tuning or continued pre-training on Bedrock as of April 2026.

Anthropic offers fine-tuning through their own API for select enterprise partners, but it's not available through the standard Bedrock workflow.

**What this means for Kuber:** Your pipeline uses Claude (Haiku for FetchData/RiskScoring, Sonnet for DocReview/Compliance). Your customization options are:

1. **Prompt engineering + RAG** (what you're already doing — and it's working)
2. **Distillation** — use Claude Sonnet as "teacher" to train a cheaper "student" model
3. **Switch specific agents** to fine-tunable models (Llama, Nova) for simple tasks

---

## 4. When Fine-Tuning Makes Sense vs When It Does Not

### Fine-tuning DOES make sense when:

1. The model consistently fails despite good prompts — you've optimized prompts, added few-shot examples, tried different models, and it's still not performing
2. You have hundreds or thousands of labeled examples of correct behavior
3. The task requires specialized formatting or terminology the base model struggles with
4. Latency matters and you need to reduce prompt length — fine-tuned models internalize instructions
5. Cost at scale justifies the investment — 10,000+ evaluations daily

### Fine-tuning does NOT make sense when:

1. Prompt engineering + RAG already works well — Ragas scores above 0.95 faithfulness
2. Your data changes frequently — lending regulations update quarterly, fine-tuned models freeze knowledge at training time
3. You need auditability — RAG points to exact source documents, fine-tuning bakes knowledge into opaque weights
4. You have a small team — fine-tuning requires data preparation, training management, evaluation, versioning, and retraining
5. You're using Claude on Bedrock — it's not supported for fine-tuning

---

## 5. Prompt Caching — The Cost Optimization Alternative

### 5.1 How Prompt Caching Actually Works

LLMs are stateless — every call is independent. The model doesn't "remember" previous calls. So how can caching work?

**It doesn't cache the prompt itself. It caches the COMPUTATION that the prompt produces.**

When an LLM processes your prompt, the expensive step is the **KV (Key-Value) computation** — processing every token through 70+ transformer layers to produce Key and Value vectors at each layer. For a 7,000-token prompt, this means computing ~70 layers × 7,000 tokens of KV pairs. This is the majority of cost and latency.

What prompt caching does: After the KV computation, Bedrock saves the KV cache on their servers, tagged with a hash of your prompt prefix. Next time you send a prompt with the same prefix, Bedrock loads the pre-computed KV pairs from storage instead of recomputing them.

**Java analogy:** Like a PreparedStatement in JDBC. The database doesn't re-parse and re-plan the SQL every time — it reuses the compiled plan and only binds new parameters. Here, the "compiled plan" is the KV cache, and the "new parameters" are your borrower data.

```
FIRST CALL (cache miss):
  System prompt (2,000 tokens)  → Compute KV pairs (expensive)
  Policy context (5,000 tokens) → Compute KV pairs (expensive)
  Borrower data (500 tokens)    → Compute KV pairs (small)
  Result: KV cache for first 7,000 tokens saved to disk.

SECOND CALL (cache hit):
  System prompt (2,000 tokens)  → LOAD from cache (skip compute!)
  Policy context (5,000 tokens) → LOAD from cache (skip compute!)
  Borrower data (500 tokens)    → Compute KV pairs (small)
  Result: 90% discount on the cached 7,000 tokens.
```

Bedrock doesn't "replace" the system prompt — it **skips the computation** that the system prompt would require. The system prompt text logically still exists in the conversation, but instead of re-processing those tokens through 70+ transformer layers, Bedrock loads the pre-computed KV pairs from storage and injects them directly. The model still "sees" the full context. The output is identical.

### Constraints

- Cached content must be a **prefix** — everything from the start must be identical. Changing one token in the middle invalidates the cache from that point onward.
- Minimum cache size: typically 1,024–2,048 tokens depending on model.
- Cache lifetime: ephemeral, typically 5 minutes. Process batches of similar loans to maximize hits.

### 5.2 Configuring Prompt Caching in LangChain

LangChain with `ChatBedrockConverse` handles caching through message metadata:

```python
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage, HumanMessage

model = ChatBedrockConverse(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    region_name="us-east-1",
    temperature=0
)

# System prompt — mark for caching
system_msg = SystemMessage(
    content="You are an underwriting compliance analyst...[2000 tokens]",
    additional_kwargs={
        "cache_control": {"type": "ephemeral"}  # Tells Bedrock to cache
    }
)

# Policy context — also mark for caching
policy_msg = HumanMessage(content=[
    {
        "type": "text",
        "text": "[5000 tokens of Texas lending policies from RAG]",
        "cache_control": {"type": "ephemeral"}  # Cache this too
    },
    {
        "type": "text",
        "text": "Evaluate borrower APP-001: FICO 710, DTI 41%..."
        # NO cache_control — this changes per evaluation
    }
])

response = model.invoke([system_msg, policy_msg])
```

**How Bedrock knows what's cached vs not:** Content WITH `cache_control` is the cacheable prefix. Content AFTER the last `cache_control` marker is always computed fresh. Bedrock hashes the prefix, checks for a cache hit, and either loads KV pairs from storage or computes them fresh.

**Verifying cache usage:**

```python
print(response.usage_metadata)
# cache_creation_input_tokens: 7000  (first call: wrote to cache)
# cache_read_input_tokens: 7000     (subsequent calls: read from cache)
```

### 5.3 Cost Impact

For Claude Sonnet on Bedrock:
- Regular input tokens: $0.003 per 1K tokens
- Cached input tokens (cache hit): $0.0003 per 1K tokens — **90% cheaper**
- Cache write (first time): $0.00375 per 1K tokens — slightly more expensive

**Without caching:** 1,000 evaluations × 7,500 input tokens = **$22.50/day**

**With caching:** 1 cache write + 1,000 cache reads + 1,000 uncached portions = **$3.63/day — 84% savings**

**Batch optimization:** Group loans by jurisdiction + loan type. Texas conventional loans share the same policy context → cache hit rate maximized within each batch.

---

## 6. Extended Thinking — Reasoning Quality Without Fine-Tuning

Extended thinking gives Claude a **private scratchpad** to reason through complex problems before producing the final answer. The thinking content is generated but separate from the answer.

### Without Extended Thinking

Claude reads the prompt and immediately generates the response. For complex multi-step regulatory reasoning, it may miss steps or make logical errors because it's generating the answer as it reasons.

### With Extended Thinking

Claude first generates a thinking block — working through the problem step by step, considering multiple angles, checking its own logic, backtracking if needed. Then it produces the final answer based on that reasoning.

For the Compliance agent evaluating a Texas home equity loan with FICO 680 and DTI 41%, extended thinking caught: DTI above 38% threshold requiring compensating factors (none adequate), three Section 50(a)(6) requirements needing verification, and compounding oil & gas industry cyclical risk. The non-thinking version missed most of these nuances.

### Enabling in LangChain/Bedrock

```python
model = ChatBedrockConverse(
    model_id="anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-east-1",
    additional_model_request_fields={
        "thinking": {
            "type": "enabled",
            "budget_tokens": 5000  # Max tokens for thinking
        }
    }
)
```

**Cost implication:** Thinking tokens are billed as output tokens. A 3,000-token thinking block + 500-token answer = 3,500 output tokens. More expensive per call but higher-quality reasoning.

**Where to use in Kuber:** Compliance agent (complex regulatory reasoning) and RiskScoring agent (multi-factor assessment). Overkill for FetchData (simple extraction).

---

## 7. The Prompt Engineering Hierarchy (Before Fine-Tuning)

Before considering fine-tuning, exhaust these cheaper approaches in order:

1. **Better system prompts** — clearer instructions, output format requirements
2. **Few-shot examples** — 2–3 examples of correct behavior in the prompt
3. **Chain-of-thought** — ask the model to reason step by step
4. **Extended thinking** — private scratchpad for complex reasoning (Claude Sonnet 3.7+)
5. **Structured output** — Pydantic models for typed responses
6. **RAG with better retrieval** — better chunking, metadata filtering, re-ranking
7. **Prompt caching** — 90% cost reduction on repeated context
8. **Model routing** — Haiku for simple tasks, Sonnet for complex
9. **Distillation** — teach a cheap model to replicate an expensive one
10. **Fine-tuning** — only when steps 1–8 are exhausted and data supports it

Steps 1–8 require zero training, zero labeled data, and can be iterated in minutes. Steps 9–10 require weeks of effort and ongoing maintenance.

---

## 8. Decision Matrix for Kuber Agents

| Agent | Current Model | Fine-Tune? | Recommendation |
|-------|--------------|-----------|----------------|
| **FetchData** | Claude Haiku | Distillation candidate | If volume justifies it, distill to Nova Micro. 50–100x cheaper per token for simple extraction. |
| **DocReview** | Claude Sonnet | Not recommended | Complex document understanding. Keep Sonnet. Prompt engineering + Textract hybrid sufficient. |
| **RiskScoring** | Claude Haiku | Possible RFT | If accuracy needs improvement, try prompt optimization and extended thinking first. RFT with Llama/Nova as fallback. |
| **Compliance** | Claude Sonnet | Not recommended | Regulatory reasoning requires frontier model quality. Cost of wrong compliance decision vastly exceeds inference savings. Keep Sonnet + extended thinking. |

---

## 9. Fine-Tuning Mechanics (For Reference)

### 9.1 Dataset Format (JSONL)

```jsonl
{"prompt": "Evaluate DTI risk for borrower with income $8,333 and debt $3,416", "completion": "DTI is 41.0%. Borderline — below 43% QM limit but above 38% threshold..."}
{"prompt": "Does LTV 84% comply with Texas Section 50(a)(6)?", "completion": "NON-COMPLIANT. Texas 50(a)(6) limits LTV to 80%..."}
```

### 9.2 Key Parameters

- **epochCount (2–5):** Number of passes through training data. More = more learning but risk overfitting.
- **batchSize (4–16):** Examples processed together. Depends on model size.
- **learningRate (0.00001):** Start low to avoid destroying base model capabilities.
- **Training data size:** Minimum ~100 examples. Sweet spot 500–2,000.

### 9.3 Cost Structure

- **Training:** Charged per token processed (tokens in data × epochs)
- **Storage:** $0.02–$0.10 per GB/month for custom model weights
- **Inference:** Requires Provisioned Throughput — committed capacity, NOT on-demand pricing. Significant operational cost.

---

## 10. Questions & Answers

### Q: How does prompt caching help with cost? Isn't the LLM stateless?

Yes, LLMs are stateless — every call is independent. Prompt caching doesn't cache the prompt text itself. It caches the KV (Key-Value) computation — the expensive step where every token is processed through 70+ transformer layers. For a 7,000-token prompt, this KV computation is the majority of cost and latency. Bedrock saves the computed KV pairs on disk, tagged with a hash of your prompt prefix. Next call with the same prefix loads the KV pairs from storage instead of recomputing them. The model still "sees" the full context (the KV pairs contain everything), but the redundant computation is skipped. Cached tokens are billed at 90% discount. Java analogy: PreparedStatement in JDBC — the database reuses the compiled query plan and only binds new parameters.

### Q: How does Bedrock know what is cached vs not? LangChain just keeps adding messages.

The `cache_control: {"type": "ephemeral"}` marker in message metadata is the signal. In LangChain, you add this to the `additional_kwargs` of your SystemMessage or as part of the content blocks in HumanMessage. Bedrock hashes everything from the start up to and including the last `cache_control` marker — that's the cache key. Content AFTER the last marker is always computed fresh. On cache hit, Bedrock loads the pre-computed KV pairs for the cached prefix and only computes KV for the new (uncached) content. The response includes cache metrics (`cache_creation_input_tokens` and `cache_read_input_tokens`) so you can verify caching is working.

### Q: So basically Bedrock replaces the system prompt with KV values to prevent the LLM computation cycle?

Exactly. Bedrock doesn't "replace" the system prompt — it skips the computation that the system prompt would require. The system prompt text logically still exists in the conversation, but instead of the model re-processing those 7,000 tokens through 70+ transformer layers (the expensive KV computation), Bedrock loads the pre-computed KV pairs from storage and injects them directly. The model still "sees" the full context. The output is identical to processing the text from scratch. You're just skipping the redundant computation.

### Q: What extra does extended thinking do when selected?

Extended thinking gives Claude a private scratchpad to reason through complex problems before producing the final answer. Without it, Claude immediately starts generating the response — for complex multi-step reasoning, it may miss steps or make logical errors. With extended thinking, Claude first generates a thinking block (thousands of tokens of internal deliberation — working through the problem step by step, considering multiple angles, checking its own logic, backtracking if needed), then produces the final answer based on that reasoning. You pay for thinking tokens as output tokens. For Kuber, use it on the Compliance agent (complex regulatory reasoning) and RiskScoring agent (multi-factor assessment). Overkill for FetchData. Extended thinking is another reason NOT to fine-tune — try thinking mode before spending weeks on training data.

### Q: Can I fine-tune Claude on Bedrock?

No. Claude models (Haiku, Sonnet, Opus) do not support fine-tuning on Bedrock as of April 2026. Bedrock fine-tuning is available for Amazon Titan, Meta Llama, Cohere Command, and Amazon Nova models. Anthropic offers fine-tuning through their own API for select enterprise partners, but not through the standard Bedrock workflow. Your customization options for Claude are: prompt engineering + RAG (current approach), distillation (use Claude as teacher to train a cheaper student model), or switching specific agents to fine-tunable models.

### Q: What is the recommended customization strategy for Kuber?

Don't fine-tune yet. Your prompt engineering + RAG architecture is correct for the current stage. The prompt engineering hierarchy (10 steps) should be exhausted in order. Steps 1–8 require zero training and can be iterated in minutes. Fine-tuning/distillation becomes relevant when: you process 5,000+ evaluations/day and token costs are significant, Ragas evaluation reveals persistent quality gaps that prompts can't fix, you have 6+ months of production data for reliable training datasets, and the company's AI platform team can support model versioning and retraining.

---

## 11. Key Takeaways

1. **Claude does NOT support fine-tuning on Bedrock.** Your customization path is prompt engineering + RAG + prompt caching + extended thinking.

2. **Prompt caching saves up to 90% on input costs** by caching KV computations for repeated prompt prefixes. Configure via `cache_control` markers in LangChain message metadata.

3. **Extended thinking** gives Claude a private reasoning scratchpad that catches nuances the standard response mode misses. Use for Compliance and RiskScoring agents.

4. **The prompt engineering hierarchy has 10 levels.** Exhaust steps 1–8 before considering fine-tuning (step 10). Each earlier step is cheaper, faster, and more auditable.

5. **Distillation is the most practical customization** for Kuber — use Claude Sonnet as teacher to train a cheaper student model for simple tasks like FetchData.

6. **Batch similar loan types together** to maximize prompt cache hit rates. Texas conventional loans share the same policy context.

---

## 12. Next Session Preview

**Week 6, Day 4: FastAPI Deployment — Production API Layer**

Topics: Building the REST API layer for your LangGraph orchestrator, async endpoint design, request/response schemas, authentication, rate limiting, health checks, and deploying to ECS Fargate.

Connection: Today we covered model optimization (caching, thinking, fine-tuning decisions). Tomorrow we make the optimized pipeline accessible as a production API.