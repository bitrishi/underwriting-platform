import os
import sys

# Ensure repository root imports work when running directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.agents.underwriting_agent import create_underwriting_Agent
from src.callbacks.tracer import UnderwritingTracer


def main() -> None:
    tracer = UnderwritingTracer()
    agent = create_underwriting_Agent()

    texas_prompt = (
        "Evaluate this Texas conventional loan application and provide a decision.\n"
        "Borrower: Elena Martinez\n"
        "Loan Amount: $328,000\n"
        "FICO Score: 695\n"
        "Monthly Debt: $3,250\n"
        "Annual Income: $108,000\n"
        "Property Value: $400,000\n"
        "Employment Years: 4\n\n"
        "This is a Texas scenario. Use tools to check DTI, LTV, FICO, and any relevant policy requirements. "
        "If state-specific rules matter, look them up before deciding."
    )

    result = agent.invoke({"input": texas_prompt}, config={"callbacks": [tracer]})

    print("\n=== RAG-ENHANCED UNDERWRITING AGENT RUN ===")
    print(texas_prompt)
    print("\n--- Agent Output ---")
    print(result)

    print("\n--- Callback Trace (Tool Calls + LLM Events) ---")
    print(tracer.get_trace_summary())


if __name__ == "__main__":
    main()
