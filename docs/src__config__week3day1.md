# Week 3 — Day 1: Assignment — Agentic RAG (Updated)

## Updated Based on Discussion

Key changes from original assignment:
1. **Combined grading + generation** in one LLM call (not separate calls for everything)
2. **Deterministic query templates** for known topics (not LLM rewriting)
3. **Multi-model architecture** — right model for right task
4. **Separate verification only for critical compliance queries**

---

## Task 1: Update `src/config/bedrock.py` — Multi-Model Registry

Add model registry and task-to-model mapping so each component uses the optimal model.

```python
# src/config/bedrock.py

from langchain_aws import ChatBedrock
from src.config.settings import settings

# Model registry — add new models as they become available
MODELS = {
    "haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "nova_micro": "amazon.nova-micro-v1:0",
    "nova_pro": "amazon.nova-pro-v1:0",
}

# Task-to-model mapping — change models per task here
TASK_MODEL_MAP = {
    "orchestrator": "haiku",         # routing decisions
    "fetch_data": "haiku",           # tool calling
    "doc_review": "sonnet",          # vision + complex documents
    "risk_scoring": "haiku",         # calculations, structured output
    "compliance": "sonnet",          # legal interpretation (worth paying more)
    "retrieval_grading": "haiku",    # simple yes/no — cheapest model works
    "hallucination_check": "haiku",  # verification
    "default": "haiku",              # fallback
}


def create_llm(
    task: str = "default",
    temperature: float = 0,
    max_tokens: int = 1024,
) -> ChatBedrock:
    """
    Create LLM client optimized for a specific task.

    Uses TASK_MODEL_MAP to select the best model.
    Changing which model handles which task is a config change, not code change.

    Args:
        task: Task name from TASK_MODEL_MAP, or model key from MODELS
        temperature: 0 for deterministic (default for underwriting)
        max_tokens: Maximum response tokens

    Returns:
        ChatBedrock instance configured for the task

    Examples:
        llm = create_llm(task="compliance")      # uses Sonnet
        llm = create_llm(task="fetch_data")       # uses Haiku
        llm = create_llm(task="retrieval_grading") # uses cheapest available
    """
    model_key = TASK_MODEL_MAP.get(task, TASK_MODEL_MAP["default"])
    model_id = MODELS.get(model_key, MODELS["haiku"])

    return ChatBedrock(
        model_id=model_id,
        region_name=settings.aws_region,
        model_kwargs={
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    )
```

**Test:** Verify `create_llm(task="compliance")` uses Sonnet and `create_llm(task="retrieval_grading")` uses Haiku.

---

## Task 2: Create `src/rag/query_templates.py` — Deterministic Queries

For known underwriting topics, use predefined queries instead of LLM rewriting. Add synonym expansion for terminology mismatches.

```python
# src/rag/query_templates.py

"""
Deterministic query templates for known underwriting topics.

These are predefined search queries optimized for our document corpus.
Use these instead of LLM query rewriting for known topics.
LLM rewriting is a fallback ONLY for unpredictable user questions.
"""

# Predefined queries for known compliance topics
# Each maps to the terminology our ACTUAL policy documents use
COMPLIANCE_QUERIES = {
    "dti": "maximum debt-to-income ratio requirements and compensating factors",
    "fico": "minimum credit score FICO requirements and risk tiers",
    "ltv": "maximum loan-to-value ratio and PMI requirements",
    "pmi": "private mortgage insurance requirements and removal conditions",
    "seasoning": "minimum time between refinance transactions seasoning period",
    "trid": "TILA-RESPA integrated disclosure timing requirements Loan Estimate",
    "employment": "employment verification requirements minimum tenure years",
    "income": "income documentation requirements verification methods",
    "appraisal": "property appraisal requirements and waiver conditions",
    "closing": "closing procedures disclosure timing requirements",
    "cashout": "cash-out refinance restrictions equity requirements",
}

# Synonym map built from analyzing our actual document corpus
# Use this to expand queries — catches terminology mismatches
# without needing an LLM call
TERM_SYNONYMS = {
    "dti": ["debt-to-income", "borrower leverage", "income ratio", "debt ratio"],
    "fico": ["credit score", "creditworthiness", "credit rating"],
    "ltv": ["loan-to-value", "equity ratio", "financing ratio"],
    "pmi": ["private mortgage insurance", "mortgage insurance premium", "MI"],
    "seasoning": ["waiting period", "minimum time between", "refinance interval"],
    "cashout": ["cash-out", "equity extraction", "home equity", "Section 50(a)(6)"],
    "trid": ["TILA-RESPA", "integrated disclosure", "Loan Estimate", "Closing Disclosure"],
}


def get_compliance_query(topic: str) -> str | None:
    """
    Get predefined query for a known compliance topic.

    Returns None if topic is not in our predefined list,
    indicating that LLM assistance or custom query is needed.

    Args:
        topic: Compliance topic key (e.g., "dti", "fico", "ltv")

    Returns:
        Predefined query string, or None if topic unknown
    """
    return COMPLIANCE_QUERIES.get(topic.lower())


def expand_query_with_synonyms(query: str) -> str:
    """
    Expand a query with known synonyms from our document corpus.

    Deterministic — no LLM call. Catches cases where user says
    "DTI" but documents say "debt-to-income ratio".

    Args:
        query: Original search query

    Returns:
        Expanded query with synonym terms appended
    """
    expanded = query
    query_lower = query.lower()

    for term, synonyms in TERM_SYNONYMS.items():
        if term in query_lower:
            # Add synonyms that aren't already in the query
            new_terms = [s for s in synonyms if s.lower() not in query_lower]
            if new_terms:
                expanded += " " + " ".join(new_terms)

    return expanded


def get_search_query(
    topic: str | None = None,
    custom_query: str | None = None,
) -> str:
    """
    Get the best search query using this priority:
    1. Predefined template (if topic is known)
    2. Custom query with synonym expansion (if provided)
    3. Raise error (if neither provided)

    Args:
        topic: Known compliance topic key
        custom_query: Custom query from user or agent

    Returns:
        Optimized search query string
    """
    if topic and topic.lower() in COMPLIANCE_QUERIES:
        return COMPLIANCE_QUERIES[topic.lower()]

    if custom_query:
        return expand_query_with_synonyms(custom_query)

    raise ValueError("Either topic or custom_query must be provided")
```

**Test:** Verify `get_search_query(topic="dti")` returns the predefined query. Verify `expand_query_with_synonyms("DTI requirements")` adds "debt-to-income" etc.

---

## Task 3: Create `src/models/compliance.py` — Combined Answer Model

One Pydantic model that does grading + answer + self-verification in a single LLM call.

```python
# src/models/compliance.py

from pydantic import BaseModel, Field
from typing import Literal


class IrrelevantDocument(BaseModel):
    """A document that was retrieved but deemed not relevant."""
    document_number: int = Field(description="1-indexed document number")
    reason: str = Field(description="Why this document is not relevant")


class ComplianceAnswer(BaseModel):
    """
    Combined grading + answer + self-verification in ONE LLM call.

    Instead of separate calls for:
    1. Grade relevance (separate call)
    2. Generate answer (separate call)
    3. Check hallucination (separate call)

    This model does all three in one response:
    1. Assess which documents are relevant
    2. Answer from relevant documents only
    3. Self-verify that all claims are supported
    """

    # Context assessment (replaces separate retrieval grader)
    sufficient_context: bool = Field(
        description="Do the provided documents contain enough information "
                    "to answer the question?"
    )
    relevant_document_numbers: list[int] = Field(
        description="Which document numbers (1-indexed) are relevant to the question"
    )
    irrelevant_documents: list[IrrelevantDocument] = Field(
        default_factory=list,
        description="Documents that were retrieved but are not relevant, with reasons"
    )

    # Answer (null if insufficient context)
    answer: str | None = Field(
        description="Answer based ONLY on relevant documents. "
                    "Set to null if sufficient_context is false."
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Source citations for each claim (document name, page, section)"
    )
    confidence: Literal["HIGH", "MEDIUM", "LOW", "NONE"] = Field(
        description="Confidence level. NONE if insufficient context."
    )

    # Self-verification (replaces separate hallucination checker)
    all_claims_supported: bool = Field(
        description="Are ALL claims in the answer directly supported "
                    "by the provided documents? If answer is null, set true."
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Any claims in the answer that are NOT directly "
                    "stated in the provided documents"
    )

    def is_trustworthy(self) -> bool:
        """Quick check: is this answer reliable enough to use?"""
        return (
            self.sufficient_context
            and self.all_claims_supported
            and len(self.unsupported_claims) == 0
            and self.confidence in ("HIGH", "MEDIUM")
        )

    def format_report(self) -> str:
        """Format as human-readable compliance report."""
        lines = []

        if not self.sufficient_context:
            lines.append("⚠️  INSUFFICIENT DOCUMENTATION")
            lines.append("The retrieved documents do not adequately answer this question.")
            if self.irrelevant_documents:
                lines.append("\nDocuments retrieved but not relevant:")
                for doc in self.irrelevant_documents:
                    lines.append(f"  - Doc {doc.document_number}: {doc.reason}")
            return "\n".join(lines)

        lines.append(f"Answer (Confidence: {self.confidence}):")
        lines.append(self.answer or "No answer generated")
        lines.append(f"\nSources:")
        for s in self.sources:
            lines.append(f"  - {s}")

        if not self.all_claims_supported:
            lines.append(f"\n⚠️  UNSUPPORTED CLAIMS DETECTED:")
            for claim in self.unsupported_claims:
                lines.append(f"  - {claim}")

        return "\n".join(lines)
```

**Test:** Create valid and invalid ComplianceAnswer instances. Verify `is_trustworthy()` logic. Test `format_report()` output.

---

## Task 4: Create `src/rag/smart_rag.py` — Hybrid RAG Pipeline

The main RAG class that uses deterministic queries + combined LLM call + optional separate verification.

```python
# src/rag/smart_rag.py

"""
Hybrid RAG pipeline:
- Deterministic queries for known topics (no LLM rewriting)
- Combined grading + answer + self-check in ONE LLM call
- Separate hallucination verification ONLY for critical queries
- Multi-model: cheap model for grading, expensive for compliance
"""

import logging
from langchain_core.prompts import ChatPromptTemplate
from src.config.bedrock import create_llm
from src.rag.vectorstore import load_vectorstore
from src.rag.rag_chain import format_docs
from src.rag.query_templates import get_search_query, expand_query_with_synonyms
from src.models.compliance import ComplianceAnswer

logger = logging.getLogger(__name__)

COMPLIANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a mortgage compliance officer reviewing regulatory documents.

INSTRUCTIONS:
1. First, assess which of the provided documents are relevant to the question
2. If fewer than 2 documents are relevant, set sufficient_context to false
3. If sufficient context exists, answer ONLY from the relevant documents
4. Cite specific source documents for every claim
5. After writing your answer, verify that EVERY claim is directly
   supported by the documents. List any claims that are not.
6. NEVER fabricate information. If documents don't cover it, say so."""),
    ("human", """CONTEXT DOCUMENTS:
{context}

QUESTION: {question}"""),
])


class SmartRAG:
    """
    Production RAG with hybrid query strategy and combined LLM grading.

    Approach:
    - Known topics: deterministic query templates (no LLM rewriting)
    - Unknown topics: synonym expansion (no LLM rewriting)
    - All queries: combined grading + answer + self-check (1 LLM call)
    - Critical queries: optional separate verification (2nd LLM call)
    """

    def __init__(self, metadata_filter: dict | None = None):
        self.vectorstore = load_vectorstore()
        self.metadata_filter = metadata_filter

    def query(
        self,
        question: str,
        topic: str | None = None,
        critical: bool = False,
    ) -> ComplianceAnswer:
        """
        Run the hybrid RAG pipeline.

        Args:
            question: Natural language question
            topic: Known topic key (e.g., "dti", "fico") for deterministic query
            critical: If True, run separate hallucination verification

        Returns:
            ComplianceAnswer with answer, sources, and quality assessment
        """
        # Step 1: Build the search query (deterministic, no LLM)
        search_query = self._build_query(question, topic)
        logger.info(f"Search query: '{search_query}'")

        # Step 2: Retrieve documents
        docs = self._retrieve(search_query)
        logger.info(f"Retrieved {len(docs)} documents")

        if not docs:
            return ComplianceAnswer(
                sufficient_context=False,
                relevant_document_numbers=[],
                answer=None,
                confidence="NONE",
                all_claims_supported=True,
                sources=[],
            )

        # Step 3: Combined grading + generation (ONE LLM call)
        # Use compliance model (Sonnet) for critical, default for routine
        task = "compliance" if critical else "default"
        llm = create_llm(task=task)
        chain = COMPLIANCE_PROMPT | llm.with_structured_output(ComplianceAnswer)

        result = chain.invoke({
            "context": format_docs(docs),
            "question": question,
        })

        logger.info(
            f"Result: sufficient={result.sufficient_context}, "
            f"confidence={result.confidence}, "
            f"supported={result.all_claims_supported}"
        )

        # Step 4: Separate hallucination check (ONLY for critical queries)
        if critical and result.answer and not result.all_claims_supported:
            logger.info("Critical query with unsupported claims — running verification")
            result = self._verify_answer(question, docs, result)

        return result

    def _build_query(self, question: str, topic: str | None) -> str:
        """Build search query: deterministic template or synonym expansion."""
        if topic:
            predefined = get_search_query(topic=topic)
            if predefined:
                logger.info(f"Using predefined query for topic '{topic}'")
                return predefined

        # No predefined template — expand with synonyms (still no LLM)
        expanded = expand_query_with_synonyms(question)
        if expanded != question:
            logger.info(f"Expanded query with synonyms: '{expanded}'")
        return expanded

    def _retrieve(self, query: str, k: int = 5) -> list:
        """Retrieve documents with optional metadata filter."""
        search_kwargs = {"k": k}
        if self.metadata_filter:
            search_kwargs["filter"] = self.metadata_filter
        return self.vectorstore.similarity_search(query, **search_kwargs)

    def _verify_answer(self, question, docs, original_result) -> ComplianceAnswer:
        """
        Separate hallucination verification for critical queries.

        Only called when:
        1. Query is marked critical AND
        2. Self-check flagged unsupported claims

        Uses a DIFFERENT prompt (critic mindset, not author mindset).
        """
        verify_llm = create_llm(task="hallucination_check")
        verify_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a compliance auditor verifying an answer
for accuracy. Your job is to be SKEPTICAL and THOROUGH.

Check whether EVERY claim in the answer is directly supported
by the source documents. Be strict — in regulatory compliance,
unsupported claims can have legal consequences."""),
            ("human", """SOURCE DOCUMENTS:
{context}

ANSWER BEING VERIFIED:
{answer}

ORIGINAL QUESTION: {question}

Verify the answer. List any claims NOT supported by the documents."""),
        ])

        verified = (
            verify_prompt
            | verify_llm.with_structured_output(ComplianceAnswer)
        ).invoke({
            "context": format_docs(docs),
            "answer": original_result.answer,
            "question": question,
        })

        return verified
```

**Test with three scenarios:**
1. Known topic: `smart_rag.query("What are the DTI limits?", topic="dti")` — uses predefined query
2. Unknown topic: `smart_rag.query("What about construction-to-permanent loans?")` — uses synonym expansion
3. Critical: `smart_rag.query("Does this comply with Section 50(a)(6)?", critical=True)` — uses Sonnet + verification

---

## Task 5: Create `src/tools/policy_tools_v2.py` — Updated Agent Tools

Two tools with clear docstrings telling the agent when to use each.

```python
# src/tools/policy_tools_v2.py

from langchain_core.tools import tool
from src.rag.smart_rag import SmartRAG
from src.rag.query_templates import COMPLIANCE_QUERIES


@tool
def search_lending_policies(
    query: str,
    topic: str = "",
    jurisdiction: str = "federal",
) -> str:
    """Search lending policies for routine lookups.

    FAST — one LLM call. Use for straightforward policy questions.

    Available topics (use these for best results):
    dti, fico, ltv, pmi, seasoning, trid, employment, income, appraisal, closing, cashout

    Args:
        query: Natural language question about policies
        topic: Known topic key for optimized search (e.g., "dti", "fico").
               Leave empty if the question doesn't match a known topic.
        jurisdiction: "federal", "state_texas", "state_california", etc.

    Returns:
        Policy answer with source citations and confidence level
    """
    metadata_filter = None
    if jurisdiction and jurisdiction != "federal":
        metadata_filter = {"jurisdiction": jurisdiction}

    rag = SmartRAG(metadata_filter=metadata_filter)
    result = rag.query(
        question=query,
        topic=topic if topic else None,
        critical=False,
    )
    return result.format_report()


@tool
def verify_compliance_requirement(
    query: str,
    jurisdiction: str = "federal",
) -> str:
    """Thorough compliance verification for critical regulatory questions.

    SLOWER but MORE ACCURATE — uses stronger model + verification.
    Use this when accuracy has legal or regulatory implications.
    Use for: specific regulatory requirements, Section references,
    compliance decisions that could be audited.

    Args:
        query: Specific compliance question
        jurisdiction: "federal", "state_texas", "state_california", etc.

    Returns:
        Verified answer with sources, confidence, and hallucination check
    """
    metadata_filter = None
    if jurisdiction and jurisdiction != "federal":
        metadata_filter = {"jurisdiction": jurisdiction}

    rag = SmartRAG(metadata_filter=metadata_filter)
    result = rag.query(
        question=query,
        topic=None,
        critical=True,
    )

    trustworthy = "✅ VERIFIED" if result.is_trustworthy() else "⚠️ NEEDS REVIEW"
    return f"[{trustworthy}]\n\n{result.format_report()}"
```

**Test:** Invoke each tool directly and verify output format.

---

## Task 6: Write Tests — `tests/test_smart_rag.py`

```python
# tests/test_smart_rag.py

"""
Tests for the hybrid SmartRAG pipeline.
"""

import pytest
from src.rag.query_templates import (
    get_search_query,
    expand_query_with_synonyms,
    get_compliance_query,
    COMPLIANCE_QUERIES,
    TERM_SYNONYMS,
)
from src.models.compliance import ComplianceAnswer, IrrelevantDocument


class TestQueryTemplates:
    """Test deterministic query generation."""

    def test_known_topic_returns_predefined_query(self):
        query = get_search_query(topic="dti")
        assert "debt-to-income" in query
        assert query == COMPLIANCE_QUERIES["dti"]

    def test_unknown_topic_with_custom_query(self):
        query = get_search_query(custom_query="construction loan rules")
        assert "construction loan rules" in query

    def test_synonym_expansion_adds_terms(self):
        expanded = expand_query_with_synonyms("DTI requirements")
        assert "debt-to-income" in expanded
        assert "DTI requirements" in expanded  # original preserved

    def test_synonym_expansion_no_duplicates(self):
        expanded = expand_query_with_synonyms("debt-to-income ratio requirements")
        # "debt-to-income" already in query, shouldn't be added again
        count = expanded.lower().count("debt-to-income")
        assert count == 1

    def test_no_topic_no_query_raises_error(self):
        with pytest.raises(ValueError):
            get_search_query()


class TestComplianceAnswer:
    """Test the combined answer model."""

    def test_trustworthy_answer(self):
        answer = ComplianceAnswer(
            sufficient_context=True,
            relevant_document_numbers=[1, 2],
            answer="The maximum DTI is 43%.",
            sources=["fannie_mae.pdf, Page 42"],
            confidence="HIGH",
            all_claims_supported=True,
        )
        assert answer.is_trustworthy()

    def test_insufficient_context_not_trustworthy(self):
        answer = ComplianceAnswer(
            sufficient_context=False,
            relevant_document_numbers=[],
            answer=None,
            confidence="NONE",
            all_claims_supported=True,
        )
        assert not answer.is_trustworthy()

    def test_unsupported_claims_not_trustworthy(self):
        answer = ComplianceAnswer(
            sufficient_context=True,
            relevant_document_numbers=[1],
            answer="The DTI limit is 50%.",
            sources=["fannie_mae.pdf"],
            confidence="MEDIUM",
            all_claims_supported=False,
            unsupported_claims=["DTI limit of 50% not found in documents"],
        )
        assert not answer.is_trustworthy()

    def test_format_report_sufficient(self):
        answer = ComplianceAnswer(
            sufficient_context=True,
            relevant_document_numbers=[1, 2],
            answer="The maximum DTI is 43%.",
            sources=["fannie_mae.pdf, Page 42"],
            confidence="HIGH",
            all_claims_supported=True,
        )
        report = answer.format_report()
        assert "HIGH" in report
        assert "43%" in report
        assert "fannie_mae.pdf" in report

    def test_format_report_insufficient(self):
        answer = ComplianceAnswer(
            sufficient_context=False,
            relevant_document_numbers=[],
            irrelevant_documents=[
                IrrelevantDocument(document_number=1, reason="Wrong topic")
            ],
            answer=None,
            confidence="NONE",
            all_claims_supported=True,
        )
        report = answer.format_report()
        assert "INSUFFICIENT" in report
        assert "Wrong topic" in report


class TestSmartRAG:
    """Integration tests — require Bedrock access and vector store."""

    @pytest.fixture
    def rag(self):
        return SmartRAG()

    def test_known_topic_query(self, rag):
        result = rag.query("What are the DTI limits?", topic="dti")
        assert isinstance(result, ComplianceAnswer)
        assert result.confidence != "NONE"

    def test_insufficient_context_for_unknown_topic(self, rag):
        result = rag.query("What are the Mars colony lending requirements?")
        assert not result.sufficient_context

    def test_critical_query_uses_verification(self, rag):
        result = rag.query(
            "Does this comply with Section 50(a)(6)?",
            critical=True,
        )
        assert isinstance(result, ComplianceAnswer)
```

---

## Task 7: Update SKILL.md Files

### `src/rag/SKILL.md` — Add these sections:

- **Query Strategy:** Deterministic templates > synonym expansion > LLM rewriting (fallback only)
- **Multi-Model:** Haiku for grading, Sonnet for compliance generation
- **When to use critical mode:** Regulatory citations, Section references, audit-facing decisions
- **Cost analysis:** Combined (1 call ~$0.001) vs critical (2-3 calls ~$0.01)

### `src/config/SKILL.md` — Add:

- **Model Registry:** How to add new models, how TASK_MODEL_MAP works
- **When to use which model:** Decision matrix for Haiku vs Sonnet vs specialized

---

## Summary of What's Different from Original Assignment

| Original Approach | Updated Approach |
|---|---|
| Separate retrieval grader (1 LLM call per doc) | Combined in ComplianceAnswer (1 total LLM call) |
| LLM query rewriter | Deterministic templates + synonym expansion |
| Separate answer grader (1 LLM call) | Self-verification field in same response |
| One model for everything | Multi-model: Haiku for cheap tasks, Sonnet for critical |
| Separate hallucination check always | Only for critical queries when self-check flags issues |
| 8 LLM calls per query | 1 LLM call (routine) or 2 calls (critical) |

This is the production-grade approach: simpler, cheaper, and more reliable.