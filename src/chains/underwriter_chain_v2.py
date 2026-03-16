"""LCEL-based underwriter chain using LangChain Expression Language.

This version uses ChatPromptTemplate with parameterized thresholds
and builds the chain using LCEL syntax: prompt | structured_llm
"""

from langchain_core.prompts import ChatPromptTemplate

from src.config.bedrock import create_llm
from src.models.decision import LoanDecision
from src.utils.prompt_loader import load_prompt


def create_underwriter_chain_v2():
    """Create an LCEL-based underwriter chain with parameterized thresholds.

    Uses ChatPromptTemplate with variables for underwriting thresholds,
    allowing dynamic rule configuration.

    Returns:
        LCEL chain that takes application_data and threshold parameters,
        returns LoanDecision object.
    """
    # Load the base prompt and modify it to use variables
    base_prompt = load_prompt("underwriter")

    # Remove the JSON schema section since we're using structured output
    schema_start = base_prompt.find("### Output Schema")
    if schema_start != -1:
        base_prompt = base_prompt[:schema_start].strip()

    # Replace hardcoded thresholds with variables
    parameterized_prompt = base_prompt.replace(
        "FICO ≥ 680", "FICO ≥ {min_fico}"
    ).replace(
        "DTI < 0.43", "DTI < {max_dti}"
    ).replace(
        "income ≥ 30 k", "income ≥ {min_income}"
    ).replace(
        "loan ≤ 5× income", "loan ≤ {max_loan_to_income}x income"
    )

    # Create the chat prompt template with variables
    prompt = ChatPromptTemplate.from_messages([
        ("system", parameterized_prompt),
        ("human", "{application_data}")
    ])

    # Create LLM with structured output
    llm = create_llm(temperature=0)

    # Configure structured output
    structured_llm = llm.with_structured_output(LoanDecision)

    # Build LCEL chain
    chain = prompt | structured_llm

    return chain


def create_default_underwriter_chain():
    """Create underwriter chain with default underwriting thresholds.

    Default thresholds:
    - min_fico: 680
    - max_dti: 0.43 (43%)
    - min_income: 30000
    - max_loan_to_income: 5

    Returns:
        LCEL chain configured with standard underwriting rules.
    """
    chain = create_underwriter_chain_v2()

    # Create a wrapper that provides default threshold values
    def evaluate_with_defaults(application_data: str) -> LoanDecision:
        return chain.invoke({
            "application_data": application_data,
            "min_fico": 680,
            "max_dti": 0.43,
            "min_income": 30000,
            "max_loan_to_income": 5
        })

    return evaluate_with_defaults


# For easy importing and usage
underwriter_chain_v2 = create_default_underwriter_chain()