# Create the comprehensive markdown file
md_content = """# Week 4, Day 1: LangGraph — State Machines for Multi-Agent Orchestration

## Session Overview
**Date:** Week 4, Day 1  
**Topic:** LangGraph fundamentals — state machines, nodes, edges, conditional routing, parallel execution, checkpointing, and human-in-the-loop. Converting the sequential pipeline from Week 3 into a proper orchestrated graph.  
**Prerequisites:** All Week 1-3 agents (FetchData, Document Review, Risk Scoring), Weekend BUILD pipeline

---

## 1. What Is LangGraph and Why It Exists

### 1.1 The Problem with Sequential Code

The Weekend BUILD from Week 3 wired three sub-agents sequentially: FetchData → Document Review → Risk Scoring. This works but has five fundamental problems that LangGraph solves.

**Problem 1: No Parallel Execution.** FetchData and Document Review are independent — they don't need each other's output. Sequential code runs them one after another. If FetchData takes 3 seconds and Doc Review takes 5 seconds, total is 8 seconds. With parallel execution, total is 5 seconds (the slower one). For a system processing 1,000 loans per day, this 37% improvement saves hours of cumulative processing time.

**Problem 2: No Conditional Routing.** What if there are no documents to review? Sequential code either always calls Doc Review (wasting time and money on an empty invocation) or requires if/else branching that gets messy with complex flows. As the number of conditions grows (no documents, borrower type varies, state-specific rules), the if/else tree becomes unmaintainable.

**Problem 3: No Error Recovery.** If Risk Scoring fails halfway through, sequential code loses everything. You restart from FetchData, re-fetching borrower data and re-processing documents — wasting time and API costs. In production with 1,000 evaluations per day, even a 1% failure rate means 10 evaluations restarting from scratch daily.

**Problem 4: No Human-in-the-Loop.** When Risk Scoring recommends MANUAL_REVIEW, a human underwriter needs to provide input before the pipeline continues. Sequential Python code cannot pause mid-execution and resume hours later when the human responds. You'd need to build a complex polling/callback system from scratch.

**Problem 5: No Visibility.** With sequential code, you only see the final result. If something went wrong in step 2 of 4, debugging requires adding print statements everywhere. There's no built-in execution history showing which steps ran, what state looked like at each point, and where things diverged from expected behavior.

### 1.2 What LangGraph Is

LangGraph is a framework for building stateful, multi-step AI applications as directed graphs. Each step (node) is a function that reads and writes to a shared state, and edges define how execution flows between nodes. It is built on top of LangChain and designed specifically for AI agent orchestration.

The mental model: think of a flowchart where each box is a processing step (your agents) and each arrow is a connection (possibly conditional). LangGraph turns that flowchart into executable code.

### 1.3 The AWS Step Functions Analogy

You already use Step Functions for Camelot's loan origination workflows. LangGraph is the same concept applied to AI agents.

Step Functions defines state machines in JSON/YAML with states (Task, Choice, Parallel, Wait), transitions between states, input/output processing per state, and execution history in the console. It orchestrates AWS services like Lambda, ECS, SQS, and SNS.

LangGraph defines state machines in Python with nodes (functions that process state), edges (connections between nodes including conditional ones), a shared state object (TypedDict or Pydantic), and checkpointing for execution history. It orchestrates AI agents, LLM calls, tool invocations, and RAG pipelines.

The mapping between Step Functions and LangGraph is direct. A Task state corresponds to a node function. A Choice state corresponds to a conditional edge. A Parallel state corresponds to fan-out from a single node to multiple nodes. The Wait state for callbacks corresponds to the interrupt() function for human-in-the-loop. Input/Output processing corresponds to the shared state object. And execution history in CloudWatch corresponds to checkpointing in PostgreSQL or Redis.

The key difference: Step Functions orchestrates AWS services via API calls. LangGraph orchestrates AI agents in-process. Step Functions is language-agnostic (JSON definition); LangGraph is Python-native. Step Functions has built-in AWS console visualization; LangGraph has LangSmith for tracing.

For production at Goldman, you might eventually wrap your LangGraph orchestrator in an ECS Fargate service and use Step Functions for the OUTER orchestration — triggering the underwriting pipeline from EventBridge events, handling retries at the infrastructure level, and integrating with other Camelot services. LangGraph handles the INNER orchestration of AI agents within a single service.

---

## 2. Core Concepts

### 2.1 State — The Shared Memory

In Step Functions, each state receives input and passes output to the next state. In LangGraph, ALL nodes share a single state object. Each node reads what it needs from state and writes what it produces back to state.

Think of it as a shared whiteboard in a conference room. Each team member (node) walks up to the whiteboard, reads what others have written, adds their contribution, and sits down. The next person does the same. The whiteboard IS the state — it accumulates information as each person contributes.

In Python, state is defined as a TypedDict — a dictionary with typed fields. Every node function receives this state as input and returns a partial update. LangGraph merges the update into the existing state. A node does not need to return the ENTIRE state — just the fields it changed. Unchanged fields carry forward automatically.

The Annotated type with a reducer function tells LangGraph how to MERGE values when multiple sources write to the same field. For list fields like errors or messages, the reducer appends rather than replaces, so contributions from multiple nodes are all preserved.

Java analogy: The state is like a shared DTO that passes through a service pipeline. Each service reads what it needs and populates its section. The Annotated reducer is like a thread-safe collection (ConcurrentLinkedQueue) where multiple writers can add entries without losing data. But unlike Java's concurrent collections, LangGraph's merge happens sequentially AFTER parallel nodes complete, not during concurrent execution.

### 2.2 Nodes — The Processing Steps

A node is a Python function that takes state as input and returns a state update dictionary. It is the equivalent of a Task state in Step Functions or a @Service method in Spring.

Each node function is simple: read from state, do work, return updates. The node does not know about other nodes — it only knows about state. This is the same decoupling principle as microservices: each service reads from a message/event and produces output, without knowing who called it or who comes next. This decoupling means you can test each node independently, replace a node's implementation without affecting others, and reorder nodes by changing edges rather than code.

Your existing agent functions (create_fetch_data_agent, create_doc_review_agent, create_risk_scoring_agent) become the implementations INSIDE nodes. The node function is a thin wrapper that reads from state, calls your agent, and writes results back to state. You are not rewriting your agents — you are wrapping them with a state interface.

### 2.3 Edges — The Connections

Edges define how nodes connect. There are three types.

Normal edges always go from node A to node B, unconditionally. After fetch_data completes, always go to risk_scoring. Like a Step Functions transition with no condition. These represent fixed dependencies in your workflow.

Conditional edges use a Python function that examines the state and returns the name of the next node. After compliance, check the state: if needs_manual_review is true, go to human_review; otherwise go to final_decision. Like a Choice state in Step Functions. The routing function is pure Python — no LLM involved. It reads a field from state and returns a string.

Entry and exit points mark where the graph starts (START) and ends (END). Every graph must have exactly one entry point and at least one exit point.

For your underwriting pipeline, all routing is deterministic — Python functions checking state fields. You CAN use an LLM for routing decisions (have the LLM decide which agent to call next), but for predictable workflows, deterministic routing is better because it is testable, debuggable, and has zero cost (no LLM call for routing).

### 2.4 Building and Compiling the Graph

You build a LangGraph by creating a StateGraph with your state type, adding nodes (giving each a name and implementation function), adding edges (normal or conditional), and compiling.

The compilation step validates the graph: ensures all nodes referenced in edges exist, all conditional edge targets are valid, there is a path from START to at least one END, and there are no unreachable nodes. If validation fails, you get a clear error at compile time rather than a runtime surprise. This is like Java's compile-time type checking — catch structural errors early.

The compiled graph is an executable application. You invoke it with initial state and it runs the full pipeline, returning the final state with all accumulated results.

### 2.5 Parallel Execution

LangGraph supports running nodes in parallel when they do not depend on each other. You achieve this by having multiple nodes as the next step from a single node (or from START). When a node has multiple outgoing edges to different target nodes, those targets run concurrently.

For a downstream node that needs results from BOTH parallel branches, you connect both branches to it. LangGraph automatically waits for ALL incoming edges to complete before executing the downstream node. This is exactly like a Parallel state in Step Functions followed by a join.

For your underwriting pipeline, FetchData and Document Review both start from START and both connect to Risk Scoring. LangGraph runs them in parallel and waits for both to finish before starting Risk Scoring. If FetchData takes 3 seconds and Doc Review takes 5 seconds, sequential would be 8 seconds, but parallel is 5 seconds.

The parallel execution uses Python's asyncio under the hood. Each parallel branch runs as a coroutine. Since your agents are I/O-bound (waiting for Bedrock API responses), this parallelism works perfectly even with Python's GIL — the same concurrency model discussed in Week 1 Day 1.

### 2.6 Checkpointing — Resume from Failure

LangGraph can save state after each node execution to a persistent store. This is the crash recovery mechanism.

Without checkpointing, if Risk Scoring fails (Bedrock timeout, Neo4j connection error, out-of-memory), you lose the FetchData and Document Review results. The entire pipeline must restart from scratch.

With checkpointing, after each node completes, LangGraph serializes the current state to the checkpoint store. If Risk Scoring fails, the checkpoint store has the state through Document Review. You fix the issue (increase timeout, restart Neo4j) and resume the graph from the last successful checkpoint. FetchData and Document Review do not re-run — their results are already in the checkpoint.

The checkpoint store is configured at compile time by passing a checkpointer to graph.compile(). Each invocation is identified by a thread_id in the config, so multiple concurrent pipeline executions each have their own checkpoint history.

### 2.7 Human-in-the-Loop

When the agent recommends MANUAL_REVIEW, the graph needs to pause and wait for human input. LangGraph provides the interrupt() function for this.

When a node calls interrupt(), execution stops. The current state is saved via checkpointing. The graph returns the interrupt value (a message describing what human input is needed). Hours or days later, when the human provides a decision, you resume the graph by invoking it with the same thread_id. Execution continues from the interrupted node with the human's input.

This is the equivalent of a Step Functions callback task. The workflow pauses, sends a notification (email, Slack, dashboard alert), and waits for an external signal to continue. In your underwriting system, the signal comes from a senior underwriter reviewing the case in the Camelot UI and entering their decision.

---

## 3. The Underwriting Orchestrator Graph

### 3.1 The Complete Graph Structure

The full graph for your underwriting system has six nodes and both conditional and parallel edges.

START splits into two parallel branches: fetch_data and doc_review. Both branches converge at risk_scoring, which waits for both to complete. After risk_scoring, execution flows to compliance. After compliance, a conditional edge checks whether manual review is needed: if yes, go to human_review; if no, go to final_decision. After human_review, go to final_decision. Final_decision connects to END.

Visual representation:
```
                    START
                      |
              +-------+-------+
              v               v
        fetch_data      doc_review    <- PARALLEL
              |               |
              +-------+-------+
                      v
               risk_scoring            <- WAITS FOR BOTH
                      |
                      v
                compliance
                      |
              +-------+-------+
              v               v
        human_review    final_decision <- CONDITIONAL
              |               |
              +-------+-------+
                      v
                     END
```

This graph handles all five problems from section 1.1: parallel execution (fetch_data and doc_review run simultaneously), conditional routing (skip doc_review when no documents, escalate to human when needed), error recovery (checkpointing after each node), human-in-the-loop (interrupt at human_review), and visibility (state tracked at every step).

### 3.2 Conditional Edge Design

The routing functions are deliberately simple. The should_review_documents function checks whether document_paths is non-empty — if yes, route to doc_review; if no, route to risk_scoring. The should_escalate function checks whether needs_manual_review is true — if yes, route to human_review; if no, route to final_decision.

These could be more complex. You might add routing based on loan type (FHA loans need additional agents), borrower type (self-employed needs Schedule C review), or property type (investment properties need different compliance checks). Each new condition is just another conditional edge function. The graph structure grows organically as business requirements expand, without touching existing node implementations.

---

## 4. How LangGraph Compares to Alternatives

LangGraph uses a state machine graph with nodes and edges. Best for complex multi-agent workflows with conditional routing, parallel execution, and human-in-the-loop. Most control, most flexibility. This is your primary choice.

CrewAI uses role-based agents defined in YAML configuration. Best for quick prototyping and simpler flows where agents have defined roles and collaborate. Less control over routing but faster to set up. We will compare this on Day 3.

AutoGen (from Microsoft) uses agent-to-agent conversation — agents talk to each other in a chat-like pattern. Best for research and multi-agent debate scenarios. Less suitable for structured pipelines like underwriting.

Bedrock Agents is AWS-managed, fully serverless. You configure action groups and knowledge bases in the AWS console. Least code, least control. Good for simple single-agent use cases but limited for multi-agent orchestration.

Custom Python (your Weekend BUILD) uses sequential function calls. Best for simple pipelines with no branching. Becomes unmanageable as complexity grows.

LangGraph is the right choice for your underwriting system because you need all five capabilities: conditional routing, parallel execution, human-in-the-loop, checkpointing, and full control over orchestration logic.

---

## 5. State Persistence: How Production Systems Store Context

### 5.1 Three Layers of Persistence

**Layer 1: Within a single agent invocation (agent_scratchpad).** The ReAct loop accumulates tool calls and results in the message list. This lives in memory DURING the invocation and is gone when the invocation completes. A single agent invocation is short-lived (5-30 seconds), so this does not need persistence. Java analogy: local variables in a method call — they exist on the stack during execution and are gone when the method returns.

**Layer 2: Between nodes in a LangGraph pipeline (checkpointing).** After each node executes, the entire state is saved to a persistent store. If the system crashes between nodes, you resume from the last checkpoint. This is the graph-level persistence that LangGraph manages.

**Layer 3: Long-term conversation history (your application database).** If your underwriting system has a chat interface where an underwriter has an ongoing conversation with the agent across hours or days, that conversation history needs to be stored in your application database. This is YOUR responsibility — LangGraph does not manage long-term chat history, only pipeline state.

### 5.2 Checkpoint Store Options

**MemorySaver** is in-memory, development only. Lost on process restart. Zero setup, zero dependencies. Use for local testing and development.

**SqliteSaver** is file-based persistence. Survives process restarts but not machine failure. Single-machine only. Use for local development when you want persistence across restarts.

**Redis** is actually the BEST fit for pipeline checkpointing. It is a pure key-value store designed for exactly this access pattern: write a blob by key, read a blob by key, set a TTL for automatic cleanup. Sub-millisecond reads and writes. With AOF persistence enabled, it also survives crashes. Since your Camelot architecture already includes Redis for caching, there is zero operational overhead to add checkpoint storage. Use for production pipeline checkpointing.

**PostgreSQL** is a relational database used as a key-value store for checkpoints. The checkpoint table has thread_id (key) and serialized state (value). It works but you are using 1% of PostgreSQL's capabilities. The advantage is queryability — you can run SQL queries to find failed executions, analyze execution times, and build debugging dashboards. Use for when you need to query checkpoint data for analytics or debugging.

**DynamoDB** is an AWS-managed key-value store. Partition key is thread_id, value is serialized state. Auto-scales, fully managed, pay-per-request pricing. Natural fit for AWS-native architectures. Use for production when you want AWS-managed storage.

The recommendation for your system: Redis for pipeline checkpoints (you already have it, right access pattern, short-lived data). DocumentDB for the final persisted results (loan decisions, audit trails — your existing data layer). PostgreSQL only if you want to build an execution analytics dashboard.

### 5.3 Why PostgreSQL for Checkpointing Is Convenience, Not Optimal

LangGraph's PostgresSaver is commonly recommended because most teams already have PostgreSQL. Adding a checkpoint table to an existing instance is zero operational overhead. But architecturally, checkpointing IS a key-value pattern: thread_id maps to state blob. PostgreSQL is a relational engine being used as a key-value store — you are using 1% of its capabilities. A key-value store like Redis or DynamoDB would be more appropriate architecturally.

### 5.4 How Inter-Node Communication Actually Works

An important clarification: within a single process, nodes communicate through IN-MEMORY state, not through the database. The checkpoint store is a BACKUP, not the communication path.

When fetch_data_node completes, it returns a dictionary with borrower_package populated. LangGraph merges this into the in-memory state object. When risk_scoring_node runs next, it reads borrower_package from the same in-memory object. No database round-trip for inter-node communication.

The checkpoint store is written to AFTER each node completes, as insurance. If the process crashes, the checkpoint store has the last good state. But during normal execution, the database is not in the hot path between nodes.

If your agents run on DIFFERENT machines (separate Fargate tasks in a distributed setup), then the checkpoint store DOES become the communication path. But for your underwriting system where all agents run in one process, inter-node communication is in-memory and fast.

### 5.5 Database Selection for Conversation Persistence

For persisting chat conversations (if you add a chat interface), the access pattern is: append a message to conversation X, read all messages for conversation X ordered by time. This is a document access pattern, not relational.

DocumentDB/MongoDB is the natural fit — one document per conversation, messages as a nested array, single-document reads by conversation_id. DynamoDB also works well with conversation_id as partition key and timestamp as sort key. Relational databases like PostgreSQL work but feel unnatural — storing chat messages in a SQL table is using a relational engine for a document access pattern.

For your system: DocumentDB for conversation persistence (if you add chat), same as where you store loan application records. This keeps everything in your existing Camelot data layer.

---

## 6. Context Compression: Managing Long Conversations

### 6.1 When Compression Matters

For your underwriting PIPELINE, compression is NOT needed. Each loan evaluation uses 5,000-10,000 tokens across all nodes. Claude Haiku's 200K context window is 20-40x what you need. The pipeline starts fresh for each loan — no accumulated history.

Compression matters for CHAT INTERFACES where a user has an extended conversation with the agent over many turns. If an underwriter chats with the agent for 50 back-and-forth messages reviewing multiple loans, the accumulated messages might reach 50,000-100,000 tokens.

### 6.2 Compression Strategies

**Summarization** replaces older messages with a compact LLM-generated summary. The last N messages remain verbatim; everything older is summarized into a paragraph preserving the key facts but dropping verbose tool call details. LangChain provides ConversationSummaryBufferMemory for this pattern. The tradeoff: costs one LLM call to generate the summary, and the summary might lose important details.

**Trimming** simply drops the oldest messages, keeping the most recent N messages or N tokens. Simple, cheap (no LLM call), but lossy — you might lose important context from early in the conversation. LangChain provides trim_messages() for this.

**Selective retention** keeps messages matching certain criteria (tool results, decisions, user messages) and drops intermediate reasoning. More sophisticated but preserves the most useful information per token.

**Fact extraction** (what production chat systems likely use) separates FACTS from CONVERSATION. Key facts are extracted and stored as structured data separately. Conversation messages are compressed or dropped over time, but facts persist indefinitely. When a new message arrives, the system loads the facts plus recent messages, not the entire conversation history.

### 6.3 Detecting Context Size Issues

You can monitor proactively by counting tokens before each LLM call and triggering compression when approaching a threshold (for example 75% of context window). You will also notice degraded quality before hitting the hard limit — LLMs start forgetting content in the middle of very long contexts (the "lost in the middle" problem). If your agent starts ignoring tool results from early in the conversation, context is too large. And if you hit the actual model context limit, the Bedrock API returns an error.

---

## 7. Parallel Execution Safety: Why No ConcurrentModificationException

### 7.1 How Parallel Nodes Work

In Java, if two threads modify the same HashMap simultaneously, you get ConcurrentModificationException. LangGraph avoids this because parallel nodes DO NOT run on shared mutable state.

When LangGraph runs nodes in parallel, each node receives a read-only snapshot of the relevant state fields. They run simultaneously but on SEPARATE copies. Neither node modifies the original state directly. Each node returns a partial update dictionary — an independent output describing what changed.

AFTER all parallel nodes complete, LangGraph merges all the returned updates into the state in a SINGLE-THREADED merge operation. There is never simultaneous mutation of the same object. The pattern is identical to Java's CompletableFuture.allOf() — each future computes independently, returns a result, and you merge results in the main thread after all complete.

### 7.2 The Reducer: Handling Same-Field Writes

If two parallel nodes write to DIFFERENT fields, there is no conflict. fetch_data writes borrower_package, doc_review writes document_review — no overlap, no issue.

If two parallel nodes write to the SAME field, the default behavior is last-writer-wins, which loses one node's contribution. This is where the Annotated reducer solves the problem.

A reducer is a function that takes (existing_value, new_value) and returns the merged result. For list fields, the add reducer concatenates both lists, preserving contributions from all nodes. For message fields, add_messages appends with deduplication.

The reducer runs during the single-threaded merge step, after all parallel nodes have completed. It is not a lock — it is a merge strategy. No concurrent access occurs, so no locking is needed.

Design rule: if two parallel nodes might write to the same field, that field MUST have a reducer. If they write to different fields, no reducer needed.

### 7.3 State Fields for Your Pipeline

For the underwriting pipeline: borrower_package is only written by fetch_data (no reducer needed), document_review is only written by doc_review (no reducer needed), risk_assessment is only written by risk_scoring (no reducer needed), errors could be written by ANY node that encounters a failure (needs Annotated list with add reducer), and messages accumulated by all nodes (needs Annotated list with add_messages reducer).

---

## 8. Q&A

### Q: Is LangGraph just Step Functions in Python?

Conceptually, yes. Both are state machines with nodes, edges, conditions, parallel execution, and checkpointing. The difference is that LangGraph is designed for AI agent orchestration — nodes are LLM-powered agents, state includes conversation history, and the framework integrates with LangChain's tool calling, RAG, and tracing. Step Functions orchestrates AWS services; LangGraph orchestrates AI agents. For production, you might use both: Step Functions for infrastructure-level orchestration (triggering pipelines from events) and LangGraph for agent-level orchestration within the pipeline.

### Q: Why not just use Step Functions for AI agents too?

You could — put each agent in a Lambda, orchestrate with Step Functions. The tradeoffs: Step Functions does not understand LLM-specific concepts (tool calling loops, agent scratchpad, streaming). Each Lambda invocation has cold start overhead. State passing between Lambdas is limited to 256KB (your accumulated state might exceed this). LangGraph runs in-process, avoiding these limitations. Some teams use both: Step Functions for the outer workflow, LangGraph inside a Fargate service for the agent logic.

### Q: Can I mix deterministic routing and LLM-based routing?

Yes. Most edges should be deterministic (Python functions checking state fields). Use LLM-based routing only when the decision genuinely requires reasoning — for example, deciding whether a complex application needs additional documentation. For your underwriting pipeline, all routing is deterministic because the flow is predictable.

### Q: What happens if two parallel nodes write to the same state field?

The reducer handles this. Without a reducer, last-writer-wins (one node's contribution lost). With an Annotated reducer like add for lists, both contributions are merged. Design your state so parallel nodes write to different fields where possible, and use reducers for shared fields like errors and messages.

### Q: How does this connect to what I have already built?

Your existing agent functions become the implementations inside nodes. The node function is a thin wrapper: read from state, call your agent, write results back to state. You are not rewriting agents — you are connecting them through a state machine. The graph structure replaces your sequential pipeline code.

### Q: Why would one use PostgreSQL for checkpointing? It is a key-value pattern.

You are right — it IS a key-value pattern. PostgreSQL is used for convenience (teams already have it), not because it is optimal. Redis or DynamoDB are better fits architecturally. Use PostgreSQL only if you need to query checkpoint data for analytics or debugging dashboards.

### Q: For persisting conversations, what database should I use?

DocumentDB/MongoDB is the natural fit — one document per conversation, messages as a nested array. This matches the append-and-read access pattern of chat history. DynamoDB also works well with conversation_id as partition key and timestamp as sort key. Avoid relational databases for raw message storage — it is a document access pattern, not a relational one.

### Q: How do agents communicate between nodes? Through the database?

No. Within a single process (your typical setup), nodes communicate through in-memory state. The checkpoint store is a BACKUP written after each node completes, not the communication path. The next node reads from the in-memory state object, not from the database. Database-based communication only applies if agents run on different machines in a distributed setup.

### Q: What happens when context becomes too big?

For your pipeline: not a concern. Each evaluation uses 5,000-10,000 tokens; the 200K limit is 20-40x headroom. For chat interfaces with long conversations: monitor token counts proactively, use summarization or trimming when approaching 75% of the context window, and consider fact extraction to separate persistent knowledge from ephemeral conversation.

### Q: Why no ConcurrentModificationException when parallel nodes update state?

Parallel nodes do not share mutable state. Each receives a read-only snapshot, runs independently, and returns a partial update. LangGraph merges all updates in a single-threaded operation AFTER all parallel nodes complete. It is identical to CompletableFuture.allOf() in Java — no shared mutable state during concurrent execution, sequential merge after all futures complete.

---

## 9. Summary: Key Concepts

| Concept | What It Does | Java / AWS Equivalent |
|---------|-------------|----------------------|
| StateGraph | Defines the orchestration graph | Step Functions state machine definition |
| Node | Processing step that reads/writes state | Task state / Lambda function |
| Edge (normal) | Unconditional connection between nodes | Step Functions transition |
| Edge (conditional) | Routes based on state examination | Choice state |
| Parallel execution | Run independent nodes simultaneously | Parallel state |
| State (TypedDict) | Shared data across all nodes | Shared DTO through pipeline |
| Annotated reducer | Merge strategy for same-field parallel writes | ConcurrentLinkedQueue merge |
| Checkpointing | Save state after each node for crash recovery | Step Functions execution history |
| interrupt() | Pause graph for human input | Step Functions callback task |
| graph.compile() | Validate and prepare graph for execution | javac compilation / CDK deploy |
| thread_id | Identifies a specific pipeline execution | Step Functions execution ARN |
| MemorySaver | Dev checkpointing (in-memory) | Local testing |
| Redis checkpoint | Production checkpointing (fast key-value) | ElastiCache for session state |
| PostgresSaver | Queryable checkpointing (analytics) | RDS for execution analytics |
| DocumentDB | Conversation and result persistence | Camelot data layer |
"""

with open("/tmp/week4_day1.md", "w") as f:
    f.write(md_content)

print(f"✅ Markdown file created: {len(md_content)} characters")