"""Day 5 Exercise: Testing Structured Output with Underwriter Chain

This exercise demonstrates end-to-end testing of the underwriter chain
with structured output parsing into LoanDecision objects.
"""

import asyncio
from src.chains.underwriter_chain import create_underwriter_chain
from src.models.application import LoanApplication


async def test_underwriter_chain():
    """Test the underwriter chain with three different loan applications."""

    # Create the underwriter chain
    chain = create_underwriter_chain()

    # Create three test applications
    applications = [
        # Application that should be APPROVED
        LoanApplication(
            borrower_name="Excellent Borrower",
            loan_amount=300000,
            fico_score=780,
            monthly_debt=1500,
            annual_income=120000,
            property_value=400000,
            employment_years=5,
        ),
        # Application that should be DECLINE
        LoanApplication(
            borrower_name="Poor Credit Borrower",
            loan_amount=250000,
            fico_score=620,
            monthly_debt=3000,
            annual_income=80000,
            property_value=280000,
            employment_years=2,
        ),
        # Borderline application that might be CONDITIONAL_APPROVAL
        LoanApplication(
            borrower_name="Borderline Borrower",
            loan_amount=200000,
            fico_score=720,
            monthly_debt=2400,
            annual_income=100000,
            property_value=220000,
            employment_years=3,
        ),
    ]

    print("Testing Underwriter Chain with Structured Output")
    print("=" * 50)

    for i, app in enumerate(applications, 1):
        print(f"\n--- Test Case {i}: {app.borrower_name} ---")
        print(f"FICO: {app.fico_score}, DTI: {app.dti:.2%}, LTV: {app.ltv:.2%}")

        # Format application data for the chain
        application_data = app.to_prompt_string()

        # Run through the chain
        try:
            decision = await chain.ainvoke({"application_data": application_data})

            # Print the decision
            print(f"Decision: {decision.decision}")
            print(f"Confidence: {decision.confidence}")
            print(f"Risk Level: {decision.risk_level}")
            print(f"Reasons: {decision.reasons}")
            if decision.conditions:
                print(f"Conditions: {decision.conditions}")
            if decision.criteria:
                print(f"Criteria: {decision.criteria}")
            if decision.reasoning_trace:
                print(f"Reasoning Trace: {decision.reasoning_trace}")

            # Type verification
            print("\nType Verification:")
            print(f"  decision type: {type(decision.decision)} (should be str)")
            print(f"  confidence type: {type(decision.confidence)} (should be float)")
            print(f"  risk_level type: {type(decision.risk_level)} (should be str)")
            print(f"  reasons type: {type(decision.reasons)} (should be list)")
            if decision.conditions:
                print(f"  conditions type: {type(decision.conditions)} (should be list)")
            if decision.criteria:
                print(f"  criteria type: {type(decision.criteria)} (should be list)")
            if decision.reasoning_trace:
                print(f"  reasoning_trace type: {type(decision.reasoning_trace)} (should be ReasoningTrace)")

            # Value verification
            print("\nValue Verification:")
            print(f"  confidence in [0,1]: {0 <= decision.confidence <= 1}")
            print(f"  decision in allowed values: {decision.decision in ['APPROVED', 'CONDITIONAL_APPROVAL', 'DECLINE']}")
            print(f"  risk_level in allowed values: {decision.risk_level in ['LOW', 'MEDIUM', 'HIGH']}")
            print(f"  reasons not empty: {len(decision.reasons) > 0}")

        except Exception as e:
            print(f"Error processing application: {e}")

    print("\n" + "=" * 50)
    print("Exercise complete!")


if __name__ == "__main__":
    asyncio.run(test_underwriter_chain())