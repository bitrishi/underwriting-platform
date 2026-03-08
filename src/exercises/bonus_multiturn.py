"""
Bonus: Multi-Turn Conversation Exercise
================================================================================

WHAT IS THIS?
A multi-turn conversation maintains context across multiple exchanges.
Instead of forgetting each question, the LLM remembers the full history.

SINGLE-TURN (what we've been doing):
  System: "You are an underwriter"
  Human: "Evaluate this loan"
  AI: "APPROVED"
  [Context lost - next conversation starts fresh]

MULTI-TURN (this exercise):
  System: "You are an underwriter"
  
  Turn 1:
    Human: "What matters in underwriting?"
    AI: "FICO, DTI, income..."
  
  Turn 2:
    Human: "What if FICO is 680?"
    AI: "680 is borderline..." [LLM remembers Turn 1 context]
  
  Turn 3:
    Human: "And DTI is 42%?"
    AI: "With 680 FICO and 42% DTI..." [LLM remembers turns 1-2]

THE KEY: Messages list grows with each turn. Each invoke sends full history.

================================================================================
"""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.config.bedrock import create_llm


def load_system_prompt() -> str:
    """Load the underwriting system prompt."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "underwriter.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    with open(prompt_path, "r") as f:
        return f.read()


def print_message(role: str, content: str, turn: int | None = None) -> None:
    """Pretty print a message in the conversation."""
    prefix = f"Turn {turn} | " if turn else ""
    
    if role == "System":
        print(f"\n🔧 {prefix}System:")
        print(f"   {content[:100]}..." if len(content) > 100 else f"   {content}")
    elif role == "Human":
        print(f"\n👤 {prefix}Human:")
        print(f"   {content}")
    elif role == "AI":
        print(f"\n🤖 {prefix}AI:")
        print(f"   {content}")
    elif role == "Context":
        print(f"\n📊 {prefix}{content}")


def main() -> None:
    """Run a multi-turn conversation about loan underwriting."""
    
    print("\n" + "=" * 80)
    print("💬 MULTI-TURN CONVERSATION EXERCISE")
    print("=" * 80)
    print("\nDemonstrating: How context is maintained across multiple turns")
    print("Watch how the LLM remembers previous answers in follow-up questions.")
    
    # Initialize LLM
    llm = create_llm(temperature=0, max_tokens=1024)
    
    # Load system prompt
    system_content = load_system_prompt()
    
    # Initialize message history with system prompt
    messages = [SystemMessage(content=system_content)]
    print_message("System", "Loaded underwriting agent system prompt")
    
    # ========================================================================
    # TURN 1: Ask about underwriting factors
    # ========================================================================
    print("\n" + "=" * 80)
    print("TURN 1: General question about underwriting factors")
    print("=" * 80)
    
    turn1_question = (
        "What are the main factors you consider when evaluating a mortgage application? "
        "Just list the factors briefly without evaluating a specific application."
    )
    
    messages.append(HumanMessage(content=turn1_question))
    print_message("Human", turn1_question, turn=1)
    
    print("\n⏳ Calling LLM (Turn 1)...")
    print(f"   Messages in history: System + Human = 2 messages")
    response1 = llm.invoke(messages)
    turn1_answer = response1.content if hasattr(response1, 'content') else str(response1)
    
    # Clean markdown if present
    if "```" in turn1_answer:
        turn1_answer = turn1_answer.split("```")[1].split("```")[0].strip()
    
    messages.append(AIMessage(content=turn1_answer))
    print_message("AI", turn1_answer, turn=1)
    
    # ========================================================================
    # TURN 2: Ask about a specific FICO scenario
    # ========================================================================
    print("\n" + "=" * 80)
    print("TURN 2: Follow-up about a borderline FICO scenario")
    print("=" * 80)
    print("📌 Context: LLM should remember factors from Turn 1")
    
    turn2_question = (
        "Now suppose I have an applicant with a FICO score of exactly 680. "
        "Based on our discussion, how would you assess this? "
        "What additional factors would be important?"
    )
    
    messages.append(HumanMessage(content=turn2_question))
    print_message("Human", turn2_question, turn=2)
    
    print("\n⏳ Calling LLM (Turn 2)...")
    print(f"   Messages in history: System + Human + AI + Human = 4 messages")
    print(f"   ✅ LLM has Turn 1 context when answering Turn 2")
    response2 = llm.invoke(messages)
    turn2_answer = response2.content if hasattr(response2, 'content') else str(response2)
    
    if "```" in turn2_answer:
        turn2_answer = turn2_answer.split("```")[1].split("```")[0].strip()
    
    messages.append(AIMessage(content=turn2_answer))
    print_message("AI", turn2_answer, turn=2)
    
    # ========================================================================
    # TURN 3: Add DTI dimension
    # ========================================================================
    print("\n" + "=" * 80)
    print("TURN 3: Add DTI dimension to the scenario")
    print("=" * 80)
    print("📌 Context: LLM should remember BOTH FICO discussion AND factors from Turn 1")
    
    turn3_question = (
        "What if that same applicant (680 FICO) also has a DTI of 42%? "
        "How does that change your assessment? Would you approve or decline?"
    )
    
    messages.append(HumanMessage(content=turn3_question))
    print_message("Human", turn3_question, turn=3)
    
    print("\n⏳ Calling LLM (Turn 3)...")
    print(f"   Messages in history: System + 3 Human + 2 AI = 6 messages")
    print(f"   ✅ LLM has Turns 1 AND 2 context when answering Turn 3")
    response3 = llm.invoke(messages)
    turn3_answer = response3.content if hasattr(response3, 'content') else str(response3)
    
    if "```" in turn3_answer:
        turn3_answer = turn3_answer.split("```")[1].split("```")[0].strip()
    
    messages.append(AIMessage(content=turn3_answer))
    print_message("AI", turn3_answer, turn=3)
    
    # ========================================================================
    # TURN 4: Drill deeper
    # ========================================================================
    print("\n" + "=" * 80)
    print("TURN 4: Clarify on conditions")
    print("=" * 80)
    print("📌 Context: LLM should remember 680 FICO, 42% DTI, and prior reasoning")
    
    turn4_question = (
        "You mentioned conditions or additional review. "
        "What specific documentation would you want to see from this applicant "
        "to make a final decision?"
    )
    
    messages.append(HumanMessage(content=turn4_question))
    print_message("Human", turn4_question, turn=4)
    
    print("\n⏳ Calling LLM (Turn 4)...")
    print(f"   Messages in history: System + 4 Human + 3 AI = 8 messages")
    print(f"   ✅ LLM has ALL previous context (Turns 1-3)")
    response4 = llm.invoke(messages)
    turn4_answer = response4.content if hasattr(response4, 'content') else str(response4)
    
    if "```" in turn4_answer:
        turn4_answer = turn4_answer.split("```")[1].split("```")[0].strip()
    
    messages.append(AIMessage(content=turn4_answer))
    print_message("AI", turn4_answer, turn=4)
    
    # ========================================================================
    # ANALYSIS
    # ========================================================================
    print("\n" + "=" * 80)
    print("ANALYSIS: How Context Persists")
    print("=" * 80)
    
    print(f"\n📈 Message History Growth:")
    print(f"   Turn 1: 2 messages total (System + Human)")
    print(f"   Turn 2: 4 messages total (above + AI + Human)")
    print(f"   Turn 3: 6 messages total (above + AI + Human)")
    print(f"   Turn 4: 8 messages total (above + AI + Human)")
    
    print(f"\n✅ Context Window:")
    print(f"   Each LLM call receives the FULL conversation history")
    print(f"   Claude reads all messages before generating response")
    print(f"   Earlier answers inform later responses")
    
    print(f"\n🎯 Key Insight:")
    print(f"   - Turn 1 established underwriting factors")
    print(f"   - Turn 2 built on those factors with FICO scenario")
    print(f"   - Turn 3 added DTI dimension (LLM remembered both factors)")
    print(f"   - Turn 4 asked follow-up (LLM remembered 680 FICO + 42% DTI)")
    
    print(f"\n💡 Why This Matters for Agents:")
    print(f"   ✓ Natural conversation flow")
    print(f"   ✓ Refinement across turns (ask follow-ups, collect details)")
    print(f"   ✓ Complex reasoning (build on previous answers)")
    print(f"   ✓ Interactive evaluation (back-and-forth with human)")
    
    print(f"\n⚠️  Cost Consideration:")
    print(f"   Multi-turn costs more (each turn sends full history)")
    print(f"   For Turn 4: Bedrock charges for all 8 messages")
    print(f"   Trade-off: Richer context vs. API cost")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
