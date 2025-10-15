"""Utility module for creating Azure service clients with flexible authentication."""

from typing import Union

from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from config.settings import settings


def get_cosmos_client() -> CosmosClient:
    """
    Create Cosmos DB client with either managed identity or key-based auth.

    Returns:
        CosmosClient: Authenticated Cosmos DB client
    """
    if settings.use_managed_identity:
        # Use Managed Identity
        credential = DefaultAzureCredential()
        return CosmosClient(url=settings.azure_cosmos_endpoint, credential=credential)
    else:
        # Use API key
        if not settings.azure_cosmos_key:
            raise ValueError(
                "AZURE_COSMOS_KEY is required when USE_MANAGED_IDENTITY=false"
            )
        return CosmosClient(
            url=settings.azure_cosmos_endpoint, credential=settings.azure_cosmos_key
        )


def get_search_client(index_name: str = None) -> SearchClient:
    """
    Create Azure AI Search client with either managed identity or key-based auth.

    Args:
        index_name: Name of the search index (defaults to settings value)

    Returns:
        SearchClient: Authenticated Search client
    """
    index_name = index_name or settings.azure_search_index_name

    if settings.use_managed_identity:
        # Use Managed Identity
        credential = DefaultAzureCredential()
        return SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=index_name,
            credential=credential,
        )
    else:
        # Use API key
        if not settings.azure_search_api_key:
            raise ValueError(
                "AZURE_SEARCH_API_KEY is required when USE_MANAGED_IDENTITY=false"
            )
        return SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=index_name,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )


def get_openai_client() -> AzureOpenAI:
    """
    Create Azure OpenAI client with either managed identity or key-based auth.

    Returns:
        AzureOpenAI: Authenticated OpenAI client
    """
    if settings.use_managed_identity:
        # Use Managed Identity
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAI(
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
        )
    else:
        # Use API key
        if not settings.azure_openai_api_key:
            raise ValueError(
                "AZURE_OPENAI_API_KEY is required when USE_MANAGED_IDENTITY=false"
            )
        return AzureOpenAI(
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
        )
