"""Utility decorators for logging and monitoring."""

import functools
import logging
from typing import Any, Callable

# Configure logger
logger = logging.getLogger(__name__)


def log_call(func: Callable) -> Callable:
    """
    Decorator that logs function calls, arguments, return values, and exceptions.
    
    Args:
        func: The function to wrap
        
    Returns:
        Wrapped function with logging
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = func.__name__
        logger.info(f"Calling {func_name} with args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.info(f"{func_name} returned {result}")
            return result
        except Exception as e:
            logger.error(f"{func_name} raised {type(e).__name__}: {e}")
            raise
    
    return wrapper
