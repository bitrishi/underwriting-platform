# Week 1 — Day 4: Prompt Engineering for Production Agents

**Date:** Session 4  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. The Five Prompt Engineering Techniques
2. Role Assignment
3. Few-Shot Examples
4. Chain-of-Thought (CoT)
5. Output Schema Enforcement
6. Negative Constraints
7. Agent Observability (reasoning_trace)
8. SKILL.md vs .txt Prompt Files
9. How Agents Know Their Capabilities

---

## The Five Techniques

| # | Technique | What It Does | Java Analogy |
|---|-----------|-------------|--------------|
| 1 | Role Assignment | Defines who the agent is | Dependency injection — which domain to use |
| 2 | Few-Shot Examples | Shows input/output pairs | TDD — write expected output first |
| 3 | Chain-of-Thought | Forces step-by-step reasoning | Adding logging to every business logic step |
| 4 | Output Schema | Constrains response format | Jackson POJO serialization |
| 5 | Negative Constraints | What agent must NOT do | @NotNull, @Max, @Valid annotations |

---

## 1. Role Assignment

```
BAD (no role):
  "What should I do with this loan? FICO 680, DTI 45%"

GOOD (with role):
  "You are a Senior Mortgage Underwriter with 15 years experience
   at a top-tier US bank. You follow Fannie Mae and Freddie Mac
   guidelines strictly. Evaluate the following..."
```

Without a role, the LLM doesn't know which knowledge domain to apply.

---

## 2. Few-Shot Examples

Show 2-3 input/output pairs. The LLM learns the exact format, detail level, and style.

```
EXAMPLE 1:
Input: FICO 740, DTI 28%, LTV 80%
Output:
{
    "decision": "APPROVED",
    "confidence": 0.95,
    "reasons": ["FICO 740 exceeds 680 threshold", "DTI 28% below 43%"]
}

EXAMPLE 2:
Input: FICO 620, DTI 48%, LTV 95%
Output:
{
    "decision": "DENIED",
    "confidence": 0.92,
    "reasons": ["FICO 620 below 680 threshold", "DTI 48% exceeds 43%"]
}
```

**Production tip:** 2-3 examples. Cover clear approve, clear deny, and borderline.

---

## 3. Chain-of-Thought (CoT)

Force the LLM to evaluate each criterion explicitly before deciding.

```
Evaluate step by step:
Step 1: Check FICO against minimum (680)
Step 2: Calculate DTI and check against maximum (43%)
Step 3: Check LTV against limits
Step 4: Evaluate employment stability
Step 5: Check compensating factors
Step 6: Final decision based on ALL steps
```

**Critical for underwriting:** CoT is your audit trail. Regulators need to see WHY. Store the full reasoning, not just the decision.

---

## 4. Output Schema Enforcement

Three levels of strictness:

```
Level 1 (unreliable): "Please respond in JSON"
Level 2 (better):     "Respond ONLY with this exact JSON schema..."
Level 3 (best):       Pydantic + with_structured_output() [Day 5]
```

---

## 5. Negative Constraints

```
CONSTRAINTS:
- NEVER approve if any single criterion fails
- NEVER assume missing data — flag as INSUFFICIENT_DATA
- NEVER provide legal advice
- If DTI between 41-43%, flag for MANUAL_REVIEW
```

---

## Agent Observability — reasoning_trace

Every response includes step-by-step reasoning for audit:

```json
{
    "decision": "APPROVED",
    "reasoning_trace": {
        "step_1_fico": "FICO 740 >= 680 threshold. PASS.",
        "step_2_dti": "DTI 24% below 43%. PASS.",
        "step_3_ltv": "LTV 79.5% below 80%. No PMI. PASS.",
        "step_4_employment": "3 years stable. PASS."
    }
}
```

Three layers of observability (built across weeks):
- **Layer 1 (Week 1):** CoT reasoning in JSON response ← we built this
- **Layer 2 (Week 4):** LangGraph action trace (which tools, which agents)
- **Layer 3 (Week 5-6):** LangSmith traces + UI timeline

---

## SKILL.md vs .txt Files

```
.txt files (LLM reads at runtime):
  → System prompts defining agent behavior
  → "You are a Senior Underwriter. Rules: ..."

SKILL.md (humans read during development):
  → Documentation about how the directory works
  → "How to add a new prompt, versioning rules, testing process"
```

The LLM's knowledge comes from three runtime sources:
1. **System prompts** (.txt) → role, rules, constraints
2. **Tool schemas** (@tool decorator) → what functions it can call
3. **Graph structure** (LangGraph code) → how agents connect

SKILL.md helps your TEAM maintain all three.

---

## Assignments (Completed ✅)

- [x] Task 1: Three system prompts with reasoning_trace
- [x] Task 2: SKILL.md files for prompts/ and agents/
- [x] Task 3: Prompt loader utility with variable substitution
- [x] Task 4: Tested 3 applications against Bedrock — JSON consistent
- [x] Task 5: Unit tests for prompt loader