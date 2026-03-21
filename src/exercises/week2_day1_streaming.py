import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
from src.chains.underwriter_chain_v2 import underwriter_chain_v2
from src.models.application import LoanApplication


async def test_streaming():
    """Test streaming with the LCEL chain."""

    print("Starting streaming test...")

    # Create a test application
    app = LoanApplication(
        borrower_name="John Doe",
        loan_amount=250000,
        fico_score=720,
        monthly_debt=2500,
        annual_income=85000,
        property_value=300000,
        employment_years=3
    )

    print("Testing LCEL Chain Streaming:")
    print("=" * 50)
    print(f"Application: {app.borrower_name}")
    print(f"FICO Score: {app.fico_score}")
    print(f"Loan Amount: ${app.loan_amount:,.0f}")
    print()

    # Note: The LCEL chain uses structured output, so streaming works differently
    # For structured output, we get the final result, not token-by-token text
    print("Note: This chain uses structured output (Pydantic model)")
    print("Streaming will show the final parsed result, not raw tokens")
    print()

    try:
        # Use stream() - for structured output, this may return the final object
        async for chunk in underwriter_chain_v2.stream(app.to_prompt_string()):
            print(f"Chunk received: {chunk}")
            if hasattr(chunk, 'decision'):
                print(f"Decision: {chunk.decision}")
                print(f"Confidence: {chunk.confidence}")
                break  # Only expect one chunk for structured output

    except Exception as e:
        print(f"Streaming failed: {e}")
        print("Falling back to regular invoke...")

        # Fallback to regular invoke
        result = underwriter_chain_v2(app.to_prompt_string())
        print(f"Regular invoke result: {result}")
        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence}")

    print("\n" + "=" * 50)


def compare_to_manual_streaming():
    """Compare LCEL streaming to manual streaming approach."""

    print("\n" + "=" * 60)
    print("COMPARISON: LCEL Streaming vs Manual Streaming")
    print("=" * 60)

    print("LCEL Streaming (Current Implementation):")
    print("✓ Automatic token-by-token streaming via chain.stream()")
    print("✓ Built-in async iteration support")
    print("✓ Handles all chain components (prompt, LLM, parser) seamlessly")
    print("✓ No manual implementation required")
    print("✓ Consistent with LangChain ecosystem")
    print()

    print("Manual Streaming (Previous Approach):")
    print("• Would require custom implementation of streaming")
    print("• Need to handle LLM streaming callbacks manually")
    print("• More complex error handling and state management")
    print("• Less maintainable and more prone to bugs")
    print("• Requires understanding of underlying LLM API streaming")
    print()

    print("Key Advantages of LCEL Streaming:")
    print("• Declarative: Define the chain, streaming 'just works'")
    print("• Composable: Streaming works with any chain composition")
    print("• Robust: Automatic error handling and cleanup")
    print("• Future-proof: Updates with LangChain improvements")


if __name__ == "__main__":
    # Run the streaming test
    asyncio.run(test_streaming())

    # Show comparison
    compare_to_manual_streaming()