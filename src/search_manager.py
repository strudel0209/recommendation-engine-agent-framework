"""Azure AI Search management for hybrid vector + keyword search."""
import logging
from typing import List, Dict, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch
)
from azure.search.documents.models import VectorizableTextQuery
from azure.identity import DefaultAzureCredential

from config.settings import settings
from src.azure_clients import get_search_client

logger = logging.getLogger(__name__)


class SearchManager:
    """Manages Azure AI Search operations for hybrid search."""
    
    def __init__(self):
        """Initialize search clients."""
        # Determine credential based on settings
        if settings.use_managed_identity:
            credential = DefaultAzureCredential()
            logger.info("Using Managed Identity for Search authentication")
        else:
            if not settings.azure_search_api_key:
                raise ValueError("AZURE_SEARCH_API_KEY is required when USE_MANAGED_IDENTITY=false")
            credential = AzureKeyCredential(settings.azure_search_api_key)
            logger.info("Using API Key for Search authentication")
        
        self.index_client = SearchIndexClient(
            endpoint=settings.azure_search_endpoint,
            credential=credential
        )
        
        # Use the centralized client getter
        self.search_client = get_search_client()
        
        logger.info("Initialized SearchManager")
    
    def create_index(self) -> SearchIndex:
        """
        Create the search index with vector search configuration.
        
        Returns:
            Created search index
        """
        # Define fields
        fields = [
            SearchField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                sortable=True,
                filterable=True
            ),
            SearchField(
                name="name",
                type=SearchFieldDataType.String,
                searchable=True,
                sortable=True
            ),
            SearchField(
                name="theme",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                facetable=True
            ),
            SearchField(
                name="description",
                type=SearchFieldDataType.String,
                searchable=True
            ),
            SearchField(
                name="category",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                facetable=True
            ),
            SearchField(
                name="tags",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                searchable=True,
                filterable=True,
                facetable=True
            ),
            SearchField(
                name="personas",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                searchable=True,
                filterable=True,
                facetable=True
            ),
            SearchField(
                name="goals",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                searchable=True,
                filterable=True,
                facetable=True
            ),
            SearchField(
                name="scale",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
                facetable=True
            ),
            SearchField(
                name="license",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True
            ),
            SearchField(
                name="dependencies",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=settings.embedding_dimensions,
                vector_search_profile_name="module-vector-profile"
            )
        ]
        
        # Configure vector search with Azure OpenAI vectorizer
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(name="hnsw-config")
            ],
            profiles=[
                VectorSearchProfile(
                    name="module-vector-profile",
                    algorithm_configuration_name="hnsw-config",
                    vectorizer_name="openai-vectorizer"
                )
            ],
            vectorizers=[
                AzureOpenAIVectorizer(
                    vectorizer_name="openai-vectorizer",
                    parameters=AzureOpenAIVectorizerParameters(
                        resource_url=settings.azure_openai_endpoint,
                        deployment_name=settings.azure_openai_embedding_deployment,
                        model_name="text-embedding-3-large"
                    )
                )
            ]
        )
        
        # Configure semantic search for improved ranking
        semantic_config = SemanticConfiguration(
            name="module-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="name"),
                content_fields=[
                    SemanticField(field_name="description")
                ],
                keywords_fields=[
                    SemanticField(field_name="tags"),
                    SemanticField(field_name="goals")
                ]
            )
        )
        
        semantic_search = SemanticSearch(configurations=[semantic_config])
        
        # Create index
        index = SearchIndex(
            name=settings.azure_search_index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        try:
            result = self.index_client.create_or_update_index(index)
            logger.info(f"Created/updated index: {result.name}")
            return result
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            raise
    
    def index_module(self, module: dict, embedding: List[float]) -> None:
        """
        Index a single module with its embedding.
        
        Args:
            module: Module data
            embedding: Pre-computed embedding vector
        """
        document = {
            "id": module["id"],
            "name": module["name"],
            "theme": module["theme"],
            "description": module["description"],
            "category": module["category"],
            "tags": module.get("tags", []),
            "personas": module.get("personas", []),
            "goals": module.get("goals", []),
            "scale": module.get("scale", []),
            "license": module.get("license"),
            "dependencies": module.get("dependencies", []),
            "content_vector": embedding
        }
        
        try:
            result = self.search_client.upload_documents(documents=[document])
            logger.info(f"Indexed module: {module['id']}, success: {result[0].succeeded}")
        except Exception as e:
            logger.error(f"Error indexing module {module['id']}: {e}")
            raise
    
    def index_modules_batch(self, modules_with_embeddings: List[tuple]) -> None:
        """
        Index multiple modules in batch.
        
        Args:
            modules_with_embeddings: List of (module, embedding) tuples
        """
        documents = []
        for module, embedding in modules_with_embeddings:
            document = {
                "id": module["id"],
                "name": module["name"],
                "theme": module["theme"],
                "description": module["description"],
                "category": module["category"],
                "tags": module.get("tags", []),
                "personas": module.get("personas", []),
                "goals": module.get("goals", []),
                "scale": module.get("scale", []),
                "license": module.get("license"),
                "dependencies": module.get("dependencies", []),
                "content_vector": embedding
            }
            documents.append(document)
        
        try:
            results = self.search_client.upload_documents(documents=documents)
            succeeded = sum(1 for r in results if r.succeeded)
            logger.info(f"Indexed {succeeded}/{len(documents)} modules")
        except Exception as e:
            logger.error(f"Error batch indexing modules: {e}")
            raise
    
    def hybrid_search(
        self,
        query: str,
        filters: Optional[str] = None,
        top: int = None
    ) -> List[dict]:
        """
        Perform hybrid search (vector + keyword) with optional filters.
        
        Args:
            query: Search query text
            filters: OData filter expression
            top: Number of results to return
            
        Returns:
            List of search results
        """
        if top is None:
            top = settings.hybrid_search_top
        
        try:
            # Create vector query with automatic vectorization
            vector_query = VectorizableTextQuery(
                text=query,
                k_nearest_neighbors=settings.vector_search_k,
                fields="content_vector"
            )
            
            # Execute hybrid search
            results = self.search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                filter=filters,
                top=top,
                select=[
                    "id", "name", "theme", "description", "category",
                    "tags", "personas", "goals", "scale", "license", "dependencies"
                ]
            )
            
            # Convert to list with scores
            results_list = []
            for result in results:
                doc = dict(result)
                doc["search_score"] = result.get("@search.score", 0)
                results_list.append(doc)
            
            logger.info(f"Hybrid search returned {len(results_list)} results for query: {query[:50]}...")
            return results_list
        except Exception as e:
            logger.error(f"Error performing hybrid search: {e}")
            raise
    
    def delete_index(self) -> None:
        """Delete the search index."""
        try:
            self.index_client.delete_index(settings.azure_search_index_name)
            logger.info(f"Deleted index: {settings.azure_search_index_name}")
        except Exception as e:
            logger.error(f"Error deleting index: {e}")
            raise
