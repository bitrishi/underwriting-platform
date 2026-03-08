"""Day 3: First LLM Call Exercise - Simple Bedrock interaction"""

from src.config.bedrock import create_llm


def main() -> None:
    """Make a simple call to Claude via Bedrock."""
    print("🚀 Day 3: First LLM Call")
    print("=" * 60)
    
    # Create LLM client
    print("\n📝 Initializing Bedrock LLM client...")
    try:
        llm = create_llm(temperature=0, max_tokens=1024)
        print("✅ LLM client created successfully")
    except Exception as e:
        print(f"❌ Failed to create LLM client: {e}")
        print("\n💡 Make sure you have:")
        print("   1. AWS credentials configured (via ~/.aws/credentials or AWS_PROFILE)")
        print("   2. AWS_REGION and BEDROCK_MODEL_ID set in .env")
        print("   3. Access to Claude on Bedrock in your AWS region")
        return
    
    # Make a simple call
    question = "What are the key factors in mortgage underwriting?"
    
    print(f"\n❓ Question: {question}")
    print("-" * 60)
    
    try:
        print("\n⏳ Calling Claude...")
        response = llm.invoke(question)
        
        # response is an AIMessage object; get the text content
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        print("\n✅ Response received:")
        print("-" * 60)
        print(response_text)
        print("-" * 60)
        
    except Exception as e:
        print(f"\n❌ Error calling LLM: {e}")
        print("\nTroubleshooting:")
        print("  • Check AWS credentials: aws sts get-caller-identity")
        print("  • Check Bedrock model: aws bedrock list-foundation-models --region us-east-1")
        print("  • Enable Claude model in your region if needed")


if __name__ == "__main__":
    main()
