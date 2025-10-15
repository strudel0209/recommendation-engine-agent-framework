"""Complete setup script for the recommendation system."""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.seed_data import seed_data
from scripts.setup_cosmos import setup_cosmos_db
from scripts.setup_search import setup_search_index

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def complete_setup():
    """
    Run complete setup:
    1. Setup Cosmos DB (database and containers)
    2. Setup Azure AI Search (index with vector config)
    3. Seed data (load sample modules and index them)
    """
    logger.info("\n" + "=" * 70)
    logger.info("RECOMMENDATION SYSTEM - COMPLETE SETUP")
    logger.info("=" * 70 + "\n")

    try:
        # Step 1: Setup Cosmos DB
        logger.info("STEP 1/3: Setting up Azure Cosmos DB...")
        logger.info("-" * 70)
        setup_cosmos_db()
        logger.info("")

        # Step 2: Setup Azure AI Search
        logger.info("STEP 2/3: Setting up Azure AI Search...")
        logger.info("-" * 70)
        setup_search_index()
        logger.info("")

        # Step 3: Seed Data
        logger.info("STEP 3/3: Seeding data...")
        logger.info("-" * 70)
        seed_data()
        logger.info("")

        # Success summary
        logger.info("=" * 70)
        logger.info("✅ SETUP COMPLETED SUCCESSFULLY!")
        logger.info("=" * 70)
        logger.info("\nYour recommendation system is ready to use!")
        logger.info("\nNext steps:")
        logger.info("  1. Start the API server:")
        logger.info("     python api/main.py")
        logger.info("\n  2. Or run tests:")
        logger.info("     python tests/test_recommendation.py")
        logger.info("\n  3. Access API documentation:")
        logger.info("     http://localhost:8000/docs")
        logger.info("=" * 70 + "\n")

    except Exception as e:
        logger.error("\n" + "=" * 70)
        logger.error("❌ SETUP FAILED")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error("\nPlease check:")
        logger.error("  1. Azure credentials are configured (az login)")
        logger.error("  2. .env file has correct Azure resource endpoints")
        logger.error("  3. Azure resources exist and are accessible")
        logger.error("=" * 70 + "\n")
        raise


if __name__ == "__main__":
    complete_setup()
