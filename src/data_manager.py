"""Azure Cosmos DB data management."""

import logging
from typing import Dict, List, Optional

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.identity import DefaultAzureCredential

from config.settings import settings

logger = logging.getLogger(__name__)


class DataManager:
    """Manages data operations with Azure Cosmos DB."""

    def __init__(self):
        """Initialize Cosmos DB client and containers."""
        credential = DefaultAzureCredential()

        self.client = CosmosClient(
            url=settings.azure_cosmos_endpoint, credential=credential
        )

        # Get or create database
        self.database = self.client.create_database_if_not_exists(
            id=settings.azure_cosmos_database
        )

        # Get or create containers
        self.modules_container = self.database.create_container_if_not_exists(
            id=settings.azure_cosmos_modules_container,
            partition_key=PartitionKey(path="/theme"),
            offer_throughput=400,
        )

        self.interactions_container = self.database.create_container_if_not_exists(
            id=settings.azure_cosmos_interactions_container,
            partition_key=PartitionKey(path="/user_id"),
            offer_throughput=400,
        )

        logger.info("Initialized DataManager with Cosmos DB")

    # Module operations
    def upsert_module(self, module: dict) -> dict:
        """
        Upsert a module document.

        Args:
            module: Module data with 'id' and 'theme' fields

        Returns:
            Upserted module document
        """
        try:
            result = self.modules_container.upsert_item(body=module)
            logger.info(f"Upserted module: {module['id']}")
            return result
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error upserting module {module.get('id')}: {e}")
            raise

    def get_module(self, module_id: str, theme: str) -> Optional[dict]:
        """
        Get a module by ID.

        Args:
            module_id: Module identifier
            theme: Theme name (partition key)

        Returns:
            Module document or None
        """
        try:
            return self.modules_container.read_item(item=module_id, partition_key=theme)
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Module not found: {module_id}")
            return None

    def get_module_by_id(self, module_id: str) -> Optional[dict]:
        """
        Get a module by ID (searches across all partitions).

        Args:
            module_id: Module identifier

        Returns:
            Module document or None
        """
        try:
            query = "SELECT * FROM c WHERE c.id = @module_id"
            parameters = [{"name": "@module_id", "value": module_id}]

            items = list(
                self.modules_container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True,
                    max_item_count=1,
                )
            )

            if items:
                return items[0]
            return None

        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error getting module {module_id}: {e}")
            return None

    def list_modules(
        self, theme: Optional[str] = None, max_items: int = 100
    ) -> List[dict]:
        """
        List modules, optionally filtered by theme.

        Args:
            theme: Optional theme filter
            max_items: Maximum number of items to return

        Returns:
            List of module documents
        """
        try:
            if theme:
                query = f"SELECT * FROM c WHERE c.theme = @theme"
                parameters = [{"name": "@theme", "value": theme}]
            else:
                query = "SELECT * FROM c"
                parameters = None

            items = list(
                self.modules_container.query_items(
                    query=query,
                    parameters=parameters,
                    max_item_count=max_items,
                    enable_cross_partition_query=True,
                )
            )

            logger.info(f"Retrieved {len(items)} modules")
            return items
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error listing modules: {e}")
            raise

    def delete_module(self, module_id: str, theme: str) -> None:
        """
        Delete a module.

        Args:
            module_id: Module identifier
            theme: Theme name (partition key)
        """
        try:
            self.modules_container.delete_item(item=module_id, partition_key=theme)
            logger.info(f"Deleted module: {module_id}")
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Module not found for deletion: {module_id}")

    # Interaction operations
    def log_interaction(self, interaction: dict) -> dict:
        """
        Log a recommendation interaction.

        Args:
            interaction: Interaction data with 'id' and 'user_id' fields

        Returns:
            Logged interaction document
        """
        try:
            result = self.interactions_container.upsert_item(body=interaction)
            logger.info(f"Logged interaction: {interaction['id']}")
            return result
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error logging interaction: {e}")
            raise

    def get_user_interactions(self, user_id: str, max_items: int = 50) -> List[dict]:
        """
        Get interactions for a specific user.

        Args:
            user_id: User identifier
            max_items: Maximum number of items to return

        Returns:
            List of interaction documents
        """
        try:
            query = (
                "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.timestamp DESC"
            )
            parameters = [{"name": "@user_id", "value": user_id}]

            items = list(
                self.interactions_container.query_items(
                    query=query,
                    parameters=parameters,
                    partition_key=user_id,
                    max_item_count=max_items,
                )
            )

            logger.info(f"Retrieved {len(items)} interactions for user {user_id}")
            return items
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error getting user interactions: {e}")
            raise

    def log_feedback(self, interaction_id: str, user_id: str, feedback: dict) -> dict:
        """
        Update interaction with user feedback.

        Args:
            interaction_id: Interaction identifier
            user_id: User identifier (partition key)
            feedback: Feedback data (action, module_id, etc.)

        Returns:
            Updated interaction document
        """
        try:
            # Get existing interaction
            interaction = self.interactions_container.read_item(
                item=interaction_id, partition_key=user_id
            )

            # Add feedback
            if "feedback" not in interaction:
                interaction["feedback"] = []

            interaction["feedback"].append(feedback)

            # Update
            result = self.interactions_container.upsert_item(body=interaction)
            logger.info(f"Added feedback to interaction: {interaction_id}")
            return result
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Interaction not found: {interaction_id}")
            raise
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Error logging feedback: {e}")
            raise
