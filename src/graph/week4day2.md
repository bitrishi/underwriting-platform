# Create Week 4 Day 2 markdown
md_content = """# Week 4, Day 2: Parallel Execution, Error Handling & Compliance Agent

## Session Overview
**Date:** Week 4, Day 2  
**Topic:** Making the LangGraph orchestrator production-grade — real parallel execution, error handling that doesn't crash the pipeline, the Compliance agent (sub-agent #4), and the architecture decision framework for when to use one agent vs. multiple agents.  
**Prerequisites:** Week 4 Day 1 (LangGraph fundamentals, graph compiling and running)

---

## 1. Parallel Execution: Making It Real

### 1.1 How LangGraph Determines Parallel vs Sequential

The graph TOPOLOGY defines execution order — not explicit async code. When you add two edges from the same source node to different target nodes, LangGraph automatically runs those targets concurrently using asyncio under the hood.

Two edges from START to different nodes means parallel. One edge from node A to node B means sequential — B waits for A. This is the same as Step Functions: a Parallel state runs branches concurrently because the state machine definition says so, not because you wrote threading code.

### 1.2 The Convergence Point

When a node has multiple incoming edges, LangGraph waits for ALL incoming sources to complete before executing that node. This is the join behavior.

If fetch_data finishes in 2 seconds but doc_review takes 8 seconds, risk_scoring waits the full 8 seconds. The state from fetch_data sits in memory, already merged, waiting for doc_review's contribution. Only when BOTH are done does risk_scoring execute with the complete state.

Java analogy: CompletableFuture.allOf(fetchFuture, docReviewFuture).thenRun(riskScoring). The join is implicit in the graph structure.

### 1.3 Conditional Parallel: Handling Empty Documents

The graph always starts both fetch_data and doc_review in parallel. But what if there are no documents? Rather than complex conditional parallel routing (which LangGraph doesn't natively support for fan-out), the production pattern is to let doc_review handle the empty case internally.

The node checks if document_paths is empty. If so, it returns instantly with a SKIPPED status and flags all required documents as missing. The overhead of starting a node that returns instantly is microseconds — negligible compared to the complexity of conditional parallel routing.

This pattern is used frequently in production: always start the node, let the node decide if it has real work to do. The graph topology stays simple (always parallel) and the business logic lives in the node where it belongs.

---

## 2. Error Handling in Nodes

### 2.1 The Pattern: Try/Except in Every Node

In sequential code, one failure crashes everything. In LangGraph, each node should handle its own errors and write the failure to state so the pipeline can continue or gracefully degrade.

Every node wraps its agent call in a try/except block. On failure, it sets its output field to None and appends an error message to the errors list (which uses the add reducer to accumulate from all nodes). The pipeline continues — downstream nodes check if their input data exists and handle the None case.

This is like Java's @CircuitBreaker pattern — a failure in one service doesn't cascade to the entire system. Each service handles its own failures and reports status.

### 2.2 Fatal Error Routing

Some failures ARE fatal — if FetchData can't even identify the borrower, there's no point running Risk Scoring or Compliance. A conditional edge after fetch_data checks if borrower_package is None. If so, it routes directly to final_decision with an error report, skipping all intermediate nodes.

This gives you graceful degradation: partial failures produce partial assessments with clear flags. Total failures skip to an error report. The pipeline never crashes silently.

### 2.3 The Safe Default: When In Doubt, Escalate

If any node fails in a way that leaves uncertainty, the safe default is to set needs_manual_review to True. This ensures a human reviews any case where the automated system couldn't complete its work. Better to escalate unnecessarily than to miss a problem.

---

## 3. The Compliance Agent: Sub-Agent #4

### 3.1 What Compliance Checks That Risk Scoring Does Not

Risk Scoring asks: "Is this loan risky?" — evaluates financial metrics, industry context, document quality. Compliance asks: "Is this decision LEGAL?" — evaluates regulatory adherence, fair lending, required disclosures. These are fundamentally different domains of expertise.

Specifically, the Compliance agent checks four categories.

**Fair Lending.** The Equal Credit Opportunity Act (ECOA) prohibits discrimination based on race, color, religion, national origin, sex, marital status, or age. The Compliance agent doesn't have access to protected characteristics (by design — this is a critical architectural choice). Instead, it verifies that denial reasons are based ONLY on legitimate financial factors documented in the RiskAssessment. If a denial cites only "industry risk" without specific financial justification, that could be a fair lending concern.

**Disclosure Requirements.** TRID (TILA-RESPA Integrated Disclosure) has strict timing rules. A new application requires a Loan Estimate within 3 business days. A denial requires an Adverse Action Notice within 30 days with specific reasons. An approval requires a Closing Disclosure at least 3 business days before closing. State-specific disclosures may also apply (Texas Section 50(a)(6) requires a 12-day notice). The Compliance agent verifies that all required disclosures are identified and triggered.

**State-Specific Procedural Requirements.** Beyond the policy compliance that Risk Scoring checks (DTI limits, LTV limits), states may have procedural requirements — specific language in disclosures, cooling periods, attorney review requirements. The Compliance agent uses RAG to verify these.

**Audit Trail Completeness.** Is the RiskAssessment sufficient for regulatory examination? Does it cite specific data for every claim? Does it document what was checked and what could not be verified? If the audit trail is incomplete, the Compliance agent flags it — because an incomplete audit trail is itself a compliance risk.

### 3.2 Compliance Can Override Recommendations

This is important: the Compliance agent can CHANGE the final recommendation. If Risk Scoring says APPROVE but Compliance finds a regulatory violation (LTV exceeds Texas maximum, missing required disclosure), the Compliance agent can override to DENY or MANUAL_REVIEW.

In the graph, this works through the needs_manual_review flag. The compliance_node checks its results: if any VIOLATION is found or if status is NON_COMPLIANT, it sets needs_manual_review to True regardless of what Risk Scoring decided. The conditional edge after compliance then routes to human_review.

### 3.3 The Compliance Tools

Two tools are RAG-based (already built in Weeks 2-3): verify_compliance_requirement for thorough regulatory lookups and search_lending_policies for routine policy lookups.

Two tools are new and deterministic (pure Python, no LLM). check_disclosure_requirements takes the decision, state, and application status and returns a list of required disclosures with timing based on TRID/ECOA/state rules. verify_audit_trail checks the risk assessment text for completeness — does it cite FICO, DTI, LTV? Does it have reasoning? Does it have a recommendation?

These deterministic tools encode hard regulatory rules that should never be left to LLM interpretation. "A Loan Estimate is required within 3 business days" is not a judgment call — it is a rule that Python code should enforce.

### 3.4 Why Sonnet for Compliance

The Compliance agent uses Sonnet (via create_llm(task="compliance")) rather than Haiku. Legal and regulatory reasoning requires understanding nuance — "does this denial reason constitute a legitimate business justification under ECOA?" is a harder reasoning task than "calculate DTI." The cost difference (Sonnet is roughly 12x Haiku per token) is justified for the compliance domain where mistakes have legal consequences.

---

## 4. When to Use One Agent vs. Multiple Agents

### 4.1 The Core Tradeoff

One agent is simpler to build and deploy. Multiple agents add orchestration complexity. The question is whether the benefits of splitting justify that complexity.

### 4.2 Three Concrete Failure Modes of One Large Agent

**Tool Selection Accuracy Degrades.** Past 10-15 tools, the LLM occasionally picks the wrong one. With 17 tools, expect 5-10% wrong tool selection rate. In 1,000 daily evaluations, that is 50-100 errors. With 4 agents of 4-5 tools each, tool selection is nearly perfect within each agent because the tools are clearly distinct.

**The System Prompt Becomes Unmanageable.** One agent needs ONE prompt covering data fetching, document review, risk scoring, and compliance. The prompt becomes enormous and contradictory — "You are a data fetcher AND a document reviewer AND a risk scorer AND a compliance officer." Each role has different rules, different priorities, different model requirements. With separate agents, each has a focused, non-contradictory prompt.

**You Cannot Use Different Models.** Your multi-model architecture assigns Haiku for calculations (cheap), Sonnet for vision (strong), Sonnet for compliance (legal reasoning). One agent means one model for everything — either overspend (Sonnet for calculations) or underperform (Haiku for legal reasoning). Separate agents enable optimal model selection per task.

### 4.3 The Decision Framework

Ask these questions in order. If you hit a "yes," consider splitting:

1. More than 10 tools total? Split into groups of 4-8.
2. Different tools need different models? Each model requirement equals a separate agent.
3. Independent tasks that could run in parallel? Separate agents enable parallelism.
4. Need isolated error handling? Separate agents can fail independently.
5. System prompt would be contradictory? Split by domain expertise.
6. Want to test or deploy components independently? Separate agents equal separate test suites.

If all answers are "no" — one agent is fine. Do not over-engineer.

### 4.4 The Practical Grouping Principle

Group tools by CAPABILITY DOMAIN and MODEL REQUIREMENT, not by individual function.

FetchData groups 4 tools that all call external APIs, all use Haiku, all need the same timeout/retry handling. Document Review groups 4 tools that all process images/PDFs, all need Sonnet for vision. Risk Scoring groups 8 tools (the largest agent) spanning calculations, RAG, and graph — all serving one purpose (risk evaluation) with a coherent prompt. Compliance groups 4 tools for regulatory verification, needs Sonnet for legal reasoning.

If Risk Scoring had 15 tools, you would split it further. If Compliance only had 2 tools, you might merge it with Risk Scoring. The boundaries are pragmatic, driven by the failure modes above, not dogmatic.

### 4.5 The Counter-Example: When One Agent Is Right

If your system only did basic loan eligibility with 6 tools (pull_borrower, pull_credit, calculate_dti, calculate_ltv, check_fico, search_policies), ONE agent handles this perfectly. All tools use Haiku, no vision needed, simple linear flow, one coherent prompt. Building 3 agents for 6 tools would be over-engineering that adds orchestration complexity with zero benefit.

### 4.6 The Microservices Parallel

This maps directly to the microservices architecture decision. A monolith works fine when the application is small and the team is small. You split into microservices when the codebase becomes too large for one team, components need to scale independently, different components need different technology stacks, or you need fault isolation. Agent architecture follows the same principles — split when complexity demands it, not before.

---

## 5. The Updated Graph: All Four Agents

### 5.1 Complete Graph Structure

With the Compliance agent added, the full graph is:

START splits into two parallel branches (fetch_data and doc_review). Both converge at risk_scoring. After risk_scoring, compliance runs. After compliance, a conditional edge routes to either human_review (if needs_manual_review) or final_decision. After human_review, execution continues to final_decision. Final_decision connects to END.

An additional error path exists: if fetch_data fails fatally (borrower_package is None), a conditional edge routes directly to final_decision, skipping risk_scoring and compliance entirely.

### 5.2 Node Summary

| Node | Agent | Model | Tools | Purpose |
|------|-------|-------|-------|---------|
| fetch_data | FetchData | Haiku | 4 (API calls) | Gather borrower data |
| doc_review | Doc Review | Sonnet | 4 (vision) | Process loan documents |
| risk_scoring | Risk Scoring | Haiku | 8 (calc + RAG + graph) | Assess risk |
| compliance | Compliance | Sonnet | 4 (RAG + rules) | Verify regulatory compliance |
| human_review | N/A | N/A | interrupt() | Pause for human input |
| final_decision | N/A | N/A | Format report | Produce final output |

---

## 6. Q&A

### Q: Why do I need 4 agents? Could one agent with all tools work?

Yes, for simple cases with fewer than 10 tools. For your system with 17 tools across different capability domains (API calls, vision, calculations, legal reasoning) needing different models (Haiku vs Sonnet), one agent degrades in tool selection accuracy, requires a contradictory system prompt, and prevents optimal model selection. The split follows the same principles as your Kuber microservices decision.

### Q: When should I use one agent vs multiple?

The decision checklist: more than 10 tools, different model requirements, independent parallel tasks, need isolated error handling, contradictory prompts, or independent testing/deployment. If none of these apply, one agent is simpler and better.

### Q: What if doc_review has no documents?

The node handles it internally — checks if document_paths is empty, returns instantly with SKIPPED status and missing document flags. The graph topology stays simple (always parallel). The business logic lives in the node.

### Q: What happens if a node fails?

Try/except in every node. On failure: set output to None, append error to errors list, continue pipeline. Downstream nodes check for None inputs. Fatal failures route to final_decision via conditional edge. Safe default: if compliance fails, escalate to human review.

### Q: Can Compliance override Risk Scoring's recommendation?

Yes. If Compliance finds a regulatory violation, it sets needs_manual_review to True regardless of Risk Scoring's decision. The conditional edge after compliance routes to human_review. This is by design — regulatory compliance takes precedence over risk assessment.

### Q: Why Sonnet for Compliance but Haiku for Risk Scoring?

Legal reasoning is harder than financial calculation. "Does this denial reason constitute a legitimate business justification under ECOA?" requires nuanced understanding that Sonnet handles better. The 12x cost difference is justified because compliance mistakes have legal consequences. Risk Scoring's calculations and straightforward tool calls work well with Haiku.

### Q: Is the microservices analogy exact?

Very close. Monolith vs microservices decision factors (team size, independent scaling, technology diversity, fault isolation) map directly to single agent vs multi-agent factors (tool count, model diversity, parallel execution, error isolation). The main difference: microservices communicate over the network, agents communicate through shared state in memory.

---

## 7. Summary: Key Concepts

| Concept | What It Does | Java / AWS Equivalent |
|---------|-------------|----------------------|
| Parallel fan-out | Two edges from same source run concurrently | Parallel state in Step Functions |
| Convergence join | Node with two incoming edges waits for both | Parallel state end / allOf() |
| Node error handling | Try/except writes to errors, does not crash | @CircuitBreaker pattern |
| Fatal error routing | Conditional edge skips to end on total failure | Step Functions Fail state |
| Safe default escalation | Uncertainty triggers human review | Escalation workflow |
| Compliance agent | Verifies decision is legal, not just financially sound | Regulatory compliance service |
| Compliance override | Can change APPROVE to DENY on violation | Regulatory veto authority |
| Multi-model routing | Haiku for calc, Sonnet for vision/legal | Different service tiers |
| Agent split decision | Split when tools exceed 10, models differ, or domains conflict | Monolith vs microservices |
| Capability domain grouping | Group tools by what they do and what model they need | Domain-driven service boundaries |
"""

with open("week4_day2.md", "w") as f:
    f.write(md_content)

print(f"✅ Markdown created: {len(md_content)} characters")