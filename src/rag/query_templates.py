"""Compatibility wrapper for query template helpers.

The codebase historically referenced `src.rag.query_templates`, while the
implementation currently lives in `src.rag.query_template`. Re-export the
public API here so both import paths work.
"""

from src.rag.query_template import (  # noqa: F401
    COMPLIANCE_QUERIES,
    TERM_SYNONYMS,
    expand_query_with_synonyms,
    get_compliance_query,
    get_search_query,
)