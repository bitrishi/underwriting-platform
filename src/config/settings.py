"""Application settings and configuration using python-dotenv."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)


@dataclass
class Settings:
    """Application settings configuration."""
    
    aws_region: str
    bedrock_model_id: str
    log_level: str
    environment: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    
    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL: {self.log_level}. "
                f"Must be one of {valid_log_levels}"
            )
        
        valid_environments = {"development", "staging", "production"}
        if self.environment.lower() not in valid_environments:
            raise ValueError(
                f"Invalid ENVIRONMENT: {self.environment}. "
                f"Must be one of {valid_environments}"
            )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment.lower() == "staging"


def load_settings() -> Settings:
    """
    Load settings from environment variables.
    
    Reads from .env file or environment variables.
    Falls back to sensible defaults if not provided.
    
    Returns:
        Settings dataclass instance
        
    Raises:
        ValueError: If required settings are missing or invalid
    """
    return Settings(
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        bedrock_model_id=os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-sonnet-20240229-v1:0"
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        environment=os.getenv("ENVIRONMENT", "development"),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "neo4jpassword"),
    )


# Global settings instance
settings = load_settings()


if __name__ == "__main__":
    # Display current settings (safe for production - doesn't show secrets)
    print("Current Settings:")
    print(f"  AWS Region: {settings.aws_region}")
    print(f"  Bedrock Model: {settings.bedrock_model_id}")
    print(f"  Log Level: {settings.log_level}")
    print(f"  Environment: {settings.environment}")
    print(f"  Neo4j URI: {settings.neo4j_uri}")
    print(f"  Neo4j User: {settings.neo4j_user}")
    print(f"  Is Production: {settings.is_production}")
    print(f"  Is Development: {settings.is_development}")
    print(f"  Is Staging: {settings.is_staging}")
