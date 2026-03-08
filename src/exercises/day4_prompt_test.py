"""Day 4: Prompt Testing Exercise — Validate prompts against real Bedrock responses."""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.bedrock import create_llm
from src.utils.prompt_loader import load_prompt


def create_application_prompt(
    borrower_name: str,
    fico_score: int,
    annual_income: float,
    monthly_debt: float,
    loan_amount: float,
) -> str:
    """Create a formatted application prompt for the underwriter."""
    monthly_income = annual_income / 12
    dti = (monthly_debt / monthly_income * 100) if monthly_income > 0 else 0

    return f"""
Borrower: {borrower_name}
FICO Score: {fico_score}
Annual Income: ${annual_income:,.0f}
Monthly Income: ${monthly_income:,.0f}
Monthly Debt: ${monthly_debt:,.0f}
Debt-to-Income Ratio: {dti:.2f}%
Requested Loan Amount: ${loan_amount:,.0f}
Loan-to-Income Ratio: {loan_amount / annual_income:.2f}x
Employment Status: Employed
Documents Provided: Tax Returns (2 yrs), Pay Stubs (2 mo), Bank Statements (2 mo)

Evaluate and provide your underwriting decision.
""".strip()


def validate_response_schema(response_text: str) -> dict:
    """Parse and validate response matches expected schema."""
    # Clean markdown if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    response_json = json.loads(response_text)

    # Validate required fields
    required_fields = {"decision", "confidence", "risk_level", "reasons"}
    missing_fields = required_fields - set(response_json.keys())

    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    # Validate field types
    assert isinstance(response_json["decision"], str)
    assert response_json["decision"] in ["APPROVED", "CONDITIONAL_APPROVAL", "DECLINE"]
    assert isinstance(response_json["confidence"], (int, float))
    assert 0.0 <= response_json["confidence"] <= 1.0
    assert isinstance(response_json["risk_level"], str)
    assert response_json["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert isinstance(response_json["reasons"], list)

    return response_json


def extract_reasoning_trace(response_text: str) -> str | None:
    """Extract reasoning trace from response if present."""
    # Look for reasoning_trace field in JSON
    try:
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_text = response_text

        response_json = json.loads(json_text)
        return response_json.get("reasoning_trace")
    except (json.JSONDecodeError, KeyError):
        return None


def print_test_result(
    app_name: str,
    response: dict,
    response_text: str = "",
    expected_decision: str | None = None,
) -> None:
    """Pretty-print test result including full response text."""
    print(f"\n{'─' * 70}")
    print(f"Application: {app_name}")
    print(f"{'─' * 70}")
    print(f"Decision: {response['decision']}")
    print(f"Confidence: {response['confidence']:.0%}")
    print(f"Risk Level: {response['risk_level']}")
    print(f"\nReasons:")
    for reason in response["reasons"]:
        print(f"  • {reason}")

    if response.get("conditions"):
        print(f"\nConditions:")
        for condition in response["conditions"]:
            print(f"  • {condition}")

    # Print reasoning trace if available
    reasoning_trace = extract_reasoning_trace(response_text)
    if reasoning_trace:
        print(f"\n📝 Reasoning Trace:")
        print(f"{'─' * 70}")
        if isinstance(reasoning_trace, list):
            for i, step in enumerate(reasoning_trace, 1):
                print(f"  {i}. {step}")
        else:
            print(f"  {reasoning_trace}")

    # Print full response for inspection
    print(f"\n📋 Full JSON Response:")
    print(f"{'─' * 70}")
    print(json.dumps(response, indent=2))

    if expected_decision:
        match = "✅" if response["decision"] == expected_decision else "❌"
        print(f"\nExpected: {expected_decision} {match}")


def main() -> None:
    """Run prompt validation tests."""

    print("\n" + "=" * 70)
    print("🧪 Day 4: Prompt Testing Exercise")
    print("=" * 70)
    print("\nTesting 3 applications with the production Underwriter prompt")
    print("Expected outcomes: APPROVE, DENY, CONDITIONAL")

    # Load the underwriter prompt
    print("\n📋 Loading prompts...")
    try:
        underwriter_prompt = load_prompt("underwriter")
        print("✅ Underwriter prompt loaded")
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return

    # Initialize LLM
    llm = create_llm(temperature=0, max_tokens=1024)

    # Test applications
    test_cases = [
        {
            "name": "Alice (Clear Approve)",
            "fico": 760,
            "income": 120000,
            "debt": 2000,
            "loan": 250000,
            "expected": "APPROVED",
        },
        {
            "name": "Bob (Clear Deny)",
            "fico": 640,
            "income": 80000,
            "debt": 3500,
            "loan": 400000,
            "expected": "DECLINE",
        },
        {
            "name": "Carol (Borderline)",
            "fico": 690,
            "income": 100000,
            "debt": 3600,
            "loan": 320000,
            "expected": "CONDITIONAL_APPROVAL",
        },
    ]

    results = []

    # ========================================================================
    # TEST EACH APPLICATION
    # ========================================================================
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST {i}: {test_case['name']}")
        print(f"{'='*70}")

        try:
            # Create messages
            system_msg = SystemMessage(content=underwriter_prompt)
            app_prompt = create_application_prompt(
                borrower_name=test_case["name"].split("(")[0].strip(),
                fico_score=test_case["fico"],
                annual_income=test_case["income"],
                monthly_debt=test_case["debt"],
                loan_amount=test_case["loan"],
            )
            human_msg = HumanMessage(content=app_prompt)

            # Call LLM
            print(f"⏳ Invoking Bedrock...")
            response = llm.invoke([system_msg, human_msg])
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            # Validate schema
            try:
                response_json = validate_response_schema(response_text)
                print_test_result(
                    test_case["name"],
                    response_json,
                    response_text=response_text,
                    expected_decision=test_case["expected"],
                )
                results.append(
                    {
                        "name": test_case["name"],
                        "decision": response_json["decision"],
                        "expected": test_case["expected"],
                        "match": response_json["decision"] == test_case["expected"],
                    }
                )
            except (json.JSONDecodeError, ValueError, AssertionError) as e:
                print(f"❌ Schema validation failed: {e}")
                print(f"Raw Response:\n{response_text}")
                results.append(
                    {
                        "name": test_case["name"],
                        "decision": "ERROR",
                        "expected": test_case["expected"],
                        "match": False,
                    }
                )

        except Exception as e:
            print(f"❌ Error: {e}")
            results.append(
                {
                    "name": test_case["name"],
                    "decision": "ERROR",
                    "expected": test_case["expected"],
                    "match": False,
                }
            )

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print(f"\n{'='*70}")
    print("📊 TEST SUMMARY")
    print(f"{'='*70}")

    passed = sum(1 for r in results if r["match"])
    total = len(results)

    for result in results:
        status = "✅ PASS" if result["match"] else "❌ FAIL"
        print(f"{status} | {result['name']}: {result['decision']} (expected {result['expected']})")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 All tests passed! Prompts are production-ready.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review prompt output and schema.")

    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
