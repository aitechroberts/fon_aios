# flows/processing/embeddings_flow.py
from prefect import flow, task, get_run_logger
from prefect.artifacts import create_table_artifact
from prefect.blocks.system import Secret
from prefect_azure.blob_storage import AzureBlobStorageContainer
from langchain_openai import AzureOpenAIEmbeddings
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchField, SearchFieldDataType,
    VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration
)
from azure.core.credentials import AzureKeyCredential
from typing import List, Dict, Any, Optional
import pyarrow.parquet as pq
import pyarrow as pa
from datetime import datetime
import os
import io

# raw-data/processed-parquet/newsapi_ai_defense_technology/2025/08/07/newsapi_ai_defense_technology_20250807_200206.parquet
@task(retries=2, retry_delay_seconds=60)
async def read_parquet_from_storage(parquet_path: str) -> List[Dict[str, Any]]:
    """Read Parquet file from storage and convert to list of dicts"""
    logger = get_run_logger()
    storage = await AzureBlobStorageContainer.load("fon-data-lake")
    
    # Read Parquet file
    parquet_bytes = await storage.read_path(parquet_path)
    
    # Convert to PyArrow table
    reader = pa.BufferReader(parquet_bytes)
    table = pq.read_table(reader)
    
    # Convert to list of dictionaries
    articles = table.to_pylist()
    
    logger.info(f"Read {len(articles)} articles from {parquet_path}")
    return articles

@task(retries=2, retry_delay_seconds=60)
async def read_multiple_parquets(parquet_paths: List[str]) -> List[Dict[str, Any]]:
    """Read multiple Parquet files and combine them"""
    logger = get_run_logger()
    
    all_articles = []
    for path in parquet_paths:
        articles = await read_parquet_from_storage(path)
        all_articles.extend(articles)
    
    logger.info(f"Read total of {len(all_articles)} articles from {len(parquet_paths)} files")
    return all_articles

@task(retries=3, retry_delay_seconds=300)
async def generate_embeddings_batch(
    articles: List[Dict[str, Any]],
    batch_size: int = 20
) -> List[Dict[str, Any]]:
    """Generate embeddings for articles in batches"""
    logger = get_run_logger()
    
    openai_key = await Secret.load("openai-api-key")
    embeddings_model = AzureOpenAIEmbeddings(api_key=openai_key.get())
    
    # Prepare texts
    texts = []
    for article in articles:
        text = f"{article['title']}\n\n{article.get('content', article.get('description', ''))}"
        texts.append(text)
    
    # Generate embeddings in batches
    all_embeddings = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        logger.info(f"Generating embeddings for batch {batch_num}/{total_batches}")
        batch_embeddings = await embeddings_model.aembed_documents(batch)
        all_embeddings.extend(batch_embeddings)
    
    # Add embeddings to articles
    articles_with_embeddings = []
    for article, embedding in zip(articles, all_embeddings):
        article_with_embedding = article.copy()
        article_with_embedding['embedding'] = embedding
        articles_with_embeddings.append(article_with_embedding)
    
    logger.info(f"Generated embeddings for {len(articles_with_embeddings)} articles")
    return articles_with_embeddings

@task
async def ensure_search_index() -> str:
    """Ensure Azure AI Search index exists"""
    logger = get_run_logger()
    
    service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
    admin_key = await Secret.load("azure-search-key")
    index_name = "fon-defense-intelligence"
    
    endpoint = f"https://{service_name}.search.windows.net"
    credential = AzureKeyCredential(admin_key.get())
    
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    
    # Check if index exists
    try:
        existing_index = index_client.get_index(index_name)
        logger.info(f"Index {index_name} already exists")
        return index_name
    except:
        logger.info(f"Creating index {index_name}")
    
    # Create index if it doesn't exist
    fields = [
        SimpleField(name="doc_id", type=SearchFieldDataType.String, key=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="description", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="source", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="published_at", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SearchField(name="url", type=SearchFieldDataType.String),
        SearchField(name="author", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="query_used", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="ingestion_timestamp", type=SearchFieldDataType.String, filterable=True),
        
        # Vector field
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="hnsw-profile"
        ),
    ]
    
    vector_search = VectorSearch(
        profiles=[
            VectorSearchProfile(
                name="hnsw-profile",
                algorithm_configuration_name="hnsw-config"
            )
        ],
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-config",
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ]
    )
    
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search
    )
    
    index_client.create_or_update_index(index)
    logger.info(f"Created index: {index_name}")
    
    return index_name

@task(retries=2, retry_delay_seconds=120)
async def index_to_search(
    articles_with_embeddings: List[Dict[str, Any]],
    index_name: str,
    batch_size: int = 100
) -> int:
    """Index articles with embeddings to Azure AI Search"""
    logger = get_run_logger()
    
    service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
    admin_key = await Secret.load("azure-search-key")
    
    endpoint = f"https://{service_name}.search.windows.net"
    credential = AzureKeyCredential(admin_key.get())
    
    search_client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential
    )
    
    documents_indexed = 0
    total_batches = (len(articles_with_embeddings) + batch_size - 1) // batch_size
    
    for i in range(0, len(articles_with_embeddings), batch_size):
        batch = articles_with_embeddings[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        # Prepare documents for indexing
        search_docs = []
        for article in batch:
            search_doc = {
                'doc_id': article['doc_id'],
                'title': article.get('title', ''),
                'content': article.get('content', ''),
                'description': article.get('description', ''),
                'source': article.get('source', ''),
                'published_at': article.get('published_at', ''),
                'url': article.get('url', ''),
                'author': article.get('author', ''),
                'query_used': article.get('query_used', ''),
                'ingestion_timestamp': article.get('ingestion_timestamp', ''),
                'content_vector': article['embedding']
            }
            search_docs.append(search_doc)
        
        logger.info(f"Indexing batch {batch_num}/{total_batches}")
        result = search_client.upload_documents(documents=search_docs)
        documents_indexed += len([r for r in result if r.succeeded])
    
    logger.info(f"Successfully indexed {documents_indexed} documents")
    return documents_indexed

@flow(name="Embeddings Processing", persist_result=True)
async def embeddings_processing_flow(
    parquet_paths: List[str] = None,
    parquet_path: str = None,  # Single path for single-source trigger
    batch_size: int = 20
) -> Dict[str, Any]:
    """Process embeddings for articles from Parquet files"""
    logger = get_run_logger()
    
    # Handle both single path and multiple paths
    if parquet_path and not parquet_paths:
        parquet_paths = [parquet_path]
    elif not parquet_paths:
        logger.error("No Parquet paths provided")
        return {"status": "error", "message": "No Parquet paths provided"}
    
    logger.info(f"Processing embeddings for {len(parquet_paths)} Parquet file(s)")
    
    # Read articles from Parquet
    if len(parquet_paths) == 1:
        articles = await read_parquet_from_storage(parquet_paths[0])
    else:
        articles = await read_multiple_parquets(parquet_paths)
    
    if not articles:
        logger.warning("No articles to process")
        return {"status": "no_data", "processed": 0}
    
    # Generate embeddings
    articles_with_embeddings = await generate_embeddings_batch(articles, batch_size)
    
    # Ensure search index exists
    index_name = await ensure_search_index()
    
    # Index to Azure Search
    indexed_count = await index_to_search(articles_with_embeddings, index_name)
    
    # Create summary artifact
    create_table_artifact(
        key="embeddings-summary",
        table={
            "Articles Processed": len(articles),
            "Articles Indexed": indexed_count,
            "Parquet Files": len(parquet_paths),
            "Index Name": index_name,
            "Timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return {
        "status": "success",
        "articles_processed": len(articles),
        "articles_indexed": indexed_count,
        "timestamp": datetime.utcnow().isoformat()
    }