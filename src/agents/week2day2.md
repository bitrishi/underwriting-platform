# Week 2 — Day 2: Tools & Function Calling

**Date:** Session 7  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. What tools are (functions the LLM can request to call)
2. How function calling works under the hood (LLM outputs JSON, YOUR code executes)
3. @tool decorator — docstrings as API contracts
4. AgentExecutor and the ReAct loop
5. Callback handlers for observability
6. Tool design best practices for production

---

## Core Concept: Agent = LLM + Tools + Loop

```
Without tools:
  User: "What's the DTI for income $120K, debt $2,400?"
  LLM:  "Approximately 24%"  ← GUESSING from training data

With tools:
  User: "What's the DTI for income $120K, debt $2,400?"
  LLM:  → requests calculate_dti(income=120000, monthly_debt=2400)
  Tool: → returns {"dti": 24.0, "pass": true}
  LLM:  "The DTI is exactly 24.0%"  ← CALCULATED, not guessed
```

---

## How Function Calling Works

**The LLM does NOT call anything.** It outputs a JSON request. YOUR code executes.

```
YOUR PYTHON PROCESS
│
├─ Send to Bedrock: messages + tool schemas
│      ↓
│  BEDROCK (Claude): "I want to call calculate_dti(120000, 2400)"
│      ↓
├─ LangChain reads the tool_use response
├─ LangChain calls YOUR Python function
├─ Function returns {"dti": 24.0}
├─ LangChain sends result BACK to Bedrock
│      ↓
│  BEDROCK: "The DTI is 24%, which passes the threshold."
│      ↓
└─ Your app receives final response
```

The LLM is a brain in a jar. It can think and speak but can't act. Tools are its hands — and you control what those hands can do.

---

## Tool Definition

```python
from langchain_core.tools import tool

@tool
def calculate_dti(annual_income: float, monthly_debt: float) -> dict:
    """Calculate Debt-to-Income ratio for mortgage underwriting.
    
    Use this tool whenever you need to evaluate a borrower's
    debt burden relative to their income.
    
    Args:
        annual_income: Borrower's annual gross income in USD
        monthly_debt: Total monthly debt obligations in USD
        
    Returns:
        DTI percentage, threshold, and pass/fail status
    """
    dti = (monthly_debt * 12) / annual_income * 100
    return {
        "dti": round(dti, 2),
        "threshold": 43.0,
        "pass": dti <= 43.0,
    }
```

Java equivalent: `@Service` implementing an interface. The docstring = Javadoc. LangChain reads type hints + docstring to generate the tool schema sent to the LLM.

---

## Creating the Agent

```python
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", load_prompt("underwriter")),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),  # tool call history
])

agent = create_tool_calling_agent(
    llm=llm,
    tools=[calculate_dti, calculate_ltv, check_fico],
    prompt=prompt,
)

executor = AgentExecutor(
    agent=agent,
    tools=[calculate_dti, calculate_ltv, check_fico],
    verbose=True,       # shows reasoning + tool calls
    max_iterations=10,  # safety limit
)

result = executor.invoke({"input": "Evaluate: FICO 740, Income $120K..."})
```

`{agent_scratchpad}` = where LangChain inserts tool call history. Without it, agent can't see its own previous tool results.

---

## Callback Handler for Observability

```python
from langchain_core.callbacks import BaseCallbackHandler

class UnderwritingTracer(BaseCallbackHandler):
    def __init__(self):
        self.trace = []

    def on_tool_start(self, tool_name, tool_input, **kwargs):
        self.trace.append({"event": "tool_start", "tool": tool_name, ...})
        print(f"  🔧 Calling: {tool_name}({tool_input})")

    def on_tool_end(self, output, **kwargs):
        self.trace.append({"event": "tool_end", "output": output, ...})
        print(f"  ✅ Result: {output}")

# Use:
tracer = UnderwritingTracer()
result = executor.invoke(
    {"input": "Evaluate..."},
    config={"callbacks": [tracer]}
)
```

---

## Tool Design Best Practices

1. **Each tool does ONE thing** — single responsibility
2. **Return structured data, not prose** — `{"dti": 24.0}` not `"The DTI is 24%"`
3. **Docstrings are the API contract** — LLM reads them to decide when/how to call
4. **Handle errors gracefully** — return error dicts, never raise unhandled exceptions
5. **Rich responses reduce round trips** — one tool returning comprehensive data > three chatty tools

---

## Q&A from This Session

### Q: The LLM decides which tool to call? Can it make mistakes?

**Yes, absolutely.** The LLM can make wrong tool selections. Common failure modes:

| Problem | Example | Fix |
|---------|---------|-----|
| Ambiguous descriptions | Two tools with similar docstrings | Make descriptions explicit: WHEN to use, WHEN NOT to use |
| Too many tools | 50 tools on one agent | Multi-agent: 3-5 tools per agent |
| Wrong argument extraction | "Income 120" → 120 not 120000 | Explicit units in parameter descriptions |
| Calling when it shouldn't | Calculates with made-up numbers | System prompt: "ONLY use tools with provided data" |
| Not calling when it should | Answers from training data | System prompt: "ALWAYS use tools for calculations" |

**Production defense in depth:**
- Layer 1: Great tool design (distinct names, clear docs)
- Layer 2: System prompt constraints (mandatory/forbidden tool usage)
- Layer 3: Pydantic validation on tool output
- Layer 4: Deterministic pre-routing (code decides routing, not LLM)
- Layer 5: Evaluation testing (Week 6)

**When to trust LLM vs. code:**

| Decision | LLM? | Code? |
|----------|------|-------|
| Which calculation to perform | ✅ | |
| Which sub-agent to call | | ✅ |
| Whether to approve/deny | ✅ | |
| Input/output validation | | ✅ |
| Which tool among 3-5 | ✅ | |
| Which tool among 50 | | ✅ |

### Q: Tools are passed as context every call — doesn't this waste tokens?

**Yes, tool schemas are sent with every LLM call.** The math:

```
One tool schema ≈ 100-200 tokens
4 tools = ~600 tokens per call
Claude Haiku: $0.00025 per 1K input tokens
4 tools overhead = $0.40 per 1,000 evaluations
```

Negligible with 3-5 tools. Problematic with 50. This is another reason for multi-agent (small toolset per agent).

**Optimization strategies:**
- Multi-agent (3-5 tools each)
- Dynamic tool selection (pre-filter by keyword)
- Concise tool descriptions (every word costs tokens on every call)
- Rich tool responses (fewer round trips)

### Q: How does the LLM actually call tools? Is it always an API?

**The LLM NEVER calls anything.** The flow:

1. Your code sends message + tool schemas to Bedrock
2. Claude RESPONDS with JSON: "I want to call X with Y"
3. YOUR code (LangChain) reads that JSON
4. YOUR code executes the Python function
5. YOUR code sends the result back to Claude
6. Claude sees the result and continues reasoning

The LLM is sandboxed. It can only REQUEST tool calls. Your code decides whether to execute them.

Tools are regular Python functions — they can do anything: API calls, DB queries, calculations, file reads. The LLM never touches your code, APIs, or databases directly.

### Q: What about authentication for external APIs?

**All credentials live in YOUR environment.** The LLM never sees any credentials.

```
LLM (Bedrock): Only sends/receives text. Auth via IAM role.
Your Tool Code: Uses YOUR credentials per service:
  - Camelot API → OAuth 2.0 / PingFederate token
  - Credit Bureau → API key + mTLS certificate
  - Google Maps → API key from Secrets Manager
  - Neo4j → Username/password from Secrets Manager
  - OpenSearch → IAM Role
```

### Q: LLMs are stateless — does the full context go every time?

**Yes.** Every tool call in the ReAct loop re-sends the ENTIRE conversation including all previous tool calls and results. The conversation grows with each tool call:

```
Call 1: ~1,500 tokens (system + user + tools)
Call 2: ~1,800 tokens (+ tool call 1 + result 1)
Call 3: ~2,200 tokens (+ tool call 2 + result 2)
```

This is what `{agent_scratchpad}` manages — the accumulated tool call history.

**Optimization:** Design tools with rich responses (one call returning comprehensive data) to minimize round trips.

### Q: In our conversation, does all context go to Claude every time?

**Yes, with limits.** Long conversations get truncated — older messages are dropped to fit the context window. This is why:

- Documents (`.md`, `.docx`) ARE the persistent memory
- Conversations are ephemeral working sessions
- Key facts are extracted to memory profiles

**Production strategies for managing context:**

| Strategy | How | Savings |
|----------|-----|---------|
| Sliding window | Keep last N messages | High, loses old context |
| Summarization | Compress old messages | Very high, loses detail |
| Memory profile | Extract key facts | Very high, facts only |
| RAG over history | Retrieve relevant past messages | High, needs vector DB |
| Hybrid | All combined | ~90%+ |

**For your agents:** Each loan evaluation should be self-contained per invocation. The `LoanApplication` model carries all needed context — don't depend on conversation history.

---

## Assignments (Completed ✅)

- [x] Task 1: Four underwriting tools (DTI, LTV, FICO, employment)
- [x] Task 2: Underwriting agent with AgentExecutor
- [x] Task 3: UnderwritingTracer callback handler
- [x] Task 4: Agent tested with 3 cases — correct tool selection
- [x] Task 5: Tool unit tests with edge cases
- [x] Task 6: tools/SKILL.md documentation