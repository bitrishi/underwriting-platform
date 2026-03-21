import os
import sys

# Ensure the repository root is on sys.path when running as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.agents.underwriting_agent import create_underwriting_Agent
from src.callbacks.tracer import UnderwritingTracer


def run_agent_scenario(prompt: str, tracer: UnderwritingTracer):
    agent = create_underwriting_Agent()
    result = agent.invoke({"input": prompt}, config={"callbacks": [tracer]})

    print("\n=== AGENT RUN ===")
    print(prompt)
    print("--- Decision / Output ---")
    print(result)
    print("--- Trace Timeline ---")
    print(tracer.get_trace_summary())
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    tracer = UnderwritingTracer()

    # 1) Strong application (should approve)
    approve_prompt = (
        "Evaluate this loan application:\n"
        "- Borrower: Alice\n"
        "- Loan Amount: $200,000\n"
        "- FICO Score: 780\n"
        "- Monthly Debt: $1,200\n"
        "- Annual Income: $150,000\n"
        "- Property Value: $400,000\n"
        "- Employment Years: 8\n"
        "\nPlease use the available tools (DTI, LTV, FICO) and decide whether to approve this loan."
    )

    # 2) Weak application (should deny)
    deny_prompt = (
        "Evaluate this loan application:\n"
        "- Borrower: Bob\n"
        "- Loan Amount: $350,000\n"
        "- FICO Score: 610\n"
        "- Monthly Debt: $4,500\n"
        "- Annual Income: $75,000\n"
        "- Property Value: $380,000\n"
        "- Employment Years: 1\n"
        "\nPlease use the available tools (DTI, LTV, FICO) and decide whether to deny this loan."
    )

    # 3) Borderline application (conditional approval)
    borderline_prompt = (
        "Evaluate this loan application:\n"
        "- Borrower: Carol\n"
        "- Loan Amount: $250,000\n"
        "- FICO Score: 700\n"
        "- Monthly Debt: $2,800\n"
        "- Annual Income: $90,000\n"
        "- Property Value: $300,000\n"
        "- Employment Years: 3\n"
        "\nPlease use the available tools (DTI, LTV, FICO) and indicate if this is a conditional approval."
    )

    for prompt in (approve_prompt, deny_prompt, borderline_prompt):
        run_agent_scenario(prompt, tracer)
        tracer.trace.clear()
