# app.py

"""
Underwriting Agent Pipeline — Week 1 Build

This is the main entry point that demonstrates the complete
loan eligibility evaluation pipeline:

1. Creates loan applications (Pydantic validated input)
2. Runs them through the underwriter chain (Bedrock LLM)
3. Gets typed decisions (Pydantic validated output)
4. Formats audit trail reports (human-readable)

Usage:
    python app.py
"""

import logging
from src.models.application import LoanApplication
from src.chains.underwriter_chain import UnderwriterChain
from src.utils.formatter import format_decision_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


def create_test_applications() -> list[LoanApplication]:
    """Create test applications covering approve, deny, and borderline."""
    return [
        LoanApplication(
            borrower_name="Alice Strong",
            fico_score=740,
            annual_income=120000,
            monthly_debt=2400,
            loan_amount=350000,
            property_value=440000,
            employment_years=5
        ),
        LoanApplication(
            borrower_name="Bob Risky",
            fico_score=620,
            annual_income=55000,
            monthly_debt=2200,
            loan_amount=280000,
            property_value=290000,
            employment_years=0.5
        ),
        LoanApplication(
            borrower_name="Carol Borderline",
            fico_score=685,
            annual_income=85000,
            monthly_debt=2900,
            loan_amount=310000,
            property_value=365000,
            employment_years=2
        ),
    ]


def main():
    """Run the complete underwriting pipeline."""
    logger.info("Starting Underwriting Pipeline")

    # Initialize the chain
    chain = UnderwriterChain()

    # Process each application
    applications = create_test_applications()

    for app in applications:
        logger.info(f"Evaluating application for {app.borrower_name}")
        print(f"\nProcessing: {app.borrower_name}...")
        print(f"  FICO: {app.fico_score} | DTI: {app.dti:.1f}% | LTV: {app.ltv:.1f}%")

        decision = chain.evaluate_safe(app)

        if decision:
            report = format_decision_report(app, decision)
            print(report)
        else:
            print(f"  ⚠️  Evaluation failed for {app.borrower_name}")

    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()