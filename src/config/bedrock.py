# src/config/bedrock.py

from langchain_aws import ChatBedrock
from src.config.settings import settings

def create_llm(
    temperature: float = 0,
    max_tokens: int = 1024
) -> ChatBedrock:
    """
    Create a Bedrock LLM client.
    
    Uses settings from .env file.
    Temperature 0 for deterministic underwriting decisions.
    
    Returns:
        ChatBedrock instance ready to invoke
    """
    return ChatBedrock(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_region,
        model_kwargs={
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
    )

# Usage anywhere in your project:
# from src.config.bedrock import create_llm
# llm = create_llm()
# response = llm.invoke("Evaluate this loan...")