"""Setup script for Azure Cosmos DB database and containers."""

import logging

from azure.cosmos import PartitionKey, exceptions

from config.settings import settings
from src.azure_clients import get_cosmos_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_cosmos_db():
    """Verify or create Cosmos DB database and containers."""
    logger.info("Starting Cosmos DB setup...")
    logger.info(
        f"Using {'Managed Identity' if settings.use_managed_identity else 'API Key'} authentication"
    )

    # Get client with appropriate authentication
    client = get_cosmos_client()

    try:
        # Try to get existing database
        logger.info(f"Checking for database: {settings.azure_cosmos_database}")
        try:
            database = client.get_database_client(settings.azure_cosmos_database)
            # Test if database exists
            database.read()
            logger.info(f"✅ Database already exists: {database.id}")
        except exceptions.CosmosResourceNotFoundError:
            logger.info(f"Database not found, attempting to create...")
            try:
                database = client.create_database(id=settings.azure_cosmos_database)
                logger.info(f"✅ Database created: {database.id}")
            except exceptions.CosmosHttpResponseError as e:
                if "not allowed" in str(e):
                    logger.error("❌ Cannot create database via data plane API.")
                    logger.error("Please create it manually using Azure Portal or CLI:")
                    logger.error(f"  az cosmosdb sql database create \\")
                    logger.error(f"    --account-name cosmos-cwstlaaqghino \\")
                    logger.error(f"    --resource-group rg-rag-telemetry \\")
                    logger.error(f"    --name {settings.azure_cosmos_database}")
                    raise
                raise

        # Try to get existing modules container
        logger.info(
            f"Checking for container: {settings.azure_cosmos_modules_container}"
        )
        try:
            modules_container = database.get_container_client(
                settings.azure_cosmos_modules_container
            )
            # Test if container exists
            modules_container.read()
            logger.info(f"✅ Modules container already exists: {modules_container.id}")
        except exceptions.CosmosResourceNotFoundError:
            logger.info(f"Container not found, attempting to create...")
            try:
                modules_container = database.create_container(
                    id=settings.azure_cosmos_modules_container,
                    partition_key=PartitionKey(path="/theme"),
                    offer_throughput=400,
                )
                logger.info(f"✅ Modules container created: {modules_container.id}")
            except exceptions.CosmosHttpResponseError as e:
                if "not allowed" in str(e):
                    logger.error("❌ Cannot create container via data plane API.")
                    logger.error("Please create it manually using Azure Portal or CLI:")
                    logger.error(f"  az cosmosdb sql container create \\")
                    logger.error(f"    --account-name cosmos-cwstlaaqghino \\")
                    logger.error(f"    --resource-group rg-rag-telemetry \\")
                    logger.error(
                        f"    --database-name {settings.azure_cosmos_database} \\"
                    )
                    logger.error(
                        f"    --name {settings.azure_cosmos_modules_container} \\"
                    )
                    logger.error(f"    --partition-key-path '/theme' \\")
                    logger.error(f"    --throughput 400")
                    raise
                raise

        # Try to get existing interactions container
        logger.info(
            f"Checking for container: {settings.azure_cosmos_interactions_container}"
        )
        try:
            interactions_container = database.get_container_client(
                settings.azure_cosmos_interactions_container
            )
            # Test if container exists
            interactions_container.read()
            logger.info(
                f"✅ Interactions container already exists: {interactions_container.id}"
            )
        except exceptions.CosmosResourceNotFoundError:
            logger.info(f"Container not found, attempting to create...")
            try:
                interactions_container = database.create_container(
                    id=settings.azure_cosmos_interactions_container,
                    partition_key=PartitionKey(path="/user_id"),
                    offer_throughput=400,
                )
                logger.info(
                    f"✅ Interactions container created: {interactions_container.id}"
                )
            except exceptions.CosmosHttpResponseError as e:
                if "not allowed" in str(e):
                    logger.error("❌ Cannot create container via data plane API.")
                    logger.error("Please create it manually using Azure Portal or CLI:")
                    logger.error(f"  az cosmosdb sql container create \\")
                    logger.error(f"    --account-name cosmos-cwstlaaqghino \\")
                    logger.error(f"    --resource-group rg-rag-telemetry \\")
                    logger.error(
                        f"    --database-name {settings.azure_cosmos_database} \\"
                    )
                    logger.error(
                        f"    --name {settings.azure_cosmos_interactions_container} \\"
                    )
                    logger.error(f"    --partition-key-path '/user_id' \\")
                    logger.error(f"    --throughput 400")
                    raise
                raise

        logger.info("\n✅ Cosmos DB setup completed successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Error setting up Cosmos DB: {e}")
        raise


if __name__ == "__main__":
    setup_cosmos_db()
