from langchain.agents import create_agent
from src.config.bedrock import create_llm
from src.tools.fetch_tools import (
    pull_borrower_data,
    pull_credit_report,
    pull_employment_history,
)
from src.tools.policy_tools import search_lending_policies
from src.utils.prompt_loader import load_prompt
def create_fetch_data_agent():
    """
    Create the FetchData sub-agent.
    
    Responsible for gathering ALL data needed for underwriting:
    - Borrower profile from loan origination system
    - Credit report from credit bureau
    - Employment history from verification service
    - Relevant lending policies via RAG
    
    The agent autonomously decides which tools to call
    and in what order based on the application.
    """
    llm = create_llm(temperature=0)
    
    system_prompt = load_prompt("fetch_data")
    
    tools = [
        pull_borrower_data,
        pull_credit_report,
        pull_employment_history,
        search_lending_policies,
    ]
    
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )