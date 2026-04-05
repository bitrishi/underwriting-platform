# Week 3, Day 5: Risk Scoring Agent — Sub-Agent #3

## Session Overview
**Date:** Week 3, Day 5  
**Topic:** Building the Risk Scoring Agent — the most sophisticated sub-agent combining ALL three data sources (calculation tools, RAG vector DB, and Neo4j knowledge graph) into a comprehensive, auditable risk assessment.  
**Prerequisites:** FetchData Agent (Week 2), Document Review Agent (Week 3 Day 3), Knowledge Graph (Week 3 Day 4), Smart RAG (Week 3 Day 1)

---

## 1. Why Risk Scoring Is the Most Complex Agent

### 1.1 The Three-Data-Source Architecture

Every other agent you've built uses one or two data sources. The Risk Scoring agent is the first to combine ALL three, and understanding WHY each source matters is the key architectural insight.

**Data Source 1: Calculation Tools (Deterministic Python)**

These are the pure math tools from Week 2 — calculate_dti, calculate_ltv, check_fico_eligibility, check_employment_stability. They take numbers in, apply formulas, return results. No AI involved. No ambiguity. DTI is 24% or it isn't. FICO is above 680 or it isn't.

In Java terms, these are your business rule engine — the equivalent of a RuleService with hard-coded thresholds. They produce the FACTUAL foundation of the risk assessment.

Why the agent needs them: The LLM should NEVER do math. If you ask Claude "what is 2400 × 12 / 120000 × 100?" it might get it right, it might not. But calculate_dti(120000, 2400) returns 24.0 every single time. Deterministic tools for deterministic calculations.

**Data Source 2: RAG / Vector DB (Policy Knowledge)**

The Smart RAG pipeline from Week 3 Day 1 retrieves lending policies, regulatory requirements, and compliance rules. It answers questions like "what is the maximum DTI for a Texas conventional loan?" by searching your policy document corpus.

In Java terms, this is like querying a document management system — you're looking up what the RULES say. The policies don't change per borrower; they're the same for everyone in the same jurisdiction and loan type.

Why the agent needs it: Calculation tools tell you the DTI IS 42%. RAG tells you the DTI LIMIT is 43% with compensating factors required above 38%. Without RAG, the agent knows the number but doesn't know the rule.

**Data Source 3: Knowledge Graph / Neo4j (Situational Intelligence)**

The knowledge graph from Week 3 Day 4 provides relationship-based context — industry default rates, similar loan outcomes, employer stability, regulatory mappings. It answers questions that neither calculations nor documents can: "How have other borrowers in this industry performed historically?"

In Java terms, this is like a risk analytics service that traverses entity relationships. It's not about what the rules say (that's RAG) or what the numbers are (that's calculation). It's about what the DATA shows for borrowers in similar situations.

Why the agent needs it: A borrower with FICO 710 and DTI 40% looks borderline by the numbers. But if their industry has an 8% default rate (vs 3% average) and 25% of similar loans defaulted, that changes the risk picture dramatically. No single document contains this insight — it emerges from traversing relationships in the graph.

### 1.2 The Synergy: Why Three Sources Together Are More Than the Sum

Consider this scenario: a borrower with FICO 710, DTI 40%, employed at a cryptocurrency startup for 2 years, seeking a Texas conventional loan.

**Calculation tools alone:** "DTI 40% passes the 43% threshold. FICO 710 passes the 680 minimum. LTV 85% exceeds 80% but below 95%. Employment 2 years meets minimum. Result: BORDERLINE PASS."

This is technically correct but dangerously incomplete. It misses that Texas has a special 80% LTV limit and that cryptocurrency is a high-risk industry.

**Add RAG:** "Texas Section 50(a)(6) limits LTV to 80%. This loan at 85% VIOLATES state regulation. DTI above 38% requires compensating factors per Fannie Mae B3-6-02."

Now we know about the policy violation. But we still don't know about the industry risk.

**Add Knowledge Graph:** "Cryptocurrency industry: 8% default rate (2.5x average). 47 similar loans, 12 defaulted (25.5%). Average defaulter FICO was 695 — this borrower at 710 is only 15 points above. Employer CryptoStartup founded 2021, funded by VC with 2 failed portfolio companies."

NOW the agent has the complete picture: the numbers (calculation), the rules (RAG), and the situational intelligence (graph). The recommendation changes from "borderline pass" to "DENY — LTV violates Texas law, and even if restructured, the industry risk profile and employer instability warrant significant concern."

This is the difference between a rules engine and an intelligent underwriter. The rules engine checks boxes. The intelligent agent connects dots.

---

## 2. Risk Scoring Architecture: How the Agent Works

### 2.1 The Agent's Decision Process

The Risk Scoring agent follows a deliberate process, encoded in its system prompt, that mirrors how a human senior underwriter evaluates a loan:

**Phase 1: Calculate the Facts**

First, establish the objective numbers. No judgment yet — just math.

The agent calls calculate_dti (income and debt data), calculate_ltv (loan amount and property value), check_fico_eligibility (credit score), and check_employment_stability (years at current employer).

This phase uses ONLY deterministic tools. The LLM decides which tools to call (based on what data is available in the input), but the tools themselves are pure Python functions. The LLM cannot influence the DTI calculation — it just receives the result.

**Phase 2: Gather Contextual Intelligence**

Now, go beyond the numbers. Understand the SITUATION.

The agent calls get_borrower_risk_context (traverses borrower → employer → industry → risk profile in Neo4j) and find_similar_past_loans (queries historical outcomes for borrowers in the same industry).

This phase uses the knowledge graph. The agent traverses entity relationships to find patterns. This is the intelligence that no rule book contains — it's emergent from the data.

**Phase 3: Check Policy Compliance**

Does this specific loan comply with all applicable regulations?

The agent calls search_lending_policies (routine policy lookup via RAG) and verify_compliance_requirement (thorough compliance check for critical regulatory questions).

This phase uses RAG with metadata filtering — the agent searches for policies matching the borrower's state and loan type. If the borrower is in Texas, only Texas regulations are retrieved.

**Phase 4: Synthesize and Score**

This is the ONLY phase where the LLM does the "thinking." It has all the facts (Phase 1), context (Phase 2), and rules (Phase 3). Now it weighs everything together: scores each criterion on a 0-100 scale, applies industry risk multipliers from the graph data, identifies policy violations and compensating factors, calculates an overall composite score, maps the score to a recommendation (APPROVE/DENY/MANUAL_REVIEW), and writes detailed reasoning for the audit trail.

### 2.2 Why This Order Matters

The order is not arbitrary. Each phase builds on the previous one. Phase 1 (Calculate) produces numbers that Phase 3 (Policy) compares against thresholds. Phase 2 (Graph) produces industry context that Phase 4 (Synthesis) uses as a risk multiplier. Phase 3 (Policy) produces specific rules that Phase 4 uses for violation flagging.

If the agent called tools in random order, it might check policies before calculating DTI — and then not know whether to search for "DTI exceptions" or "DTI standard rules" because it doesn't know the actual DTI yet.

The system prompt enforces this order, but the agent has flexibility WITHIN each phase. In Phase 1, it might calculate DTI before or after LTV depending on what data is available. The constraint is phase ordering, not individual tool ordering.

### 2.3 Tool Count and Agent Complexity

This agent has 8 tools — more than the 3-5 optimal range discussed in Week 2. Why is this acceptable?

The tools fall into clearly distinct categories: 4 calculation tools (each does one specific calculation — unambiguous), 2 RAG tools (one for routine lookup, one for critical verification — distinct docstrings), and 2 graph tools (one for borrower context, one for similar loans — different purposes).

The agent rarely confuses tools because they serve completely different purposes. "Calculate DTI" and "find similar loans" are not ambiguous — no docstring overlap. This is different from having 8 tools that all do variations of "search documents."

That said, in production you might split this into two sub-agents: a Calculation Agent (4 tools) and a Context Agent (4 tools), with a mini-orchestrator combining their results. This is a valid optimization but adds architectural complexity. For now, 8 well-differentiated tools work fine.

---

## 3. Scoring Theory: Quantifying Risk

### 3.1 Individual Criterion Scoring

Each underwriting criterion is scored independently on a 0-100 scale. The scoring is NOT done by the LLM making up numbers — it follows explicit guidelines defined in the system prompt. This is a hybrid approach: the thresholds are deterministic, but the agent applies judgment for borderline cases.

**DTI Scoring:**
DTI ≤ 36% scores 100 (excellent — well below any threshold). DTI 36-38% scores 80-90 (good — below standard maximum). DTI 38-43% scores 50-70 (borderline — requires compensating factors per most guidelines). DTI above 43% scores 0-40 (fails standard QM threshold).

**FICO Scoring:**
FICO ≥ 740 scores 100 (excellent credit tier). FICO 700-739 scores 80-90 (good credit). FICO 680-699 scores 60-75 (acceptable, meets minimum). FICO below 680 scores 0-50 (below minimum for most conventional loans).

**LTV Scoring:**
LTV ≤ 75% scores 100 (strong equity position). LTV 75-80% scores 85-95 (at conventional limit, no PMI). LTV 80-90% scores 50-70 (requires PMI). LTV 90-95% scores 30-50 (high LTV, elevated risk). LTV above 95% scores 0-20 (very high risk, limited programs).

**Employment Scoring:**
5+ years at current employer scores 100 (very stable). 2-5 years scores 70-90 (meets standard requirements). 1-2 years scores 50-65 (borderline, may need additional documentation). Under 1 year scores 20-45 (unstable, significant risk factor).

Why ranges instead of fixed values? Because the LLM adds context-aware judgment within the range. A DTI of 38% for a tech worker with stable income deserves a higher score within the 80-90 range than a DTI of 38% for a seasonal worker. The ranges provide guardrails while allowing the agent to reason about the specific situation.

### 3.2 Industry Risk Multiplier

This is where the knowledge graph data directly impacts the score. The industry default rate modifies the overall score after individual criterion scoring:

Default rate below 3% (healthcare, government): No adjustment. This is the baseline. Default rate 3-5% (technology, manufacturing): -5 points. Slightly elevated risk. Default rate 5-10% (cryptocurrency, speculative sectors): -10 points. Significant risk. Default rate above 10% (highly volatile industries): -20 points. Major risk factor.

This multiplier is applied AFTER individual criterion scoring. So a borrower with 75/100 from criteria in a 7% default rate industry becomes 65/100 — potentially pushing them from APPROVE to MANUAL_REVIEW.

The multiplier recognizes that individual borrower metrics don't exist in a vacuum. A perfect borrower in a collapsing industry is still at risk because their employer might fail, their income might disappear, and the property market in their area (often correlated with industry) might decline.

### 3.3 Overall Score to Recommendation Mapping

Score 80-100 maps to LOW risk and APPROVE. Score 60-79 maps to MEDIUM risk and APPROVE with conditions (may require additional documentation, higher rate, or reduced loan amount). Score 40-59 maps to HIGH risk and MANUAL_REVIEW (escalate to senior underwriter). Score 0-39 maps to CRITICAL risk and DENY.

The MANUAL_REVIEW category is critical for production. Rather than forcing binary APPROVE/DENY, borderline cases go to a human. This is important for three reasons. First, regulatory protection — regulators want to see that borderline cases get human judgment, not just AI decisions. Second, error handling — if the agent misinterpreted data or missed context, the human catches it. Third, fairness — automated denials can create disparate impact, and human review adds a fairness check.

### 3.4 Compensating Factors and Risk Factors

The agent doesn't just produce a number — it identifies specific factors that strengthen or weaken the application.

Compensating factors are things that improve the case despite borderline numbers: FICO significantly above minimum (e.g., 750 when minimum is 680), low DTI offsetting high LTV, very stable employment (10+ years same employer), significant cash reserves (6+ months of mortgage payments), or low overall debt burden despite one high metric.

Risk factors are things that worsen the case beyond what numbers show: industry with high default rate, young employer (under 3 years old), employer connected to flagged entities, multiple borderline criteria (no single fail but everything is marginal), missing documentation (from Document Review agent), or cross-document discrepancies (income doesn't match across W-2 and tax return).

The agent lists these explicitly in the output because they form the REASONING that regulators need for the audit trail. A score of 55 with clear compensating factors might be treated differently than a score of 55 with additional risk factors.

---

## 4. How the Agent Decides Which Tools to Call

### 4.1 Tool Selection Is Input-Dependent

The agent doesn't always call all 8 tools. It reads the input and decides what's needed.

For a full evaluation with all data provided, it calls all 8 tools — calculates all metrics, checks graph, verifies policies. For partial data with missing income, it skips DTI calculation (can't calculate without income), still checks FICO, LTV, employment, and notes "DTI: UNABLE TO CALCULATE — income data missing." For a specific question like "Is this FICO eligible?", it only calls check_fico_eligibility and doesn't waste tokens on unrelated tools.

This adaptive behavior comes from the system prompt instruction to "use the appropriate tools based on available data" combined with the LLM's reasoning about what data is present in the input.

### 4.2 Handling Missing Data

In production underwriting, data is often incomplete. The agent handles this gracefully.

If a tool can't be called (missing input data), the agent notes it as an "UNABLE TO VERIFY" criterion rather than skipping it silently. This is critical for audit — the decision record must show what was checked and what COULDN'T be checked.

If a tool returns an error (external API timeout, graph connection failure), the agent flags it as a risk factor: "Industry context unavailable — unable to assess industry risk. Recommend manual review."

The design principle: NEVER silently skip a check. Either verify it, or explicitly document that you couldn't.

---

## 5. Production Considerations

### 5.1 Deterministic vs. LLM-Based Scoring

A key architectural question: should the scoring be done by the LLM or by deterministic Python code?

The current approach uses LLM scoring within guidelines. The LLM receives the scoring guidelines in its system prompt and produces scores. The guidelines constrain the output (DTI ≤ 36% must score 80-100), but the LLM has judgment within ranges. The pros are that it can consider nuances, compensating factors, and unusual situations — more like a human underwriter. The cons are that it's non-deterministic (same application might get 72 or 75 on different runs) and harder to audit.

The alternative approach uses deterministic scoring plus LLM synthesis. Python functions calculate exact scores using fixed formulas. The LLM only synthesizes the narrative — explaining WHY the score is what it is. The pros are reproducibility (same input always produces same score) and easy auditing. The cons are that it can't handle edge cases or nuances — purely mechanical.

The production recommendation is a hybrid. Use deterministic scoring for the numbers (DTI score = 85, FICO score = 72, etc.) and use the LLM for synthesis, compensating factor identification, and narrative generation. This gives you auditability on the scores and intelligence on the reasoning.

### 5.2 Audit Trail Requirements

For the company-level production, every risk assessment must include: what data was used (specific values for every criterion), where data came from (which tools were called, what they returned), what rules were applied (policy citations from RAG), what context was considered (industry data from knowledge graph), what the decision was (score, level, recommendation), why the decision was made (step-by-step reasoning), and what was NOT available (missing data, failed tool calls).

The RiskAssessment Pydantic model captures all of this. The format_report() method produces a human-readable version. The callback tracer from Week 2 captures the tool call history. Together, these provide a complete audit trail that satisfies regulatory requirements.

### 5.3 Cost Per Risk Assessment

Phase 1 (Calculation): 4 tool calls at approximately $0.0003 each (Haiku per call) = $0.0012. The calculation tools themselves are free (pure Python). The cost is the 4 LLM calls where the agent DECIDES to call each tool.

Phase 2 (Graph): 2 tool calls at approximately $0.0003 each = $0.0006. The Neo4j queries themselves are negligible cost.

Phase 3 (RAG): 2 tool calls at approximately $0.001 each (if using Smart RAG with Sonnet for critical queries) = $0.002.

Phase 4 (Synthesis): 1 final LLM call to produce the assessment at approximately $0.001.

Plus the growing agent_scratchpad context (each tool call adds approximately 200-400 tokens to subsequent calls).

Total estimated cost: approximately $0.005-$0.010 per risk assessment. At 1,000 evaluations per day: $5-10 per day.

---

## 6. How Risk Scoring Connects to the Full Pipeline

### 6.1 Upstream: What Feeds Into Risk Scoring

The Risk Scoring agent doesn't gather data itself — it receives pre-gathered data from the other agents.

From the FetchData Agent (Week 2), it receives the BorrowerPackage containing borrower profile, credit report, employment record, and applicable policies from RAG. This gives the agent the RAW NUMBERS (income, debt, FICO, years employed).

From the Document Review Agent (Week 3 Day 3), it receives the DocumentReviewPackage containing extracted document data, cross-validation results, and missing document flags. This gives the agent VERIFIED DATA (W-2 wages confirmed, employer name matches across documents). If Document Review found discrepancies, Risk Scoring treats them as risk factors.

### 6.2 Downstream: What Consumes the Risk Assessment

The Compliance Agent (Week 4) will receive the RiskAssessment and perform a final regulatory compliance check — ensuring the recommendation doesn't violate any fair lending laws, that all required disclosures are triggered, and that the audit trail is complete.

The Orchestrator (Week 4) coordinates the entire flow and presents the final decision to the user/system.

### 6.3 The Weekend BUILD: Three-Agent Pipeline

The Weekend BUILD wires FetchData, Document Review, and Risk Scoring into a sequential pipeline — a precursor to the full LangGraph orchestrator in Week 4. This pipeline takes an application ID and document paths as input, runs all three agents in sequence, and produces a complete underwriting decision report.

This sequential pipeline works but is not optimal. FetchData and Document Review are independent — they could run in parallel. Error handling is basic. There's no conditional routing or human-in-the-loop. Week 4's LangGraph solves all of these by converting the sequential pipeline into a proper state machine graph.

---

## 7. The Pydantic Output Model: Design Rationale

### 7.1 CriterionScore Model

Each individual criterion gets its own CriterionScore object with name, value, threshold, passed (boolean), score (0-100), and detail (explanation string).

Why separate the boolean passed from the integer score? Because they serve different purposes. The passed field is a hard gate: does this criterion meet the minimum requirement? The score field is a gradient: how WELL does it meet the requirement? A FICO of 681 passes (passed=true) but scores poorly (score=55). A FICO of 780 also passes but scores excellently (score=100). The boolean handles policy compliance; the score handles risk grading.

### 7.2 IndustryContext Model

This model wraps the knowledge graph data in a structured format: industry name, default rate, similar loan counts, average defaulter FICO, risk level, and a context note.

The avg_defaulter_fico field is optional (None if not enough data). This is important — if the graph has only 3 loans in an industry, the average defaulter FICO is statistically meaningless. The agent should note this: "Insufficient data for industry FICO analysis (n=3)."

### 7.3 RiskAssessment Model

The top-level model combines everything: overall score, risk level, recommendation, individual criteria scores, industry context, policy violations, policy warnings, document issues, reasoning, compensating factors, and risk factors.

The has_critical_issues() method is a convenience for downstream consumers — if any cross-validation found CRITICAL severity issues, the entire assessment should be escalated regardless of the score.

The format_report() method produces the human-readable audit trail. This is what a senior underwriter or regulator would read. It's not a debug log — it's a professional underwriting decision document.

---

## 8. Expected Agent Behavior: Walkthrough

To make the agent's behavior concrete, here is what happens when the Risk Scoring agent receives a borderline application: FICO 710, Income $95K, Debt $3,200/month, Loan $310K, Property $365K in Texas, Employer CryptoStartup for 2 years.

The agent first enters Phase 1 and calls calculate_dti(95000, 3200), which returns DTI of 40.4% passing the 43% threshold. It calls calculate_ltv(310000, 365000), which returns LTV of 84.9% requiring PMI. It calls check_fico_eligibility(710), which returns tier GOOD and eligible true. It calls check_employment_stability(2.0), which returns meets_minimum true with stability MODERATE.

The agent then enters Phase 2 and calls get_borrower_risk_context("1234"), which traverses the knowledge graph and returns that the borrower works in the cryptocurrency industry with an 8% default rate. It calls find_similar_past_loans("cryptocurrency"), which returns 12 approved and 3 defaulted out of 15 total similar loans.

In Phase 3, the agent calls search_lending_policies with the DTI compensating factors topic filtered to Texas jurisdiction, and gets back that DTI between 38-43% requires compensating factors. It calls verify_compliance_requirement for Texas LTV limits and discovers that Texas Section 50(a)(6) limits LTV to 80%.

Finally in Phase 4, the agent synthesizes everything. FICO 710 scores 75/100. DTI 40.4% scores 55/100. LTV 84.9% scores 30/100 (violates Texas 80% limit). Employment 2 years scores 65/100. Raw composite is approximately 56. Industry risk multiplier of -10 brings it to 46. Risk level: HIGH. Recommendation: MANUAL_REVIEW with a policy violation flag on LTV.

The reasoning notes: "LTV 84.9% exceeds Texas Section 50(a)(6) maximum of 80% — this is a policy violation that must be resolved. Even if restructured to meet LTV, borderline DTI (40.4%) in a high-risk industry (cryptocurrency, 8% default rate, 25% of similar loans defaulted) combined with relatively short employment tenure (2 years) warrants senior underwriter review. Compensating factor: FICO 710 is above minimum and above the average defaulter FICO of 695 for this industry."

---

## 9. Comparison: Rules Engine vs. Agent-Based Risk Scoring

### Traditional Rules Engine (Drools, Java-based)

A traditional rules engine evaluates predefined IF-THEN rules against data. In Java, you'd define rules like "IF dti > 43 THEN deny" and "IF fico < 680 THEN deny." The engine executes all applicable rules and produces a deterministic result.

Strengths: completely deterministic, fast execution, easy to audit (rules are explicit code), established regulatory acceptance.

Weaknesses: cannot handle ambiguity or competing factors, requires a new rule for every edge case (rule explosion), cannot explain WHY in natural language (just which rules fired), cannot dynamically seek additional context, cannot weigh compensating factors against risk factors.

### Agent-Based Risk Scoring (What You're Building)

The agent receives the same data but REASONS about it. It can weigh that a borderline DTI is offset by excellent FICO. It can recognize that an industry risk multiplier changes the picture. It can generate a natural language explanation that a regulator or senior underwriter can read and understand.

Strengths: handles nuance and ambiguity, generates human-readable explanations, can dynamically seek additional context (call more tools if needed), weighs competing factors, adapts to unusual situations without new rules.

Weaknesses: non-deterministic (same input may produce slightly different reasoning), harder to audit (LLM reasoning is a black box), more expensive (multiple LLM calls vs. in-memory rule execution), requires careful prompt engineering to ensure consistent behavior.

### The Hybrid Production Approach

The best production systems combine both. Hard rules (FICO < 580 is always DENY, LTV > 97% is always DENY) are implemented as deterministic Python code that runs BEFORE the agent. The agent handles the gray area — borderline cases where multiple factors must be weighed. This gives you the speed and determinism of a rules engine for clear-cut cases, and the intelligence of an agent for complex ones.

---

## 10. Q&A

### Q: Why does the agent need all three data sources? Can't RAG alone be sufficient?

RAG finds what DOCUMENTS say — policies, regulations, guidelines. It tells you the rules. But rules alone don't make good underwriting decisions. You also need the actual numbers (calculation tools) and the situational context (knowledge graph). A real underwriter doesn't just read the rulebook — they calculate the metrics, check the borrower's background, and compare to past experience. The three data sources mirror this: calculation equals metrics, RAG equals rulebook, graph equals experience.

### Q: Can the scoring be fully deterministic instead of LLM-based?

Yes, and for some production deployments this is preferable. You'd write Python functions that compute exact scores from formulas, then use the LLM only for narrative synthesis. The tradeoff: deterministic scoring is reproducible and auditable but can't handle edge cases. LLM scoring handles nuance but introduces variability. The recommended hybrid uses deterministic scores plus LLM narrative.

### Q: What happens if the knowledge graph has no data for the borrower's industry?

The agent handles this gracefully. The IndustryContext model has optional fields for exactly this reason. If the graph returns no industry data, the agent sets industry_context to None and notes in the reasoning: "Industry context unavailable — no historical data for this sector. Scoring based on standard criteria only." It does NOT make up industry data.

### Q: How is this different from a traditional rules engine?

A traditional rules engine (like Drools in Java) evaluates predefined rules against data and produces a deterministic result. It can't handle ambiguity, weigh competing factors, or generate explanations. The Risk Scoring agent does all of these: it weighs compensating factors against risk factors, handles missing data gracefully, generates detailed reasoning, and adapts its analysis to the specific situation. It's a rules engine plus reasoning engine plus explanation generator combined.

### Q: Why not have the Orchestrator do the risk scoring directly instead of a separate agent?

Separation of concerns. The orchestrator's job is routing — deciding which agent to call and when. The risk scoring agent's job is assessment — evaluating risk comprehensively. If you put both in one agent, you'd have 15+ tools (routing tools plus calculation tools plus RAG tools plus graph tools), which degrades tool selection accuracy. Each agent stays focused with 3-8 tools in its domain.

### Q: What about fair lending compliance? Can an AI agent make loan decisions?

This is a critical regulatory question. The Equal Credit Opportunity Act (ECOA) and Fair Housing Act prohibit discrimination in lending. An AI system making loan decisions must be explainable — you must be able to show WHY a loan was denied. The RiskAssessment's detailed reasoning, source citations, and criteria scores provide this explainability. However, most production deployments use the agent for RECOMMENDATION, not DECISION. A human underwriter makes the final call, especially for denials and borderline cases (MANUAL_REVIEW). The agent assists the human; it doesn't replace them.

### Q: How do you test that the agent produces consistent results?

This is what Week 6's evaluation framework (LangSmith/Ragas) addresses. You create a test dataset of loan applications with KNOWN correct outcomes (approved/denied by human underwriters). You run the agent on all test cases and measure: decision accuracy (does it match the human?), score consistency (similar applications get similar scores?), reasoning quality (are the cited factors relevant?), hallucination rate (does it claim things not supported by data?). This is the AI equivalent of regression testing.

---

## 11. Summary: Key Concepts

| Concept | What It Does | Java Equivalent |
|---------|-------------|-----------------|
| Three-source architecture | Combines calculation + RAG + graph | Service aggregating multiple data sources |
| Phased evaluation | Calculate → Context → Policy → Synthesize | Pipeline pattern with ordered stages |
| Criterion scoring (0-100) | Quantifies each risk factor individually | Scoring model with weighted factors |
| Industry risk multiplier | Graph data modifies overall score | Risk adjustment from external data feed |
| Compensating factors | Strengths that offset weaknesses | Business rule exceptions |
| MANUAL_REVIEW category | Borderline cases escalated to humans | Escalation workflow |
| Audit trail | Complete reasoning for every decision | Regulatory compliance logging |
| Deterministic vs LLM scoring | Hard numbers vs contextual judgment | Rules engine vs expert system |
| format_report() | Human-readable decision document | Report generator service |
| has_critical_issues() | Quick check for escalation triggers | Alert/flag mechanism |
| Hybrid approach | Deterministic scores + LLM reasoning | Rules engine + AI assistant |
| Fair lending compliance | Explainability for regulatory requirements | ECOA/FHA audit documentation |