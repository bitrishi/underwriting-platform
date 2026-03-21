# Week 2 — Day 4: RAG Pipeline — Retrieve → Augment → Generate

**Date:** Session 9  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. The RAG flow (Retrieve → Augment → Generate)
2. Building RAG chains with LCEL
3. format_docs() for context injection with source citations
4. RunnablePassthrough for parallel retrieval + question passing
5. Structured RAG output (PolicyAnswer with citations)
6. Retriever as a tool (agent autonomously searches policies)
7. How tool calling ACTUALLY works at the API level

---

## The RAG Flow

```
User Question
    │
    ▼
RETRIEVE — Search vector store (with metadata filter)
    │ Returns 3 most relevant chunks
    ▼
AUGMENT — Insert docs into prompt: "Answer using ONLY this context"
    │
    ▼
GENERATE — LLM reasons over real documents, cites sources
    │
    ▼
Answer with source citations
```

Java analogy: Service that queries the database BEFORE applying business logic, instead of answering from cached assumptions.

---

## RAG Chain with LCEL

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

def format_docs(docs) -> str:
    """Format retrieved docs with source metadata for citation."""
    formatted = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        formatted.append(
            f"[Document {i}]\n"
            f"Source: {source}, Page {page}\n"
            f"Content: {doc.page_content}\n"
        )
    return "\n---\n".join(formatted)

def create_rag_chain(metadata_filter=None):
    llm = create_llm(temperature=0)
    vectorstore = load_vectorstore()
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 3, **({"filter": metadata_filter} if metadata_filter else {})}
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer ONLY from provided context. Cite sources. "
                   "If insufficient, say so."),
        ("human", "CONTEXT:\n{context}\n\nQUESTION: {question}"),
    ])

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain
```

**How the LCEL dict works:**

```python
{
    "context": retriever | format_docs,    # search → format as string
    "question": RunnablePassthrough(),     # pass question through unchanged
}
# Runs BOTH in parallel, produces:
# {"context": "formatted docs...", "question": "user's question"}
```

`RunnablePassthrough()` = identity function. Needed because retriever transforms input (question → documents) but prompt also needs the original question.

---

## Structured RAG Output

```python
class PolicyAnswer(BaseModel):
    """Typed RAG response with citations."""
    answer: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    sources: list[str] = Field(min_length=1)
    relevant_quotes: list[str]
    sufficient_context: bool

# Chain returns typed PolicyAnswer, not free text
chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm.with_structured_output(PolicyAnswer)
)

result = chain.invoke("What is the maximum LTV for Texas loans?")
print(result.answer)              # "The maximum LTV is 80%..."
print(result.sources)             # ["state_regulations.pdf, Page 7"]
print(result.sufficient_context)  # True
```

---

## Retriever as a Tool

Most powerful pattern — agent decides WHEN to search policies:

```python
@tool
def search_lending_policies(
    query: str,
    jurisdiction: str = "federal",
    loan_type: str = "all",
) -> str:
    """Search lending policies and regulations.
    
    Use when you need to verify regulatory requirements,
    policy guidelines, or compliance rules.
    """
    vectorstore = load_vectorstore()
    results = vectorstore.similarity_search(
        query, k=3,
        filter={"jurisdiction": jurisdiction} if jurisdiction != "all" else None,
    )
    return format_docs(results)
```

Agent autonomously calls this when evaluating loans — searches Texas regulations, checks TRID requirements, verifies DTI exception rules.

---

## Q&A from This Session

### Q: The LLM doesn't call tools, right? How does it "tell" your code to call a tool?

**The LLM response has a structured `type` field, NOT text parsing.**

When the LLM wants to call a tool, the API response contains:

```json
{
    "content": [{
        "type": "tool_use",
        "name": "calculate_dti",
        "input": {"annual_income": 120000, "monthly_debt": 2400},
        "id": "call_001"
    }],
    "stop_reason": "tool_use"
}
```

When the LLM wants to respond with text:

```json
{
    "content": [{
        "type": "text",
        "text": "Based on the analysis, DTI is 24%..."
    }],
    "stop_reason": "end_turn"
}
```

**`type: "tool_use"` vs `type: "text"`** — this is how LangChain knows. It checks `response.tool_calls`:

```python
response = llm_with_tools.invoke(messages)

if response.tool_calls:          # non-empty = tool request
    for call in response.tool_calls:
        tool_name = call["name"]     # which tool
        tool_args = call["args"]     # parameters
        tool_id = call["id"]         # for matching result back
        
        result = tool_map[tool_name].invoke(tool_args)
        # Send result back to LLM as ToolMessage
else:                               # empty = text response
    return response.content          # final answer
```

**This is NOT text parsing.** Old frameworks used regex on text like "Action: calculate_dti". Modern function calling uses structured API response types. This is why you need a model that supports function calling (Haiku/Claude) — the capability is built into the API protocol.

### The complete round trip:

```
Call 1: Your code → Bedrock (messages + tools)
        Bedrock → Your code (type: "tool_use", name: "calculate_dti")
        Your code executes calculate_dti()

Call 2: Your code → Bedrock (messages + previous tool call + result)
        Bedrock → Your code (type: "tool_use", name: "check_fico")
        Your code executes check_fico()

Call 3: Your code → Bedrock (messages + all tool calls + all results)
        Bedrock → Your code (type: "text", "APPROVED...")
        Agent loop ends — final answer
```

Each call re-sends FULL history (stateless). AgentExecutor manages this loop automatically.

---

## Key Concepts Summary

| Concept | What It Does | Java Equivalent |
|---------|-------------|-----------------|
| RAG chain | Retrieve → Augment → Generate | Query DB → apply logic |
| `as_retriever()` | Vector store → retriever component | DAO pattern |
| `RunnablePassthrough()` | Pass input unchanged | Identity function |
| `format_docs()` | Documents → prompt string | DTO mapper |
| PolicyAnswer | Typed RAG response | Response POJO |
| Retriever as tool | Agent decides when to search | Service calling DAO |
| `type: "tool_use"` | API response for tool requests | Not text — structured protocol |
| `response.tool_calls` | List of requested tool calls | Structured, not parsed |

---

## Assignments (Completed ✅)

- [x] Task 1: RAG chain (rag_chain.py) with format_docs and metadata filtering
- [x] Task 2: PolicyAnswer Pydantic model with citations
- [x] Task 3: Policy search tools (lending policies + compliance rules)
- [x] Task 4: RAG chain tested — including sufficient_context=false
- [x] Task 5: Agent with RAG tool — autonomously searched Texas policies ✅
- [x] Task 6: RAG tests with metadata filtering