"""Script to seed data: load sample modules and index them."""
import logging
import json
from pathlib import Path

from src.data_manager import DataManager
from src.embeddings import EmbeddingsManager
from src.search_manager import SearchManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_sample_data():
    """Load sample modules and themes from JSON files."""
    data_dir = Path(__file__).parent.parent / "data"
    
    # Load modules
    with open(data_dir / "sample_modules.json", "r") as f:
        modules = json.load(f)
    
    # Load themes
    with open(data_dir / "sample_themes.json", "r") as f:
        themes = json.load(f)
    
    logger.info(f"Loaded {len(modules)} modules and {len(themes)} themes")
    return modules, themes


def seed_data():
    """
    Seed the system with sample data:
    1. Load sample modules and themes
    2. Generate embeddings for modules
    3. Store modules in Cosmos DB
    4. Index modules in Azure AI Search
    """
    logger.info("Starting data seeding...")
    
    try:
        # Initialize managers
        data_manager = DataManager()
        embeddings_manager = EmbeddingsManager()
        search_manager = SearchManager()
        
        # Load sample data
        modules, themes = load_sample_data()
        
        # Step 1: Store modules in Cosmos DB
        logger.info("Storing modules in Cosmos DB...")
        for module in modules:
            data_manager.upsert_module(module)
            logger.info(f"  ✓ Stored: {module['name']}")
        
        # Step 2: Generate embeddings
        logger.info("Generating embeddings for modules...")
        module_texts = [embeddings_manager.prepare_module_text(m) for m in modules]
        embeddings = embeddings_manager.generate_embeddings_batch(module_texts)
        logger.info(f"  ✓ Generated {len(embeddings)} embeddings")
        
        # Step 3: Index in Azure AI Search
        logger.info("Indexing modules in Azure AI Search...")
        modules_with_embeddings = list(zip(modules, embeddings))
        search_manager.index_modules_batch(modules_with_embeddings)
        logger.info("  ✓ Indexed all modules")
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("✅ Data seeding completed successfully!")
        logger.info(f"   - Modules in Cosmos DB: {len(modules)}")
        logger.info(f"   - Modules in Search Index: {len(modules)}")
        logger.info(f"   - Themes available: {len(themes)}")
        logger.info("="*60 + "\n")
        
        # Display module summary
        logger.info("Module Summary by Theme:")
        theme_counts = {}
        for module in modules:
            theme = module.get("theme", "unknown")
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
        
        for theme, count in sorted(theme_counts.items()):
            logger.info(f"  - {theme}: {count} modules")
    
    except Exception as e:
        logger.error(f"❌ Error seeding data: {e}")
        raise


if __name__ == "__main__":
    seed_data()
