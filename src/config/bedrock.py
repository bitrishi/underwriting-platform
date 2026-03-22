"""
Multi-model Bedrock client factory.

Routes tasks to the optimal model:
- Haiku: cheap, fast — routing, tool calling, grading
- Sonnet: expensive, smart — legal reasoning, compliance, vision
- Titan Embed: embeddings only

Changing which model handles which task is a CONFIG change, not a code change.
"""

from langchain_aws import ChatBedrock
from src.config.settings import settings


# ============================================================
# MODEL REGISTRY
# Add new models here as they become available on Bedrock
# ============================================================
MODELS = {
    "haiku": "anthropic.claude-3-haiku-20240307-v1:0",
    "sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "nova_micro": "amazon.nova-micro-v1:0",
    "nova_pro": "amazon.nova-pro-v1:0",
    # Future: add specialized models here
    # "legal_specialist": "some-vendor.legal-model-v1:0",
}


# ============================================================
# TASK-TO-MODEL MAPPING
# This is THE key architecture decision.
# Change one line here to swap models for any task.
# ============================================================
TASK_MODEL_MAP = {
    # Agent tasks
    "orchestrator": "haiku",             # routing decisions — needs tool calling
    "fetch_data": "haiku",               # data retrieval — needs tool calling
    "doc_review": "sonnet",              # vision + complex docs — worth paying more
    "risk_scoring": "haiku",             # calculations — structured output
    "compliance": "sonnet",              # legal interpretation — strongest reasoning

    # RAG tasks
    "retrieval_grading": "haiku",        # simple relevant/not — cheapest works
    "hallucination_check": "haiku",      # verification — doesn't need heavy reasoning
    "rag_generation": "haiku",           # routine policy lookups
    "rag_generation_critical": "sonnet", # critical compliance answers

    # Default fallback
    "default": "haiku",
}


def create_llm(
    task: str = "default",
    temperature: float = 0,
    max_tokens: int = 1024,
) -> ChatBedrock:
    """
    Create a Bedrock LLM client optimized for a specific task.

    Looks up the best model for the task in TASK_MODEL_MAP,
    then creates a ChatBedrock instance with that model.

    Args:
        task: Task name from TASK_MODEL_MAP (e.g., "compliance", "fetch_data")
              Can also be a model key from MODELS (e.g., "haiku", "sonnet")
        temperature: 0 for deterministic (default for all underwriting tasks)
        max_tokens: Maximum response tokens

    Returns:
        ChatBedrock instance configured for the task

    Examples:
        # Route by task (recommended):
        llm = create_llm(task="compliance")          # → Sonnet
        llm = create_llm(task="fetch_data")           # → Haiku
        llm = create_llm(task="retrieval_grading")    # → Haiku (cheapest)

        # Override with specific model:
        llm = create_llm(task="sonnet")               # → Sonnet directly
    """
    # Look up model for this task, fall back to default
    model_key = TASK_MODEL_MAP.get(task, task)
    model_id = MODELS.get(model_key, MODELS["haiku"])

    return ChatBedrock(
        model_id=model_id,
        region_name=settings.aws_region,
        model_kwargs={
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    )


def get_model_for_task(task: str) -> str:
    """
    Get the model name assigned to a task.
    Useful for logging and debugging.

    Args:
        task: Task name from TASK_MODEL_MAP

    Returns:
        Model key (e.g., "haiku", "sonnet")
    """
    return TASK_MODEL_MAP.get(task, TASK_MODEL_MAP["default"])