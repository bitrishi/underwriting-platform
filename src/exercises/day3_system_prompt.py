"""Day 3: System Prompt Exercise - Evaluate loan applications with structured prompts"""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.bedrock import create_llm


def load_system_prompt() -> str:
    """
    Load the underwriting system prompt from file.
    
    Returns:
        System prompt text
        
    Raises:
        FileNotFoundError: If prompt file not found
    """
    prompt_path = Path(__file__).parent.parent / "prompts" / "underwriter.txt"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, "r") as f:
        return f.read()


def create_application_message(
    borrower_name: str,
    fico_score: int,
    annual_income: float,
    monthly_debt: float,
    loan_amount: float,
    employment_status: str = "employed",
    docs_provided: list[str] | None = None,
) -> str:
    """
    Create a human message describing a loan application.
    
    Args:
        borrower_name: Applicant name
        fico_score: Credit score
        annual_income: Yearly income
        monthly_debt: Monthly debt obligations
        loan_amount: Requested loan amount
        employment_status: Employment situation
        docs_provided: List of documents provided
        
    Returns:
        Formatted application message
    """
    if docs_provided is None:
        docs_provided = ["Tax Returns (2 years)", "Pay Stubs (2 months)", "Bank Statements"]
    
    monthly_income = annual_income / 12
    dti = (monthly_debt / monthly_income) * 100 if monthly_income > 0 else 0
    
    message = f"""
Evaluate this loan application:

**Applicant:** {borrower_name}
**FICO Score:** {fico_score}
**Annual Income:** ${annual_income:,.2f}
**Monthly Income:** ${monthly_income:,.2f}
**Monthly Debt Obligations:** ${monthly_debt:,.2f}
**Debt-to-Income Ratio:** {dti:.2f}%
**Requested Loan Amount:** ${loan_amount:,.2f}
**Loan-to-Income Ratio:** {(loan_amount / annual_income):.2f}x
**Employment Status:** {employment_status}
**Documents Provided:** {", ".join(docs_provided)}

Provide your underwriting decision and assessment in the prescribed JSON format.
"""
    return message.strip()


def evaluate_application(
    borrower_name: str,
    fico_score: int,
    annual_income: float,
    monthly_debt: float,
    loan_amount: float,
    employment_status: str = "employed",
    docs_provided: list[str] | None = None,
) -> dict:
    """
    Evaluate a loan application using Claude and the system prompt.
    
    Args:
        borrower_name: Applicant name
        fico_score: Credit score
        annual_income: Yearly income
        monthly_debt: Monthly debt obligations
        loan_amount: Requested loan amount
        employment_status: Employment situation
        docs_provided: List of documents provided
        
    Returns:
        Parsed decision JSON from Claude
        
    Raises:
        json.JSONDecodeError: If response is not valid JSON
    """
    # Load system prompt
    system_prompt = load_system_prompt()
    
    # Create LLM client
    llm = create_llm(temperature=0, max_tokens=1024)
    
    # Create messages
    system_message = SystemMessage(content=system_prompt)
    human_message = HumanMessage(
        content=create_application_message(
            borrower_name=borrower_name,
            fico_score=fico_score,
            annual_income=annual_income,
            monthly_debt=monthly_debt,
            loan_amount=loan_amount,
            employment_status=employment_status,
            docs_provided=docs_provided,
        )
    )
    
    # Invoke LLM
    print(f"📋 Evaluating application for {borrower_name}...")
    response = llm.invoke([system_message, human_message])
    
    # Parse response
    response_text = response.content if hasattr(response, 'content') else str(response)
    
    # Clean up response if it has markdown code blocks
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    try:
        decision = json.loads(response_text)
        return decision
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse response as JSON: {e}")
        print(f"Response text:\n{response_text}")
        raise


def print_decision(decision: dict) -> None:
    """
    Pretty-print a loan decision.
    
    Args:
        decision: Decision dictionary from evaluate_application()
    """
    print(f"\n{'='*60}")
    print(f"Decision: {decision['decision']}")
    print(f"Confidence: {decision['confidence']:.1%}")
    print(f"Risk Level: {decision['risk_level']}")
    print(f"FICO Assessment: {decision['fico_assessment']}")
    print(f"DTI Assessment: {decision['dti_assessment']}")
    print(f"\nReasons:")
    for reason in decision['reasons']:
        print(f"  • {reason}")
    
    if decision.get('conditions'):
        print(f"\nConditions:")
        for condition in decision['conditions']:
            print(f"  • {condition}")
    
    if decision.get('regulatory_notes'):
        print(f"\nRegulatory Notes: {decision['regulatory_notes']}")
    print(f"{'='*60}")


def main() -> None:
    """Run the system prompt exercise."""
    print("\n🚀 Day 3: System Prompt Exercise")
    print("Loading underwriting system prompt and evaluating sample applications...")
    
    # Sample applications to evaluate
    applications = [
        {
            "name": "Alice Johnson",
            "fico": 750,
            "income": 120000,
            "monthly_debt": 2000,
            "loan_amount": 300000,
            "employment": "employed",
            "docs": ["Tax Returns (2 years)", "Pay Stubs (2 months)", "Bank Statements (2 months)", "W-2s"],
        },
        {
            "name": "Bob Smith",
            "fico": 680,
            "income": 100000,
            "monthly_debt": 3500,
            "loan_amount": 400000,
            "employment": "employed",
            "docs": ["Tax Returns (1 year)", "Pay Stubs"],
        },
        {
            "name": "Carol Davis",
            "fico": 650,
            "income": 90000,
            "monthly_debt": 3000,
            "loan_amount": 250000,
            "employment": "self-employed",
            "docs": ["Business Tax Returns"],
        },
    ]
    
    # Evaluate each application
    for app in applications:
        try:
            decision = evaluate_application(
                borrower_name=app["name"],
                fico_score=app["fico"],
                annual_income=app["income"],
                monthly_debt=app["monthly_debt"],
                loan_amount=app["loan_amount"],
                employment_status=app["employment"],
                docs_provided=app["docs"],
            )
            print_decision(decision)
        except Exception as e:
            print(f"❌ Error evaluating {app['name']}: {e}")
            print("\nTroubleshooting:")
            print("  • Check AWS credentials and Bedrock access")
            print("  • Verify .env file has valid AWS_REGION and BEDROCK_MODEL_ID")
            print("  • Ensure src/prompts/underwriter.txt exists")
            return


if __name__ == "__main__":
    main()
