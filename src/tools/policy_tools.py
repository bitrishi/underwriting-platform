from langchain_core.tools import tool

from src.rag.rag_chain import format_docs
from src.rag.vectorstore import load_vectorstore

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
    vectorstore = load_vectorstore()

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

    results = vectorstore.similarity_search(enriched_query, k=3, filter=metadata_filter)
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

    vectorstore = load_vectorstore()
    results = vectorstore.similarity_search(query, k=3, filter=metadata_filter)
    return format_docs(results)