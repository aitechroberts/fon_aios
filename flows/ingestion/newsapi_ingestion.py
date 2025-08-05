# flows/ingestion/news_ingestion_modular.py
from prefect import flow, task, get_run_logger
from prefect.artifacts import create_table_artifact
from prefect.blocks.system import Secret
from prefect_azure.blob_storage import AzureBlobStorageBlock
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import httpx
import json
import hashlib
import pyarrow as pa
import pyarrow.parquet as pq
from collections import defaultdict
import asyncio

QUERY_STRING = ""

@task(retries=3, retry_delay_seconds=60)
async def fetch_newsapi_articles(
    query: str = f"{QUERY_STRING}",
    lookback_days: int = 1
) -> List[Dict[str, Any]]:
    """Fetch articles from NewsAPI"""
    logger = get_run_logger()
    
    newsapi_key = await Secret.load("newsapi-key")
    
    to_date = datetime.now(datetime.timezone.utc)
    from_date = to_date - timedelta(days=lookback_days)
    
    articles = []
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "from": from_date.strftime('%Y-%m-%d'),
                "to": to_date.strftime('%Y-%m-%d'),
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 100,
                "apiKey": newsapi_key.get()
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            for article in data.get('articles', []):
                article_id = hashlib.md5(article['url'].encode()).hexdigest()
                
                articles.append({
                    'doc_id': f"newsapi_{article_id}",
                    'title': article.get('title', ''),
                    'content': article.get('content', ''),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'published_at': article.get('publishedAt', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'source_id': article.get('source', {}).get('id', 'unknown'),
                    'author': article.get('author', ''),
                    'url_to_image': article.get('urlToImage', ''),
                    'ingestion_timestamp': datetime.now(datetime.timezone.utc).isoformat(),
                    'query_used': query
                })
            
            logger.info(f"Fetched {len(articles)} articles from NewsAPI")
        else:
            logger.error(f"NewsAPI request failed: {response.status_code}")
            raise Exception(f"NewsAPI request failed: {response.text}")
    
    return articles

@task
async def group_articles_by_source(articles: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group articles by their source"""
    logger = get_run_logger()
    
    grouped = defaultdict(list)
    for article in articles:
        source_name = article['source'].replace(' ', '_').replace('/', '_')
        grouped[source_name].append(article)
    
    logger.info(f"Grouped articles into {len(grouped)} sources")
    for source, source_articles in grouped.items():
        logger.info(f"  - {source}: {len(source_articles)} articles")
    
    return dict(grouped)

@task
async def store_json_by_source(
    grouped_articles: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    """Store JSON files separated by source"""
    logger = get_run_logger()
    storage = await AzureBlobStorageBlock.load("fon-data-lake")
    
    timestamp = datetime.utcnow()
    date_path = timestamp.strftime('%Y/%m/%d')
    stored_paths = []
    
    for source_name, articles in grouped_articles.items():
        # Create source-specific filename
        file_name = f"{source_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        file_path = f"newsapi/{date_path}/{file_name}"
        
        # Store articles for this source
        await storage.write_path(
            path=file_path,
            content=json.dumps(articles, indent=2).encode()
        )
        
        stored_paths.append(file_path)
        logger.info(f"Stored {len(articles)} articles from {source_name} to {file_path}")
    
    return stored_paths

@task
async def create_parquet_rollup(
    grouped_articles: Dict[str, List[Dict[str, Any]]]
) -> str:
    """Create a combined Parquet file from all articles"""
    logger = get_run_logger()
    storage = await AzureBlobStorageBlock.load("fon-data-lake")
    
    # Combine all articles into single list
    all_articles = []
    for source_articles in grouped_articles.values():
        all_articles.extend(source_articles)
    
    # Define Parquet schema
    schema = pa.schema([
        ('doc_id', pa.string()),
        ('title', pa.string()),
        ('content', pa.string()),
        ('description', pa.string()),
        ('url', pa.string()),
        ('published_at', pa.string()),
        ('source', pa.string()),
        ('source_id', pa.string()),
        ('author', pa.string()),
        ('url_to_image', pa.string()),
        ('ingestion_timestamp', pa.string()),
        ('query_used', pa.string())
    ])
    
    # Convert to PyArrow table
    table = pa.Table.from_pylist(all_articles, schema=schema)
    
    # Write to Parquet format in memory
    parquet_buffer = pa.BufferOutputStream()
    pq.write_table(
        table, 
        parquet_buffer,
        compression='snappy',  # Good balance of speed and compression
        use_dictionary=True,   # Efficient for repeated strings like sources
        compression_level=None
    )
    
    # Store Parquet file
    timestamp = datetime.utcnow()
    date_path = timestamp.strftime('%Y/%m/%d')
    parquet_path = f"newsapi/{date_path}/combined_{timestamp.strftime('%Y%m%d_%H%M%S')}.parquet"
    
    await storage.write_path(
        path=parquet_path,
        content=parquet_buffer.getvalue().to_pybytes()
    )
    
    # Log statistics
    parquet_size = len(parquet_buffer.getvalue()) / 1024  # KB
    json_size_estimate = len(json.dumps(all_articles).encode()) / 1024  # KB
    compression_ratio = json_size_estimate / parquet_size if parquet_size > 0 else 0
    
    logger.info(f"Created Parquet file: {parquet_path}")
    logger.info(f"  - Articles: {len(all_articles)}")
    logger.info(f"  - Parquet size: {parquet_size:.2f} KB")
    logger.info(f"  - Compression ratio: {compression_ratio:.2f}x")
    
    return parquet_path

@flow(name="News Ingestion", persist_result=True)
async def news_ingestion_flow(
    query: str = "defense contract OR DARPA OR military technology",
    lookback_days: int = 1
) -> Dict[str, Any]:
    """Modular ingestion flow - just fetch and store, no embeddings"""
    logger = get_run_logger()
    logger.info(f"Starting news ingestion for query: {query}")
    
    # Fetch articles
    articles = await fetch_newsapi_articles(query, lookback_days)
    
    if not articles:
        logger.warning("No articles fetched")
        return {
            "status": "no_data",
            "articles_count": 0,
            "sources": []
        }
    
    # Group by source
    grouped_articles = await group_articles_by_source(articles)
    
    # Store JSON files by source
    json_paths = await store_json_by_source(grouped_articles)
    
    # Create Parquet rollup
    parquet_path = await create_parquet_rollup(grouped_articles)
    
    # Create summary artifact
    source_summary = {
        source: len(articles) 
        for source, articles in grouped_articles.items()
    }
    
    create_table_artifact(
        key="ingestion-summary",
        table={
            "Total Articles": len(articles),
            "Sources": len(grouped_articles),
            "Source Breakdown": str(source_summary),
            "Parquet Path": parquet_path,
            "Query": query,
            "Timestamp": datetime.utcnow().isoformat()
        }
    )
    
    # Return result with parquet path for downstream processing
    return {
        "status": "success",
        "articles_count": len(articles),
        "sources": list(grouped_articles.keys()),
        "json_paths": json_paths,
        "parquet_path": parquet_path,  # This is what triggers embedding flow
        "timestamp": datetime.utcnow().isoformat()
    }