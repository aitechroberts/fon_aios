# flows/ingestion/newsapi_single_topic_flow.py
from prefect import flow, task, get_run_logger
from prefect.artifacts import create_table_artifact
from prefect_azure.blob_storage import AzureBlobStorageContainer
from datetime import datetime
from typing import Dict, Any, List
import json
import pyarrow as pa
import pyarrow.parquet as pq
import sys
import os
from azure.storage.blob import BlobServiceClient, StandardBlobTier

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flows.ingestion.news_sources import NewsAPIaiTopicSource
from config.newsapi_ai_topics import TEST_TOPIC

@task
async def fetch_and_store_articles(
    topic_config: Dict[str, Any],
    max_articles: int = 10
) -> Dict[str, Any]:
    """Fetch articles from NewsAPI.ai and store them"""
    logger = get_run_logger()
    
    # Create source instance
    source = NewsAPIaiTopicSource(
        topic_uri=topic_config['uri'],
        topic_name=topic_config['name'],
        topic_key='defense_technology'  # Using the key from config
    )
    
    # Prepare parameters for fetching
    params = {
        'max_articles': max_articles,
        'sort_by': topic_config.get('sort_by', 'fq')
    }
    
    # Load Azure storage block
    storage = await AzureBlobStorageContainer.load("fon-data-lake")

    # Get connection string from environment for blob tier control
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client("aios-data-lake")
    
    # Setup paths
    timestamp = datetime.utcnow()
    date_path = timestamp.strftime('%Y/%m/%d')
    json_base_path = f"{source.source_name}/{date_path}"
    parquet_path = f"processed-parquet/{source.source_name}/{date_path}/{source.source_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.parquet"
    
    # Collect articles
    articles = []
    items_processed = 0
    
    logger.info(f"Fetching articles from {topic_config['name']}...")
    
    # Fetch and transform articles
    async for raw_item in source.fetch_data_stream(params):
        # Transform the article
        transformed = source.transform_data(raw_item)
        articles.append(transformed)
        
        # Store individual JSON
        json_path = f"{json_base_path}/{transformed['doc_id']}.json"
        json_content = json.dumps(transformed, indent=2, default=str).encode()
        # await storage.write_path(json_path, json_content)

        # Upload with warm tier
        blob_client = container_client.get_blob_client(json_path)
        blob_client.upload_blob(
            data=json_content,
            overwrite=True,
            standard_blob_tier=StandardBlobTier.WARM  # Set to warm tier
        )

        items_processed += 1
        
        if items_processed % 10 == 0:
            logger.info(f"Processed {items_processed} articles...")
    
    logger.info(f"Total articles fetched: {items_processed}")
    
    # Create Parquet file if we have articles
    if articles:
        # Define schema for Parquet
        schema = pa.schema([
            ('doc_id', pa.string()),
            ('title', pa.string()),
            ('content', pa.string()),
            ('description', pa.string()),
            ('link', pa.string()),
            ('published_at', pa.timestamp('ms')),
            ('source', pa.string()),
            ('source_type', pa.string()),
            ('topic_name', pa.string()),
            ('topic_key', pa.string()),
            ('categories', pa.list_(pa.string())),
            ('ingestion_timestamp', pa.timestamp('ms'))
        ])
        
        # Create Parquet table
        table = pa.Table.from_pylist(articles, schema=schema)
        
        # Write to buffer
        parquet_buffer = pa.BufferOutputStream()
        writer = pq.ParquetWriter(parquet_buffer, schema)
        writer.write_table(table)
        writer.close()
        
        # Upload Parquet file
        # await storage.write_path(parquet_path, parquet_buffer.getvalue().to_pybytes())

        # Upload Parquet with warm tier
        full_parquet_path = f"raw-data/{parquet_path}"
        blob_client = container_client.get_blob_client(full_parquet_path)
        blob_client.upload_blob(
            data=parquet_buffer.getvalue().to_pybytes(),
            overwrite=True,
            standard_blob_tier=StandardBlobTier.WARM  # Set to warm tier
        )
        logger.info(f"Created Parquet file with WARM tier: {full_parquet_path}")
    
    return {
        'items_processed': items_processed,
        'json_path': json_base_path,
        'parquet_path': parquet_path if articles else None,
        'timestamp': timestamp.isoformat()
    }

@flow(name="NewsAPI.ai Single Topic Test")
async def newsapi_single_topic_flow(
    max_articles: int = 100,
) -> Dict[str, Any]:
    """
    Test flow for single NewsAPI.ai topic with limited articles
    
    Args:
        max_articles: Maximum articles to fetch (default 100 for testing)
    """
    logger = get_run_logger()
    
    # Get topic config
    topic_config = TEST_TOPIC['defense_technology']
    
    # Check if topic URI is configured
    if topic_config['uri'].startswith("YOUR_"):
        logger.error("Topic URI not configured in config/newsapi_ai_topics.py")
        return {"status": "error", "message": "Topic URI not configured"}
    
    logger.info(f"Starting NewsAPI.ai single topic test ingestion")
    logger.info(f"Topic: {topic_config['name']}")
    logger.info(f"Topic URI: {topic_config['uri']}")
    logger.info(f"Max articles: {max_articles}")
    
    # Fetch and store articles
    result = await fetch_and_store_articles(topic_config, max_articles)
    
    # Create artifact for monitoring
    create_table_artifact(
        key="newsapi-test-ingestion",
        table={
            "Topic": topic_config['name'],
            "Articles Requested": max_articles,
            "Articles Ingested": result.get('items_processed', 0),
            "JSON Path": result.get('json_path', ''),
            "Parquet Path": result.get('parquet_path', ''),
            "Timestamp": datetime.utcnow().isoformat()
        }
    )
    
    logger.info(f"Ingestion complete: {result.get('items_processed', 0)} articles")
    
    return {
        "status": "success",
        **result
    }