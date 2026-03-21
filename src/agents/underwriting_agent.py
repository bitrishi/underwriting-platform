from langchain.agents import create_agent
from src.config.bedrock import create_llm
from src.tools.underwriting_tools import calculate_dti, calculate_ltv, check_fico_eligibility
from src.tools.policy_tools import search_lending_policies
from src.utils.prompt_loader import load_prompt


def create_underwriting_Agent():
    """Create an underwriting agent that uses Bedrock LLM and custom tools.

    The agent will evaluate loan applications by calling tools for DTI, LTV, and FICO checks,
    and then synthesize the results to make an underwriting decision.

    Returns:
        An AgentExecutor that can be invoked with loan application data.
    """
    # Load the system prompt for underwriting
    system_prompt = load_prompt("underwriter")

    # Create the Bedrock LLM with deterministic settings
    llm = create_llm(temperature=0)

    # Define the tools the agent can use
    tools = [
        calculate_dti,
        calculate_ltv,
        check_fico_eligibility,
        search_lending_policies,
    ]

    # Create the agent using the current LangChain API
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )

    # create_agent returns an agent object that can be invoked using `agent.invoke()`
    return agent