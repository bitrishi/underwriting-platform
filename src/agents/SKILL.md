# Agents SKILL — Underwriting Agent Layer

## Overview

The `src/agents/` package defines agent entry points used in exercises and
runtime flows. Agents are built with LangChain's current `create_agent` API and
are invoked using a `messages` payload.

## Implemented Agents

### `create_underwriting_Agent()`
**File:** `src/agents/underwriting_agent.py`

Purpose:
- Evaluate underwriting scenarios using tool calls and policy lookup support.

Current tools:
- `calculate_dti`
- `calculate_ltv`
- `check_fico_eligibility`
- `search_lending_policies`

Input shape:
```python
{
    "messages": [
        {"role": "user", "content": "Evaluate this loan application ..."}
    ]
}
```

### `create_fetch_data_agent()`
**File:** `src/agents/fetch_data.py`

Purpose:
- Gather borrower, credit, employment, and policy context needed before
  downstream underwriting decisions.

Current tools:
- `pull_borrower_data`
- `pull_credit_report`
- `pull_employment_history`
- `search_lending_policies`

Execution flow expected by prompt:
1. Pull borrower profile by application id
2. Pull credit data using borrower SSN last four
3. Pull employment data using borrower SSN last four
4. Pull state-relevant policy snippets

Input shape:
```python
{
    "messages": [
        {"role": "user", "content": "Gather all underwriting data for APP-001"}
    ]
}
```

## Agent Invocation Notes

- These agents return a LangGraph/LangChain state object that includes
  `messages`; exercise scripts should read the final message for display.
- Use callback handlers (for example `UnderwritingTracer`) via `config`:
```python
agent.invoke(payload, config={"callbacks": [tracer]})
```
- Prefer deterministic settings (`temperature=0`) for underwriting and compliance
  use cases.

## Compatibility Notes

- `create_tool_calling_agent`/`AgentExecutor` style setup has been migrated to
  `create_agent` for current LangChain compatibility.
- Agent prompts are loaded from `src/prompts/*.txt` through `load_prompt(...)`.

## Testing Guidance

- Integration tests for fetch-agent wiring and execution are in
  `tests/test_fetch_agent.py`.
- Keep tests deterministic by monkeypatching `create_agent` and policy search
  tools instead of invoking live Bedrock dependencies.
