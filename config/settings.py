"""Configuration settings for the recommendation system."""

import logging
import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Azure OpenAI
    azure_openai_endpoint: str = Field(..., env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_key: Optional[str] = Field(
        None, env="AZURE_OPENAI_API_KEY"
    )  # Optional now
    azure_openai_embedding_deployment: str = Field(
        default="text-embedding-3-large", env="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    )
    azure_openai_chat_deployment: str = Field(
        default="gpt-4o-mini", env="AZURE_OPENAI_CHAT_DEPLOYMENT"
    )
    azure_openai_api_version: str = Field(
        default="2024-12-01-preview", env="AZURE_OPENAI_API_VERSION"
    )

    # Azure AI Search
    azure_search_endpoint: str = Field(..., env="AZURE_SEARCH_ENDPOINT")
    azure_search_api_key: Optional[str] = Field(
        None, env="AZURE_SEARCH_API_KEY"
    )  # Optional now
    azure_search_index_name: str = Field(
        default="eliona-modules", env="AZURE_SEARCH_INDEX_NAME"
    )

    # Azure Cosmos DB
    azure_cosmos_endpoint: str = Field(..., env="AZURE_COSMOS_ENDPOINT")
    azure_cosmos_key: Optional[str] = Field(
        None, env="AZURE_COSMOS_KEY"
    )  # Optional now
    azure_cosmos_database: str = Field(
        default="eliona-catalog", env="AZURE_COSMOS_DATABASE"
    )
    azure_cosmos_modules_container: str = Field(
        default="modules", env="AZURE_COSMOS_MODULES_CONTAINER"
    )
    azure_cosmos_interactions_container: str = Field(
        default="interactions", env="AZURE_COSMOS_INTERACTIONS_CONTAINER"
    )

    # Azure AI Foundry
    azure_ai_project_endpoint: str = Field(..., env="AZURE_AI_PROJECT_ENDPOINT")
    azure_ai_model_deployment: str = Field(
        default="gpt-4o-mini", env="AZURE_AI_MODEL_DEPLOYMENT"
    )

    # Application
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", env="ENVIRONMENT")
    use_managed_identity: bool = Field(
        default=False, env="USE_MANAGED_IDENTITY"
    )  # New flag

    # Search parameters
    vector_search_k: int = 50
    hybrid_search_top: int = 10

    # Embedding dimensions for text-embedding-3-large
    embedding_dimensions: int = 1024

    class Config:
        # Find .env file relative to project root
        env_file = str(Path(__file__).parent.parent / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()

# Configure logging
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.info(f"Logging level set to: {settings.log_level.upper()}")
