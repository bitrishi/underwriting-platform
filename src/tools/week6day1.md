# Week 6, Day 1: LangSmith — Tracing, Evaluation & Anthropic SDK Comparison

**Date:** April 5, 2026  
**Module:** Evaluation & Observability  
**Platform:** Kuber Loan Origination System  

---

## 1. Session Overview

**Topic:** LangSmith deep dive — tracing, debugging, production monitoring, and the critical comparison between building with Anthropic SDK directly versus LangChain/LangGraph for observability.

**Prerequisites:** Weeks 1–5 complete. LangGraph orchestration architecture decided. Four-agent pipeline designed (FetchData/Haiku, DocReview/Sonnet, RiskScoring/Haiku, Compliance/Sonnet).

**Key Deliverable:** Understanding of two development paths for AI observability and a justified recommendation for Kuber's production stack.

---

## 2. Why AI-Specific Observability

Infrastructure monitoring (CloudWatch, X-Ray) catches operational problems: service is down, latency is high, errors are spiking. These are necessary but insufficient for AI systems.

LangSmith catches a fundamentally different category — **QUALITY problems**:

- **Wrong tool selection:** Risk Scoring calls `search_lending_policies` when it should have called `get_borrower_risk_context`. No errors in logs. Infrastructure sees a successful evaluation. But the risk assessment missed critical context.

- **Irrelevant RAG retrieval:** Compliance agent searches for "Texas LTV limits" but the top results are about California. No errors, no timeouts — just wrong content flowing through a working pipeline.

- **Prompt degradation:** You update the risk scoring prompt. Since then, the agent produces lower confidence scores and more MANUAL_REVIEW recommendations. Throughput and latency are unchanged. Only output quality shifted.

- **Model version drift:** AWS updates Haiku from one version to another. The new version handles tool calling differently — sometimes skipping the employment check. Your tests still pass, but reasoning paths changed.

### The Three-Layer Monitoring Stack

| Layer | What It Monitors | Key Question |
|-------|-----------------|--------------|
| **CloudWatch** | Container health, CPU, memory, API error rates, business metrics | Is the system running? |
| **X-Ray** | Bedrock API latency, S3 access, DynamoDB queries, service dependency chains | Where is the system slow? |
| **LangSmith** | LLM prompts, tool selection, RAG retrieval quality, agent decisions, output quality | Is the system reasoning correctly? |

You need all three. CloudWatch catches "the system is down." X-Ray catches "Bedrock is slow today." LangSmith catches "the agent is choosing wrong tools since Tuesday's prompt update."

---

## 3. What LangSmith Is

LangSmith is LangChain's proprietary observability and evaluation platform designed specifically for LLM applications. It provides tracing, debugging, monitoring, dataset management, and evaluation capabilities.

### 3.1 Licensing Model

- **LangChain (framework):** Fully open source, MIT license. Free forever.
- **LangGraph (orchestration):** Open source, MIT license. Free.
- **LangSmith (observability):** Proprietary SaaS. Free tier (5,000 traces/month), paid for production volume. Self-hosted enterprise option available.

Business model: give away the framework to drive adoption, monetize the hosted platform. Same pattern as MongoDB Atlas, Elastic Cloud, Grafana Cloud.

### 3.2 How Tracing Works

When you enable tracing, every LangChain/LangGraph operation is automatically captured with no code changes needed:

- Every LLM call (model, prompt, response, tokens, latency)
- Every tool invocation (name, input, output, duration)
- Every chain step (input, output, intermediate steps)
- Every agent reasoning step (thought, action, observation)
- Every LangGraph node execution (state before, state after, duration)

The trace is hierarchical. One loan evaluation creates a top-level trace. Inside it: LangGraph execution with each node as a child span. Inside each node: the agent execution with each ReAct loop iteration. Inside each iteration: the LLM call and any tool calls.

### 3.3 Enabling LangSmith with LangChain/LangGraph

Two environment variables — no code changes:

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=<your-langsmith-api-key>
export LANGCHAIN_PROJECT=kuber-underwriting  # optional
```

LangChain detects the environment variables and automatically sends traces to LangSmith. Every `invoke()`, `stream()`, and tool call is captured. This is the power of framework-level integration.

---

## 4. The Core Architectural Decision: Anthropic SDK vs LangChain

This is the most important architectural decision affecting your observability stack. Two fundamentally different paths to building the same system.

### 4.1 Path 1: Anthropic SDK Direct + LangSmith Tracing

You call Claude's API directly (via the `anthropic` Python SDK or Bedrock's Converse API). You write the ReAct loop yourself. You manage tool calling, state, and routing in plain Python. For observability, you use LangSmith's `wrap_anthropic` wrapper.

#### Code Example: Direct SDK Agent

```python
import anthropic
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic

# Wrap the Anthropic client — this is the key line
client = wrap_anthropic(anthropic.Anthropic())

# Define tools as plain dicts (Anthropic native format)
tools = [
    {
        "name": "pull_borrower_data",
        "description": "Fetches borrower profile from Kuber",
        "input_schema": {
            "type": "object",
            "properties": {
                "application_id": {"type": "string", "description": "Loan application ID"}
            },
            "required": ["application_id"]
        }
    },
    {
        "name": "calculate_dti",
        "description": "Calculates debt-to-income ratio",
        "input_schema": {
            "type": "object",
            "properties": {
                "monthly_income": {"type": "number"},
                "monthly_debt": {"type": "number"}
            },
            "required": ["monthly_income", "monthly_debt"]
        }
    }
]

# Your tool implementations
def execute_tool(name: str, input_data: dict) -> str:
    if name == "pull_borrower_data":
        return '{"name": "Acme Corp", "fico": 710, "revenue": 5000000}'
    elif name == "calculate_dti":
        dti = input_data["monthly_debt"] / input_data["monthly_income"] * 100
        return f'{{"dti_ratio": {dti:.1f}}}'
    return '{"error": "Unknown tool"}'

# The @traceable decorator traces YOUR functions (non-LLM code)
@traceable(name="Risk Scoring Agent", run_type="chain")
def risk_scoring_agent(application_id: str) -> str:
    """ReAct loop — YOU manage the iteration."""
    messages = [
        {
            "role": "user",
            "content": f"Evaluate risk for loan application {application_id}. "
                       f"Pull borrower data, calculate DTI, provide risk score 0-100."
        }
    ]
    
    # ReAct loop — keep calling until Claude stops requesting tools
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system="You are an underwriting risk analyst. Use tools to gather data, then score risk.",
            tools=tools,
            messages=messages
        )
        
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            return final_text

result = risk_scoring_agent("APP-001")
```

**What LangSmith captures:** The `risk_scoring_agent` function as a top-level "chain" run (from `@traceable`). Each `client.messages.create()` call as a child "llm" run (from `wrap_anthropic`). Full prompt, response, tool calls, token counts, latency. But NOT: your `execute_tool` function details, state transitions, or parallel execution metadata unless you manually add `@traceable` to each function.

**To trace your own functions, add decorators:**

```python
@traceable(name="Execute Tool", run_type="tool")
def execute_tool(name: str, input_data: dict) -> str:
    # Now this is also traced
    ...
```

Every function you want traced needs the `@traceable` decorator. You're opting in function by function.

### 4.2 Path 2: LangChain/LangGraph with Automatic Tracing

LangChain wraps the Claude API. LangGraph manages orchestration. For observability, you set two environment variables and LangSmith captures everything automatically.

#### Code Example: LangGraph Agent

```python
# Just set env vars — that's ALL for tracing
# export LANGCHAIN_TRACING_V2=true
# export LANGCHAIN_API_KEY=<your-key>
# export LANGCHAIN_PROJECT=kuber-underwriting

from langchain_aws import ChatBedrockConverse
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
import operator

# Define typed state
class UnderwritingState(TypedDict):
    application_id: str
    borrower_data: dict
    dti_ratio: float
    risk_score: int
    messages: Annotated[list, operator.add]

# Define tools as LangChain tools
@tool
def pull_borrower_data(application_id: str) -> dict:
    """Fetches borrower profile from Kuber."""
    return {"name": "Acme Corp", "fico": 710, "revenue": 5000000}

@tool
def calculate_dti(monthly_income: float, monthly_debt: float) -> dict:
    """Calculates debt-to-income ratio."""
    return {"dti_ratio": monthly_debt / monthly_income * 100}

# Create model
model = ChatBedrockConverse(
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    region_name="us-east-1",
    temperature=0
)

# LangGraph nodes
def fetch_data_node(state: UnderwritingState) -> dict:
    agent = model.bind_tools([pull_borrower_data])
    # ... agent logic
    return {"borrower_data": {...}}

def risk_scoring_node(state: UnderwritingState) -> dict:
    agent = model.bind_tools([calculate_dti])
    # ... agent logic
    return {"risk_score": 65, "dti_ratio": 40.4}

# Build graph
graph = StateGraph(UnderwritingState)
graph.add_node("fetch_data", fetch_data_node)
graph.add_node("risk_scoring", risk_scoring_node)
graph.add_edge(START, "fetch_data")
graph.add_edge("fetch_data", "risk_scoring")
graph.add_edge("risk_scoring", END)

app = graph.compile()

# Run — LangSmith traces EVERYTHING automatically
result = app.invoke({"application_id": "APP-001", "messages": []})
```

**What LangSmith captures automatically (zero additional code):**

- Full LangGraph execution as top-level trace
- Each node (`fetch_data`, `risk_scoring`) as child spans
- Each LLM call within each node as grandchild spans
- Each tool invocation as great-grandchild spans
- State before/after each node
- Conditional edge decisions
- Parallel execution branches
- Token usage, latency, cost per call
- The complete reasoning chain

---

## 5. Comprehensive Comparison Matrix

| Dimension | Anthropic SDK Direct | LangChain / LangGraph |
|-----------|---------------------|----------------------|
| **Setup Complexity** | 3–5 lines wrapper code + @traceable on every function (20–30 decorators) | 2 environment variables. Done. |
| **Trace Depth** | LLM calls + manually instrumented functions only | Everything automatic: nodes, LLM calls, tools, state, edges, parallel branches |
| **Vendor Lock-in** | Minimal. Swap tracing layer (Langfuse, Phoenix). Swap LLM by changing client. | Coupled to LangChain abstractions + LangSmith SaaS. Framework switch = rewrite. |
| **Team Onboarding (30 devs)** | Must understand raw API, tool calling protocol, ReAct loop. More transparent. | Learn LangChain abstractions. Steeper curve, but tracing is free once learned. |
| **Production Debugging** | See LLM calls, may miss WHY tool was selected or state context. | Click trace → see exact failed node, state, LLM reasoning, tool call, response. |
| **Cost Control** | Trace only what you choose. Fewer traces = lower cost. | More traces (instruments internal ops). Less control over volume. |
| **Data Residency** | Use any self-hosted solution. No data leaves VPC. | LangSmith Cloud sends data externally. Self-hosted enterprise is expensive. |
| **LLM Portability** | Switching Claude to GPT = rewrite API calls (different formats). | Switch models by changing one config line. Same interface for all providers. |
| **Code Ownership** | You own every line. No framework magic. Maximum control. | Framework manages internals. Less code to write, more abstraction to understand. |

---

## 6. LangSmith 2025–2026 Feature Evolution

### 6.1 LangSmith Fleet (formerly Agent Builder)

Renamed and expanded in March 2026. Now includes agent identity, permissions, sharing across teams, and skills. Two authorization types: Assistants (use end-user credentials) and Claws (fixed credentials). This is LangChain's attempt to become the full agent lifecycle platform, not just tracing.

### 6.2 Insights Agent

An AI agent within LangSmith that automatically categorizes production traces. Answers: "What are users asking my agent?" and "Where is my agent failing?" by clustering traces into usage patterns and failure modes. Generally available for Plus and Enterprise tiers.

### 6.3 Multi-turn Evals

Evaluation at the conversation level, not just individual traces. Measures semantic intent (what the user tried to do), semantic outcomes (whether the task completed), and agent trajectory (how the interaction unfolded including tool calls). For Kuber: evaluate the entire end-to-end loan evaluation as one unit.

### 6.4 Pairwise Annotation Queues

Compare two agent outputs side-by-side and pick a winner. When you update a prompt, run old vs new versions against the same inputs and have reviewers pick which is better. This is exactly how you'd prove to the company's risk committee that a prompt change improved accuracy.

### 6.5 LangSmith Fetch CLI

Trace access directly from terminal or IDE. Debug without leaving your code editor. Launched December 2025.

### 6.6 OpenTelemetry Support

LangSmith now supports OpenTelemetry integration in both directions: export LangSmith traces to your existing OTel pipeline, or ingest OTel data into LangSmith. Connects to existing enterprise monitoring infrastructure.

### 6.7 Cost Tracking

Unified view of costs across full agent workflow, not just LLM calls. Submit custom cost metadata for any run (tool calls, API calls, external services).

---

## 7. Observability Alternatives for Production

For the company's production environment, LangSmith Cloud may not be viable due to data residency. Here are the alternatives evaluated:

| Tool | Type | LangChain Support | Self-Hosted? | Best For |
|------|------|------------------|-------------|----------|
| **LangSmith** | Proprietary SaaS | Deep (automatic) | Enterprise tier | LangChain teams |
| **Langfuse** | Open source (ClickHouse-backed) | Good (decorators + OTel) | Yes, free | Data residency |
| **Arize Phoenix** | Open source | Good (OTel) | Yes, local-first | Development / RAG debug |
| **Datadog LLM** | Enterprise SaaS | Via OTel | N/A (SaaS) | Existing Datadog shops |
| **OTel + Grafana** | Open source DIY | Manual instrumentation | Full control | Maximum control |

**Langfuse acquisition note:** In January 2026, ClickHouse acquired Langfuse as part of a $400M Series D round, signaling long-term stability and strategic importance of LLM observability in the data infrastructure stack. Langfuse remains open source and self-hostable.

---

## 8. What a LangSmith Trace Reveals

For one Kuber loan evaluation, the LangSmith trace shows:

- **Top-level run:** total duration, total tokens, total cost, final output
- **Each LangGraph node as a child span:** which node, how long, state passed in, state produced
- **Each LLM call within each node:** model used, full prompt (system + user + tool results), full response, token counts (input/output/cache), latency
- **Each tool call:** tool name, input arguments, return value, execution time
- **State transitions:** complete state object before and after each node
- **Conditional routing decisions:** which edge was taken and why

You can drill from "evaluation took 11 seconds" down to "this specific LLM call in the third iteration of risk scoring took 2.1 seconds and generated a tool call for `calculate_dti`."

### 8.1 LangSmith for Testing and Evaluation

You create a **DATASET** in LangSmith — a collection of input/output pairs representing known-good evaluations. Example: 50 loan applications with human-verified correct decisions (25 approved, 15 denied, 10 manual review).

You run your pipeline against the dataset. LangSmith captures every trace. You define **EVALUATORS** — functions that score each output against the expected result. "Did the agent produce the correct recommendation?" "Was the risk score within 10 points of the human assessment?" "Were all required criteria checked?"

LangSmith displays results: 48/50 correct, 2 mismatches. Drill into the 2 failures, find the exact reasoning step that went wrong, fix it, re-run. Regression testing for AI.

This is how you prove to the company's risk committee that the system works correctly. Not "we tested it manually" but "we ran 500 historical applications through the system, achieved 96.4% agreement with human underwriters, and here are the 18 disagreements with detailed analysis."

---

## 9. LangSmith Pricing Considerations

- **Free tier:** 5,000 traces/month. Covers development and initial testing.
- **Your pipeline math:** 1,000 evaluations/day × ~20 LLM calls each = 20,000 traces/day = 600,000/month. This is well into paid territory.
- LangSmith's per-trace pricing can trigger large bills at scale. Self-hosted enterprise removes per-trace costs but adds infrastructure and license costs. This is a key factor in the the company production decision.

---

## 10. Recommended Architecture for Kuber

Given that you've already chosen LangGraph for orchestration, here is the recommended observability path:

### Development Phase (Current)

- Use LangSmith Cloud free tier (5,000 traces/month)
- Auto-tracing with LangGraph gives deepest possible visibility
- Debug in minutes instead of hours
- Build evaluation datasets from real trace data

### Staging / Pre-Production

- Deploy Langfuse self-hosted in the company's AWS VPC
- Run Langfuse alongside LangSmith Cloud to validate feature parity
- Build evaluation pipelines that work with both
- Test OpenTelemetry export from LangGraph to Langfuse

### Production

- **Langfuse self-hosted** (primary AI observability) — no data leaves the company's VPC
- **CloudWatch** (infrastructure monitoring) — container health, API metrics
- **X-Ray** (service call tracing) — Bedrock latency, DynamoDB, S3
- **Bedrock Guardrails** (content safety) — built into the pipeline
- Custom dashboards combining all three layers

---

## 11. Questions & Answers

### Q: Which approach gives deeper traces?

LangChain/LangGraph with automatic tracing gives significantly deeper traces. Because LangSmith hooks into LangChain at the framework level, it captures internal operations that are invisible to the wrapper approach: prompt template formatting, output parsing, retriever operations, graph state mutations, conditional edge decisions, parallel execution branches. With the Anthropic SDK approach, you only see what you explicitly instrument.

### Q: Which approach takes more setup code?

Anthropic SDK Direct takes substantially more code. You write the ReAct loop (the `while True` loop with tool call handling) yourself — roughly 50–100 lines per agent versus LangChain's `create_tool_calling_agent` one-liner. You also need to add `@traceable` decorators to every function you want traced (potentially 20–30 across your codebase), whereas LangChain/LangGraph requires only 2 environment variables for complete tracing.

### Q: For the company production, which approach do you recommend and why?

LangChain/LangGraph for orchestration (already decided in Week 4) with Langfuse self-hosted for production observability. The reasoning: LangGraph gives you typed state, parallel execution, checkpointing, and human-in-the-loop patterns that would take months to build from scratch. Langfuse gives you self-hosted AI observability with good LangChain integration and no data leaving the company's VPC. Use LangSmith Cloud during development for its superior developer experience, then transition to Langfuse for production.

### Q: What is the dev-to-prod observability transition plan?

**Phase 1 (Now):** LangSmith Cloud free tier for development. Learn the tracing patterns, build evaluation datasets, debug your pipeline.

**Phase 2 (Staging):** Deploy Langfuse in the company's AWS. Validate that trace data you need in production is captured. Build custom dashboards.

**Phase 3 (Production):** Langfuse + CloudWatch + X-Ray as the three-layer stack. Export OpenTelemetry data from LangGraph to Langfuse. Keep LangSmith Cloud for development iteration.

### Q: Can you use LangSmith without LangChain?

Yes. LangSmith now works with any framework. For the Anthropic SDK, use `wrap_anthropic` to wrap the client. For custom code, use `@traceable` decorator or the LangSmith SDK directly. LangSmith also supports OpenTelemetry ingestion. However, the deepest, most automatic tracing still requires LangChain/LangGraph. Other frameworks need manual instrumentation.

### Q: What about Langfuse being acquired by ClickHouse?

In January 2026, ClickHouse acquired Langfuse as part of a $400M Series D round. This is positive for long-term stability — ClickHouse is the columnar database that Langfuse already uses as its backend. The acquisition signals that LLM observability is strategically important to the data infrastructure ecosystem. Langfuse remains open source and self-hostable.

### Q: How does LangSmith compare to Datadog LLM Monitoring?

Different strengths. LangSmith has deeper LLM-specific features: evaluation datasets, pairwise comparisons, prompt versioning, the Insights Agent for automatic trace categorization. Datadog integrates with existing enterprise monitoring infrastructure and provides a unified view across traditional services and LLM calls. If the company already uses Datadog, adding LLM Monitoring is operationally simpler but less feature-rich for AI-specific debugging than LangSmith.

### Q: What are the new LangSmith features since our last discussion?

Key additions: LangSmith Fleet (agent identity, permissions, skills — March 2026), Insights Agent (automatic trace categorization and clustering), Multi-turn Evals (conversation-level evaluation), Pairwise Annotation Queues (A/B testing agent outputs), LangSmith Fetch CLI (terminal-based trace access), OpenTelemetry bidirectional support, unified cost tracking across full workflows, and LangGraph v1.1 with type-safe streaming and Pydantic coercion.

---

## 12. Key Takeaways

1. **AI observability is a different category from infrastructure monitoring.** CloudWatch tells you the system is running. LangSmith tells you the system is reasoning correctly. You need both.

2. **LangChain/LangGraph with LangSmith provides the deepest automatic tracing.** The Anthropic SDK approach gives more control but requires manual instrumentation.

3. **For the company production:** LangGraph (orchestration) + Langfuse self-hosted (AI observability) + CloudWatch/X-Ray (infrastructure). LangSmith Cloud for development.

4. **LangSmith's evaluation features** (datasets, evaluators, pairwise comparison) are how you prove AI quality to risk committees — not manual testing, but systematic regression testing against human-verified baselines.

5. **The observability landscape is maturing fast.** Langfuse (ClickHouse-backed), Arize Phoenix, Datadog LLM Monitoring, and OpenTelemetry are all viable alternatives to LangSmith for different organizational needs.

---

## 13. Next Session Preview

**Week 6, Day 2: Ragas — Automated RAG Evaluation & Testing**

Topics: RAG quality metrics (faithfulness, answer relevancy, context precision, context recall), building test datasets from production traces, automated evaluation pipelines, hallucination detection, integrating Ragas with LangSmith/Langfuse for continuous quality monitoring.

Connection: Today we built the observability foundation (tracing, debugging). Tomorrow we add the evaluation layer — automated testing that measures whether your RAG retrieval and agent reasoning are actually producing correct results.