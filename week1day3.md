# Week 1 — Day 3: AWS Bedrock Setup + First LLM Call

**Date:** Session 3  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. What is Bedrock architecturally (ECS for AI models)
2. Authentication (IAM — same as Camelot)
3. Two ways to call Bedrock (raw boto3 vs. LangChain)
4. Temperature (deterministic vs. creative)
5. System Prompts (agent configuration)
6. Message Types (SystemMessage, HumanMessage, AIMessage)
7. Production-grade Bedrock client setup

---

## 1. Bedrock = ECS for AI Models

```
Camelot:  Java code → ECS Fargate → AWS manages containers
Bedrock:  Python code → Bedrock API → AWS manages GPU inference
```

No model hosting, no instance sizing, no CUDA drivers. Call an API, get a response.

**Available models:** Claude (Anthropic), Titan (Amazon), Llama (Meta), Mistral.  
**Our choice:** Claude — strongest reasoning and tool-use capabilities.

---

## 2. Authentication

```
Camelot:  ECS Task → IAM Task Role → DocumentDB, S3 permissions
Bedrock:  Your code → IAM User/Role → bedrock-runtime permission
```

Same IAM, same VPC, same AWS SDK pattern. Local dev uses AWS CLI profile. Production uses Lambda/Fargate task execution role.

---

## 3. Two Ways to Call Bedrock

### Way 1: Raw boto3 (like raw JDBC)

```python
import boto3
import json

# Same pattern as any AWS SDK call
client = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1"
)

response = client.invoke_model(
    modelId="anthropic.claude-3-sonnet-20240229-v1:0",
    contentType="application/json",
    accept="application/json",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": "What is a DTI ratio?"
            }
        ]
    })
)

result = json.loads(response["body"].read())
answer = result["content"][0]["text"]
```

Verbose — manual JSON, manual parsing. Like raw JDBC PreparedStatement.

### Way 2: LangChain + Bedrock (like Spring JPA)

```python
from langchain_aws import ChatBedrock

llm = ChatBedrock(
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    region_name="us-east-1",
    model_kwargs={
        "max_tokens": 1024,
        "temperature": 0
    }
)

response = llm.invoke("What is a DTI ratio?")
print(response.content)
```

LangChain handles serialization, parsing, errors, retries. This is what we use for agents.

---

## 4. Temperature

```python
# temperature = 0: Deterministic. Same input = same output.
# Use for: underwriting decisions, data extraction, compliance
llm_precise = ChatBedrock(model_kwargs={"temperature": 0})

# temperature = 0.7: Creative. Varied outputs.
# Use for: generating explanations, brainstorming
llm_creative = ChatBedrock(model_kwargs={"temperature": 0.7})
```

Java analogy: `temperature=0` is a pure function. `temperature>0` adds `Random.nextInt()` internally.

**For underwriting: always temperature 0.** Deterministic, reproducible decisions.

---

## 5. System Prompts

Sets agent behavior for the entire conversation. Like configuring a Spring bean at startup.

```python
from langchain_core.messages import SystemMessage, HumanMessage

messages = [
    SystemMessage(content="""
You are a Senior Loan Underwriter at a major bank.

Rules:
- NEVER approve without verifying FICO >= 680
- NEVER approve if DTI > 43%
- ALWAYS provide confidence score (0.0 to 1.0)

Output format (valid JSON):
{
    "decision": "APPROVED" or "DENIED",
    "confidence": 0.0-1.0,
    "reasons": ["reason1", "reason2"]
}
    """),
    HumanMessage(content="""
Evaluate: FICO 740, Income $120K, Monthly Debt $2,400, Loan $350K
    """)
]

response = llm.invoke(messages)
```

---

## 6. Message Types

```python
from langchain_core.messages import (
    SystemMessage,    # Sets behavior       (like @Configuration)
    HumanMessage,     # User input          (like @RequestBody)
    AIMessage,        # LLM response        (like ResponseEntity<T>)
)

# Conversation = list of messages (LLM sees full history)
messages = [
    SystemMessage(content="You are an underwriter..."),
    HumanMessage(content="Evaluate loan #12345"),
    AIMessage(content='{"decision": "APPROVED"...}'),
    HumanMessage(content="What if FICO dropped to 650?"),
]
```

---

## 7. Production Bedrock Client

```python
# src/config/bedrock.py
from langchain_aws import ChatBedrock
from src.config.settings import settings

def create_llm(
    temperature: float = 0,
    max_tokens: int = 1024
) -> ChatBedrock:
    """Create a Bedrock LLM client using project settings."""
    return ChatBedrock(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        model_kwargs={
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    )
```

---

## Quick Reference

| Concept | Java Equivalent | Purpose |
|---------|----------------|---------|
| `boto3.client("bedrock-runtime")` | `AmazonBedrockClient.builder()` | Raw SDK |
| `ChatBedrock()` | `@Service` managed bean | High-level LLM client |
| `temperature=0` | Pure function | Deterministic output |
| `SystemMessage` | `@Configuration` | Agent behavior setup |
| `HumanMessage` | `@RequestBody` | User input |
| `AIMessage` | `ResponseEntity<T>` | LLM response |

---

## Assignments (Completed ✅)

- [x] Task 1: `src/config/bedrock.py` factory function
- [x] Task 2: First LLM call
- [x] Task 3: System prompt from file + evaluation
- [x] Task 4: Temperature experiment
- [x] Task 5: Configuration tests

**Note:** Used a non-Claude model due to access. Will need to verify tool-calling compatibility for Week 2+.