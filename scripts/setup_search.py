"""Setup script for Azure AI Search index."""
import logging

from config.settings import settings
from src.search_manager import SearchManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_search_index():
    """Create Azure AI Search index with vector search configuration."""
    logger.info("Starting Azure AI Search setup...")
    logger.info(f"Using {'Managed Identity' if settings.use_managed_identity else 'API Key'} authentication")
    
    try:
        search_manager = SearchManager()
        
        # Create index
        logger.info("Creating search index with hybrid search configuration...")
        index = search_manager.create_index()
        
        logger.info(f"✅ Search index created successfully: {index.name}")
        logger.info(f"   - Vector dimensions: {1024}")
        logger.info(f"   - Algorithm: HNSW")
        logger.info(f"   - Vectorizer: Azure OpenAI (text-embedding-3-large)")
        logger.info(f"   - Semantic ranking: Enabled")
        
        return index
    
    except Exception as e:
        logger.error(f"❌ Error setting up search index: {e}")
        raise


if __name__ == "__main__":
    setup_search_index()
