"""Prompt loader utilities for reading and templating system prompts."""

from pathlib import Path
from typing import Any


def load_prompt(agent_name: str) -> str:
    """Load a prompt file from the `src/prompts` directory.

    Args:
        agent_name: Base name of the prompt file (without extension).

    Returns:
        The raw prompt text loaded from disk.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    prompts_dir = Path(__file__).parent.parent / "prompts"
    file_path = prompts_dir / f"{agent_name}.txt"

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file for '{agent_name}' not found at {file_path}")

    return file_path.read_text(encoding="utf-8")


def load_prompt_with_variables(agent_name: str, **kwargs: Any) -> str:
    """Load a prompt and substitute variables using Python format syntax.

    Variables in the prompt should appear as `{variable_name}`.  
    This is a simple templating mechanism; missing keys will raise `KeyError`.

    Args:
        agent_name: Base name of the prompt file (without extension).
        **kwargs: Values to substitute into the prompt.

    Returns:
        Prompt text with variables replaced.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
        KeyError: If the prompt contains placeholders not provided in `kwargs`.
    """
    template = load_prompt(agent_name)
    try:
        return template.format(**kwargs)
    except KeyError as e:
        missing = e.args[0]
        raise KeyError(f"Missing template variable: {missing}") from e
