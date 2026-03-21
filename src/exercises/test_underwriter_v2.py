"""Test the LCEL-based underwriter chain v2 with the same test applications."""

import asyncio
from src.chains.underwriter_chain_v2 import underwriter_chain_v2
from src.models.application import LoanApplication
from src.utils.formatter import format_decision_report


def test_underwriter_chain_v2():
    """Test the LCEL-based underwriter chain with three test applications."""

    # Create the same test applications as the original
    applications = [
        # Application that should be APPROVED
        LoanApplication(
            borrower_name="Alice Strong",
            loan_amount=350000,
            fico_score=740,
            monthly_debt=2400,
            annual_income=120000,
            property_value=440000,
            employment_years=5,
        ),
        # Application that should be DECLINE
        LoanApplication(
            borrower_name="Bob Risky",
            loan_amount=280000,
            fico_score=620,
            monthly_debt=2200,
            annual_income=55000,
            property_value=290000,
            employment_years=0.5,
        ),
        # Borderline application
        LoanApplication(
            borrower_name="Carol Borderline",
            loan_amount=310000,
            fico_score=685,
            monthly_debt=2900,
            annual_income=85000,
            property_value=365000,
            employment_years=2,
        ),
    ]

    print("Testing LCEL-based Underwriter Chain v2")
    print("=" * 50)

    for i, app in enumerate(applications, 1):
        print(f"\n--- Test Case {i}: {app.borrower_name} ---")
        print(f"FICO: {app.fico_score} | DTI: {app.dti:.2%} | LTV: {app.ltv:.2%}")

        # Format application data for the chain
        application_data = app.to_prompt_string()

        try:
            # Use the LCEL chain
            decision = underwriter_chain_v2(application_data)

            # Print the decision
            print(f"Decision: {decision.decision}")
            print(f"Confidence: {decision.confidence}")
            print(f"Risk Level: {decision.risk_level}")
            print(f"Reasons: {decision.reasons}")
            if decision.conditions:
                print(f"Conditions: {decision.conditions}")

            # Format and display the full report
            report = format_decision_report(app, decision)
            print("\n" + report)

        except Exception as e:
            print(f"Error processing application: {e}")

    print("\n" + "=" * 50)
    print("LCEL Chain v2 test complete!")


if __name__ == "__main__":
    test_underwriter_chain_v2()