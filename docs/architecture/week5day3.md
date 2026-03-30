md_content = """# Week 5, Day 3: Bedrock Guardrails — Content Safety for Production

## Session Overview
**Date:** Week 5, Day 3
**Topic:** AWS Bedrock Guardrails — content filtering, PII protection, denied topics, word filters, and contextual grounding checks. Implementation for production underwriting with per-agent guardrail configurations.
**Prerequisites:** Week 5 Day 1-2 (MCP, A2A), Week 4 complete orchestrator

---

## 1. Why Guardrails Are Non-Negotiable for Financial Services

### 1.1 The Risks Without Guardrails

Your underwriting agent processes SSNs, income data, and credit scores. Without guardrails it could leak PII if someone asks "what SSN did you just process?" and the agent helpfully answers. It could generate discriminatory content — statements about neighborhoods, demographics, or protected characteristics that constitute illegal redlining under the Fair Housing Act. It could hallucinate regulatory advice, confidently stating incorrect limits that lead to non-compliant loan approvals. It could go off-topic, wasting Sonnet API costs on poems and jokes in a financial system's logs. And adversarial input could trick it into generating content about mortgage fraud or document falsification.

### 1.2 Regulatory Requirement

For Goldman production, guardrails are not optional. OCC, CFPB, and FDIC all expect financial institutions to have controls on AI systems. A system that processes real loans with real borrower data requires content safety enforcement at the infrastructure level, not just prompt-level instructions.

---

## 2. What Bedrock Guardrails Are

### 2.1 Architecture

Bedrock Guardrails is a managed AWS service that sits BETWEEN your application and the LLM. It intercepts BOTH directions — input (what you send to the model) and output (what the model returns) — checking each against configurable policies.

Without guardrails: your agent code sends directly to Bedrock LLM and gets a response with no filtering. With guardrails: your agent code sends to Guardrails (input check) which passes to Bedrock LLM, and the response passes through Guardrails (output check) before reaching your code.

Think of it as Kong API Gateway for AI. Kong sits between clients and services enforcing rate limits, authentication, and content policies. Bedrock Guardrails sits between your agent code and the LLM enforcing content safety, PII filtering, and topic restrictions.

### 2.2 Transparent Integration

Guardrails intercept at the API level. You do NOT modify your agent code, prompts, or tools. You configure guardrails in the AWS console or via boto3, get a guardrail ID, and reference it when creating your ChatBedrock client. The filtering happens transparently on every invoke() call.

---

## 3. The Five Types of Guardrails

### 3.1 Content Filters — Block Harmful Content

Filters for hate speech, insults, sexual content, violence, and misconduct. Each category has configurable threshold: none, low, medium, high. For underwriting, set all to HIGH — no reason for an underwriting agent to generate any of this.

Works on BOTH input and output. Adversarial prompt injection caught on input. LLM-generated harmful content caught on output.

The misconduct filter is particularly important for financial services — catches content about financial fraud, illegal activities, and regulatory evasion.

### 3.2 Denied Topics — Keep Agent On-Task

You define specific topics the agent must NOT discuss using natural language descriptions. Bedrock uses its own classifier to detect when conversation enters that territory.

For your system: deny personal financial advice (the agent evaluates loans, does not advise borrowers), deny off-topic conversation (poems, jokes, coding help — every off-topic call wastes money), deny lending discrimination (agent must never discuss, acknowledge, or reason about protected characteristics in lending context).

### 3.3 PII Filters — Protect Sensitive Data

Can BLOCK (reject entire request/response if PII detected) or ANONYMIZE/REDACT (replace PII with placeholder tokens).

For your system: allow PII in internal processing (agent needs SSN, income, FICO to work), redact PII in any response going to UI or logs (underwriter sees "***-**-6789" not full SSN), block credit card numbers entirely (never needed in underwriting).

PII categories Bedrock detects: SSN, credit/debit card numbers, phone numbers, email addresses, names, addresses, dates of birth, driver's license numbers, passport numbers, bank account numbers, and more.

### 3.4 Word Filters — Block Specific Terms

Simple word-level blocking (exact match, not semantic). Provide a list of words or phrases that must never appear. Useful for blocking phrases that sound like legal commitments ("we guarantee approval," "you are entitled to"), internal system names you do not want revealed, competitor names, and profanity (AWS provides a managed profanity list).

### 3.5 Contextual Grounding Check — Reduce Hallucination

Checks whether the model's response is grounded in provided context (RAG documents, tool results) or hallucinated. You provide a grounding source and a threshold. If claims in the response are not supported by the grounding source beyond the threshold, the guardrail flags or blocks the response.

For your Compliance agent this is critical — it should ONLY make regulatory claims based on retrieved policy documents. If it generates a compliance statement not found in any retrieved document, the grounding check catches it.

---

## 4. Guardrails vs System Prompt Constraints

### 4.1 Defense in Depth

You already have constraints in system prompts — "NEVER approve if FICO < 680," "NEVER discuss protected characteristics." System prompt constraints are instructions the LLM SHOULD follow. But LLMs can and do ignore instructions, especially under adversarial input or edge cases. The LLM might follow your instruction 99% of the time and fail 1%.

Guardrails are ENFORCEMENT the LLM cannot bypass. They operate at the API level, outside the LLM's control. Even if the LLM generates discriminatory content despite prompt instructions, the guardrail catches and blocks it.

System prompt equals rules posted on the wall. Guardrails equal the security guard who physically prevents violations. You want both. Rules handle 99%. The guard catches the 1%.

Java analogy: system prompt constraints are input validation in your service code. Guardrails are WAF (Web Application Firewall) rules at the infrastructure level. You validate in code AND at the firewall.

---

## 5. Per-Agent Guardrail Configuration

### 5.1 Different Agents, Different Risk Profiles

Each agent processes different types of content and has different risk profiles. Guardrails should be configured per agent role.

**FetchData agent:** Processes PII heavily (SSN, income). PII filter set to allow in processing but redact in logs. Content filter HIGH on all categories. Denied topics: everything non-data-fetching. Grounding check not applicable since no generative content.

**Document Review agent:** Processes document images containing PII. PII filter allows in processing (needs to read documents). Content filter HIGH. Denied topics: everything non-document-review. Grounding check at medium threshold since extraction should match document content.

**Risk Scoring agent:** Generates risk assessments with reasoning. PII filter redacts in output (risk report should not contain raw SSN). Content filter HIGH with special attention to discrimination and bias. Denied topics: personal advice, competitor comparison. Grounding check HIGH since risk claims must be grounded in data and policies.

**Compliance agent:** Generates regulatory statements. PII filter redacts in output. Content filter HIGH. Denied topics: personal advice, legal guarantees. Grounding check VERY HIGH since regulatory claims MUST be grounded in retrieved regulation text — hallucination here is most dangerous.

### 5.2 Implementation Pattern

The create_llm() factory function accepts a task parameter that determines both the model AND the guardrail configuration. A TASK_GUARDRAIL_MAP controls which agents use guardrails. Internal-only tasks like retrieval grading may skip guardrails to save latency and cost.

---

## 6. Handling Guardrail Interventions

### 6.1 What Happens When a Guardrail Triggers

If INPUT is blocked: Bedrock returns an error with a guardrail intervention code. Your agent receives this instead of an LLM response. Handle gracefully — log the intervention, flag for review, do not crash.

If OUTPUT is blocked: Bedrock returns a canned safe response instead of the LLM's actual response. Your code should detect this by checking for guardrail intervention markers in response metadata and handle appropriately.

If PII is REDACTED: Response content has PII replaced with tokens. Your code receives the redacted version. Original PII never leaves Bedrock's service boundary.

### 6.2 Production Error Handling

In your LangGraph nodes, wrap agent calls with guardrail-aware error handling. If a ClientError with AccessDeniedException occurs, the guardrail blocked the INPUT. If response metadata shows guardrailAction as INTERVENED, the guardrail modified or blocked the OUTPUT. In both cases, set the node output to None, log the intervention, and escalate to manual review.

The safe default: if a guardrail triggers on risk scoring or compliance output, set needs_manual_review to True. If the automated system cannot produce a safe response, a human must review.

---

## 7. What Guardrails Cannot Do

### 7.1 Limitations

Cannot catch subtle bias. Detects explicit discrimination ("deny because of race") but not proxy discrimination ("deny because of neighborhood" where neighborhood correlates with race). Detecting proxy discrimination requires fairness testing at the evaluation level in Week 6.

Cannot verify business logic correctness. Does not know whether DTI 40% should be approved or denied. Catches harmful content, PII leaks, and off-topic responses — not business logic errors.

Cannot prevent all prompt injection. Sophisticated adversarial inputs might bypass guardrails. Defense in depth (guardrails plus prompt constraints plus input validation) is the production approach.

Cannot replace human oversight. Guardrails reduce risk but do not eliminate it. Human review via MANUAL_REVIEW remains essential.

---

## 8. Cost and Performance

### 8.1 Latency

Approximately 100-300ms per guardrail evaluation (input check plus output check). For your pipeline with 15-20 LLM calls, adds 1.5-6 seconds total. Noticeable but acceptable within 15-second target.

### 8.2 Cost

Approximately $0.75 per 1,000 text units evaluated. For your pipeline at approximately 5,000 tokens per evaluation: approximately $0.004 per evaluation. At 1,000 evaluations per day: $4/day. Negligible compared to LLM costs ($25-35/day).

The cost of NOT having guardrails — regulatory fine, data breach, discrimination lawsuit — makes $4/day trivial.

---

## 9. Implementation Details

### 9.1 Creating the Guardrail

Use boto3 to create the guardrail with create_guardrail(). Configure all five protection types: content filters (all HIGH), denied topics (personal advice, off-topic, discrimination), PII entities (SSN anonymize, credit card block), word filters (legal commitment phrases plus managed profanity list), and blocked messaging for input and output interventions.

Save the returned guardrailId and version to your .env file.

### 9.2 Integrating with ChatBedrock

Pass guardrails configuration (identifier and version) when creating ChatBedrock. Every invoke() call on that client is automatically filtered. No changes to agent code, prompts, or tools.

### 9.3 Per-Agent Configuration

The create_llm(task=) factory uses a TASK_GUARDRAIL_MAP to determine which agents use guardrails. Internal tasks (retrieval grading) can skip guardrails. User-facing tasks (risk scoring, compliance) always use them.

### 9.4 Testing

Test each guardrail type independently. Content filter: send harmful request, verify blocked. Denied topic: ask for personal advice, verify blocked. PII redaction: include SSN in prompt, verify redacted in response. Word filter: prompt with blocked phrase, verify caught. Normal operation: send legitimate underwriting prompt, verify NOT blocked. Discrimination: send neighborhood-based risk question, verify caught.

The most important test is the last one — verify guardrails do NOT block legitimate underwriting work. An overly strict guardrail that blocks real evaluations is worse than no guardrail.

---

## 10. Q&A

### Q: Can guardrails completely prevent the agent from making biased decisions?

No. Guardrails catch explicit discriminatory CONTENT — statements about protected characteristics in lending context. They cannot catch proxy discrimination (using neighborhood as a proxy for race) or structural bias in the training data. Preventing bias requires fairness testing (Week 6), careful feature selection (never use protected attributes), and ongoing monitoring of decision patterns across demographics.

### Q: If guardrails add 100-300ms per call and I have 15 calls, that is 1.5-4.5 seconds. Can I skip guardrails for internal calls?

Yes, and you should for purely internal processing. Retrieval grading (is this document relevant?) does not need guardrails — no user-facing output, no PII risk. Your TASK_GUARDRAIL_MAP controls this. Apply guardrails to user-facing and decision-generating calls. Skip for internal classification and routing calls.

### Q: What if the guardrail blocks a legitimate underwriting evaluation?

This is the false positive problem. If content filters are too aggressive, they might block risk assessments that discuss financial distress, debt problems, or credit issues — which are core to underwriting. Test thoroughly with real underwriting scenarios. If false positives occur, adjust filter thresholds from HIGH to MEDIUM for specific categories while keeping HIGH for categories irrelevant to underwriting (sexual, violence).

### Q: Should I use the same guardrail for all agents or create separate ones?

You can use one guardrail with the configuration broad enough for all agents. Or create separate guardrails per agent role for tighter control. The tradeoff: one guardrail is simpler to manage but cannot be customized per agent. Multiple guardrails allow different PII policies, different grounding thresholds, and different denied topics per agent but require more management.

For your system, start with one guardrail. If you find that one agent needs different settings (Compliance needs stricter grounding than FetchData), create a second guardrail for that agent.

### Q: How do guardrails interact with the grounding check in my Agentic RAG from Week 3?

They complement each other. Your SmartRAG ComplianceAnswer model has a self-check field (all_claims_supported). That is application-level grounding. Bedrock's contextual grounding check is infrastructure-level grounding. Both can catch hallucination. The SmartRAG check is more nuanced (your custom logic). The Bedrock check is more reliable (cannot be bypassed by prompt manipulation). Use both — defense in depth.

---

## 11. Summary

| Concept | What It Does | Java / AWS Equivalent |
|---------|-------------|----------------------|
| Bedrock Guardrails | Managed content safety between app and LLM | WAF / Kong API Gateway |
| Content filters | Block hate, violence, sexual, misconduct | Content security policy |
| Denied topics | Keep agent on-task, block off-topic | URL path restrictions |
| PII filters (ANONYMIZE) | Redact SSN, phone, email in output | Data masking |
| PII filters (BLOCK) | Reject if PII detected | DLP (Data Loss Prevention) |
| Word filters | Block specific phrases | WAF keyword rules |
| Contextual grounding | Check response matches source context | Output validation |
| Guardrail ID + version | Reference in ChatBedrock config | WAF rule group ARN |
| Per-agent config | Different guardrails per agent role | Per-service security policy |
| Input intervention | Block before LLM sees it | Request filtering |
| Output intervention | Block before code receives it | Response filtering |
| False positives | Guardrail blocks legitimate work | WAF false positive tuning |
| Defense in depth | Guardrails + prompts + code validation | WAF + app validation + DB constraints |
| Cost | ~$0.004/evaluation, ~$4/day at 1K evals | Security infrastructure cost |
"""

with open("week5_day3.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")