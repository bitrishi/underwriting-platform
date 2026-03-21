# src/chains/underwriter_chain.py

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError

from src.config.bedrock import create_llm
from src.models.application import LoanApplication
from src.models.decision import LoanDecision
from src.utils.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class UnderwriterChain:
    """
    Production-grade underwriting evaluation chain.

    Combines:
    - System prompt loaded from src/prompts/underwriter.txt
    - Bedrock LLM with temperature=0 (deterministic)
    - Pydantic validation on output
    - Fallback parsing for models without function calling

    Java equivalent: A @Service class with @Autowired dependencies
    that processes a request and returns a typed response.
    """

    def __init__(self):
        """Initialize chain with LLM, prompt, and structured output."""
        self.llm = create_llm(temperature=0)
        self.system_prompt = load_prompt("underwriter")
        logger.info("UnderwriterChain initialized")

    def evaluate(self, application: LoanApplication) -> LoanDecision:
        """
        Evaluate a loan application and return a typed decision.

        Args:
            application: Validated LoanApplication with borrower data

        Returns:
            LoanDecision with decision, confidence, reasoning trace

        Raises:
            ValidationError: If LLM output doesn't match schema
            Exception: If Bedrock API call fails
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=application.to_prompt_string()),
        ]

        # Try structured output first
        try:
            structured_llm = self.llm.with_structured_output(
                LoanDecision,
                method="json_mode"
            )
            result = structured_llm.invoke(messages)
            logger.info(
                f"Evaluation complete: {result.decision} "
                f"(confidence: {result.confidence})"
            )
            return result

        except Exception as e:
            logger.warning(f"Structured output failed, using fallback: {e}")
            return self._fallback_parse(messages)

    def _fallback_parse(self, messages) -> LoanDecision:
        """
        Fallback: invoke raw LLM, parse JSON, validate with Pydantic.

        Used when with_structured_output doesn't work
        (e.g., Nova Micro without function calling support).
        """
        response = self.llm.invoke(messages)
        raw_text = response.content

        # Strip markdown code fences if present
        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("\n", 1)[1]
        if clean_text.endswith("```"):
            clean_text = clean_text.rsplit("```", 1)[0]
        clean_text = clean_text.strip()

        # Parse JSON and validate with Pydantic
        data = json.loads(clean_text)
        result = LoanDecision.model_validate(data)

        logger.info(
            f"Fallback evaluation complete: {result.decision} "
            f"(confidence: {result.confidence})"
        )
        return result

    def evaluate_safe(self, application: LoanApplication) -> LoanDecision | None:
        """
        Safe evaluation with full error handling.

        Returns None on failure instead of raising.
        Logs all errors for debugging.
        """
        try:
            return self.evaluate(application)
        except ValidationError as e:
            logger.error(f"Output validation failed: {e.errors()}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return None
        

    # In src/chains/underwriter_chain.py, add:

def evaluate_streaming(self, application: LoanApplication) -> LoanDecision:
    """
    Evaluate with real-time streaming output.

    Shows the LLM's response token-by-token as it generates,
    then parses the complete response into a LoanDecision.
    """
    messages = [
        SystemMessage(content=self.system_prompt),
        HumanMessage(content=application.to_prompt_string()),
    ]

    # Collect full response while streaming to console
    full_response = ""
    print("\n🤔 Agent thinking...\n")

    for chunk in self.llm.stream(messages):
        token = chunk.content
        print(token, end="", flush=True)
        full_response += token

    print("\n\n✅ Response complete. Validating...\n")

    # Parse and validate the complete response
    clean = full_response.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1]
    if clean.endswith("```"):
        clean = clean.rsplit("```", 1)[0]

    data = json.loads(clean.strip())
    return LoanDecision.model_validate(data)    