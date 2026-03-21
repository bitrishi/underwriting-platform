# Week 2 — Day 1: LangChain Deep Dive

**Date:** Session 6  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. What is LangChain architecturally (Spring Boot for AI)
2. The Six Core Abstractions (Models, Messages, Prompts, Parsers, Chains, Tools)
3. ChatPromptTemplate (reusable prompts with variables)
4. LCEL — LangChain Expression Language (the pipe `|` operator)
5. RunnableParallel (concurrent chains)
6. RunnableBranch (conditional routing)
7. Streaming with LCEL

---

## LangChain = Spring Boot for AI

```
Java:    Raw Servlets → Spring Boot → Focus on business logic
Python:  Raw boto3    → LangChain  → Focus on agent logic
```

LangChain is a library (toolkit), not a framework. You pick the pieces you need.

---

## The Six Abstractions

| Abstraction | Java Equivalent | What It Does |
|-------------|----------------|-------------|
| Models | Service clients | Interface to LLMs (Bedrock, OpenAI) |
| Messages | Request/Response DTOs | Structured conversation |
| Prompts | Thymeleaf templates | Templates with variables |
| Output Parsers | Jackson deserializer | Parse LLM text to typed objects |
| Chains | Stream pipelines | Compose steps into a pipeline |
| Tools | Interface implementations | Functions agents can call |

---

## ChatPromptTemplate

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a Senior Loan Underwriter.
Rules:
- NEVER approve if FICO < {min_fico}
- NEVER approve if DTI > {max_dti}%"""),
    ("human", """Evaluate:
Borrower: {borrower_name}
FICO: {fico_score}"""),
])

# Fill in variables at invocation time
messages = prompt.invoke({
    "min_fico": 680,
    "max_dti": 43,
    "borrower_name": "John Doe",
    "fico_score": 740,
})
```

Like parameterized SQL — reusable, type-safe, composable.

---

## LCEL: The Pipe Operator

```python
# Data flows left to right: prompt → LLM → parser
chain = prompt | llm | StrOutputParser()
result = chain.invoke({"question": "What is DTI?"})

# With structured output — one line pipeline
chain = prompt | llm.with_structured_output(LoanDecision)
decision = chain.invoke({"application_text": "..."})
# decision is a typed LoanDecision object
```

Java equivalent: `CompletableFuture.supplyAsync().thenApply().thenApply()`

---

## RunnableParallel

```python
from langchain_core.runnables import RunnableParallel

parallel = RunnableParallel(
    credit=credit_chain,
    employment=employment_chain,
    property=property_chain,
)

results = parallel.invoke({"app_id": "12345"})
# results = {"credit": ..., "employment": ..., "property": ...}
# All three ran concurrently
```

Java equivalent: `CompletableFuture.allOf(a, b, c)`

---

## RunnableBranch

```python
from langchain_core.runnables import RunnableBranch

chain = RunnableBranch(
    (lambda x: x["fico"] < 680, denial_chain),
    (lambda x: x["dti"] > 41, review_chain),
    approval_chain,  # default
)
```

Routes input to different chains based on conditions.

---

## Streaming

```python
# Every LCEL chain is automatically streamable
for chunk in chain.stream({"application_text": "..."}):
    print(chunk, end="", flush=True)
```

No special code needed — built into LCEL.

---

## Week 1 → Week 2 Evolution

| Week 1 (raw) | Week 2 (LangChain) |
|--------------|---------------------|
| `load_prompt("underwriter")` | `ChatPromptTemplate.from_messages()` |
| `llm.invoke(messages)` | `chain.invoke({"app": "..."})` |
| `json.loads() + model_validate()` | `llm.with_structured_output(Model)` |
| `asyncio.gather(a, b, c)` | `RunnableParallel(a=..., b=..., c=...)` |
| Manual if/else routing | `RunnableBranch(...)` |

---

## Assignments (Completed ✅)

- [x] Task 1: Refactored underwriter chain to LCEL (v2)
- [x] Task 2: RunnableParallel with 3 concurrent chains
- [x] Task 3: RunnableBranch with FICO-based routing
- [x] Task 4: Streaming with LCEL chain
- [x] Task 5: Tests for chain v2, parallel, and routing