"""Input/output models for tool operations."""

from pydantic import BaseModel, Field


class CreditCheckInput(BaseModel):
    """Input model for credit check operations."""
    
    borrower_id: str = Field(..., description="Unique borrower identifier")
    fico_score: int = Field(..., ge=300, le=850, description="FICO credit score (300-850)")
    check_type: str = Field(default="basic", description="Type of credit check: basic, detailed, or full")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "borrower_id": "B12345",
                "fico_score": 750,
                "check_type": "detailed"
            }
        }


class DataFetchInput(BaseModel):
    """Input model for data fetch operations."""
    
    borrower_id: str = Field(..., description="Unique borrower identifier")
    data_types: list[str] = Field(default=["credit", "employment"], description="Types of data to fetch")
    
    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "borrower_id": "B12345",
                "data_types": ["credit", "employment", "income"]
            }
        }
