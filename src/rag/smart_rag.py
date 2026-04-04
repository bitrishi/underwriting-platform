"""
Hybrid RAG pipeline — production-grade.

Architecture decisions:
1. Deterministic queries for known topics (no LLM rewriting)
2. Synonym expansion for terminology mismatches (no LLM rewriting)
3. Combined grading + answer + self-check in ONE LLM call
4. Multi-model: cheap model for routine, expensive for critical
5. Separate hallucination verification ONLY when self-check flags issues

Cost:
- Routine query: 1 LLM call (~$0.001 with Haiku)
- Critical query: 1-2 LLM calls (~$0.003-0.010 with Sonnet)
"""

import logging
from langchain_core.prompts import ChatPromptTemplate
from src.config.bedrock import create_llm
from src.rag.vectorstore import load_vectorstore
from src.rag.rag_chain import format_docs
from src.rag.query_templates import (
    get_compliance_query,
    expand_query_with_synonyms,
)
from src.models.compliance import ComplianceAnswer
from src.utils.circuit_breaker import opensearch_breaker
from src.utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


# ============================================================
# PROMPTS
# ============================================================

# Main compliance prompt — used for BOTH routine and critical queries.
# The ComplianceAnswer model forces the LLM to grade + answer + self-verify
# in a single response.
COMPLIANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a mortgage compliance officer reviewing regulatory documents.

INSTRUCTIONS (follow in order):
1. Read ALL provided context documents carefully
2. Assess which documents are relevant to the SPECIFIC question asked
3. If fewer than 2 documents are relevant, set sufficient_context to false
   and set answer to null
4. If sufficient context exists, answer ONLY from the relevant documents
5. Cite the specific source document, page, and section for every claim
6. After writing your answer, RE-READ it and verify that EVERY claim
   is directly supported by the documents
7. If you find any claim you made that isn't directly in the documents,
   list it in unsupported_claims

CRITICAL RULES:
- NEVER fabricate regulations, thresholds, or requirements
- NEVER mix information from different jurisdictions
- If documents discuss a related but DIFFERENT topic, mark as irrelevant
- "I don't know" is always better than an unsupported answer"""),
    ("human", """CONTEXT DOCUMENTS:
{context}

QUESTION: {question}"""),
])

# Separate verification prompt — ONLY used for critical queries
# when self-check flags potential issues.
# Uses a "critic" persona, not "author" — different mindset.
VERIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a compliance AUDITOR verifying someone else's work.
Your job is to be SKEPTICAL and THOROUGH.

You are given source documents and an answer that was written
based on those documents. Check whether EVERY claim in the
answer is directly supported by the source documents.

Be strict — in regulatory compliance, unsupported claims
can have legal consequences. When in doubt, flag it."""),
    ("human", """SOURCE DOCUMENTS:
{context}

ANSWER BEING VERIFIED:
{answer}

ORIGINAL QUESTION: {question}

Verify the answer. Identify any unsupported claims."""),
])


class SmartRAG:
    """
    Production RAG with hybrid query strategy and combined LLM grading.

    Usage:
        rag = SmartRAG(metadata_filter={"jurisdiction": "state_texas"})

        # Routine lookup — 1 LLM call
        result = rag.query("What are the DTI limits?", topic="dti")

        # Critical compliance check — uses Sonnet + optional verification
        result = rag.query(
            "Does this comply with Section 50(a)(6)?",
            critical=True,
        )

        # Check quality
        if result.is_trustworthy():
            print(result.answer)
        else:
            print("Needs human review")
    """

    def __init__(self, metadata_filter: dict | None = None):
        """
        Initialize SmartRAG.

        Args:
            metadata_filter: Applied to ALL searches.
                e.g., {"jurisdiction": "state_texas"} limits
                all results to Texas documents.
        """
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

        Flow:
        1. Build search query (deterministic — no LLM)
        2. Retrieve documents from vector store
        3. Combined grading + generation + self-check (1 LLM call)
        4. If critical AND self-check flags issues → separate verification

        Args:
            question: Natural language question
            topic: Known topic key for deterministic query
                   (e.g., "dti", "fico", "ltv")
                   Pass None for unknown topics.
            critical: If True, uses stronger model (Sonnet) and
                      runs separate verification when needed.

        Returns:
            ComplianceAnswer with answer, sources, quality metrics
        """
        # ──────────────────────────────────────────────
        # Step 1: Build search query (NO LLM call)
        # ──────────────────────────────────────────────
        search_query = self._build_query(question, topic)
        logger.info(f"Search query: '{search_query[:80]}...'")

        # ──────────────────────────────────────────────
        # Step 2: Retrieve documents
        # ──────────────────────────────────────────────
        docs = self._retrieve(search_query)
        logger.info(f"Retrieved {len(docs)} documents")

        # Handle empty results
        if not docs:
            logger.warning("No documents retrieved")
            return ComplianceAnswer(
                sufficient_context=False,
                relevant_document_numbers=[],
                answer=None,
                confidence="NONE",
                all_claims_supported=True,
            )

        # ──────────────────────────────────────────────
        # Step 3: Combined grading + generation (1 LLM call)
        # ──────────────────────────────────────────────
        # Choose model based on criticality
        task = "rag_generation_critical" if critical else "rag_generation"
        llm = create_llm(task=task)

        chain = COMPLIANCE_PROMPT | llm.with_structured_output(
            ComplianceAnswer
        )

        result = chain.invoke({
            "context": format_docs(docs),
            "question": question,
        })

        logger.info(
            f"Result: sufficient={result.sufficient_context}, "
            f"confidence={result.confidence}, "
            f"claims_supported={result.all_claims_supported}, "
            f"relevant_docs={result.relevant_document_numbers}"
        )

        # ──────────────────────────────────────────────
        # Step 4: Separate verification (ONLY if needed)
        # ──────────────────────────────────────────────
        # Only runs when ALL of these are true:
        #   - Query is marked critical
        #   - An answer was generated
        #   - Self-check flagged unsupported claims
        if (
            critical
            and result.answer
            and not result.all_claims_supported
        ):
            logger.info(
                "Critical query with unsupported claims — "
                "running separate verification"
            )
            result = self._verify_answer(question, docs, result)

        return result

    def _build_query(self, question: str, topic: str | None) -> str:
        """
        Build the search query. Deterministic — no LLM call.

        Priority:
        1. Predefined template if topic is known
        2. Synonym expansion for unknown topics
        """
        # Try predefined query first
        if topic:
            predefined = get_compliance_query(topic)
            if predefined:
                logger.info(f"Using predefined query for topic '{topic}'")
                return predefined
            else:
                logger.info(
                    f"Topic '{topic}' not in templates, "
                    f"using synonym expansion"
                )

        # Fall back to synonym expansion (still no LLM call)
        expanded = expand_query_with_synonyms(question)
        if expanded != question:
            logger.info(f"Expanded with synonyms: '{expanded[:80]}...'")
        return expanded

    def _retrieve(self, query: str, k: int = 5) -> list:
        """
        Retrieve documents with optional metadata filter.

        Args:
            query: Search query (from _build_query)
            k: Number of documents to retrieve

        Returns:
            List of Document objects with content and metadata
        """
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.3,
            max_delay=3.0,
            retryable_exceptions=(TimeoutError, ConnectionError),
            jitter=True,
        )
        def _search() -> list:
            search_kwargs = {"k": k}
            if self.metadata_filter:
                search_kwargs["filter"] = self.metadata_filter
            return self.vectorstore.similarity_search(query, **search_kwargs)

        try:
            return opensearch_breaker.call(_search)
        except Exception:
            logger.warning("OpenSearch/FAISS search unavailable; returning empty retrieval set")
            return []

    def _verify_answer(
        self,
        question: str,
        docs: list,
        original_result: ComplianceAnswer,
    ) -> ComplianceAnswer:
        """
        Separate hallucination verification.

        Uses a DIFFERENT prompt with a "critic" persona — not the
        same LLM call that generated the answer. This avoids the
        bias of an author grading their own work.

        Only called when:
        1. Query is marked critical, AND
        2. Self-check already flagged unsupported claims

        Args:
            question: Original question
            docs: Retrieved documents
            original_result: The answer being verified

        Returns:
            New ComplianceAnswer from the verification call
        """
        verify_llm = create_llm(task="hallucination_check")

        chain = VERIFICATION_PROMPT | verify_llm.with_structured_output(
            ComplianceAnswer
        )

        verified = chain.invoke({
            "context": format_docs(docs),
            "answer": original_result.answer,
            "question": question,
        })

        logger.info(
            f"Verification result: "
            f"supported={verified.all_claims_supported}, "
            f"hallucinated={verified.unsupported_claims}"
        )

        return verified