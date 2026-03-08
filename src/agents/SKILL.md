# Agents SKILL — Multi-Agent Underwriting Architecture

## Overview

The `src/agents/` directory implements a multi-agent orchestration system where specialized agents collaborate to evaluate mortgage applications. The **Orchestrator Agent** coordinates parallel sub-agents (FetchData, RiskScoring, DocumentReview, Compliance) to produce final underwriting decisions.

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator Agent                                         │
│  (Master coordinator, final decision)                       │
└────┬──────┬──────────┬──────────────┬──────────────────────┘
     │      │          │              │
     ▼      ▼          ▼              ▼
┌──────────┬──────────┬────────────┬──────────────┐
│ Fetch    │ Risk     │ Document   │ Compliance   │
│ Data     │ Scoring  │ Review     │ Check        │
│ Agent    │ Agent    │ Agent      │ Agent        │
├──────────┼──────────┼────────────┼──────────────┤
│ Retrieves│ Scores   │ Validates  │ Ensures      │
│ borrower │ credit   │ documents  │ regulatory   │
│ info     │ risk     │ & income   │ compliance   │
└──────────┴──────────┴────────────┴──────────────┘
```

---

## Agent Inventory

### 1. **Orchestrator Agent**
**File:** `src/agents/orchestrator.py`  
**Status:** ✅ Production-ready  
**Purpose:** Master decision engine that coordinates evaluation of loan applications

#### Key Functions

##### `evaluate_applications(applications: list[LoanApplication]) -> list[LoanDecision]`
**Responsibility:**
- Accept batch of loan applications
- Apply eligibility rules using list comprehension
- Generate structured decisions with confidence scores and reasoning
- Return deterministic JSON decisions

**Eligibility Rules:**
- FICO score ≥ 680
- Debt-to-Income ratio < 0.43
- Reasonable loan-to-income ratio (≤ 5x annual income)

**Output:**
```python
@dataclass
class LoanDecision:
    decision: bool  # True=Approved, False=Denied
    confidence: float  # 0.0–1.0
    reasons: list[str]  # Explanation factors
```

**Implementation Details:**
- Uses `app.is_eligible()` to check rule compliance
- Assigns confidence: 0.85 (eligible), 0.75 (ineligible)
- Builds detailed reason list via `_build_reasons()`

**Example Usage:**
```python
from src.agents.orchestrator import evaluate_applications

apps = [LoanApplication(...), LoanApplication(...)]
decisions = evaluate_applications(apps)
for decision in decisions:
    print(f"Decision: {decision.decision}, Confidence: {decision.confidence}")
```

##### `_build_reasons(app: LoanApplication) -> list[str]`
**Responsibility:**
- Generate human-readable evaluation factors
- Assess FICO score quality
- Calculate and evaluate DTI
- Judge loan amount reasonableness

**Returns:**
- List of 3–4 reason strings explaining the decision

**Rules Applied:**
- FICO ≥700 = "Good FICO score"
- FICO <700 = "Low FICO score"
- DTI <0.36 = "Acceptable DTI"
- DTI ≥0.36 = "High DTI"
- Loan ≤ 0.5× annual income = "Loan amount reasonable"

---

### 2. **FetchData Agent**
**File:** `src/agents/fetch_data.py`  
**Status:** 🔰 Stub (to be implemented)  
**Purpose:** Retrieve and validate all required borrower information

#### Planned Implementation

**Responsibilities:**
- Query credit bureau for FICO score
- Retrieve employment verification
- Gather income documentation (tax returns, pay stubs, W-2s)
- Collect debt inventory (mortgages, auto loans, credit cards, student loans)
- Aggregate asset information (savings, investments, real estate)
- Track missing vs. complete data fields

**Tools Used:**
- Bedrock Claude with `fetch_data.txt` system prompt
- LangChain tool definitions for credit bureau, employment, income verification

**Input Schema:**
```json
{
  "borrower_id": "string",
  "borrower_name": "string",
  "ssn": "string (masked or encrypted)"
}
```

**Output Schema:**
```json
{
  "credit_score": 300–850,
  "employment_status": "EMPLOYED|SELF_EMPLOYED|UNEMPLOYED|RETIRED",
  "annual_income": float,
  "monthly_debt": float,
  "assets": {
    "liquid": float,
    "real_estate": float,
    "investments": float
  },
  "missing_fields": ["field1", "field2", ...],
  "data_quality": "HIGH|MEDIUM|LOW",
  "sources": ["credit_bureau", "tax_return", ...]
}
```

**Invocation Pattern:**
```python
# From orchestrator, invoke sub-agent concurrently
fetched_data = await fetch_data_agent.execute(borrower_id="APP-12345")
```

**Concurrency:** Runs in parallel with RiskScoring and DocumentReview agents

---

### 3. **RiskScoring Agent**
**File:** `src/agents/risk_scoring.py`  
**Status:** 🔰 Stub (to be implemented)  
**Purpose:** Calculate quantitative credit risk metrics and categorize

#### Planned Implementation

**Responsibilities:**
- Compute Debt-to-Income (DTI) ratio from fetched data
- Categorize FICO score into risk tiers
- Calculate Loan-to-Value (LTV) if property appraisal available
- Identify compensating factors (down payment %, cash reserves, employment stability)
- Generate numeric risk score (1–100)
- Recommend approval, review, or decline

**Tools Used:**
- Bedrock Claude with `risk_scoring.txt` system prompt
- Mathematical calculator for precise ratio computations

**Input Schema:**
```json
{
  "fico_score": 300–850,
  "annual_income": float,
  "monthly_debt": float,
  "down_payment": float,
  "loan_amount": float,
  "property_value": float
}
```

**Output Schema:**
```json
{
  "dti_ratio": 0.0–1.0,
  "fico_category": "LOW|MEDIUM|HIGH",
  "ltv_ratio": 0.0–1.0,
  "compensating_factors": ["12mo_reserves", "30%_down", "stable_employment"],
  "risk_score": 1–100,
  "recommendation": "APPROVE|REVIEW|DECLINE"
}
```

**Risk Tiers:**
| FICO | LTV | DTI | Recommendation |
|------|-----|-----|---|
| 740+ | ≤80% | ≤36% | APPROVE |
| 700–739 | ≤85% | ≤41% | REVIEW (with compensators) |
| 660–699 | ≤75% | ≤39% | REVIEW |
| <660 | ≤70% | ≤36% | DECLINE |

**Invocation Pattern:**
```python
risk_assessment = await risk_scoring_agent.execute(
    fico_score=720,
    annual_income=120000,
    monthly_debt=2000,
    loan_amount=250000,
    property_value=350000
)
```

**Concurrency:** Runs in parallel with FetchData and DocumentReview agents

---

### 4. **DocumentReview Agent**
**File:** `src/agents/doc_review.py`  
**Status:** 🔰 Stub (to be implemented)  
**Purpose:** Validate completeness and authenticity of submitted documentation

#### Planned Implementation

**Responsibilities:**
- Verify required documents have been submitted (tax returns, pay stubs, bank statements, etc.)
- Check document dates are current (tax returns within 2 years, pay stubs within 60 days)
- Cross-reference document consistency (income on pay stub matches tax return)
- Flag missing or suspicious documents
- Rate document quality (COMPLETE, PARTIAL, INSUFFICIENT)

**Tools Used:**
- Bedrock Claude for document content analysis
- Document validation rules engine

**Input Schema:**
```json
{
  "documents_submitted": [
    {"type": "tax_return", "year": 2024, "pages": 5},
    {"type": "pay_stub", "current": true, "date": "2024-03-01"}
  ]
}
```

**Output Schema:**
```json
{
  "documents_complete": true|false,
  "missing_documents": ["type1", "type2"],
  "inconsistencies": ["type1 vs type2 income mismatch"],
  "document_quality": "COMPLETE|PARTIAL|INSUFFICIENT",
  "recommendation": "APPROVE|NEEDS_SUPPLEMENTAL_DOCS|DECLINE"
}
```

**Invocation Pattern:**
```python
doc_validation = await doc_review_agent.execute(
    borrower_id="APP-12345",
    submitted_docs=doc_list
)
```

**Concurrency:** Runs in parallel with FetchData and RiskScoring agents

---

### 5. **Compliance Agent**
**File:** `src/agents/compliance.py`  
**Status:** 🔰 Stub (to be implemented)  
**Purpose:** Ensure underwriting decision complies with regulatory requirements

#### Planned Implementation

**Responsibilities:**
- Verify qualified mortgage (QM) rule compliance
- Check interest rate reasonableness per market conditions
- Validate debt obligation calculations per Regulation Z
- Ensure fair lending practices (no discrimination detected)
- Check for adverse action documentation requirements
- Flag regulatory red flags (structuring, sanctions list)

**Tools Used:**
- Bedrock Claude for regulatory interpretation
- Rules engine for QM, Reg Z, fair lending checks

**Input Schema:**
```json
{
  "applicant_demographics": {
    "age": int,
    "race": "OPTIONAL_IF_PROVIDED",
    "gender": "OPTIONAL_IF_PROVIDED"
  },
  "loan_terms": {
    "rate": float,
    "term_months": int,
    "total_debt_obligation": float
  },
  "debt_to_income": float,
  "decision": "APPROVED|CONDITIONAL|DECLINE"
}
```

**Output Schema:**
```json
{
  "qm_compliant": true|false,
  "rate_reasonable": true|false,
  "fair_lending_compliant": true|false,
  "regulatory_flags": ["flag1", "flag2"],
  "recommendation": "PROCEED|CORRECT_AND_PROCEED|DO_NOT_PROCEED"
}
```

**Invocation Pattern:**
```python
compliance_check = await compliance_agent.execute(
    applicant=app,
    decision=decision,
    loan_terms=terms
)
```

**Concurrency:** Runs after orchestrator decision (serial, not parallel)

---

## Agent Patterns & Implementation

### Pattern 1: Convention-Based Prompt Discovery
**Purpose:** Agents automatically discover their prompts using naming convention
**Mechanism:** Agent name maps directly to prompt file name

**Pattern Flow:**
```
Agent Class Name    →    Prompt File Name    →    File Location
────────────────────────────────────────────────────────────────
OrchestratorAgent   →    "underwriter"       →    src/prompts/underwriter.txt
FetchData(Agent)    →    "fetch_data"        →    src/prompts/fetch_data.txt
RiskScoring(Agent)  →    "risk_scoring"      →    src/prompts/risk_scoring.txt
DocumentReview(Ag)  →    "doc_review"        →    src/prompts/doc_review.txt
Compliance(Agent)   →    "compliance"        →    src/prompts/compliance.txt
```

**Production Implementation:**
```python
from src.utils.prompt_loader import load_prompt
from src.config.bedrock import create_llm
from langchain_core.messages import SystemMessage, HumanMessage

class OrchestratorAgent:
    """Master underwriting agent with automatic prompt discovery."""
    
    def __init__(self):
        # Step 1: Discover prompt by convention
        # Agent knows to look for "underwriter.txt" without explicit path
        self.system_prompt = load_prompt("underwriter")
        
        # Step 2: Initialize LLM with production settings
        self.llm = create_llm(temperature=0, max_tokens=1024)
    
    def evaluate(self, app_data: dict) -> dict:
        """Evaluate loan application using discovered prompt."""
        # Step 3: Use discovered prompt in message
        system_msg = SystemMessage(content=self.system_prompt)
        human_msg = HumanMessage(content=self._format_app(app_data))
        
        # Step 4: Invoke LLM (prompt guides decision)
        response = self.llm.invoke([system_msg, human_msg])
        return self._parse_response(response.content)
    
    def _format_app(self, data: dict) -> str:
        """Format application data for LLM."""
        return f"FICO: {data['fico']}\nDTI: {data['dti']:.2%}\n..."
    
    def _parse_response(self, text: str) -> dict:
        """Parse JSON response per prompt schema."""
        import json
        return json.loads(text)
```

### Pattern 2: Multi-Agent Discovery (Parallel Execution)
**Purpose:** Orchestrator discovers sub-agent prompts in parallel
**Mechanism:** Each sub-agent independently loads its own prompt

**Example: Orchestrator with 3 sub-agents**
```python
import asyncio
from src.agents.fetch_data import FetchDataAgent
from src.agents.risk_scoring import RiskScoringAgent
from src.agents.doc_review import DocumentReviewAgent

class OrchestratorAgent:
    def __init__(self):
        # Orchestrator discovers its prompt
        self.system_prompt = load_prompt("underwriter")
        self.llm = create_llm(temperature=0)
        
        # Initialize sub-agents
        # Each discovers its own prompt independently:
        self.fetch_agent = FetchDataAgent()      # loads fetch_data.txt
        self.risk_agent = RiskScoringAgent()     # loads risk_scoring.txt
        self.doc_agent = DocumentReviewAgent()   # loads doc_review.txt
    
    async def evaluate_with_subagents(self, app):
        """
        Coordinate 3 sub-agents in parallel.
        Each agent uses its own discovered prompt.
        """
        # All discover their prompts and execute in parallel
        fetch_result, risk_result, doc_result = await asyncio.gather(
            self.fetch_agent.execute(app),    # Uses fetch_data.txt
            self.risk_agent.execute(app),     # Uses risk_scoring.txt
            self.doc_agent.execute(app),      # Uses doc_review.txt
        )
        
        # Synthesize results using orchestrator prompt
        return self._synthesize(fetch_result, risk_result, doc_result)
    
    def _synthesize(self, fetch, risk, doc) -> dict:
        """Combine sub-agent results."""
        return {
            "data": fetch,
            "risk_assessment": risk,
            "doc_validation": doc,
            "final_decision": "APPROVED" if all([fetch, risk, doc]) else "DECLINE"
        }
```

### Pattern 3: Sequential Orchestration (Current Implementation)
**Used by:** Orchestrator → checks rules locally  
**Execution:** Single-threaded, synchronous  
**Example:**
```python
def evaluate_applications(applications):
    return [
        LoanDecision(
            decision=app.is_eligible(),
            confidence=0.85 if app.is_eligible() else 0.75,
            reasons=_build_reasons(app)
        )
        for app in applications
    ]
```

### Pattern 4: LangGraph State Machine (Future)
**Purpose:** Manage complex decision branching with conditional sub-agent invocation
**Benefits:** Explicit workflow for multi-step decisions

**Example with conditional branching:**
```python
from langgraph.graph import StateGraph

class ApplicationEvaluationState(TypedDict):
    """State passed between agents."""
    application: dict
    fetch_result: dict
    risk_assessment: dict
    doc_validation: dict
    decision: str

# Create workflow graph
graph = StateGraph(ApplicationEvaluationState)

# Add nodes (agents)
graph.add_node("fetch_data", fetch_data_agent.execute)
graph.add_node("risk_scoring", risk_scoring_agent.execute)
graph.add_node("doc_review", doc_review_agent.execute)
graph.add_node("final_decision", orchestrator_agent.execute)

# Add edges
graph.add_edge("fetch_data", "risk_scoring")
graph.add_conditional_edges(
    "risk_scoring",
    lambda state: "doc_review" if state["risk_assessment"]["risk_score"] > 50 else "final_decision"
)
graph.add_edge("doc_review", "final_decision")

# Compile and use
workflow = graph.compile()
result = workflow.invoke({"application": app_data})
```

---

## Agent Prompt Discovery Workflow

**How production agents know when and where to fetch prompts:**

```
┌────────────────────────────────────────────────────────────┐
│ AGENT STARTUP                                              │
│ new OrchestratorAgent()  new FetchDataAgent()  etc.        │
└──────────────┬────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────┐
│ PROMPT DISCOVERY (Convention-Based, No Config Needed)     │
│                                                            │
│ Each agent infers prompt name from class intent:           │
│ • Orchestrator → "underwriter"                             │
│ • FetchData → "fetch_data"                                 │
│ • RiskScoring → "risk_scoring"                             │
│ • DocumentReview → "doc_review"                            │
│ • Compliance → "compliance"                                │
│                                                            │
│ Build file path: src/prompts/{prompt_name}.txt             │
└──────────────┬────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────┐
│ PROMPT LOADER (load_prompt utility)                        │
│                                                            │
│ For each agent:                                            │
│ 1. Resolve file path using pathlib.Path                    │
│ 2. Check file exists (raise FileNotFoundError if not)      │
│ 3. Read file contents (UTF-8 encoded)                      │
│ 4. Return prompt text to agent                             │
│                                                            │
│ Agent now has: self.system_prompt = "full prompt text..."  │
└──────────────┬────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────┐
│ LLM INITIALIZATION (create_llm factory)                    │
│                                                            │
│ Each agent also discovers LLM config:                      │
│ 1. Read AWS credentials from environment                   │
│ 2. Initialize Bedrock ChatBedrock client                   │
│ 3. Set temperature (0 for deterministic decisions)         │
│ 4. Set max_tokens (1024 for typical decisions)             │
│                                                            │
│ Agent now has: self.llm = ChatBedrock(...)                 │
└──────────────┬────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────┐
│ AGENT READY FOR EXECUTION                                  │
│                                                            │
│ Agent initialization complete:                             │
│ ✓ Discovered and loaded system prompt                      │
│ ✓ Configured LLM client                                    │
│ ✓ Ready to process applications                            │
│                                                            │
│ No explicit configuration files needed!                    │
│ No hardcoded paths!                                        │
│ No manual setup!                                           │
└────────────────────────────────────────────────────────────┘
```

---

## Agent Tools Integration

### Currently Integrated
- **Bedrock API** (LangChain ChatBedrock)
- **Prompt Loader** (auto-discovers prompts)
- **LoanApplication Model** for data access
- **LoanDecision Dataclass** for structured output
- **@log_call Decorator** for function instrumentation

### Planned Tools (Sub-Agents)
Each sub-agent will extend the discovery pattern with tools

#### FetchData Agent Tools
```python
class FetchDataAgent:
    def __init__(self):
        self.system_prompt = load_prompt("fetch_data")
        self.llm = create_llm(temperature=0)
        # Agent will use these tools:
        self.tools = {
            "get_credit_score": CreditBureauTool(),      # Returns FICO
            "verify_employment": EmploymentTool(),        # Returns employer info
            "retrieve_income": IncomeTool(),               # Returns tax docs
            "fetch_debts": DebtTool(),                     # Returns debt list
            "aggregate_assets": AssetsTool(),              # Returns asset values
        }
    
    async def execute(self, app_id: str) -> dict:
        """Execute with tools defined by prompt."""
        # Prompt will instruct which tools to use in what order
        # Tools are invoked based on prompt guidance
        pass
```

#### RiskScoring Agent Tools
```python
class RiskScoringAgent:
    def __init__(self):
        self.system_prompt = load_prompt("risk_scoring")
        self.llm = create_llm(temperature=0)
        self.tools = {
            "calculate_dti": DTICalculator(),
            "categorize_fico": FICOCategorizer(),
            "apply_compensators": CompensatingFactorsTool(),
            "score_risk": RiskScoringTool(),
        }
```

#### DocumentReview Agent Tools
```python
class DocumentReviewAgent:
    def __init__(self):
        self.system_prompt = load_prompt("doc_review")
        self.llm = create_llm(temperature=0)
        self.tools = {
            "validate_completeness": DocCompletenessValidator(),
            "check_dates": DocumentDateValidator(),
            "cross_validate": AmountCrossValidator(),
        }
```

---

## Pattern 3: Sequential Orchestration (Current)
**Used by:** Orchestrator → checks rules locally  
**Execution:** Single-threaded, synchronous  
**Example:**
```python
def evaluate_applications(applications):
    return [
        LoanDecision(
            decision=app.is_eligible(),
            confidence=0.85 if app.is_eligible() else 0.75,
            reasons=_build_reasons(app)
        )
        for app in applications
    ]
```

---

## Agent Tools Integration

### Currently Integrated
- **Bedrock API** (LangChain ChatBedrock)
- **Prompt Loader** (auto-discovers agent prompts)
- **LoanApplication Model** for data access
- **LoanDecision Dataclass** for structured output
- **@log_call Decorator** for function instrumentation

### Planned Tools (Sub-Agents Extension)
When agents are enhanced with function calling, each will use domain-specific tools:

#### FetchData Tools
- `get_credit_score(ssn: str) -> int`
- `verify_employment(employer_id: str) -> dict`
- `retrieve_income_docs(borrower_id: str) -> list[Document]`
- `fetch_debt_accounts(borrower_id: str) -> list[DebtAccount]`
- `aggregate_assets(borrower_id: str) -> dict`

#### RiskScoring Tools
- `calculate_dti(monthly_debt: float, annual_income: float) -> float`
- `categorize_fico(score: int) -> str`
- `apply_compensating_factors(data: dict) -> dict`
- `score_risk(metrics: dict) -> int`

#### DocumentReview Tools
- `validate_document_completeness(docs: list) -> dict`
- `check_document_dates(docs: list) -> dict`
- `cross_validate_amounts(docs: list) -> dict`

#### Compliance Tools
- `check_qm_compliance(terms: dict) -> bool`
- `validate_fair_lending(app: dict) -> bool`
- `check_sanctions_list(name: str) -> bool`
- `generate_adverse_action_notice(decision: str) -> str`

---

## Adding a New Agent

### Step 1: Create Agent File
```bash
touch src/agents/new_agent.py
```

### Step 2: Implement Agent Class
**Template:**
```python
"""New agent for [purpose]."""

from typing import Any

class NewAgent:
    """Handles [specific responsibility]."""
    
    def __init__(self):
        """Initialize agent with LLM and tools."""
        from src.config.bedrock import create_llm
        from src.utils.prompt_loader import load_prompt
        
        self.llm = create_llm(temperature=0, max_tokens=1024)
        self.system_prompt = load_prompt("new_agent")
    
    async def execute(self, **kwargs) -> dict:
        """
        Execute agent task.
        
        Args:
            **kwargs: Task-specific parameters
            
        Returns:
            Structured decision/output dict
        """
        from langchain_core.messages import HumanMessage, SystemMessage
        
        response = self.llm.invoke([
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=self._format_input(kwargs))
        ])
        
        return self._parse_output(response)
    
    def _format_input(self, data: dict) -> str:
        """Format input data for LLM."""
        return str(data)
    
    def _parse_output(self, response: Any) -> dict:
        """Parse LLM response into structured output."""
        import json
        return json.loads(response.content)
```

### Step 3: Create Prompt File
```bash
touch src/prompts/new_agent.txt
```

Apply production prompt techniques:
- Role definition
- Task context
- 5–7 step CoT
- 3+ few-shot examples
- JSON schema
- Negative constraints

### Step 4: Add to Agents __init__
```python
# src/agents/__init__.py
from src.agents.new_agent import NewAgent

__all__ = ["NewAgent"]
```

### Step 5: Integrate with Orchestrator
```python
# src/agents/orchestrator.py
from src.agents.new_agent import NewAgent

async def evaluate_applications(applications):
    new_agent = NewAgent()
    
    for app in applications:
        result = await new_agent.execute(app=app)
        # Use result in decision logic
```

### Step 6: Write Tests
```python
# tests/test_agents.py
import pytest
from src.agents.new_agent import NewAgent

@pytest.mark.asyncio
async def test_new_agent_executes():
    agent = NewAgent()
    result = await agent.execute(test_input="value")
    assert result is not None
    assert "required_field" in result
```

### Step 7: Run Test Suite
```bash
pytest tests/test_agents.py -v
python -m src.exercises.day4_prompt_test
```

---

## Testing & Validation

### Unit Tests (`tests/test_agents.py`)
```bash
pytest tests/test_agents.py -v
```
**Coverage:**
- Each agent's core function
- Input validation
- Output schema compliance
- Error handling for missing/invalid data

### Integration Tests (`tests/test_integration.py`)
```bash
pytest tests/test_integration.py -v
```
**Coverage:**
- Agent-to-agent communication
- Full evaluation pipeline with all agents
- Decision consistency across multiple runs

### Prompt Testing (`src/exercises/day4_prompt_test.py`)
```bash
python -m src.exercises.day4_prompt_test
```
**Coverage:**
- 3 standard test applications (approve, deny, borderline)
- JSON schema validation
- Prompt response quality

---

## Agent Execution Flow (Future)

```
┌─────────────────────────────────────────────────────────────┐
│  User Submits Loan Application                              │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator.evaluate(application)                         │
│  ├─ await FetchData(borrower_id) [PARALLEL]               │
│  ├─ await RiskScoring(app_data) [PARALLEL]                │
│  └─ await DocumentReview(submitted_docs) [PARALLEL]       │
│                                                             │
│  ┌──────────┬─────────────┬────────────────┐               │
│  │ Credit   │ Risk Score  │ Doc Quality    │               │
│  │ Data     │ Assessment  │ Validation     │               │
│  └──────────┴─────────────┴────────────────┘               │
│                                                             │
│  await Compliance(decision, terms)  [SERIAL]              │
│  └─ Regulatory compliance check                            │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Return LoanDecision                                        │
│  {                                                          │
│    "decision": "APPROVED|CONDITIONAL|DECLINE",            │
│    "confidence": 0.95,                                     │
│    "risk_level": "LOW",                                     │
│    "reasons": [...],                                       │
│    "conditions": [...],                                    │
│    "regulatory_notes": [...]                               │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent imports fail | Check `__init__.py` files in agents directory |
| LLM response parsing fails | Verify prompt JSON schema is correct; add error handling |
| Async errors (`RuntimeError: Event loop`)| Use `asyncio.run()` or pytest-asyncio |
| Sub-agents timeout | Increase `max_tokens` or reduce prompt verbosity |
| Non-deterministic decisions | Verify `temperature=0`; check Few-shot examples clarity |
| Memory leaks in long-running | Use context managers; ensure LLM clients are closed |

---

## Quick Links
- **Orchestrator Agent:** [src/agents/orchestrator.py](orchestrator.py)
- **Prompt Loader:** [src/utils/prompt_loader.py](../utils/prompt_loader.py)
- **Bedrock Config:** [src/config/bedrock.py](../config/bedrock.py)
- **Models:** [src/models/loan.py](../models/loan.py)
- **Prompts:** [src/prompts/](../prompts/)
- **LangChain Docs:** [LangChain Python](https://python.langchain.com/)
- **LangGraph Docs:** [LangGraph State Management](https://langchain-ai.github.io/langgraph/)
