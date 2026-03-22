"""
Deterministic query templates for known underwriting topics.

WHY THIS EXISTS:
- Predefined queries are MORE RELIABLE than LLM-rewritten queries
- LLM rewriting doesn't know what's in YOUR vector store
- Deterministic queries are testable, predictable, and free (no LLM call)

WHEN TO USE:
- Known topics (DTI, FICO, LTV, etc.) → use COMPLIANCE_QUERIES
- Unknown topics with known terms → use synonym expansion
- Completely unpredictable questions → synonym expansion is still better than LLM rewriting

HOW TO MAINTAIN:
- When you add new policy documents, add their key terms to TERM_SYNONYMS
- When you identify a new standard topic, add it to COMPLIANCE_QUERIES
- Review search quality quarterly and update terms based on failed queries
"""


# ============================================================
# PREDEFINED QUERIES FOR KNOWN COMPLIANCE TOPICS
# These are optimized for the terminology in our actual documents.
# Each key maps to a search query that works well against our vector store.
# ============================================================
COMPLIANCE_QUERIES: dict[str, str] = {
    "dti": (
        "maximum debt-to-income ratio requirements "
        "compensating factors qualified mortgage"
    ),
    "fico": (
        "minimum credit score FICO requirements "
        "risk tiers conventional loan eligibility"
    ),
    "ltv": (
        "maximum loan-to-value ratio limits "
        "PMI requirements conventional conforming"
    ),
    "pmi": (
        "private mortgage insurance requirements "
        "PMI removal conditions 78 percent LTV"
    ),
    "seasoning": (
        "minimum time between refinance transactions "
        "seasoning period waiting period requirements"
    ),
    "trid": (
        "TILA-RESPA integrated disclosure timing requirements "
        "Loan Estimate Closing Disclosure business days"
    ),
    "employment": (
        "employment verification requirements "
        "minimum tenure years stability assessment"
    ),
    "income": (
        "income documentation requirements "
        "verification methods pay stubs tax returns"
    ),
    "appraisal": (
        "property appraisal requirements "
        "waiver conditions automated valuation"
    ),
    "closing": (
        "closing procedures disclosure timing "
        "requirements settlement closing costs"
    ),
    "cashout": (
        "cash-out refinance restrictions "
        "equity requirements home equity Section 50"
    ),
}


# ============================================================
# SYNONYM MAP — BUILT FROM ANALYZING OUR ACTUAL DOCUMENTS
# This catches terminology mismatches without an LLM call.
# User says "DTI" but documents say "debt-to-income ratio"
# ============================================================
TERM_SYNONYMS: dict[str, list[str]] = {
    "dti": [
        "debt-to-income",
        "debt to income",
        "borrower leverage",
        "income ratio",
        "debt ratio",
    ],
    "fico": [
        "credit score",
        "creditworthiness",
        "credit rating",
        "credit history",
    ],
    "ltv": [
        "loan-to-value",
        "loan to value",
        "equity ratio",
        "financing ratio",
    ],
    "pmi": [
        "private mortgage insurance",
        "mortgage insurance premium",
        "MI requirement",
    ],
    "seasoning": [
        "waiting period",
        "minimum time between",
        "refinance interval",
        "transaction history",
    ],
    "cashout": [
        "cash-out",
        "cash out",
        "equity extraction",
        "home equity",
        "Section 50(a)(6)",
    ],
    "trid": [
        "TILA-RESPA",
        "integrated disclosure",
        "Loan Estimate",
        "Closing Disclosure",
        "LE/CD",
    ],
    "prepayment": [
        "prepayment penalty",
        "early payoff",
        "early payment",
    ],
    "conventional": [
        "conforming",
        "Fannie Mae",
        "Freddie Mac",
        "GSE",
    ],
}


def get_compliance_query(topic: str) -> str | None:
    """
    Get predefined query for a known compliance topic.

    Returns None if topic is not in our predefined list,
    indicating synonym expansion or custom query is needed.

    Args:
        topic: Compliance topic key (e.g., "dti", "fico", "ltv")

    Returns:
        Predefined query string optimized for our vector store,
        or None if topic is unknown

    Example:
        >>> get_compliance_query("dti")
        "maximum debt-to-income ratio requirements compensating factors..."
        >>> get_compliance_query("space_travel")
        None
    """
    return COMPLIANCE_QUERIES.get(topic.lower().strip())


def expand_query_with_synonyms(query: str) -> str:
    """
    Expand a search query with known synonyms from our document corpus.

    Deterministic — no LLM call needed. Catches cases where the user
    says "DTI" but our documents say "debt-to-income ratio".

    Only adds terms that aren't already present in the query
    to avoid redundancy.

    Args:
        query: Original search query (from user or agent)

    Returns:
        Expanded query with synonym terms appended

    Example:
        >>> expand_query_with_synonyms("DTI requirements for Texas")
        "DTI requirements for Texas debt-to-income debt to income borrower leverage"
    """
    expanded = query
    query_lower = query.lower()

    for term, synonyms in TERM_SYNONYMS.items():
        # Check if the key term appears in the query
        if term.lower() in query_lower:
            # Add only synonyms not already in the query
            new_terms = [
                syn for syn in synonyms
                if syn.lower() not in query_lower
            ]
            if new_terms:
                expanded += " " + " ".join(new_terms)

    return expanded


def get_search_query(
    topic: str | None = None,
    custom_query: str | None = None,
) -> str:
    """
    Get the best search query using this priority:

    1. Predefined template (if topic is known) — most reliable
    2. Custom query with synonym expansion — good for unknown topics
    3. Raise error if neither provided

    Args:
        topic: Known compliance topic key (e.g., "dti")
        custom_query: Custom natural language query

    Returns:
        Optimized search query string

    Raises:
        ValueError: If neither topic nor custom_query provided

    Example:
        >>> get_search_query(topic="dti")
        "maximum debt-to-income ratio requirements..."

        >>> get_search_query(custom_query="Texas prepayment rules")
        "Texas prepayment rules prepayment penalty early payoff..."
    """
    # Priority 1: Known topic → predefined query
    if topic:
        predefined = get_compliance_query(topic)
        if predefined:
            return predefined

    # Priority 2: Custom query → expand with synonyms
    if custom_query:
        return expand_query_with_synonyms(custom_query)

    raise ValueError(
        "Either topic or custom_query must be provided. "
        f"Known topics: {list(COMPLIANCE_QUERIES.keys())}"
    )