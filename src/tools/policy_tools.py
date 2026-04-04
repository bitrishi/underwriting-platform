from langchain_core.tools import tool

from src.rag.rag_chain import format_docs
from src.rag.vectorstore import build_vectorstore, load_vectorstore
from src.utils.circuit_breaker import opensearch_breaker
from src.utils.retry import retry_with_backoff


def _search_with_rebuild_on_mismatch(
    query: str,
    metadata_filter=None,
    k: int = 3,
):
    """Run similarity search and rebuild store if FAISS dimensionality is stale."""
    @retry_with_backoff(
        max_retries=2,
        base_delay=0.3,
        max_delay=3.0,
        retryable_exceptions=(TimeoutError, ConnectionError),
        jitter=True,
    )
    def _run_similarity_search() -> list:
        vectorstore = load_vectorstore()
        try:
            return vectorstore.similarity_search(query, k=k, filter=metadata_filter)
        except AssertionError:
            # Rebuild when persisted index dimensions do not match current embedding model.
            rebuilt = build_vectorstore("data/policies")
            return rebuilt.similarity_search(query, k=k, filter=metadata_filter)

    try:
        return opensearch_breaker.call(_run_similarity_search)
    except Exception:
        return []

@tool
def search_lending_policies(
    query: str,
    jurisdiction: str = "federal",
    loan_type: str = "all",
) -> str:
    """Search lending policies and regulations.
    
    Use this tool when you need to verify a specific
    regulatory requirement, policy guideline, or
    compliance rule.
    
    Args:
        query: Natural language question about policies
        jurisdiction: "federal", "state_texas", etc.
        loan_type: "conventional", "fha", "va", "all"
        
    Returns:
        Relevant policy text with source citations
    """
    source_keywords: list[str] = []

    jurisdiction_key = jurisdiction.lower().strip()
    if jurisdiction_key not in {"all", "federal", "any"}:
        if "texas" in jurisdiction_key:
            source_keywords.append("texas")
        else:
            source_keywords.append(jurisdiction_key)

    loan_type_key = loan_type.lower().strip()
    enriched_query = query
    if loan_type_key not in {"all", "any"}:
        # Keep loan_type in the semantic query so retrieval remains broad even
        # when documents do not carry explicit loan_type metadata.
        enriched_query = f"{query} (loan type: {loan_type_key})"

    metadata_filter = None
    if source_keywords:
        metadata_filter = lambda m: all(
            keyword in str(m.get("source", "")).lower() for keyword in source_keywords
        )

    results = _search_with_rebuild_on_mismatch(
        enriched_query,
        metadata_filter=metadata_filter,
        k=3,
    )
    return format_docs(results)


@tool
def search_compliance_rules(query: str, regulation_type: str) -> str:
    """Search compliance-focused regulatory text (TRID, RESPA, TILA, etc.).

    Use this tool to find disclosure timing, tolerance, and compliance rules.

    Args:
        query: Natural language compliance question.
        regulation_type: Regulation family, for example "TRID", "RESPA", "TILA".

    Returns:
        Retrieved compliance snippets with source metadata and citations.
    """
    regulation_key = regulation_type.lower().strip()
    regulation_aliases = {
        "trid": ["trid"],
        "respa": ["respa", "trid"],
        "tila": ["tila", "trid"],
        "hmda": ["hmda"],
        "state": ["state", "texas"],
        "all": [],
    }
    keywords = regulation_aliases.get(regulation_key, [regulation_key])

    metadata_filter = None
    if keywords:
        metadata_filter = lambda m: any(
            keyword in str(m.get("source", "")).lower() for keyword in keywords
        )

    results = _search_with_rebuild_on_mismatch(
        query,
        metadata_filter=metadata_filter,
        k=3,
    )
    return format_docs(results)