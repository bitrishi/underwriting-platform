"""
Tests for the hybrid SmartRAG pipeline.

Organized in three groups:
1. TestQueryTemplates — deterministic query generation (no Bedrock needed)
2. TestComplianceAnswer — Pydantic model validation (no Bedrock needed)
3. TestSmartRAG — integration tests (requires Bedrock + vector store)
"""

import pytest
from src.rag.query_templates import (
    get_compliance_query,
    get_search_query,
    expand_query_with_synonyms,
    COMPLIANCE_QUERIES,
)
from src.rag.smart_rag import SmartRAG
from src.models.compliance import ComplianceAnswer, IrrelevantDocument
from src.config.bedrock import create_llm, get_model_for_task, TASK_MODEL_MAP


# ============================================================
# TEST GROUP 1: Query Templates (no Bedrock needed)
# ============================================================
class TestQueryTemplates:
    """Test deterministic query generation — runs without Bedrock."""

    def test_known_topic_returns_predefined_query(self):
        """Known topics should return our optimized query."""
        query = get_search_query(topic="dti")
        assert "debt-to-income" in query
        assert query == COMPLIANCE_QUERIES["dti"]

    def test_all_topics_have_queries(self):
        """Every topic in the registry should return a non-empty query."""
        for topic in COMPLIANCE_QUERIES:
            query = get_compliance_query(topic)
            assert query is not None
            assert len(query) > 10

    def test_unknown_topic_returns_none(self):
        """Unknown topics should return None."""
        assert get_compliance_query("space_travel") is None
        assert get_compliance_query("martian_lending") is None

    def test_custom_query_with_synonym_expansion(self):
        """Custom queries should get synonym expansion."""
        query = get_search_query(custom_query="DTI requirements for Texas")
        assert "DTI requirements for Texas" in query
        assert "debt-to-income" in query  # synonym added

    def test_synonym_expansion_no_duplicates(self):
        """Synonyms already in query should not be added again."""
        query = expand_query_with_synonyms(
            "debt-to-income ratio requirements"
        )
        # "debt-to-income" already present — should not duplicate
        count = query.lower().count("debt-to-income")
        assert count == 1

    def test_no_topic_no_query_raises_error(self):
        """Must provide either topic or custom_query."""
        with pytest.raises(ValueError, match="Either topic or custom_query"):
            get_search_query()

    def test_case_insensitive_topic(self):
        """Topics should match regardless of case."""
        assert get_compliance_query("DTI") is not None
        assert get_compliance_query("dti") is not None
        assert get_compliance_query("Dti") is not None

    def test_multiple_synonyms_expanded(self):
        """Query mentioning multiple known terms gets all synonyms."""
        query = expand_query_with_synonyms("DTI and FICO requirements")
        assert "debt-to-income" in query
        assert "credit score" in query


# ============================================================
# TEST GROUP 2: ComplianceAnswer Model (no Bedrock needed)
# ============================================================
class TestComplianceAnswer:
    """Test the combined answer model validation and methods."""

    def test_trustworthy_answer(self):
        """Fully supported answer should be trustworthy."""
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
        """No context should not be trustworthy."""
        answer = ComplianceAnswer(
            sufficient_context=False,
            relevant_document_numbers=[],
            answer=None,
            confidence="NONE",
            all_claims_supported=True,
        )
        assert not answer.is_trustworthy()

    def test_unsupported_claims_not_trustworthy(self):
        """Hallucinated claims should not be trustworthy."""
        answer = ComplianceAnswer(
            sufficient_context=True,
            relevant_document_numbers=[1],
            answer="The DTI limit is 50%.",
            sources=["fannie_mae.pdf"],
            confidence="MEDIUM",
            all_claims_supported=False,
            unsupported_claims=["DTI limit of 50% not in documents"],
        )
        assert not answer.is_trustworthy()

    def test_low_confidence_not_trustworthy(self):
        """LOW confidence should not be trustworthy."""
        answer = ComplianceAnswer(
            sufficient_context=True,
            relevant_document_numbers=[1],
            answer="Maybe 43%.",
            sources=["fannie_mae.pdf"],
            confidence="LOW",
            all_claims_supported=True,
        )
        assert not answer.is_trustworthy()

    def test_format_report_with_answer(self):
        """Report with answer should include key information."""
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
        assert "✅" in report

    def test_format_report_insufficient(self):
        """Report without context should show warning."""
        answer = ComplianceAnswer(
            sufficient_context=False,
            relevant_document_numbers=[],
            irrelevant_documents=[
                IrrelevantDocument(
                    document_number=1,
                    reason="Discusses LTV, not DTI"
                ),
            ],
            answer=None,
            confidence="NONE",
            all_claims_supported=True,
        )
        report = answer.format_report()
        assert "INSUFFICIENT" in report
        assert "LTV, not DTI" in report

    def test_format_report_with_hallucinations(self):
        """Report with hallucinations should show warning."""
        answer = ComplianceAnswer(
            sufficient_context=True,
            relevant_document_numbers=[1],
            answer="DTI limit is 50%.",
            sources=["fannie_mae.pdf"],
            confidence="MEDIUM",
            all_claims_supported=False,
            unsupported_claims=["50% limit not in documents"],
        )
        report = answer.format_report()
        assert "⚠️" in report
        assert "50% limit" in report


# ============================================================
# TEST GROUP 3: Multi-Model Config (no Bedrock needed)
# ============================================================
class TestMultiModelConfig:
    """Test that task-to-model mapping is configured correctly."""

    def test_compliance_uses_sonnet(self):
        assert get_model_for_task("compliance") == "sonnet"

    def test_fetch_data_uses_haiku(self):
        assert get_model_for_task("fetch_data") == "haiku"

    def test_retrieval_grading_uses_cheapest(self):
        assert get_model_for_task("retrieval_grading") == "haiku"

    def test_critical_rag_uses_sonnet(self):
        assert get_model_for_task("rag_generation_critical") == "sonnet"

    def test_routine_rag_uses_haiku(self):
        assert get_model_for_task("rag_generation") == "haiku"

    def test_unknown_task_falls_back_to_default(self):
        assert get_model_for_task("nonexistent_task") == TASK_MODEL_MAP["default"]

    def test_all_mapped_models_exist_in_registry(self):
        """Every model referenced in TASK_MODEL_MAP should exist in MODELS."""
        from src.config.bedrock import MODELS
        for task, model_key in TASK_MODEL_MAP.items():
            assert model_key in MODELS, (
                f"Task '{task}' maps to model '{model_key}' "
                f"which is not in MODELS registry"
            )


# ============================================================
# TEST GROUP 4: SmartRAG Integration (requires Bedrock + vector store)
# Mark with @pytest.mark.integration to skip in CI without credentials
# ============================================================
@pytest.mark.integration
class TestSmartRAGIntegration:
    """Integration tests — require Bedrock access and built vector store."""

    @pytest.fixture
    def rag(self):
        return SmartRAG()

    @pytest.fixture
    def texas_rag(self):
        return SmartRAG(metadata_filter={"jurisdiction": "state_texas"})

    def test_known_topic_returns_answer(self, rag):
        """Known topic query should return a ComplianceAnswer."""
        result = rag.query("What are the DTI limits?", topic="dti")
        assert isinstance(result, ComplianceAnswer)
        assert result.confidence != "NONE"

    def test_unknown_question_returns_insufficient(self, rag):
        """Questions not in our docs should return insufficient."""
        result = rag.query("What are the Mars colony lending requirements?")
        assert not result.sufficient_context

    def test_texas_filter_returns_texas_docs(self, texas_rag):
        """Texas-filtered RAG should only return Texas documents."""
        result = texas_rag.query("What are the LTV limits?", topic="ltv")
        if result.sources:
            for source in result.sources:
                # Should reference Texas documents
                assert "texas" in source.lower() or "state" in source.lower()

    def test_critical_query_returns_answer(self, texas_rag):
        """Critical query should still return a valid answer."""
        result = texas_rag.query(
            "What are the Section 50(a)(6) restrictions?",
            critical=True,
        )
        assert isinstance(result, ComplianceAnswer)

    def test_trustworthy_answer_for_known_topic(self, rag):
        """Well-documented topic should produce trustworthy answer."""
        result = rag.query("What is the minimum FICO score?", topic="fico")
        # Should be trustworthy if our docs cover FICO requirements
        if result.sufficient_context:
            assert result.confidence in ("HIGH", "MEDIUM")