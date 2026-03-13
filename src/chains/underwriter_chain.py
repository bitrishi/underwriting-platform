"""LangChain chains for underwriting workflows.

This module provides pre-configured chains that integrate prompts,
LLMs, and structured output parsing for the underwriting system.
"""

from langchain_core.prompts import ChatPromptTemplate

from src.config.bedrock import create_llm
from src.config.settings import settings
from src.models.decision import LoanDecision
from src.utils.prompt_loader import load_prompt


def create_underwriter_chain():
    """Create a LangChain chain for the underwriter agent.

    This chain loads the underwriter prompt, configures the Bedrock LLM,
    and sets up structured output parsing to return LoanDecision objects.

    The chain expects input as a dictionary with an 'application_data' key
    containing the formatted borrower information string.

    Returns:
        A LangChain chain that takes application data and returns LoanDecision.
    """
    # Load the underwriter system prompt
    system_prompt = load_prompt("underwriter")

    # Create the chat prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{application_data}")
    ])

    # Create the LLM with appropriate configuration
    llm = create_llm(temperature=0, max_tokens=1024)

    # Configure structured output based on model capabilities
    model_id = settings.bedrock_model_id.lower()
    if "nova-micro" in model_id:
        # Nova Micro supports json_mode for better structured output
        structured_llm = llm.with_structured_output(LoanDecision, method="json_mode")
    else:
        # Default structured output for other models
        structured_llm = llm.with_structured_output(LoanDecision)

    # Create and return the chain
    chain = prompt | structured_llm
    return chain