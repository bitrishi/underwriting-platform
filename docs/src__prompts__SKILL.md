# Prompts SKILL — System Prompt Management

## Overview

The `src/prompts/` directory contains all system and task-specific prompts for the mortgage underwriting platform. These prompts guide Bedrock Claude agents through loan evaluation workflows using production-grade prompt engineering techniques.

## Prompts Inventory

### 1. **underwriter.txt** — Master Orchestrator Prompt
**Purpose:** Guide the primary underwriting decision engine to evaluate loan applications end-to-end.

**Techniques Applied:**
- **Role Definition:** "You are an experienced mortgage underwriter..."
- **Chain-of-Thought (7-step):** Review profile → Check credit → Assess debt → Calculate ratios → Evaluate compensating factors → Check compliance → Provide decision
- **Few-Shot Examples (3):** APPROVED (760 FICO, 30% DTI) | CONDITIONAL (690 FICO, 40% DTI) | DECLINE (650 FICO, 45% DTI)
- **JSON Schema:** Enforced output with `decision`, `confidence`, `risk_level`, `reasons` fields
- **Negative Constraints (3):** Prohibits hallucination, missing documentation acceptance, and rule violation

**Output Schema:**
```json
{
  "decision": "APPROVED|CONDITIONAL_APPROVAL|DECLINE",
  "confidence": 0.0–1.0,
  "risk_level": "LOW|MEDIUM|HIGH",
  "reasons": ["reason1", "reason2", ...],
  "conditions": ["condition1", ...] // optional, for CONDITIONAL_APPROVAL
}
```

**Invoked By:** `src/exercises/day3_system_prompt.py`, `src/exercises/day4_prompt_test.py`

---

### 2. **fetch_data.txt** — Data Retrieval Agent Prompt
**Purpose:** Instruct the FetchData sub-agent to systematically gather required borrower information.

**Key Features:**
- **Ordered Retrieval:** Credit → Employment → Income → Debts → Assets
- **Completeness Tracking:** Identifies and reports missing or incomplete data fields
- **Validation Rules:** Rejects hallucinated values; requires documented sources
- **JSON Output:** Returns data completeness map with field-by-field status

**Output Schema:**
```json
{
  "credit_score": integer,
  "employment_status": "string",
  "annual_income": float,
  "monthly_debt": float,
  "assets": float,
  "missing_fields": ["field1", "field2", ...],
  "data_quality": "HIGH|MEDIUM|LOW"
}
```

**Invoked By:** `src/agents/fetch_data.py` (stub; to be implemented)

---

### 3. **risk_scoring.txt** — Risk Assessment Agent Prompt
**Purpose:** Calculate and categorize credit risk based on quantitative metrics.

**Key Metrics:**
- **DTI Calculation:** `monthly_debt / (annual_income / 12)`
- **FICO Risk Tiers:** <650=HIGH | 650–699=MEDIUM | 700+=LOW
- **LTV Computation:** `loan_amount / property_value`
- **Compensating Factors:** Down payment, cash reserves, stable employment

**Output Schema:**
```json
{
  "dti_ratio": 0.0–1.0,
  "fico_risk_category": "LOW|MEDIUM|HIGH",
  "ltv_ratio": 0.0–1.0,
  "compensating_factors": ["factor1", ...],
  "risk_score": 1–100,
  "recommendation": "APPROVE|REVIEW|DECLINE"
}
```

**Invoked By:** `src/agents/risk_scoring.py` (stub; to be implemented)

---

## Design Rules & Best Practices

### Prompt Structure
1. **Role Definition (Paragraph 1)**
   - Clearly state the agent's expertise and responsibility
   - Example: "You are an experienced mortgage underwriter with 20 years of lending authority..."

2. **Task Context (Paragraph 2)**
   - Explain what the agent is evaluating and why
   - Include business rules (FICO ≥680, DTI <43%)

3. **Chain-of-Thought Steps (Paragraph 3)**
   - Break evaluation into 5–7 sequential steps
   - Each step narrows the decision space
   - Include reasoning-before-judgment logic

4. **Few-Shot Examples (Paragraph 4)**
   - Include 3+ diverse complete examples
   - Cover approve, deny, and edge case scenarios
   - Show both input format and expected output

5. **Output Schema (Paragraph 5)**
   - Provide explicit JSON structure with required fields
   - Define field types, value ranges, and enumerations
   - Include field validation rules (e.g., confidence ∈ [0, 1])

6. **Negative Constraints (Paragraph 6)**
   - List what the agent MUST NOT do
   - Prevent hallucination, rule violations, unsupported inferences
   - Frame as prohibitions not permissions

### Versioning Strategy
- **Semantic Versioning:** `vX.Y.Z` where X=major policy changes, Y=prompt text refinements, Z=punctuation/clarity fixes
- **Location:** Document versions in comments at prompt file top
- **Changelog:** Maintain in `CHANGELOG.md` when meaningful updates occur
- **Current Version:** All prompts are v1.0.0 (production-ready)

### Temperature & Parameters
- **underwriter.txt:** temperature=0 (deterministic lending decisions required)
- **fetch_data.txt:** temperature=0 (exact data retrieval)
- **risk_scoring.txt:** temperature=0 (calculation consistency)
- **Exploration Prompts:** temperature=0.7 for explanatory variants

---

## Prompt Loader Utility

### Function: `load_prompt(agent_name: str) -> str`
**Purpose:** Load prompt text from file with automatic path resolution.

**Parameters:**
- `agent_name` (str): Prompt base name without `.txt` extension (e.g., `"underwriter"`)

**Returns:**
- Prompt text as string, stripped of leading/trailing whitespace

**Raises:**
- `FileNotFoundError`: If prompt file doesn't exist; includes full path in error message for debugging

**Example:**
```python
from src.utils.prompt_loader import load_prompt

underwriter_prompt = load_prompt("underwriter")
print(underwriter_prompt)  # Prints full system prompt text
```

### Function: `load_prompt_with_variables(agent_name: str, **kwargs) -> str`
**Purpose:** Load prompt and substitute template variables using Python's `.format()`.

**Parameters:**
- `agent_name` (str): Prompt base name
- `**kwargs`: Variable names and values (e.g., `borrower_name="Alice"`, `loan_amount=250000`)

**Returns:**
- Prompt text with all `{variable_name}` placeholders replaced

**Raises:**
- `FileNotFoundError`: If prompt file doesn't exist
- `KeyError`: If required variable placeholder in prompt is not provided in kwargs

**Example:**
```python
from src.utils.prompt_loader import load_prompt_with_variables

prompt = load_prompt_with_variables(
    "underwriter",
    borrower_name="Alice Smith",
    loan_amount=250000
)
```

---

## Integration Patterns

### System Message Pattern
```python
from langchain_core.messages import SystemMessage, HumanMessage
from src.config.bedrock import create_llm
from src.utils.prompt_loader import load_prompt

llm = create_llm(temperature=0, max_tokens=1024)
system_prompt = load_prompt("underwriter")
system_msg = SystemMessage(content=system_prompt)
human_msg = HumanMessage(content="Evaluate this application: ...")
response = llm.invoke([system_msg, human_msg])
```

### Multi-Turn Conversation Pattern
```python
from langchain_core.messages import AIMessage

messages = [system_msg]

# Turn 1
turn_1 = HumanMessage(content="Can you approve this?")
messages.append(turn_1)
response_1 = llm.invoke(messages)
messages.append(AIMessage(content=response_1.content))

# Turn 2
turn_2 = HumanMessage(content="What if the applicant has 12 months savings?")
messages.append(turn_2)
response_2 = llm.invoke(messages)
# Full history automatically sent; LLM maintains context
```

---

## How Agents Discover & Use Prompts

### Agent Discovery Mechanism
Production-grade agents use **convention-based discovery** where:

1. **Prompt Naming Convention:** Agent name maps directly to prompt file
   ```
   FetchData Agent → load_prompt("fetch_data") → src/prompts/fetch_data.txt
   RiskScoring Agent → load_prompt("risk_scoring") → src/prompts/risk_scoring.txt
   Orchestrator Agent → load_prompt("underwriter") → src/prompts/underwriter.txt
   ```

2. **Automatic Path Resolution:** The loader uses `pathlib.Path` to find prompts relative to source structure
   ```python
   # Loader automatically finds: {project_root}/src/prompts/{agent_name}.txt
   prompt = load_prompt("underwriter")  # No path specified!
   ```

3. **Configuration-Driven Behavior:** Agents read environment variables to select which LLM and temperature to use
   ```python
   # Each agent checks configuration
   llm = create_llm(
       temperature=0,  # Deterministic for lending decisions
       max_tokens=1024
   )
   ```

### Agent Initialization Pattern
**Example: How the Orchestrator Agent discovers and loads its prompt**

```python
# src/agents/orchestrator.py
from src.config.bedrock import create_llm
from src.utils.prompt_loader import load_prompt
from langchain_core.messages import SystemMessage, HumanMessage

class OrchestratorAgent:
    """Master underwriting agent."""
    
    def __init__(self):
        """
        Agent initialization: automatically discovers prompt configuration.
        This pattern works for all agents in the system.
        """
        # Step 1: Load prompt by agent name (convention-based discovery)
        self.system_prompt = load_prompt("underwriter")
        
        # Step 2: Create LLM client with production settings
        self.llm = create_llm(
            temperature=0,           # Deterministic decisions required
            max_tokens=1024          # Reasonable response length
        )
    
    def evaluate(self, application_data: dict) -> dict:
        """
        Evaluate a loan application using discovered prompt.
        """
        # Step 3: Use the discovered prompt in message invocation
        system_msg = SystemMessage(content=self.system_prompt)
        human_msg = HumanMessage(content=self._format_application(application_data))
        
        # Step 4: Invoke LLM (prompt guides the decision)
        response = self.llm.invoke([system_msg, human_msg])
        return self._parse_response(response.content)
    
    def _format_application(self, data: dict) -> str:
        """Format application into template for evaluation."""
        return f"FICO: {data['fico']}\nDTI: {data['dti']}\n..."
    
    def _parse_response(self, text: str) -> dict:
        """Parse LLM response (should be JSON per prompt schema)."""
        import json
        return json.loads(text)
```

### Production Agent Discovery Workflow

**Flow: How production agents know to fetch prompts**

```
┌─────────────────────────────────────────────────────────┐
│ 1. AGENT STARTUP                                        │
│    new OrchestratorAgent()                              │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 2. PROMPT DISCOVERY (Convention-Based)                 │
│    Agent name: "orchestrator"                           │
│    → Infer prompt name: "underwriter"                   │
│    → Build path: src/prompts/underwriter.txt            │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 3. LOAD PROMPT                                          │
│    load_prompt("underwriter")                           │
│    ├─ Resolve file path via pathlib                     │
│    ├─ Read file contents                                │
│    └─ Return prompt text to agent                       │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 4. LLM CONFIGURATION                                    │
│    create_llm(temperature=0, max_tokens=1024)           │
│    ├─ Read AWS credentials from environment             │
│    ├─ Initialize Bedrock ChatBedrock client             │
│    └─ Return configured LLM instance                    │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 5. AGENT READY                                          │
│    Agent now has:                                       │
│    ├─ system_prompt (from file)                         │
│    └─ llm (configured client)                           │
│                                                         │
│    Agent is ready to process applications               │
└─────────────────────────────────────────────────────────┘
```

### Multi-Agent Discovery (Parallel Sub-Agents)

**Example: How orchestrator discovers all sub-agent prompts**

```python
# src/agents/orchestrator.py
import asyncio
from src.agents.fetch_data import FetchDataAgent
from src.agents.risk_scoring import RiskScoringAgent
from src.agents.doc_review import DocumentReviewAgent

class OrchestratorAgent:
    def __init__(self):
        # Orchestrator discovers its own prompt
        self.system_prompt = load_prompt("underwriter")
        self.llm = create_llm(temperature=0)
        
        # Orchestrator also initializes sub-agents
        # Each sub-agent independently discovers its own prompt!
        self.fetch_data_agent = FetchDataAgent()      # will load fetch_data.txt
        self.risk_scoring_agent = RiskScoringAgent()  # will load risk_scoring.txt
        self.doc_review_agent = DocumentReviewAgent() # will load doc_review.txt
    
    async def evaluate_with_subagents(self, app_data: dict):
        """
        Each sub-agent independently discovers and loads its prompt.
        """
        # All 3 agents discover their prompts in parallel
        results = await asyncio.gather(
            self.fetch_data_agent.execute(app_data),      # Uses fetch_data.txt
            self.risk_scoring_agent.execute(app_data),    # Uses risk_scoring.txt
            self.doc_review_agent.execute(app_data),      # Uses doc_review.txt
        )
        return results
```

**Each agent discovers independently:**
- FetchDataAgent independently loads `src/prompts/fetch_data.txt`
- RiskScoringAgent independently loads `src/prompts/risk_scoring.txt`
- DocumentReviewAgent independently loads `src/prompts/doc_review.txt`
- No configuration needed beyond the prompt file name

### Why This Architecture?

| Benefit | How It Works |
|---------|-------------|
| **No Configuration Files** | Convention-based discovery: agent name → prompt file name |
| **Auto Path Resolution** | `pathlib.Path` finds prompts regardless of working directory |
| **Scalability** | New agents added without changing configuration |
| **Testability** | Agents can load test prompts by overriding name |
| **Modularity** | Each agent owns its prompt discovery logic |
| **Production-Ready** | Environment variables control LLM selection (boto3 credentials) |

### Example: Adding a New Agent with Automatic Discovery

```python
# src/agents/new_agent.py
from src.config.bedrock import create_llm
from src.utils.prompt_loader import load_prompt

class NewAgent:
    def __init__(self):
        # Auto-discovers prompt just by naming convention!
        # Agent looks for: src/prompts/new_agent.txt
        self.system_prompt = load_prompt("new_agent")
        self.llm = create_llm(temperature=0)
    
    def execute(self, data: dict) -> dict:
        from langchain_core.messages import SystemMessage, HumanMessage
        response = self.llm.invoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=str(data))
        ])
        return json.loads(response.content)

# That's it! No configuration, no setup beyond creating the prompt file.
# Production-grade agent with automatic prompt discovery.
```

---

## Testing & Validation

### Prompt Testing Exercise (`day4_prompt_test.py`)
**Test Framework:** Validates prompts against real Bedrock responses with 3 standard applications:

1. **Alice (Clear Approve):** FICO 760, DTI 30%
2. **Bob (Clear Deny):** FICO 640, DTI 43.75%
3. **Carol (Borderline):** FICO 690, DTI 36%

**Validation Checks:**
- JSON schema compliance (required fields present, types correct)
- Decision consistency (same application always produces same decision at temperature=0)
- Confidence bounds (0.0 ≤ confidence ≤ 1.0)
- Risk level enumeration (LOW|MEDIUM|HIGH)
- Reasoning trace extraction (displays step-by-step thinking)

**Running Tests:**
```bash
python -m src.exercises.day4_prompt_test
```

**Sample Output:**
```
======================================================================
🧪 Day 4: Prompt Testing Exercise
======================================================================

Testing 3 applications with the production Underwriter prompt
Expected outcomes: APPROVE, DENY, CONDITIONAL

📋 Loading prompts...
✅ Underwriter prompt loaded
⏳ Invoking Bedrock...

──────────────────────────────────────────────────────────────────────
Application: Alice (Clear Approve)
──────────────────────────────────────────────────────────────────────
Decision: APPROVED
Confidence: 95%
Risk Level: LOW

Reasons:
  • Good FICO score (760)
  • Acceptable DTI (30%)
  • Loan amount reasonable relative to income

📝 Reasoning Trace:
──────────────────────────────────────────────────────────────────────
  1. Review borrower profile: High income, stable employment
  2. Check credit score: 760 FICO is excellent
  3. Assess debt obligations: DTI 30% is acceptable
  4. Calculate qualifying ratios: All within guidelines
  5. Evaluate compensating factors: Strong financial position
  6. Check regulatory compliance: All requirements met
  7. Provide decision: APPROVED

📋 Full JSON Response:
──────────────────────────────────────────────────────────────────────
{
  "decision": "APPROVED",
  "confidence": 0.95,
  "risk_level": "LOW",
  "reasons": [
    "Good FICO score (760)",
    "Acceptable DTI (30%)",
    "Loan amount reasonable relative to income"
  ]
}

Expected: APPROVED ✅
```

### Unit Tests (`tests/test_prompts.py`)
**Coverage (20 tests):**
- Prompt file existence and non-empty content
- `load_prompt()` error handling
- `load_prompt_with_variables()` substitution accuracy
- Role definitions (all prompts define expertise)
- Output format specifications (JSON schema, fields)
- Business constraints and rules
- Domain-specific metrics (DTI, FICO, LTV for each agent)

**Running Tests:**
```bash
pytest tests/test_prompts.py -v
```

---

## Adding a New Prompt

### Step 1: Create Prompt File
```bash
touch src/prompts/new_agent.txt
```

### Step 2: Apply Production Technique Template
**Mandatory structure:**
1. Role definition paragraph
2. Task explanation with business rules
3. 5–7 step Chain-of-Thought pipeline
4. 3+ Few-shot examples with input/output pairs
5. Explicit JSON output schema definition
6. 3+ Negative constraints

### Step 3: Load in Agent
```python
from src.utils.prompt_loader import load_prompt

def new_agent():
    prompt = load_prompt("new_agent")
    # Use prompt with LLM...
```

### Step 4: Add Tests
Update `tests/test_prompts.py`:
```python
def test_load_prompt_new_agent_exists():
    prompt = load_prompt("new_agent")
    assert len(prompt) > 50
    assert "key_phrase" in prompt.lower()
```

### Step 5: Run Full Prompt Suite
```bash
pytest tests/test_prompts.py -v
python -m src.exercises.day4_prompt_test
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `FileNotFoundError: 'underwriter' not found` | Verify file exists: `ls src/prompts/underwriter.txt` |
| `KeyError: '{variable_name}'` in `load_prompt_with_variables()` | Ensure all format variables in prompt are provided as kwargs |
| JSON parsing errors in LLM responses | Check prompt includes explicit schema; add markdown code block delimiters if needed |
| Non-deterministic outputs at temperature=0 | Verify LLM initialized with `temperature=0`, not default value |
| Inconsistent decisions across runs | Check prompt Few-shot examples clearly demonstrate decision boundaries |

---

## Quick Links
- **Prompt Loader Utility:** [src/utils/prompt_loader.py](../utils/prompt_loader.py)
- **Bedrock Integration:** [src/config/bedrock.py](../config/bedrock.py)
- **Test Suite:** [tests/test_prompts.py](../../tests/test_prompts.py)
- **Day 4 Exercise:** [src/exercises/day4_prompt_test.py](../exercises/day4_prompt_test.py)
- **LangChain Messages API:** [LangChain Docs](https://api.python.langchain.com/en/latest/messages/)
4. Prompts are versioned — never edit in place, create new versions
5. Every prompt change is tested against the eval dataset before deploy

## How Prompts Are Loaded
```python
from pathlib import Path

def load_prompt(agent_name: str) -> str:
    """Load system prompt from prompts directory."""
    path = Path(__file__).parent / f"{agent_name}.txt"
    return path.read_text()
```