# Week 6, Day 2: Ragas — Automated RAG Evaluation, Testing & AWS Bedrock Evaluation

**Date:** April 5, 2026  
**Module:** Evaluation & Testing  
**Platform:** Kuber Loan Origination System  

---

## 1. Session Overview

**Topic:** Ragas framework deep dive — the four core RAG evaluation metrics, synthetic test data generation, integration with LangSmith/Langfuse, comparison with DeepEval and AWS Bedrock's native evaluation capabilities.

**Prerequisites:** Week 6 Day 1 complete (LangSmith tracing, Anthropic SDK vs LangChain comparison). Smart RAG (Strategy 5) and Agentic RAG (Strategy 6) architectures from Week 5.

**Key Deliverable:** A production evaluation strategy for Kuber's four-agent underwriting pipeline using the right combination of Ragas, Bedrock Evaluation, and DeepEval.

---

## 2. Why RAG Evaluation Is Harder Than Standard LLM Evaluation

Standard LLM evaluation asks one question: is the output good? RAG evaluation is harder because **two components can fail independently**:

- The **retriever** might pull wrong documents (OpenSearch returns California policies for a Texas query)
- The **generator** might hallucinate despite correct context (Claude has the right DTI regulation but outputs the wrong number)
- Both can fail in ways that **cancel each other out** — producing a plausible answer that is completely wrong

Traditional metrics like BLEU and ROUGE were designed for translation and summarization. They measure text similarity but cannot assess whether a response is grounded in retrieved context, whether all relevant information was retrieved, or whether the agent called the correct tools. Ragas was specifically designed to fill this gap.

---

## 3. What Ragas Is

Ragas (Retrieval Augmented Generation Assessment) is an open-source evaluation framework specifically designed for RAG pipelines. Introduced by Shahul Es et al. in 2023, it pioneered **reference-free evaluation** — meaning you don't need human-written ground truth for every test case.

- Open source, MIT license, free
- Uses **LLM-as-judge** to evaluate outputs (uses a separate LLM to score your pipeline's outputs)
- Integrates with LangChain, LlamaIndex, LangSmith, and Langfuse
- Provides both individual metrics and a composite RAGAS score
- Can generate synthetic test datasets from your documents
- The latest version supports 25+ metrics including agent-specific metrics (Tool Call Accuracy, Agent Goal Accuracy)

---

## 4. The Four Core Ragas Metrics

These metrics evaluate two sides of the pipeline: **retrieval quality** (did we find the right documents?) and **generation quality** (did we produce the right answer?).

### 4.1 Faithfulness (Generation Quality)

**Question it answers:** "Is the generated answer factually consistent with the retrieved context?"

**How it works:**
1. Break the generated answer into individual claims/statements
2. For each claim, verify if it can be inferred from the retrieved context
3. Faithfulness = (claims supported by context) / (total claims)

**Kuber example:**

```
Question: "What is the maximum DTI for a Texas conventional QM?"
Retrieved Context: "For Texas conventional qualified mortgages, the maximum 
  DTI ratio is 43%. Compensating factors may be considered for DTIs between 
  38% and 43%."
Generated Answer: "The maximum DTI for a Texas conventional QM is 43%, with 
  compensating factors considered above 38%. The borrower must also have a 
  minimum FICO of 680."

Claims:
1. "Maximum DTI is 43%" → Supported by context ✓
2. "Compensating factors above 38%" → Supported by context ✓  
3. "Minimum FICO of 680" → NOT in context ✗ (hallucination!)

Faithfulness = 2/3 = 0.67
```

A score of 0.67 means the agent is hallucinating. The FICO requirement was fabricated. For compliance, this is unacceptable — you need faithfulness above 0.95.

**What low faithfulness diagnoses:** Hallucination. The model is adding unsupported facts. Fix by tightening the system prompt ("only state facts found in the provided context") or switching to the Agentic RAG strategy with a separate hallucination-checking step.

### 4.2 Answer Relevancy (Generation Quality)

**Question it answers:** "Is the generated answer actually relevant to the question asked?"

**How it works:** Ragas generates multiple hypothetical questions from the answer, then measures semantic similarity between these generated questions and the original question. If the answer is relevant, the generated questions should be similar to the original.

**Kuber example:**

```
Question: "What is the maximum DTI for a Texas conventional QM?"
Answer: "The Texas housing market has seen significant growth in recent 
  years, with property values increasing by 15% since 2023."

Generated questions from answer:
- "How has the Texas housing market performed recently?"
- "What is the property value trend in Texas?"

Similarity to original question: LOW
Answer Relevancy: 0.15
```

The answer is factually correct (maybe) but completely irrelevant to what was asked. The agent went off-topic.

**What low relevancy diagnoses:** Agent went off-topic, called the wrong tool, or retrieved context about an unrelated subject.

### 4.3 Context Precision (Retrieval Quality)

**Question it answers:** "Of the documents retrieved, how many were actually relevant? Were relevant ones ranked higher?"

**How it works:** For each retrieved document, an LLM judges whether it's relevant to the question. The metric rewards systems that rank relevant documents higher. Scores range 0 to 1, with 1 meaning all retrieved documents were relevant and well-ranked.

**Kuber example:**

```
Question: "What are the LTV limits for Texas home equity loans?"

Retrieved documents (top-3):
1. "Texas Section 50(a)(6) limits LTV to 80%..." → RELEVANT ✓
2. "California AB-2024 modifies LTV requirements..." → IRRELEVANT ✗
3. "Texas home equity lending requires disclosures..." → RELEVANT ✓

Context Precision ≈ 0.67
```

**What low precision diagnoses:** Bad metadata filtering, embedding drift, or search returning noise. Your retriever is pulling irrelevant documents.

### 4.4 Context Recall (Retrieval Quality)

**Question it answers:** "Did the retrieved documents contain ALL the information needed to answer correctly?"

**How it works:** Compares the ground truth answer against the retrieved contexts. For each claim in the ground truth, checks if it can be attributed to the retrieved context. This is the only core metric that requires ground truth answers.

**Kuber example:**

```
Question: "What are the requirements for Texas Section 50(a)(6)?"
Ground Truth: "Texas 50(a)(6) requires: LTV max 80%, 12-day cooling period, 
  borrower receives copy 1 day before closing, fees limited to 3%."

Retrieved Context: "Section 50(a)(6) limits LTV to 80% and imposes a 12-day 
  waiting period between application and closing."

Ground truth claims:
1. "LTV max 80%" → Found in context ✓
2. "12-day cooling period" → Found in context ✓
3. "Copy 1 day before closing" → NOT in context ✗
4. "Fees limited to 3%" → NOT in context ✗

Context Recall = 2/4 = 0.50
```

**What low recall diagnoses:** Top-k too low, chunking splits related content across chunks, missing synonym expansion, or incomplete document corpus.

### 4.5 The Evaluation Matrix

| Metric | Evaluates | Needs Ground Truth? | Diagnoses |
|--------|-----------|-------------------|-----------|
| **Faithfulness** | Generation | No | Hallucination, fabricated facts |
| **Answer Relevancy** | Generation | No | Off-topic responses, wrong tool |
| **Context Precision** | Retrieval | No (or optional reference) | Irrelevant docs, bad filtering |
| **Context Recall** | Retrieval | Yes | Missing info, low top-k, bad chunking |

---

## 5. Implementing Ragas for Kuber

### 5.1 Core Evaluation Code

Using the current Ragas collections-based API pattern (the legacy `evaluate()` API is being deprecated in v0.4):

```python
from ragas import SingleTurnSample
from ragas.metrics import (
    Faithfulness, ResponseRelevancy,
    LLMContextPrecisionWithoutReference,
    LLMContextRecallWithReference,
)
from ragas.llms import llm_factory
from openai import AsyncOpenAI

# Use a DIFFERENT model than your pipeline to avoid bias
client = AsyncOpenAI()
evaluator_llm = llm_factory("gpt-4o-mini", client=client)

# Create scorers
faithfulness = Faithfulness(llm=evaluator_llm)
relevancy = ResponseRelevancy(llm=evaluator_llm)
ctx_precision = LLMContextPrecisionWithoutReference(llm=evaluator_llm)
ctx_recall = LLMContextRecallWithReference(llm=evaluator_llm)

# Define test cases
test_cases = [
    {
        "question": "What is the maximum DTI for a Texas conventional QM?",
        "contexts": [
            "For Texas conventional QM, the maximum DTI ratio is 43%.",
            "Compensating factors may be considered for DTI between 38% and 43%."
        ],
        "answer": "The maximum DTI for a Texas conventional QM is 43%. Compensating factors may be considered for DTIs between 38% and 43%.",
        "ground_truth": "The maximum DTI is 43%. Compensating factors like cash reserves above 6 months can be considered for DTIs between 38% and 43%."
    },
    # ... more test cases
]

# Evaluate
async def evaluate_pipeline():
    for tc in test_cases:
        sample = SingleTurnSample(
            user_input=tc["question"],
            response=tc["answer"],
            retrieved_contexts=tc["contexts"],
            reference=tc["ground_truth"]
        )
        
        f_score = await faithfulness.single_turn_ascore(sample)
        r_score = await relevancy.single_turn_ascore(sample)
        cp_score = await ctx_precision.single_turn_ascore(sample)
        cr_score = await ctx_recall.single_turn_ascore(sample)
        
        print(f"Faithfulness: {f_score:.3f}")
        print(f"Answer Relevancy: {r_score:.3f}")
        print(f"Context Precision: {cp_score:.3f}")
        print(f"Context Recall: {cr_score:.3f}")
```

### 5.2 Synthetic Test Data Generation

Instead of manually writing 500 test cases, Ragas generates diverse test questions from your actual documents:

```python
from ragas.testset import TestsetGenerator
from langchain_community.document_loaders import DirectoryLoader

loader = DirectoryLoader("./lending_policies/", glob="**/*.pdf")
documents = loader.load()

generator = TestsetGenerator(llm=llm_factory("gpt-4o-mini"))
testset = generator.generate_with_langchain_docs(
    documents=documents,
    testset_size=50,
)

# Generates: simple factual, reasoning, and multi-hop questions
df = testset.to_pandas()
```

### 5.3 Integration with Langfuse

```python
from langfuse import get_client
langfuse = get_client()

# Push Ragas scores back into Langfuse traces
for result in results:
    langfuse.create_score(
        name="faithfulness",
        value=result["faithfulness"],
        trace_id=result["trace_id"]  # from your pipeline trace
    )
```

Now in Langfuse, you can see each production trace alongside its quality scores. Filter traces where faithfulness drops below 0.9. Build dashboards showing quality trends over time.

---

## 6. Beyond the Four Core Metrics

Ragas has grown to 25+ metrics. The additional metrics most relevant to Kuber:

- **Context Entity Recall:** Checks if specific entities (company names, regulation numbers, dollar amounts) from the ground truth appear in retrieved context. Critical for compliance where exact regulatory references matter.
- **Noise Sensitivity:** Measures how much the answer changes when irrelevant context is injected. A robust pipeline should ignore noise.
- **Factual Correctness:** Goes beyond faithfulness to check if the answer is factually correct against ground truth.
- **Tool Call Accuracy:** Did the agent call the right tools? Directly evaluates your four agents' tool selection.
- **Agent Goal Accuracy:** Did the agent achieve its intended goal? Evaluates end-to-end outcomes.
- **Rubrics-based Scoring:** Define custom rubrics for domain-specific evaluation (e.g., 1–5 scale for "Regulatory compliance completeness").

---

## 7. AWS Bedrock's Native Evaluation Capabilities

Since Kuber runs on Bedrock, AWS provides three levels of evaluation that can reduce or replace dependency on external tools like Ragas.

### 7.1 Level 1: Bedrock Model Evaluation (GA April 2024)

**Purpose:** Choosing which model to use — comparing Claude vs Llama vs Mistral for your specific use case.

- **Automatic (Programmatic):** Provide a dataset, Bedrock scores using built-in metrics (BERT Score, F1, exact match). No LLM-as-judge needed.
- **Human Evaluation:** Human reviewers compare model outputs. Use the company employees or AWS-managed team. Cost: $0.21 per task.
- **LLM-as-Judge:** Pick an evaluator model that scores outputs against correctness, completeness, faithfulness, and harmfulness.

### 7.2 Level 2: Knowledge Base Evaluation (RAG Evaluation)

**Purpose:** Evaluating your RAG pipeline — directly competes with Ragas.

- **Retrieval Evaluation:** Tests document retrieval quality. Metrics: context relevance and context coverage. Maps to Ragas's Context Precision and Context Recall.
- **Retrieve-and-Generate Evaluation:** Tests end-to-end RAG. Metrics: faithfulness, correctness, completeness. Maps to Ragas's Faithfulness and Answer Relevancy.

**Key advantage over Ragas:** Fully managed inside AWS. No pip installs, no separate accounts, no data leaving your VPC. Evaluation data containing loan application details stays within Bedrock's trust boundary.

### 7.3 Level 3: AgentCore Evaluations (GA March 2026)

**Purpose:** Evaluating AI agents — the newest and most relevant for your four-agent pipeline. 13 built-in evaluators.

- **Built-in evaluators:** Pre-configured with prompt templates, evaluator models, and scoring criteria. Managed infrastructure — you don't consume your own model quotas.
- **Custom evaluators:** Define your own evaluation instructions, criteria, and scoring schema. Build the company-specific compliance checks.
- **Code-based evaluators (Lambda):** Run custom evaluation code in AWS Lambda. Critical for deterministic checks: "Did the response include the exact DTI value of 40.4%?" "Does the risk score follow the format 0–100?" A Lambda function checks with certainty where an LLM might hallucinate.

AgentCore Evaluations uses **OpenTelemetry traces** with generative AI semantic conventions. It reads the OTel trace of your agent execution (which LangGraph can export) and evaluates the full trajectory.

### 7.4 Bedrock vs Ragas vs LangSmith vs DeepEval

| Capability | Bedrock Eval | Ragas | LangSmith | DeepEval |
|-----------|-------------|-------|-----------|----------|
| **RAG retrieval metrics** | Context relevance, coverage | Context precision, recall, entity recall | Custom evaluators | Contextual precision, recall, relevancy |
| **RAG generation metrics** | Faithfulness, correctness, completeness | Faithfulness, answer relevancy | Custom + Open Evals | Faithfulness, answer relevancy, G-Eval |
| **Agent evaluation** | 13 built-in + custom + Lambda | Tool call accuracy, agent goal | Trajectory evaluators | Task completion |
| **Data residency** | Stays in AWS VPC | Depends on evaluator LLM | Cloud or self-hosted | Depends on evaluator LLM |
| **CI/CD integration** | API-based, manual | Script-based | API-based | Native pytest |
| **Synthetic test gen** | Not built-in | Yes (knowledge graph) | Not built-in | Yes (goldens) |
| **Infrastructure** | Fully managed | pip install, self-manage | SaaS or self-hosted | pip install, self-manage |

---

## 8. DeepEval: pytest-Style LLM Testing

DeepEval is an LLM evaluation framework built for developers who think in pytest. If Ragas is a "metrics library" you call from a script, DeepEval is a "testing framework" you integrate into CI/CD.

**Java analogy:** Ragas is like writing metric calculations in a Jupyter notebook. DeepEval is like writing JUnit tests for your AI — you run `pytest` and it tells you pass/fail.

### 8.1 How DeepEval Works

```python
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric

def test_compliance_check():
    test_case = LLMTestCase(
        input="What is the max DTI for Texas conventional QM?",
        actual_output="The maximum DTI is 43%.",
        retrieval_context=[
            "Texas conventional QM max DTI is 43% with compensating factors above 38%."
        ],
        expected_output="Maximum DTI is 43%."
    )
    
    faithfulness = FaithfulnessMetric(threshold=0.95)
    relevancy = AnswerRelevancyMetric(threshold=0.90)
    assert_test(test_case, [faithfulness, relevancy])

# Run with: deepeval test run test_compliance.py
```

### 8.2 When to Use Ragas vs DeepEval

| Aspect | Ragas | DeepEval |
|--------|-------|----------|
| **Philosophy** | Metrics library for analysis | Testing framework for CI/CD |
| **Interface** | Python scripts, Jupyter notebooks | pytest integration, CLI |
| **CI/CD** | You build the integration | Native (`deepeval test run`) |
| **Metrics** | 25+ (RAG-focused) | 14+ (broader: toxicity, bias, G-Eval) |
| **Best for** | Exploratory evaluation, development | Automated quality gates, CI/CD pipelines |

---

## 9. Key Tool Clarifications

### 9.1 What Is Langfuse?

Langfuse is the open-source alternative to LangSmith. It does the same job — tracing, monitoring, and evaluating LLM applications — but you can self-host it in your own infrastructure.

**Java analogy:** LangSmith is like Datadog (great SaaS, data goes to their servers). Langfuse is like a self-hosted Grafana + Prometheus stack (you own everything, runs in your VPC).

- Open source, self-hostable, free
- Acquired by ClickHouse in January 2026 ($400M Series D) — long-term stability signal
- Works with LangChain, LlamaIndex, Anthropic SDK, OpenAI SDK, and any custom stack via OpenTelemetry
- Less polished UI than LangSmith, fewer built-in features, but covers core observability needs

**Why it matters for the company:** LangSmith Cloud sends prompts and loan data to LangChain's servers. Langfuse runs inside the company's AWS VPC — nothing leaves your network.

### 9.2 What Is LlamaIndex?

LlamaIndex is LangChain's main competitor — another Python framework for building LLM applications. But where LangChain is a general-purpose framework (agents, chains, memory, tools), LlamaIndex focuses specifically on **data ingestion and retrieval** — a RAG-first framework.

**Java analogy:** LangChain is like Spring Boot (does everything). LlamaIndex is like Hibernate (focused on data access and querying).

- Document loaders for 100+ formats (PDF, Word, Slack, Notion, databases, APIs)
- Advanced indexing strategies (tree index, keyword table, vector store, knowledge graph index)
- Query engines that combine multiple retrieval strategies

**Why you chose LangChain/LangGraph instead:** Your system is agent-heavy, not retrieval-heavy. LangGraph's state machine orchestration is more important for a four-agent pipeline than LlamaIndex's advanced retrieval features.

---

## 10. Recommended Production Evaluation Pipeline for Kuber

### Development Phase

- LangSmith Cloud (tracing + built-in evaluation with datasets and trajectory checks)
- Ragas (RAG-specific metrics for compliance and risk scoring agents)
- Bedrock Model Evaluation (validate model selection for each agent role)

### CI/CD Phase

- DeepEval (pytest-style quality gates in GitLab pipeline)
- Every PR that touches a prompt must pass the evaluation suite before merge
- Bedrock AgentCore Evaluations via API to validate agent behavior

### Production Phase

- Langfuse self-hosted (tracing + monitoring in the company's VPC)
- Bedrock Knowledge Base Evaluation (RAG quality scoring — stays in AWS)
- Bedrock AgentCore Evaluations with code-based (Lambda) evaluators for deterministic compliance checks
- Custom dashboards combining trace data, evaluation scores, and infrastructure metrics

### Offline Regression (Weekly)

- Run Ragas against full 500+ case test dataset
- Compare to baseline — flag any metric dropping more than 2%
- Use LangSmith's pairwise annotation queues for A/B testing prompt changes

---

## 11. Questions & Answers

### Q: What is Langfuse?

Langfuse is the open-source alternative to LangSmith for LLM observability. It provides tracing, monitoring, and evaluation capabilities that you can self-host in your own VPC. It was acquired by ClickHouse in January 2026. The key advantage for the company is data residency — your prompts, loan data, and evaluation results never leave your AWS infrastructure. Langfuse works with LangChain, LlamaIndex, Anthropic SDK, and any custom framework via OpenTelemetry. It has a less polished UI than LangSmith but covers the core needs: trace visualization, score tracking, dataset management, and integration with evaluation frameworks like Ragas.

### Q: What is LlamaIndex?

LlamaIndex is a Python framework that competes with LangChain, but with a RAG-first focus. Where LangChain is a general-purpose LLM framework (agents, chains, memory, tools), LlamaIndex specializes in data ingestion, indexing, and retrieval. It supports 100+ document loaders, advanced indexing strategies (tree, keyword table, vector store, knowledge graph), and sophisticated query engines. You chose LangChain/LangGraph over LlamaIndex because your system is agent-heavy, not retrieval-heavy — LangGraph's state machine orchestration (typed state, parallel execution, checkpointing, human-in-the-loop) is more important for a four-agent underwriting pipeline than LlamaIndex's advanced retrieval features.

### Q: For LangSmith, can I define expected outputs and compare them with agent results?

Yes, exactly. LangSmith's evaluation datasets feature lets you create test cases with inputs and human-verified expected outputs. You run your pipeline against the dataset and LangSmith compares actual vs expected. You can also define trajectory evaluators that check whether the agent called the right tools in the right order — for example, "Risk Scoring agent MUST call pull_borrower_data, calculate_dti, and search_lending_policies." LangSmith tracks which test cases passed, which failed, scores over time, and whether metrics improve or degrade after prompt changes. This is the core of regression testing for AI.

### Q: What are the alternatives to Ragas?

Five main alternatives: (1) **DeepEval** — pytest-style LLM testing with 14+ metrics, native CI/CD integration. (2) **LangSmith's built-in evaluators** — custom evaluators and the Open Evals library for hallucination, relevance, correctness, and agent trajectory. (3) **AWS Bedrock Evaluation** — three levels: Model Evaluation, Knowledge Base Evaluation (RAG), and AgentCore Evaluations (agents). Fully managed, stays in AWS VPC. (4) **Arize Phoenix** — open source, local-first, strong embedding visualization for debugging RAG retrieval. (5) **Manual/custom evaluation** — write your own evaluation logic in Python for the company-specific compliance metrics.

### Q: Does Anthropic provide evaluation tools?

Not as a standalone product. Anthropic's philosophy is to build the best model and let the ecosystem build tooling around it. However: Claude itself can serve as an LLM-as-judge (use Claude to evaluate Claude's outputs with a different model variant). The Anthropic SDK supports structured output (JSON mode) which makes building custom evaluators easy. Anthropic's Bedrock integration works with AWS's evaluation tools. Unlike LangChain (which builds the framework AND the evaluation platform), Anthropic stays focused on the model layer.

### Q: What is DeepEval?

DeepEval is an LLM evaluation framework built for developers who think in pytest. You write test cases as Python functions, define metrics with pass/fail thresholds (e.g., faithfulness > 0.95), and run them with `deepeval test run`. It provides 14+ metrics including answer relevancy, faithfulness, contextual precision/recall, toxicity, and bias. Its key differentiator from Ragas is native CI/CD integration — designed as a quality gate in your GitLab pipeline. For Kuber: use DeepEval so every PR that touches a prompt must pass evaluation before merge.

### Q: What evaluation does AWS Bedrock provide?

Three levels. **Level 1 (Model Evaluation, GA April 2024):** Compare models using automatic metrics, human evaluation, or LLM-as-judge. **Level 2 (Knowledge Base Evaluation):** Evaluate RAG retrieval (context relevance, coverage) and end-to-end RAG (faithfulness, correctness, completeness). Directly competes with Ragas but fully managed and stays in VPC. **Level 3 (AgentCore Evaluations, GA March 2026):** 13 built-in evaluators for agents covering correctness, safety, tool selection accuracy, completeness, and faithfulness. Supports custom evaluators and code-based Lambda evaluators for deterministic checks. Uses OpenTelemetry traces to evaluate full agent trajectories. For Kuber, AgentCore Evaluations with Lambda evaluators is the most relevant.

### Q: Should we use Bedrock Evaluation instead of Ragas?

For production, yes — Bedrock Evaluation should be the primary evaluation tool because it's fully managed and keeps data in your VPC. Ragas becomes a development-phase tool for deeper analysis and synthetic test data generation (which Bedrock doesn't provide). Recommended split: Bedrock for production evaluation and compliance-critical checks, Ragas for development exploration and test dataset generation, DeepEval for CI/CD quality gates.

### Q: For compliance evaluation, should faithfulness threshold be higher than 0.95?

Yes. For compliance-critical agents (your Compliance agent checking Texas 50(a)(6) requirements), faithfulness should be 0.98+. A single hallucinated compliance claim could expose the company to regulatory risk. For non-compliance agents (FetchData, general risk commentary), 0.90–0.95 is acceptable. Threshold should be calibrated per agent based on consequences of errors.

---

## 12. Key Takeaways

1. **RAG evaluation requires measuring BOTH retrieval quality and generation quality** — Context Precision/Recall for retrieval, Faithfulness/Answer Relevancy for generation.

2. **Ragas is the standard open-source RAG evaluation framework**, but AWS Bedrock's native evaluation (especially AgentCore Evaluations with Lambda-based deterministic checks) is better suited for the company's production requirements.

3. **DeepEval fills the CI/CD gap** — pytest-style quality gates that no other tool provides natively.

4. **The production evaluation stack:** Bedrock Evaluations (primary) + Langfuse (tracing) + DeepEval (CI/CD) + Ragas (development analysis and synthetic test generation).

5. **Faithfulness thresholds should be calibrated per agent:** 0.98+ for compliance, 0.90+ for general risk assessment.

6. **Langfuse** is your open-source LangSmith alternative for production (data stays in VPC). **LlamaIndex** is a RAG-focused alternative to LangChain (you chose LangChain for its agent orchestration strengths).

---

## 13. Next Session Preview

**Week 6, Day 3: Fine-tuning on Bedrock**

Topics: Custom model training on your underwriting data, when fine-tuning beats prompt engineering, Bedrock's fine-tuning workflow (dataset preparation, training job configuration, evaluation), cost analysis, and the practical decision of whether Kuber's agents need fine-tuned models or if prompt engineering with RAG is sufficient.

Connection: Today we built the evaluation framework. Tomorrow we explore whether fine-tuning can improve the scores that evaluation revealed as weak — particularly for domain-specific underwriting terminology and regulatory interpretation.

---

## 14. Week 6 Day 3 Prep: Fine-Tuning, Distillation, and Cost Model

This section answers your three-part decision exercise using the latest measured agent-level scores from `src/exercises/week6_day2_ragas_eval.py`.

### Part A: Fine-Tuning Decision Analysis

#### A1) FetchData Agent

- Quality gap (from current evaluation):
    - Faithfulness: `0.2897`
    - Answer relevancy: `0.1504`
    - Context precision: `0.7145`
    - Context recall: `1.0000`
- Interpretation:
    - Retrieval coverage is strong (recall is perfect in this synthetic set), but answer quality is weak and drifts off strict extraction behavior.
    - This looks like an output-format and grounding problem more than a missing-data problem.
- Can it be fixed without fine-tuning?
    - Yes, likely mostly fixable with:
        - tighter extraction prompt contracts,
        - strict JSON schema + validator/retry,
        - more in-context examples for edge fields (`employment_type`, `years_at_current`, missing/null fields),
        - deterministic post-processing for known field names.
- If fine-tuning is needed:
    - Base model: `Amazon Nova Micro` (or equivalent small instruction model available for customization).
    - Why: FetchData is structured extraction/transformation; latency and cost matter more than deep reasoning.
- Training data needed + the company availability:
    - Needed: input record blobs + expected canonical JSON output, including hard negatives (missing fields, conflicting upstream values, malformed IDs).
    - the company likely has most of this in LOS payloads, API logs, and downstream normalized borrower records.
    - Data gap: curated "gold" outputs for ambiguous cases; needs annotation pass.

#### A2) DocReview Agent

- Quality gap:
    - Faithfulness: `0.4734`
    - Answer relevancy: `0.1348`
    - Context precision: `0.2971`
    - Context recall: `0.5585`
- Interpretation:
    - Both retrieval and generation are weak, especially precision/recall from OCR context.
    - Biggest risk is noisy OCR chunks and incomplete document grounding.
- Can it be fixed without fine-tuning?
    - Significant gains should come first from better RAG/OCR pipeline:
        - improved document chunking by section/layout,
        - OCR confidence filtering,
        - metadata filters (`doc_type`, `tax_year`, `borrower_id`),
        - citation-required answer template.
    - Prompt/examples help, but RAG quality is the dominant lever here.
- If fine-tuning is needed:
    - Base model: `Nova Lite` (or another mid-size model with stronger extraction reasoning).
    - Why: Doc review needs more robust span extraction and table-like normalization than Nova Micro.
- Training data needed + the company availability:
    - Needed: document text/OCR + expected extracted fields + span/citation references.
    - the company has source documents and outcomes; may not yet have span-level labels at scale.
    - Data gap: high-quality annotation set for W-2, paystub, 1040 variants.

#### A3) RiskScoring Agent

- Quality gap:
    - Faithfulness: `0.0636`
    - Answer relevancy: `0.0185`
    - Context precision: `0.0000`
    - Context recall: `0.0000`
- Interpretation:
    - Current evaluation indicates severe mismatch between retrieved context and generated scoring narrative.
    - This should be treated as architecture-first, not model-first.
- Can it be fixed without fine-tuning?
    - Yes, and this should be the first path:
        - move DTI/LTV/FICO logic to deterministic code,
        - keep model only for explanation text,
        - enforce policy retrieval by jurisdiction + loan product,
        - add rule-engine outputs directly into prompt context.
- If fine-tuning is needed:
    - Base model: `Nova Lite` or a small instruct model for explanation style only.
    - Do not rely on fine-tuning for numeric policy calculation correctness.
- Training data needed + the company availability:
    - Needed: input profile + rule features + final recommendation + rationale.
    - the company likely has historical decisions and feature snapshots.
    - Data gap: consistent rationale quality labels and explicit policy-citation labels.

#### A4) Compliance Agent

- Quality gap:
    - Faithfulness: `0.2293`
    - Answer relevancy: `0.1612`
    - Context precision: `0.1033`
    - Context recall: `0.3215`
- Interpretation:
    - High compliance risk: hallucination and incomplete retrieval of required disclosure rules.
    - This is safety-critical and should prioritize deterministic checks.
- Can it be fixed without fine-tuning?
    - Mostly yes via governance and retrieval hardening:
        - jurisdiction-first policy retrieval,
        - mandatory citation in output,
        - rule checklist validation (blocking violations => override),
        - deterministic Lambda evaluators in Bedrock AgentCore.
- If fine-tuning is needed:
    - Base model: `Nova Pro` or highest-quality available customizable model for legal/policy language.
    - Still pair with deterministic policy validators; fine-tuning alone is insufficient.
- Training data needed + the company availability:
    - Needed: policy text by jurisdiction/version, historical compliance reviews, exception decisions, and final disclosure outcomes.
    - the company has policy corpora and review decisions; annotation quality and recency/versioning are the main challenges.

### Part B: Distillation Design (FetchData Agent)

#### B1) Ten Teacher Prompts for Claude Sonnet

Use a strict teacher instruction prefix for all prompts:
"Extract and normalize only the requested fields. Return valid JSON matching schema. Use `null` for missing values. No extra commentary."

1. "Extract borrower profile from APP-001 payload with income, debt, loan_amount, property_state, ssn_last_four."
2. "Given mixed LOS + bureau text, return canonical credit/employment object for borrower 5678."
3. "Normalize currency-formatted values (`$120,000`) and percentage strings (`43%`) to numeric fields."
4. "Resolve conflicting debt values from two systems using source priority: LOS > Credit Bureau > Manual Note."
5. "Parse partial payload where `employment_years` is missing and emit nullable schema output."
6. "Extract all required upstream fields for risk engine from APP-002 and include `data_quality_flags`."
7. "From noisy OCR text, recover W-2 wages and employer fields; ignore unrelated footer/legal text."
8. "Map synonym keys (`fico`, `credit_score`, `bureau_score`) into unified `fico_score` field."
9. "Handle malformed SSN token (`***-**-1234`); return only last four and mark `pii_redacted=true`."
10. "Batch-parse 3 borrower snippets and return array of normalized records with deterministic key ordering."

#### B2) Expected Teacher Outputs

Output format should be stable JSON. Example shape:

```json
{
    "application_id": "APP-001",
    "borrower_id": "5678",
    "annual_income": 120000,
    "monthly_debt": 2400,
    "loan_amount": 350000,
    "property_state": "TX",
    "fico_score": 740,
    "employment": {
        "employer_name": "Acme Lending Services",
        "employment_type": "FULL_TIME",
        "years_at_current": 5.0
    },
    "ssn_last_four": "1234",
    "data_quality_flags": [],
    "source_trace": ["los_v2", "credit_bureau_v3"],
    "pii_redacted": true
}
```

Required output characteristics:

- Exact schema compliance
- Deterministic key order
- Explicit `null` for missing values
- Source trace for auditability
- No natural-language explanation

#### B3) Student Model Choice

- Student: `Nova Micro`
- Why this student is a fit:
    - FetchData is mostly transformation/extraction, not deep reasoning.
    - Lowest per-token cost among candidates in your pricing set.
    - Fast latency supports high-volume underwriting pre-check flows.

#### B4) Distillation Evaluation vs Original (Claude Haiku Baseline)

Evaluate in four gates:

1. Offline golden set (must pass before shadow):
     - 1,000+ labeled FetchData cases
     - Exact-match JSON validity, field-level F1, null-handling accuracy
2. Ragas/quality layer:
     - Faithfulness, answer relevancy (for any textual fields), plus custom extraction completeness metric
3. Online shadow mode:
     - Run both models on same traffic for 2 weeks
     - Compare discrepancy rate, downstream risk-engine correction rate, and manual override rate
4. Business KPI gate:
     - Approval latency improvement
     - Cost per 1,000 applications
     - No increase in compliance exceptions

Promotion criterion example:

- Distilled model must be within 1% absolute accuracy of baseline on critical fields and improve unit economics by >=50%.

### Part C: Cost Analysis and Break-Even

Given prices:

- Claude Haiku: `$0.001 / 1K input`, `$0.005 / 1K output`
- Nova Micro: `$0.000035 / 1K input`, `$0.00014 / 1K output`

Per-request cost formulas:

- `Cost_haiku = 0.001 * (input_tokens/1000) + 0.005 * (output_tokens/1000)`
- `Cost_nova = 0.000035 * (input_tokens/1000) + 0.00014 * (output_tokens/1000)`
- `Savings_per_request = Cost_haiku - Cost_nova`

Assumptions for break-even estimate:

- Distillation program one-time cost: `$2,000`
    - teacher labeling + data curation + training/eval pipeline runs
- Amortization window: `180 days`
    - daily amortized training cost: `$11.11/day`
- Provisioned Throughput for custom model (assumption): `$30/day`

Scenario table:

| Scenario | Avg Input Tokens | Avg Output Tokens | Haiku Cost/Req | Nova Cost/Req | Savings/Req | Break-even Volume/Day (No PT, training amortized only) | Break-even Volume/Day (With PT + amortized training) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lean | 500 | 120 | $0.00110 | $0.0000343 | $0.0010657 | 10,426 | 38,577 |
| Base | 900 | 180 | $0.00180 | $0.0000567 | $0.0017433 | 6,374 | 23,582 |
| Heavy | 1500 | 280 | $0.00290 | $0.0000917 | $0.0028083 | 3,957 | 14,639 |

Base-case conclusion:

- If you run on-demand (no PT lock-in), distillation pays back around `6.4k FetchData requests/day`.
- If you require provisioned throughput at `$30/day`, payback shifts to about `23.6k requests/day`.

Decision rule:

- Distill now if stable daily FetchData volume is above break-even and schema accuracy targets are met.
- Defer distillation if volume is below break-even; optimize prompts/RAG first and revisit monthly.