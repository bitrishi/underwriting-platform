md_content = """# Week 5, Day 2: A2A — Agent-to-Agent Protocol

## Session Overview
**Date:** Week 5, Day 2
**Topic:** A2A (Agent-to-Agent Protocol) — how agents communicate across system boundaries, the protocol internals, Agent Cards for discovery, task lifecycle for delegation, and comparison with MCP.
**Prerequisites:** Week 5 Day 1 (MCP), Week 4 complete orchestrator

---

## 1. What Problem A2A Solves

### 1.1 The Cross-System Challenge

MCP solves how an agent talks to TOOLS. A2A solves how an agent talks to OTHER AGENTS in different systems.

In your underwriting system, all four agents run in one LangGraph process. They communicate through shared state — fetch_data writes borrower_package, risk_scoring reads it. Simple, fast, in-memory.

But when your agent needs to interact with agents that are NOT in your system — a Servicing team's agent, a Fraud Detection agent, an AMC's appraisal agent — they cannot share LangGraph state. They are separate applications, built by different teams, running on different infrastructure, possibly using different frameworks.

### 1.2 Cross-System Scenarios

Your underwriting agent approves a loan and needs the Servicing agent to set up payment processing. Different application, different team, different infrastructure.

Your underwriting agent needs a property appraisal from an AMC agent. The result takes days — the AMC dispatches an appraiser, collects the report, returns the valuation.

Goldman's Fraud Detection agent notices suspicious activity and needs to alert your underwriting agent mid-evaluation to pause processing.

In all cases, agents are in DIFFERENT systems. Cannot share state. Cannot import functions. Need a communication protocol.

### 1.3 How It Works Today (Without A2A)

REST APIs between services — works but is request-response only. No task lifecycle, status tracking, or capability discovery. Message queues (SQS/EventBridge) — handles async but no standard schema for agent capabilities or task status. Shared database — creates tight coupling between teams.

All approaches are ad-hoc. Each cross-agent integration is custom. 10 agents needing to interact = potentially 45 custom integrations. Each with custom protocols, schemas, authentication.

---

## 2. What A2A Is

A2A is Google's proposal (published early 2025) for standardizing agent-to-agent communication across system boundaries. It defines how agents discover each other's capabilities, delegate tasks, receive status updates, and exchange results.

If MCP is "how agents talk to tools" (agent → tool), A2A is "how agents talk to agents" (agent → agent).

### 2.1 The Key Difference from MCP

MCP tools are PASSIVE — they execute what they are told. You COMMAND an MCP tool. Like a programmer using a library function.

A2A agents are AUTONOMOUS — they have their own goals, tools, workflows, and decision-making. You REQUEST something from an A2A agent. Like a manager delegating to another manager who decides how to accomplish the task.

MCP: "Calculate DTI with income 120000 and debt 2400." Tool returns result immediately. Done.

A2A: "Set up servicing for this approved loan." Agent acknowledges. Starts working. Asks "which property for collateral?" You answer. Agent continues. Hours later: "Done, account number SVC-98765."

MCP has no task lifecycle, no status tracking, no back-and-forth. A2A has all of these because the other side is an AGENT with its own process.

---

## 3. The Protocol: Three Layers

### 3.1 Layer 1: Discovery — Agent Cards

In MCP, servers publish tool lists. In A2A, agents publish AGENT CARDS — machine-readable descriptions of the entire agent.

The Agent Card is a JSON file hosted at a well-known URL, typically at /.well-known/agent.json. Like robots.txt for websites or openid-configuration for OAuth. Any agent that knows the URL can fetch the card and learn what this agent can do.

An Agent Card contains: identity (name, description, organization), capabilities (streaming support, push notifications), skills (high-level things the agent can do — like "evaluate_loan" or "pre_qualify"), input/output formats, authentication requirements (OAuth scopes, token URLs), and the endpoint URL for submitting tasks.

The critical difference from MCP: MCP exposes individual TOOLS (pull_credit_report, calculate_dti — low-level functions). A2A exposes SKILLS (evaluate_loan, setup_servicing — high-level capabilities). A skill might internally use dozens of tools, multiple sub-agents, and complex orchestration. The external consumer sees only the skill, not the internals.

A shared directory or registry is possible: agents register their cards, other agents search by capability. "Find me an agent that can do property appraisals" returns the AMC agent's URL. This registry is not standardized yet but the Agent Card format makes it possible.

### 3.2 Layer 2: Task Lifecycle — Delegation and Tracking

When Agent A wants Agent B to do something, it creates a TASK via a POST request to Agent B's endpoint. Standard HTTPS with JSON payload. Not a new transport protocol — regular REST.

The task has a defined lifecycle with standard states:

submitted — Agent B received the request but has not started.
working — Agent B is actively processing. May send intermediate status updates.
input-required — Agent B needs more information from Agent A. Sends a question. Agent A responds. Back-and-forth communication within the task.
completed — Agent B finished. Result in the final message.
failed — Agent B could not complete. Error details in message.
canceled — Agent A canceled before completion.

Agent A can check status by polling (GET request for task by ID) or by receiving push updates via Server-Sent Events (streaming). For long-running tasks (appraisals taking days), SSE streaming or polling is essential.

The input-required state is where A2A goes beyond simple REST. The executing agent can ASK QUESTIONS mid-task. The requesting agent answers. The executing agent continues with the clarification. No custom protocol needed — the task lifecycle and message format handle it standardly. This is like the human-in-the-loop pattern from Week 4 Day 4 but between agents instead of between agent and human.

### 3.3 Layer 3: Messages — Multi-Part Content

Messages within a task use a "parts" structure supporting multiple content types:

Text parts for natural language communication. Data parts for structured JSON with MIME types — how agents exchange typed data (loan details, risk assessments). File parts for references to documents (URLs to fetch, not embedded content).

A single message can contain all three: explanation text, structured loan data, and a link to the appraisal PDF.

---

## 4. How It Works Internally: The Complete Flow

### 4.1 Your Agent Talks to Servicing Agent

Step 1 — Discovery: Your system fetches the Servicing agent's Agent Card from its well-known URL. The card says it has a skill "setup_loan_servicing" accepting loan details.

Step 2 — Authentication: Your system obtains an OAuth token from PingFederate using scopes specified in the Agent Card. Standard OAuth — same as any Goldman service-to-service auth.

Step 3 — Task creation: Your LangGraph final_decision_node sends a POST to the Servicing agent's /tasks endpoint with loan details. Regular HTTPS request from your Fargate service.

Step 4 — Servicing receives: The Servicing agent's web controller (FastAPI, Flask, whatever) receives the POST, validates OAuth token, reads payload, passes loan details to its internal agent. Its internal architecture (LangGraph, CrewAI, custom) is invisible to you.

Step 5 — Processing: Servicing agent creates payment schedule, sets up escrow, configures auto-draft. Might take seconds or hours.

Step 6 — Back-and-forth (if needed): Servicing agent encounters ambiguity — borrower has two properties, which is collateral? Sets task to input-required with the question. Your system receives, answers. Servicing continues.

Step 7 — Completion: Task status changes to completed with result (servicing account number, payment schedule).

Step 8 — Your system reads result: Via SSE push or next poll. Stores servicing details in loan record.

### 4.2 Your Mental Model Was Correct

You said: "Agent A sends a POST with payload to Agent B's REST controller, which passes it as context to its agent." That is exactly right. A2A standardizes the payload format, adds task lifecycle tracking, and adds capability discovery — but the transport is regular HTTPS.

---

## 5. A2A vs MCP: Definitive Comparison

### 5.1 What Each Standardizes

MCP standardizes agent-to-tool communication. The tool is passive, executes what it is told. Synchronous function calls with parameters and results. No task lifecycle. Like calling a library.

A2A standardizes agent-to-agent communication. The agent is autonomous, has its own decision-making. Asynchronous task delegation with lifecycle tracking. Back-and-forth possible. Like delegating to a colleague.

### 5.2 For Your Underwriting System

FetchData calling a credit bureau API — MCP (using a tool). FetchData asking another team's Data Agent to gather specialized data — A2A (collaborating with an agent). Risk Scoring calling calculate_dti — MCP (using a tool). Risk Scoring asking a Fraud Detection agent to assess risk — A2A (collaborating with an agent).

Internal agent communication (within your LangGraph) — neither MCP nor A2A. Shared state is simpler, faster, and more reliable.

### 5.3 The Stack

JDBC standardized database access. MCP standardizes tool access. A2A standardizes agent access. One standard per layer.

---

## 6. A2A vs EventBridge

Goldman already has cross-service communication via EventBridge. How is A2A different?

EventBridge is fire-and-forget event publishing. Service A publishes "loan approved." Any interested service consumes. No task lifecycle, no status tracking, no back-and-forth, no capability discovery. Like posting on a bulletin board.

A2A is task-oriented communication. Agent A submits a task to Agent B. Agent B acknowledges, works, sends updates, asks questions, returns result. Like assigning a task to a specific person.

For simple notifications (loan approved, status changed): EventBridge is right. For task delegation between agents (order appraisal, set up servicing): A2A provides the richer interaction pattern needed.

---

## 7. Honest Assessment

### 7.1 Do You Need A2A Today?

No. Your agents are all in one LangGraph process. Internal communication via shared state is simpler, faster, and more reliable than any protocol.

### 7.2 When A2A Becomes Valuable

When Goldman has multiple agent systems: Servicing team, Fraud team, Portfolio team each have their own agents needing to interact with yours. Standard protocol prevents ad-hoc integration chaos.

When the mortgage industry has agents: AMCs, title companies, credit bureaus with their own agents. A2A is how your system interacts without custom integrations per partner.

### 7.3 Current State

A2A is VERY early. Google published the spec in April 2025. Reference implementations exist but minimal production adoption. No major framework has built-in support yet. Understand the concept, monitor adoption, do not implement.

---

## 8. Q&A

### Q: How do two agents actually talk? Is it REST?

Yes. A2A uses standard HTTPS with JSON payloads. Agent A sends POST to Agent B's endpoint. Agent B's controller receives it, validates auth, passes to internal agent, returns response. Regular web service communication with a standardized payload format.

### Q: Agent A sends POST to Agent B's controller which passes it as context to its agent?

Exactly right. The receiving service has a web controller (FastAPI, Flask, Spring) that receives the A2A task request. It extracts the task details and passes them to its internal agent — which might be LangGraph, CrewAI, or custom code. The internal architecture is invisible to the caller. A2A standardizes the external interface, not the internal implementation.

### Q: Is A2A like MCP but for agents instead of tools? Exposing agents via a shared directory?

Yes. MCP: servers expose TOOLS, agents discover and call them. A2A: agents expose SKILLS (via Agent Cards), other agents discover and delegate tasks. MCP tool list is low-level functions (pull_credit_report). A2A skill list is high-level capabilities (evaluate_loan). A shared registry where agents register cards and others search by capability is the directory concept — not standardized yet but enabled by the Agent Card format.

### Q: What is the protocol? Is it standardized request/response like MCP?

Yes. Same principle as MCP. MCP standardizes tools/list and tools/call. A2A standardizes: Agent Card (capability discovery at well-known URL), task creation (POST /tasks with standard JSON), task status (GET /tasks/{id} or SSE stream), task messaging (multi-part content with text, data, files), and task lifecycle states (submitted, working, input-required, completed, failed, canceled). Every A2A agent speaks the same format. Switch from one agent provider to another by changing the URL, same as MCP.

### Q: How does authentication work between agents?

Standard OAuth 2.0. The Agent Card specifies the token URL and required scopes. Your system obtains a token from PingFederate (or whatever the card specifies) and includes it in every request. Same service-to-service auth pattern Goldman already uses. The A2A protocol does not invent new auth — it references existing OAuth/OIDC standards.

### Q: How many agents can one agent talk to?

No protocol limit. Your agent can connect to as many other agents as needed — Servicing, Fraud, AMC, Title, Insurance. Each is just a different URL. Practical limits are: auth token management (need tokens for each), latency (each interaction adds time), and complexity (managing many async tasks).

---

## 9. Summary

| Concept | What It Does | Analogy |
|---------|-------------|---------|
| A2A | Standardizes agent-to-agent communication | HTTP for agents |
| Agent Card | Machine-readable agent description at well-known URL | robots.txt / OpenID config |
| Skills | High-level capabilities an agent advertises | Service API endpoints |
| Task | Unit of delegated work with lifecycle | JIRA ticket between teams |
| Task states | submitted → working → input-required → completed/failed | Workflow status tracking |
| input-required | Executing agent asks requesting agent for clarification | Back-and-forth conversation |
| Messages (parts) | Multi-type content: text + data + files | Email with attachments |
| SSE streaming | Push status updates to requesting agent | WebSocket-like updates |
| MCP vs A2A | Tools (passive, commanded) vs Agents (autonomous, requested) | Library vs colleague |
| EventBridge vs A2A | Fire-and-forget events vs task delegation with tracking | Bulletin board vs task assignment |
| Agent registry | Directory where agents publish cards for discovery | DNS for agents |
| Current state | Spec published April 2025, minimal adoption | Monitor, do not implement |
| For your system | Not needed today, valuable when Goldman has multiple agent systems | Same as MCP trajectory |
"""

with open("week5_day2.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")