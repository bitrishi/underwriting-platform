"""
Day 3: Temperature Experiment
================================================================================

OBSERVATIONS:
- temperature=0: Deterministic. Same prompt → identical response every time.
  Used for: loan underwriting, compliance checks, regulatory decisions.
  Why: Need consistency and reproducibility. Can't have different decisions
  for the same application data.

- temperature=0.7: Creative/Variable. Same prompt → different responses.
  Some vary word choice, some vary decision confidence, some vary reasons.
  Used for: brainstorming, exploratory analysis, discussion generation.
  Why: Adds variety for human review. But DANGEROUS for lending decisions.

KEY INSIGHT:
For agents making financial decisions, always use temperature=0 or very low.
For agents doing analysis/writing, temperature=0.5-0.7 is fine.
Never use high temperature (>0.8) for deterministic tasks like underwriting.

================================================================================
"""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.bedrock import create_llm


def load_system_prompt() -> str:
    """Load the underwriting system prompt from file."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "underwriter.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, "r") as f:
        return f.read()


def create_test_application() -> str:
    """Create a single test loan application for temperature comparison."""
    return """
Evaluate this loan application:

**Applicant:** Michael Chen
**FICO Score:** 720
**Annual Income:** $125,000
**Monthly Income:** $10,416.67
**Monthly Debt Obligations:** $3,500
**Debt-to-Income Ratio:** 33.60%
**Requested Loan Amount:** $350,000
**Loan-to-Income Ratio:** 2.80x
**Employment Status:** employed
**Documents Provided:** Tax Returns (2 years), Pay Stubs (2 months), Bank Statements (2 months), W-2s

Provide your underwriting decision and assessment in the prescribed JSON format.
""".strip()


def evaluate_with_temperature(temperature: float, attempt_num: int) -> dict:
    """
    Evaluate the same application with specified temperature.
    
    Args:
        temperature: Temperature setting (0-1)
        attempt_num: Attempt number for labeling
        
    Returns:
        Parsed decision JSON
    """
    system_prompt = load_system_prompt()
    llm = create_llm(temperature=temperature, max_tokens=1024)
    
    system_message = SystemMessage(content=system_prompt)
    human_message = HumanMessage(content=create_test_application())
    
    print(f"  Attempt {attempt_num}...", end=" ", flush=True)
    response = llm.invoke([system_message, human_message])
    print("✓")
    
    response_text = response.content if hasattr(response, 'content') else str(response)
    
    # Clean up markdown blocks
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    return json.loads(response_text)


def print_response(decision: dict, temp: float, attempt: int) -> None:
    """Pretty-print a single response."""
    print(f"\n{'─' * 70}")
    print(f"Temperature: {temp} | Attempt: {attempt}")
    print(f"{'─' * 70}")
    print(f"Decision: {decision['decision']}")
    print(f"Confidence: {decision['confidence']:.1%}")
    print(f"Risk Level: {decision['risk_level']}")
    print(f"FICO Assessment: {decision['fico_assessment']}")
    print(f"DTI Assessment: {decision['dti_assessment']}")
    print(f"Reasons:")
    for reason in decision['reasons']:
        print(f"  • {reason}")


def main() -> None:
    """Run temperature comparison experiment."""
    print("\n" + "=" * 70)
    print("🌡️  Temperature Experiment: Deterministic vs Creative")
    print("=" * 70)
    
    print("\nTest Application: Michael Chen")
    print("  FICO: 720 | Income: $125,000 | Debt: $3,500/mo | DTI: 33.6%")
    
    responses_0 = []
    responses_07 = []
    
    # Temperature 0 (deterministic)
    print("\n" + "=" * 70)
    print("PHASE 1: Temperature = 0 (Deterministic)")
    print("=" * 70)
    print("Running 3 evaluations with temperature=0...")
    
    for i in range(1, 4):
        try:
            decision = evaluate_with_temperature(temperature=0.0, attempt_num=i)
            responses_0.append(decision)
            print_response(decision, 0.0, i)
        except Exception as e:
            print(f"❌ Error: {e}")
            return
    
    # Temperature 0.7 (creative)
    print("\n" + "=" * 70)
    print("PHASE 2: Temperature = 0.7 (Creative/Variable)")
    print("=" * 70)
    print("Running 3 evaluations with temperature=0.7...")
    
    for i in range(1, 4):
        try:
            decision = evaluate_with_temperature(temperature=0.7, attempt_num=i)
            responses_07.append(decision)
            print_response(decision, 0.7, i)
        except Exception as e:
            print(f"❌ Error: {e}")
            return
    
    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    
    # Check consistency of temp 0
    print("\n📊 Temperature = 0 Consistency:")
    decisions_0 = [r['decision'] for r in responses_0]
    confidences_0 = [r['confidence'] for r in responses_0]
    risk_levels_0 = [r['risk_level'] for r in responses_0]
    
    print(f"  Decisions: {decisions_0[0]}, {decisions_0[1]}, {decisions_0[2]}")
    all_same = len(set(decisions_0)) == 1
    print(f"  All identical: {'✅ YES' if all_same else '❌ NO'}")
    
    print(f"  Confidence levels: {confidences_0}")
    print(f"  Risk levels: {risk_levels_0}")
    
    # Check variability of temp 0.7
    print("\n📊 Temperature = 0.7 Variability:")
    decisions_07 = [r['decision'] for r in responses_07]
    confidences_07 = [r['confidence'] for r in responses_07]
    risk_levels_07 = [r['risk_level'] for r in responses_07]
    
    print(f"  Decisions: {decisions_07[0]}, {decisions_07[1]}, {decisions_07[2]}")
    unique_decisions = len(set(decisions_07))
    print(f"  Unique decisions: {unique_decisions} (vary: {'✅ YES' if unique_decisions > 1 else 'No variation'})")
    
    print(f"  Confidence levels: {confidences_07}")
    conf_variance = max(confidences_07) - min(confidences_07)
    print(f"  Confidence variance: {conf_variance:.1%}")
    
    print(f"  Risk levels: {risk_levels_07}")
    
    # Key insight
    print("\n" + "=" * 70)
    print("KEY FINDINGS")
    print("=" * 70)
    print(f"✅ Temperature 0: Highly deterministic (all decisions: {decisions_0[0]})")
    print(f"   → Best for: Loan decisions, compliance checks, regulatory tasks")
    print(f"\n⚠️  Temperature 0.7: Variable (variance in responses)")
    print(f"   → Risk: Different decisions for same application!")
    print(f"   → Use only for: Brainstorming, exploratory analysis")
    print(f"\n💡 For lending: ALWAYS use temperature=0")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
