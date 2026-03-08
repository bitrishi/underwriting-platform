"""Decorators for tool operations."""

import functools
from typing import Any, Callable, Type

from pydantic import BaseModel, ValidationError


def validate_input(model: Type[BaseModel]) -> Callable:
    """
    Decorator factory that validates the first function argument against a Pydantic model.
    
    Raises ValueError with detailed validation errors if input is invalid.
    
    Usage:
        @validate_input(CreditCheckInput)
        def check_credit(input_data: CreditCheckInput) -> dict:
            return {"status": "approved"}
    
    Args:
        model: Pydantic BaseModel class to validate against
        
    Returns:
        Decorator function that validates and wraps the function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if function has at least one argument
            if not args:
                raise ValueError(
                    f"Function '{func.__name__}' requires at least one argument to validate"
                )
            
            first_arg = args[0]
            
            try:
                # If it's a dict, validate by constructing the model
                if isinstance(first_arg, dict):
                    model.model_validate(first_arg)
                # If it's already an instance of the model, skip validation
                elif isinstance(first_arg, model):
                    pass
                # Try to validate it as-is (will fail with clear message)
                else:
                    model.model_validate(first_arg)
                    
            except ValidationError as e:
                # Build a clear error message from Pydantic's validation errors
                error_details = "; ".join(
                    f"{error['loc'][0]}: {error['msg']}" 
                    for error in e.errors()
                )
                raise ValueError(
                    f"Invalid input for '{func.__name__}': {error_details}"
                )
            except Exception as e:
                raise ValueError(
                    f"Validation error in '{func.__name__}': {str(e)}"
                )
            
            # Call the original function
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
