# Multi-Turn Conversation Explained

## Executive Summary

**Multi-turn conversations** allow an LLM to remember and use context from previous exchanges in the same chat.

---

## The Core Difference

### Single-Turn (What We've Done Before)
```python
messages = [
    SystemMessage(content="You are an underwriting agent..."),
    HumanMessage(content="Evaluate this loan: FICO 680, DTI 42%..."),
]
response = llm.invoke(messages)
# After this, context is lost. Next conversation starts fresh.
```

### Multi-Turn (New Concept)
```python
messages = [
    SystemMessage(content="You are an underwriting agent..."),
]

# Turn 1
messages.append(HumanMessage(content="What factors matter?"))
response1 = llm.invoke(messages)  # 2 messages total
messages.append(AIMessage(content=response1.content))

# Turn 2 - LLM REMEMBERS Turn 1
messages.append(HumanMessage(content="What if FICO is 680?"))
response2 = llm.invoke(messages)  # 4 messages total. LLM reads all 4.
messages.append(AIMessage(content=response2.content))

# Turn 3 - LLM REMEMBERS Turns 1 AND 2
messages.append(HumanMessage(content="And DTI is 42%?"))
response3 = llm.invoke(messages)  # 6 messages total. LLM reads all 6.
messages.append(AIMessage(content=response3.content))
```

---

## How It Works: The Message List Grows

**The golden rule:** Every call to `llm.invoke(messages)` sends **the entire message history**.

```
Turn 1:
  Call: llm.invoke([System, Human1])
  Response: AI1
  
Turn 2:
  Call: llm.invoke([System, Human1, AI1, Human2])  ← Full history!
  Response: AI2
  
Turn 3:
  Call: llm.invoke([System, Human1, AI1, Human2, AI2, Human3])  ← Full history!
  Response: AI3
```

Claude reads the **entire conversation** before generating each response.

---

## Concrete Example from bonus_multiturn.py

### Turn 1: Foundation
```
Human: "What are the main factors in mortgage underwriting?"
AI: "FICO score, debt-to-income ratio, income stability, 
     employment history, down payment, property value, 
     credit history, and collateral quality..."
```

### Turn 2: Build on Foundation
```
Human: "What if that applicant has a FICO of 680?"
AI: "680 is at the borderline of our minimum 680 requirement. 
     Given this score, I would:
     - Request additional documentation
     - Scrutinize debt-to-income ratio more carefully (must be < 43%)
     - Verify employment stability..."
```

**Key:** AI references the factors from Turn 1 and applies them to the FICO scenario.

### Turn 3: Add Complexity
```
Human: "And if DTI is 42%?"
AI: "With FICO 680 (borderline) AND DTI 42% (near maximum of 43%), 
     this is a high-risk application. I would recommend:
     - Conditional approval pending additional documentation
     - Stronger financial reserves required
     - Consider co-signer..."
```

**Key:** AI remembers BOTH the FICO discussion AND the general factors from Turn 1.

### Turn 4: Drill Deeper
```
Human: "What documentation would help approve this?"
AI: "Given the 680 FICO and 42% DTI combo mentioned earlier:
     - Last 2 years tax returns (essential)
     - 3+ months bank statements (to show reserves)
     - Letter of employment verification
     - Explanation letter for any credit issues..."
```

**Key:** AI references the specific scenario (680 FICO, 42% DTI) from Turn 3.

---

## Why This Matters

### 1. **Natural Conversation Flow**
Ask follow-ups naturally without repeating context.

### 2. **Refinement Across Turns**
```
Turn 1: "Approve or decline?"
Turn 2: "What if I reduce the loan amount?"
Turn 3: "What if I get a co-signer?"
```
The LLM refinds its decision based on new information.

### 3. **Complex Reasoning**
Build sophisticated reasoning across multiple exchanges:
```
Turn 1: Understand requirements
Turn 2: Apply to scenario A
Turn 3: Apply to scenario B
Turn 4: Compare scenarios A vs B (LLM remembers both!)
```

### 4. **Interactive Evaluation**
Not a one-shot API call. A collaborative conversation.

---

## Technical Implementation

```python
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# Initialize with system prompt
messages = [SystemMessage(content="You are...")]

# Turn 1
messages.append(HumanMessage(content="Question 1?"))
response = llm.invoke(messages)
messages.append(AIMessage(content=response.content))

# Turn 2
messages.append(HumanMessage(content="Question 2?"))
response = llm.invoke(messages)  # Sends ALL messages!
messages.append(AIMessage(content=response.content))

# Turn 3, 4, ... etc
```

---

## Cost Implications ⚠️

**Important:** Each turn costs more because you send more tokens.

```
Turn 1: 200 tokens (System + Human)
Turn 2: 400 tokens (System + Human + AI + Human) ← Doubled!
Turn 3: 600 tokens (System + 3x Human + 2x AI) ← Tripled!
Turn 4: 800 tokens (System + 4x Human + 3x AI) ← Quadrupled!

Total API cost: 200 + 400 + 600 + 800 = 2,000 tokens
vs. Single-turn x4: 200 + 200 + 200 + 200 = 800 tokens
```

**Multi-turn costs 2.5x more but provides richer context.**

---

## When to Use Multi-Turn vs Single-Turn

### Use Multi-Turn When:
- ✅ Interactive evaluation (human asks for clarifications)
- ✅ Refinement across questions (build up complex analysis)
- ✅ Conversation feels natural
- ✅ Cheaper than making independent predictions

### Use Single-Turn When:
- ✅ Batch evaluation (process 1000s of loan applications)
- ✅ No follow-up questions needed
- ✅ Cost is primary concern
- ✅ Each evaluation is independent

---

## Key Insight for Agents

**For your underwriting platform:**

- **Single-turn:** Fast, cheap. Best for automated loan screening.
- **Multi-turn:** Rich context. Best for exceptions committee review.

Example:
```python
# Automated screening (single-turn)
for application in all_applications:
    decision = evaluate_application(application)  # 1 API call

# Exceptions committee (multi-turn)
def interactive_review(application):
    chat_history = []
    while not decided:
        clarification = human_asks_question()
        decision = get_llm_assessment(chat_history, clarification)
        chat_history.append((clarification, decision))
```

---

## Running the Example

```bash
python -m src.exercises.bonus_multiturn
```

This runs 4 sequential conversations:
1. **Turn 1:** Ask about general underwriting factors
2. **Turn 2:** Scenario with 680 FICO (LLM remembers factors)
3. **Turn 3:** Add 42% DTI (LLM remembers FICO + factors)
4. **Turn 4:** Ask for documentation reqs (LLM remembers 680 FICO + 42% DTI)

Watch how each response builds on previous context! 🎯
