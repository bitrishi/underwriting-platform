# Markdown file
md_content = """# Week 4, Day 4: Human-in-the-Loop & Checkpointing

## Session Overview
**Date:** Week 4, Day 4  
**Topic:** Implementing the MANUAL_REVIEW workflow — graph interrupt, checkpoint persistence, resume mechanics, and the API pattern for human review in production.  
**Prerequisites:** Week 4 Day 1-3 (LangGraph graph, parallel execution, error handling)

---

## 1. The Real-World Scenario

Your Risk Scoring agent evaluates a loan and returns MANUAL_REVIEW — FICO 710, DTI 40%, cryptocurrency industry, borderline case. A senior underwriter at the company needs to review the full assessment, possibly pull additional information, and make the final call. This might happen 30 minutes later, or the next business day.

The graph needs to STOP at the human_review node, SAVE everything computed so far (borrower data, document review, risk assessment, compliance check), and RESUME exactly where it left off when the human responds.

In mortgage underwriting, roughly 20-30% of applications require some form of manual review. Without human-in-the-loop, those applications either get auto-denied (losing business) or auto-approved (accepting risk). Neither is acceptable.

---

## 2. How interrupt() Works Under the Hood

### 2.1 The Ten-Step Lifecycle

**Step 1:** The graph runs through fetch_data, doc_review, risk_scoring, and compliance. All succeed. The compliance node determines needs_manual_review is True.

**Step 2:** The conditional edge routes to human_review_node. The node starts executing.

**Step 3:** human_review_node calls interrupt() with a message describing what the human needs to review. This message includes the risk assessment summary, compliance results, and borrower data.

**Step 4:** LangGraph saves the ENTIRE accumulated state to the checkpoint store (Redis). Everything from all four completed agents is serialized and stored. The checkpoint includes which node was executing and where execution stopped.

**Step 5:** The graph invocation RETURNS to your application code. It returns the interrupt value (the review message), NOT a final result. The graph is not done — it is paused.

**Step 6:** Your application code sends the interrupt message to the human through whatever channel your system uses — Kuber UI notification, email, Slack message. This is YOUR code, not LangGraph.

**Step 7:** Time passes. Hours or days. The graph is not running. No process is waiting. No thread is sleeping. The state sits in Redis. Your application servers can restart, deploy new code, scale up or down. The checkpoint persists independently of any running process.

**Step 8:** The human provides a decision through the Kuber UI. Your API receives: "APPROVED with conditions — require 6 months cash reserves."

**Step 9:** Your API resumes the graph using the same thread_id and the human's input. LangGraph loads the checkpoint from Redis, reconstructs the full state, injects the human's response as the return value of interrupt(), and execution continues from human_review_node.

**Step 10:** human_review_node completes. Writes the human's decision to state. Execution continues to final_decision_node, which produces the complete report. Graph reaches END. Result persisted to DocumentDB.

### 2.2 The Key Insight: Nothing Is Running During the Pause

This is the most important point. The interrupt is NOT a sleeping thread, a waiting process, or a long-polling connection. The state machine literally stops. The Python process that was running the graph can exit completely. When the human responds, a COMPLETELY NEW process (possibly on a different server) loads the checkpoint and continues.

Java analogy: This is exactly how Step Functions callback tasks work. The state machine pauses, the execution state is persisted by AWS, and a completely separate process (triggered by an SQS message or API call) resumes the execution. No process waits.

---

## 3. What Each Checkpoint Stores

### 3.1 Full State Snapshots

Yes — every checkpoint stores the ENTIRE accumulated state up to that point. Each checkpoint is a complete, self-contained snapshot.

Checkpoint #1 (after fetch_data) contains: app_id, borrower_package (populated), and all other fields as null.

Checkpoint #2 (after doc_review) contains: app_id, borrower_package (from #1), document_review (newly populated), and remaining fields as null.

Checkpoint #3 (after risk_scoring) contains: everything from #1 and #2 plus risk_assessment.

Checkpoint #4 (after compliance, INTERRUPTED) contains: everything from #1 through #3 plus compliance_result, plus metadata marking this as interrupted at human_review.

### 3.2 Why Full Snapshots Instead of Deltas

If checkpoint #3 only stored the delta (just risk_scoring output), resuming would require loading and replaying checkpoints #1, #2, and #3 in sequence. That is slower (3 reads instead of 1) and more fragile (if #1 is corrupted, #3 is useless).

Full snapshots mean instant resume from any point — load one checkpoint, you have everything. The tradeoff is storage duplication, but at approximately 10 KB per checkpoint, this is negligible.

### 3.3 Storage Sizing

Each checkpoint is approximately 2-10 KB depending on accumulated data. A single pipeline execution with 6 nodes creates 6 checkpoints totaling approximately 30-50 KB. At 1,000 evaluations per day, that is 30-50 MB per day. With a 7-day TTL for automatic cleanup, the maximum storage is approximately 350 MB. Redis handles this trivially.

---

## 4. The thread_id: How Resume Finds the Right Checkpoint

### 4.1 What thread_id Is

The thread_id is a string YOU choose that uniquely identifies one pipeline execution. For your underwriting system, use the application ID: "APP-001", "APP-002", etc. It serves the same purpose as a Step Functions execution ARN.

Multiple concurrent evaluations each have their own thread_id and their own checkpoint chain. They do not interfere with each other.

### 4.2 How Resume Works Mechanically

When your API calls app.invoke(Command(resume=human_decision), config={"configurable": {"thread_id": "APP-001"}}):

LangGraph sees thread_id "APP-001." It queries the checkpoint store for the latest checkpoint with this thread_id. It finds a checkpoint with status "interrupted" at human_review_node. It deserializes the full state (all four agents' outputs). It injects the resume value (human's decision) as the return value of the interrupt() call. Execution continues from human_review_node as if interrupt() just returned.

LangGraph does NOT "understand" that this is a human response. It simply sees: "thread APP-001 has an interrupted checkpoint. Caller provided a resume value. Inject and continue." The semantic meaning (human review) is your application logic. LangGraph handles the pause/persist/resume mechanics.

### 4.3 What If Two Processes Try to Resume the Same thread_id?

The checkpoint store should use optimistic locking or your API should enforce single-resume semantics. In practice, the pending review queue in the Kuber UI should show "APP-001: pending review" and once a reviewer claims it, others see "APP-001: under review by Jane Smith." This is standard workflow management — the same pattern you use for any task assignment system.

---

## 5. The Production API Pattern

### 5.1 Three Endpoints

**Endpoint 1: Start Evaluation.** Receives a loan evaluation request, starts the graph. Returns immediately with either a final result (graph completed without interrupt) or a "pending review" status (graph interrupted).

**Endpoint 2: Get Pending Reviews.** The Kuber UI queries for all interrupted pipeline executions. This queries the checkpoint store for executions with status "interrupted." Returns a list of loans awaiting human review with their risk summaries.

**Endpoint 3: Submit Review Decision.** The human submits their decision. The API resumes the graph with the human's input and returns the final result.

This three-endpoint pattern cleanly separates automated pipeline execution from human review workflow. The graph handles AI logic. The API handles human interaction. The checkpoint store bridges the gap.

### 5.2 Checkpoint Cleanup

For completed pipelines, checkpoints can be deleted after the final result is persisted to DocumentDB. Set a TTL on Redis keys — 7 days is reasonable for interrupted pipelines. If the human does not respond in 7 days, the checkpoint expires and the evaluation must be restarted.

---

## 6. When NOT to Use Human-in-the-Loop

Not every MANUAL_REVIEW needs a graph interrupt. Consider alternatives.

If the review is simple (just approve/deny), skip the interrupt. Have the pipeline produce a "PENDING_REVIEW" decision and a batch process routes pending decisions to humans. Avoids interrupt/resume complexity.

If the review requires new data (human says "get a more recent credit report"), the interrupt pattern gets complicated — the response triggers more agent work. You may need a graph cycle: human_review → fetch_more_data → risk_scoring_v2 → human_review_again. LangGraph supports cycles.

If review turnaround is fast (minutes), a simpler blocking approach might work — the API holds the connection open. But for mortgage underwriting where reviews take days, the async interrupt/resume pattern is necessary.

---

## 7. Q&A

### Q: Does every checkpoint store the WHOLE context?

Yes. Each checkpoint is a complete snapshot. Checkpoint #3 contains EVERYTHING from fetch_data, doc_review, AND risk_scoring. It is self-contained — you can resume from #3 without needing #1 or #2. This is by design: full snapshots enable instant resume from any point.

### Q: If I run the whole flow again, do I need all context?

If restarting from scratch: no stored context needed, invoke with fresh initial state. If resuming from failure: the checkpoint has everything, load and continue. If resuming from human review: checkpoint has all four agents' outputs, inject human decision and continue.

### Q: The interrupt pauses the state machine?

Yes, literally. The process exits. Nothing runs. State persists in Redis. A new process (possibly different server) resumes later. Not a sleeping thread or waiting connection — a true pause with externalized state.

### Q: When the human returns, how does LangGraph find the right chain?

The thread_id is the key. Your API stores the thread_id with the pending review. When the human responds, your API calls resume with the same thread_id. LangGraph looks it up in Redis, finds the interrupted checkpoint, loads state, injects the response, continues execution. LangGraph does not "understand" human responses — it handles pause/persist/resume mechanics. The semantic meaning is your application logic.

### Q: What if the system restarts while a review is pending?

No impact. The checkpoint is in Redis, not in the process memory. Any new process instance can resume using the thread_id. This is the entire point of externalizing state to a checkpoint store.

### Q: How much storage do checkpoints use?

Approximately 10 KB per checkpoint, 30-50 KB per pipeline execution, 30-50 MB per day at 1,000 evaluations. With 7-day TTL: maximum 350 MB in Redis. Trivial.

---

## 8. Summary: Key Concepts

| Concept | What It Does | Java / AWS Equivalent |
|---------|-------------|----------------------|
| interrupt() | Pauses graph, saves state, returns message | Step Functions callback task |
| thread_id | Uniquely identifies one pipeline execution | SF execution ARN |
| Checkpoint (full snapshot) | Complete state at each node, enables instant resume | SF execution history |
| Resume with Command | Loads checkpoint, injects human input, continues | SF SendTaskSuccess |
| Redis checkpoint store | Persists state across process restarts | DynamoDB for SF state |
| TTL on checkpoints | Auto-cleanup of expired pending reviews | S3 lifecycle policy |
| Three-endpoint API | Start / pending reviews / submit decision | Workflow management API |
| Optimistic locking | Prevents double-resume of same thread | Conditional DynamoDB write |
| Nothing runs during pause | Process exits, state in Redis only | Serverless — no idle compute |
"""

with open("week4_day4.md", "w") as f:
    f.write(md_content)
print(f"✅ MD created: {len(md_content)} chars")