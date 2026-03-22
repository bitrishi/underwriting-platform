# src/agents/doc_review.py

from langchain.agents import create_agent
from src.config.bedrock import create_llm
from src.tools.document_tools import (
    classify_document,
    extract_document_data,
    compare_documents,
    validate_document_package,
)
from src.utils.prompt_loader import load_prompt


def create_doc_review_agent():
    """Create the Document Review sub-agent.

    Processes uploaded loan documents:
    1. Classifies each document by type (classify_document)
    2. Extracts structured data using text or vision routing (extract_document_data)
    3. Cross-validates data across documents (compare_documents)
    4. Builds a validated review package and flags missing docs (validate_document_package)

    Uses Claude Sonnet via ``create_llm(task="doc_review")`` — vision and legal
    reasoning tasks benefit from Sonnet's stronger comprehension.

    Returns:
        A LangGraph agent compiled with the doc-review system prompt and all
        four document tools. Invoke with a ``messages`` payload.
    """
    llm = create_llm(task="doc_review")

    tools = [
        classify_document,
        extract_document_data,
        compare_documents,
        validate_document_package,
    ]

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=load_prompt("doc_review"),
    )
