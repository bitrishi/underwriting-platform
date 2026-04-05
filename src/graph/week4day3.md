# Week 4 Day 3 - Markdown
md_content = """# Week 4, Day 3: CrewAI — Alternative Orchestration & When to Use What

## Session Overview
**Date:** Week 4, Day 3  
**Topic:** CrewAI as an alternative to LangGraph, side-by-side comparison using actual underwriting code, and the decision framework for choosing between orchestration approaches.  
**Prerequisites:** Week 4 Day 1-2 (LangGraph fundamentals, parallel execution, error handling)

---

## 1. The Core Philosophy Difference

### 1.1 Two Mental Models for the Same Problem

LangGraph thinks in GRAPHS. You define nodes, edges, state, and conditions. You control exactly how data flows. The developer is the architect — you design the blueprint.

CrewAI thinks in TEAMS. You define agents with roles, give them goals, and let the framework figure out how they collaborate. The developer is the manager — you hire the team and set objectives.

Same problem, different mental models. The LangGraph approach says "I will build a state machine with explicit nodes and edges." The CrewAI approach says "I have 4 agents with defined roles and task dependencies."

Java analogy: LangGraph is like writing a Step Functions state machine (explicit control flow). CrewAI is like Spring Batch with job dependencies (you declare what depends on what, the framework schedules execution).

### 1.2 Why They Look Similar on the Surface

For simple cases (2 agents, sequential flow), the code IS structurally similar. Both use the same LangChain @tool decorator for tools. Both call the same LLM. Both produce agent outputs. The surface-level components are identical because both are built on LangChain.

The differences emerge at the ORCHESTRATION layer — how agents are connected, how data flows between them, and what happens when things go wrong.

---

## 2. How CrewAI Works

### 2.1 Agents: Role + Goal + Backstory

In CrewAI, an agent is defined by three strings: role (who the agent is), goal (what it is trying to achieve), and backstory (context that shapes its behavior). These three strings are concatenated into a system prompt automatically. You do not write system prompts manually — CrewAI generates them from these parameters.

This is faster to set up than LangGraph's manual prompt templates. But it gives you less control. In LangGraph, you can add few-shot examples, output schemas, negative constraints, and chain-of-thought instructions to your system prompt. In CrewAI, you get role + goal + backstory and that is it (unless you pass additional prompt customization).

### 2.2 Tasks: Description + Agent + Dependencies

A Task in CrewAI is a unit of work assigned to an agent. It has a description (what to do), expected_output (what success looks like), agent (who does it), and optionally context (which other tasks it depends on).

The context parameter is how CrewAI handles data flow. If risk_task has context=[fetch_task], CrewAI automatically passes fetch_task's output as context to risk_task. The output is passed as a STRING — natural language text, not typed data.

### 2.3 Crew: The Team That Executes

A Crew groups agents and tasks together with a process type. Process.sequential runs tasks in order. Process.hierarchical has a "manager" agent that delegates tasks to other agents. The crew.kickoff() method starts execution.

---

## 3. The Real Differences That Matter

### 3.1 State Management — The Biggest Difference

This is the fundamental architectural difference, not syntax.

In LangGraph, data flows between nodes as TYPED STATE. When fetch_node writes borrower_data to state, risk_node reads state["borrower_data"]["fico"] and gets the integer 740. It is typed, validated, and guaranteed to be in the expected format. If the data is wrong, Pydantic catches it immediately.

In CrewAI, data flows between tasks as NATURAL LANGUAGE. When fetch_task completes, its output is a string like "I found the borrower John Doe with FICO 740 and income $120K." The risk_task receives this string as context. The risk agent must READ and PARSE the string to find the FICO score. What if the string format changes? What if it says "credit score" instead of "FICO"? What if it writes "seven hundred forty" instead of "740"?

For your underwriting system where numerical precision matters (DTI of 40.4% vs 40% can change a decision), typed state is essential. You cannot rely on string parsing for production financial calculations.

### 3.2 Parallel Execution

LangGraph supports true parallel execution natively. Two edges from the same source node run concurrently using asyncio. This is how your fetch_data and doc_review run simultaneously.

CrewAI has Process.sequential (one task at a time) and Process.hierarchical (a manager delegates, but still one task at a time per worker). There is no true parallel execution of independent tasks. For your pipeline where FetchData and Document Review could run simultaneously, CrewAI forces sequential execution — 8 seconds instead of 5.

### 3.3 Conditional Routing

LangGraph has conditional edges — Python functions that examine state and decide the next node. Deterministic, testable, zero-cost (no LLM call for routing). Your should_review_documents and should_escalate functions are pure Python.

CrewAI has no equivalent. Tasks run in the order defined. If you need conditional logic (skip document review when no documents, escalate to human on compliance failure), you must either build it outside CrewAI or have the agent itself decide (which costs an LLM call and introduces unpredictability).

### 3.4 Crash Recovery

LangGraph checkpoints state after each node. If Node 3 of 5 crashes, you resume from Node 3 — Nodes 1 and 2 do not re-run. Their results are in the checkpoint.

CrewAI has no checkpointing. If Task 3 of 5 crashes, you restart the entire crew from Task 1. All previous work is lost. For a pipeline where FetchData calls external APIs (credit bureau, employment verification) that cost money per call, re-running them on every failure is wasteful.

### 3.5 Human-in-the-Loop

LangGraph's interrupt() pauses the graph cleanly. State is checkpointed. The graph can resume hours or days later with the same thread_id. The human's input is injected into state and execution continues from where it paused.

CrewAI has a human_input parameter that blocks execution and waits for terminal input. It is synchronous — the process must stay alive while waiting. It cannot persist across sessions or server restarts. For your MANUAL_REVIEW workflow where a senior underwriter might review the case the next business day, CrewAI's approach does not work.

---

## 4. Side-by-Side Code Comparison

### 4.1 What Is Identical

Tools are identical in both frameworks. Both use LangChain's @tool decorator. You write the tool function once and use it in either framework. The tool code does not change.

The LLM client is identical. Both use ChatBedrock or any LangChain-compatible LLM. You create the LLM once and pass it to either framework.

### 4.2 What Differs: Agent Definition

In LangGraph, you write a ChatPromptTemplate (system message, human message, agent_scratchpad placeholder) and create an AgentExecutor with create_tool_calling_agent. The prompt is in a .txt file you control completely — you can add few-shot examples, output schemas, chain-of-thought instructions, negative constraints.

In CrewAI, you create an Agent with role, goal, backstory, and tools parameters. CrewAI generates the system prompt internally from these three strings. Faster to write, but you cannot add few-shot examples or output schema instructions without workarounds.

### 4.3 What Differs: Orchestration

In LangGraph, you define a StateGraph, add nodes (functions that read/write typed state), add edges (connections with optional conditions), and compile. The graph is explicit — you can look at it and know exactly what runs when.

In CrewAI, you define Tasks with context dependencies and a Crew with a process type. The execution order is implicit — inferred from the task list and context dependencies. Simpler to write, but harder to debug when execution does not match expectations.

### 4.4 What Differs: Data Handoff

In LangGraph: Node A writes state["borrower_data"] = {"fico": 740, "income": 120000}. Node B reads state["borrower_data"]["fico"] which returns the integer 740. Typed, validated, direct access.

In CrewAI: Task A produces a string "The borrower has FICO 740 and income $120,000." Task B receives this string as context and must extract the FICO value from natural language. If Task A's output format changes, Task B might fail silently or extract the wrong value.

### 4.5 Lines of Code

For a simple 2-agent sequential pipeline, LangGraph takes approximately 45 lines and CrewAI takes approximately 25 lines. The difference grows with complexity — parallel execution, conditional routing, error handling, and checkpointing add more code to LangGraph but are simply not available in CrewAI.

---

## 5. AutoGen: The Third Option

Microsoft's AutoGen takes a conversation-based approach — agents talk to each other like a group chat. Agent A says something, Agent B responds, Agent A replies. It is designed for scenarios where agents need to debate, critique, or refine answers collaboratively.

For underwriting, AutoGen is not a good fit. Underwriting is a structured pipeline (fetch, review, score, comply), not a conversation. You do not want the Risk Assessor and Compliance Officer debating — you want them executing defined roles in sequence.

AutoGen is better for code review (agents critique each other's code), research synthesis (agents argue different perspectives), and creative brainstorming.

---

## 6. The Decision Framework

### 6.1 When to Choose LangGraph

Choose LangGraph when you need precise control over execution flow, true parallel execution of independent tasks, typed state management with Pydantic validation, checkpointing and crash recovery, human-in-the-loop that persists across sessions, conditional routing based on state, production reliability with predictable costs, or when the company production underwriting is the target.

### 6.2 When to Choose CrewAI

Choose CrewAI when building a quick prototype or demo, when non-engineers need to understand the system, when agents should collaborate dynamically (delegating tasks to each other), when minimal code is preferred, or when the flow is simple and sequential with no branching.

### 6.3 Can You Use Both?

Yes. Some teams use CrewAI for rapid prototyping and migrate to LangGraph for production. The agents and tools are the same (both use LangChain) — only the orchestration layer changes. You could also use CrewAI for simpler sub-workflows inside a LangGraph node.

---

## 7. Q&A

### Q: They look the same to me. What is actually different?

For simple cases (2 agents, sequential), they ARE nearly identical in outcome. The differences emerge with complexity: typed state vs string parsing, parallel vs sequential only, conditional routing vs no routing, checkpointing vs restart-from-scratch, persistent human-in-the-loop vs blocking prompt. If your system stays simple, either works. Your underwriting system is not simple.

### Q: If CrewAI is faster to build, why not start there and migrate?

You could for a demo. The risk: migration is not just swapping the framework. CrewAI agents pass unstructured text between them. LangGraph nodes pass typed state. Converting from unstructured to structured requires rethinking the data flow. If you know you need production features (which you do), start with the production framework.

### Q: CrewAI backstory — is that just a system prompt?

Essentially yes. Role + goal + backstory are concatenated into a system prompt. The advantage is readability and convention. The disadvantage is less control — no few-shot examples, output schemas, or custom prompt sections without workarounds.

### Q: Does CrewAI support Pydantic structured output?

CrewAI has output_pydantic on Tasks, but the handoff between tasks is still text-based. Task A's output is passed as a string in Task B's context. LangGraph's state is typed throughout — no serialization/deserialization between nodes.

### Q: Which for Kuber's natural language query service?

For a simpler flow (parse query, generate SQL, execute, format response), CrewAI might work fine. For the underwriting system with parallel agents, compliance checks, conditional routing, and human-in-the-loop — LangGraph.

---

## 8. Summary: Key Concepts

| Aspect | LangGraph | CrewAI |
|--------|-----------|--------|
| Mental model | Graph (nodes + edges) | Team (roles + tasks) |
| System prompt | Manual ChatPromptTemplate (full control) | Auto-generated from role/goal/backstory |
| Tools | @tool (LangChain) — identical | @tool (LangChain) — identical |
| Data between agents | Typed state (TypedDict/Pydantic) | Unstructured text (string) |
| Orchestration | Explicit graph topology | Implicit task dependencies |
| Parallel execution | Native (asyncio fan-out) | Not available |
| Conditional routing | Conditional edges (Python functions) | Not available |
| Checkpointing | Built-in (Redis/Postgres) | Not available |
| Human-in-the-loop | interrupt() — persistent, resumable | Blocking terminal input |
| Error handling | Per-node try/except, fatal routing | Crew-level retry only |
| Lines of code (simple) | ~45 | ~25 |
| Best for | Production, complex flows | Prototypes, simple flows |
| Your underwriting system | Yes — needs all production features | No — missing critical capabilities |
"""

with open("week4_day3.md", "w") as f:
    f.write(md_content)
print(f"✅ MD created: {len(md_content)} chars")