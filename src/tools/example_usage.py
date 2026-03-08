"""Example usage of the @validate_input decorator."""

from src.tools.decorators import validate_input
from src.tools.inputs import CreditCheckInput, DataFetchInput


@validate_input(CreditCheckInput)
def check_credit(input_data: CreditCheckInput) -> dict:
    """
    Perform a credit check on a borrower.
    Input is automatically validated against CreditCheckInput model.
    
    Args:
        input_data: Validated CreditCheckInput
        
    Returns:
        Dictionary with credit check results
    """
    return {
        "borrower_id": input_data.borrower_id,
        "fico_score": input_data.fico_score,
        "check_type": input_data.check_type,
        "status": "completed",
        "result": "approved" if input_data.fico_score >= 700 else "needs_review"
    }


@validate_input(DataFetchInput)
def fetch_borrower_data(input_data: DataFetchInput) -> dict:
    """
    Fetch data for a borrower.
    Input is automatically validated against DataFetchInput model.
    
    Args:
        input_data: Validated DataFetchInput
        
    Returns:
        Dictionary with fetched data
    """
    return {
        "borrower_id": input_data.borrower_id,
        "data_types_fetched": input_data.data_types,
        "status": "success",
        "records_count": len(input_data.data_types)
    }


if __name__ == "__main__":
    # Example 1: Valid input as dict
    print("Example 1: Valid input as dict")
    try:
        result = check_credit({
            "borrower_id": "B12345",
            "fico_score": 750,
            "check_type": "detailed"
        })
        print(f"✅ Result: {result}\n")
    except ValueError as e:
        print(f"❌ Error: {e}\n")
    
    # Example 2: Valid input as model instance
    print("Example 2: Valid input as model instance")
    try:
        input_obj = CreditCheckInput(
            borrower_id="B67890",
            fico_score=680,
            check_type="basic"
        )
        result = check_credit(input_obj)
        print(f"✅ Result: {result}\n")
    except ValueError as e:
        print(f"❌ Error: {e}\n")
    
    # Example 3: Invalid input (FICO score too low)
    print("Example 3: Invalid input (FICO score out of range)")
    try:
        result = check_credit({
            "borrower_id": "B99999",
            "fico_score": 200,  # Invalid: must be 300-850
            "check_type": "full"
        })
        print(f"✅ Result: {result}\n")
    except ValueError as e:
        print(f"❌ Error: {e}\n")
    
    # Example 4: Invalid input (missing required field)
    print("Example 4: Invalid input (missing required field)")
    try:
        result = check_credit({
            "borrower_id": "B11111",
            # Missing "fico_score" - required field
        })
        print(f"✅ Result: {result}\n")
    except ValueError as e:
        print(f"❌ Error: {e}\n")
    
    # Example 5: DataFetchInput example
    print("Example 5: DataFetchInput with valid data")
    try:
        result = fetch_borrower_data({
            "borrower_id": "B22222",
            "data_types": ["credit", "employment", "income"]
        })
        print(f"✅ Result: {result}\n")
    except ValueError as e:
        print(f"❌ Error: {e}\n")
