"""Azure OpenAI embeddings generation."""

import logging
from typing import List

from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from src.azure_clients import get_openai_client

logger = logging.getLogger(__name__)


class EmbeddingsManager:
    """Manages embedding generation using Azure OpenAI."""

    def __init__(self):
        """Initialize the embeddings manager with Azure OpenAI client."""
        # Use centralized client factory with appropriate authentication
        self.client = get_openai_client()
        self.deployment = settings.azure_openai_embedding_deployment
        logger.info(f"Initialized EmbeddingsManager with deployment: {self.deployment}")

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of embedding values (1024 dimensions for text-embedding-3-large)
        """
        try:
            response = self.client.embeddings.create(
                model=self.deployment,
                input=text,
                dimensions=settings.embedding_dimensions,
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding with {len(embedding)} dimensions")
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 16
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch

        Returns:
            List of embeddings
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.deployment,
                    input=batch,
                    dimensions=settings.embedding_dimensions,
                )
                embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(embeddings)
                logger.debug(f"Generated {len(embeddings)} embeddings in batch")
            except Exception as e:
                logger.error(f"Error generating batch embeddings: {e}")
                raise

        logger.info(f"Generated {len(all_embeddings)} embeddings total")
        return all_embeddings

    def prepare_module_text(self, module: dict) -> str:
        """
        Prepare module data as text for embedding.

        Args:
            module: Module dictionary

        Returns:
            Formatted text representation
        """
        parts = [
            f"Module: {module.get('name', '')}",
            f"Theme: {module.get('theme', '')}",
            f"Description: {module.get('description', '')}",
            f"Category: {module.get('category', '')}",
            f"Tags: {', '.join(module.get('tags', []))}",
            f"Goals: {', '.join(module.get('goals', []))}",
            f"Personas: {', '.join(module.get('personas', []))}",
        ]

        if module.get("dependencies"):
            parts.append(f"Dependencies: {', '.join(module['dependencies'])}")

        return " | ".join(parts)
