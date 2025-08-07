# flows/ingestion/newsapi_topics_flow.py
from prefect import flow, task, get_run_logger
from prefect.artifacts import create_table_artifact, create_link_artifact
from prefect_azure.blob_storage import AzureBlobStorageBlock
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import pyarrow as pa
import pyarrow.parquet as pq
import os
import sys

# Add project root to path
sys.path.append('/opt/airflow/src')

from flows.ingestion.newsapi_sources import NewsAPIaiTopicSource
from config.newsapi_topics import TOPICS

@task(retries=2, retry_delay_seconds=60)
async def ingest_single_topic(
    topic_key: str, 
    topic_config: Dict[str, Any],
    storage_block_name: str = "fon-data-lake"
) -> Dict[str, Any]:
    """
    Ingest articles from a single NewsAPI.ai topic
    Returns metadata about the ingestion
    """
    logger = get_run_logger()
    
    # Check if topic URI is configured
    if topic_config['uri'].startswith("YOUR_"):
        logger.warning(f"Topic URI not configured for {topic_key}, skipping")
        return {
            "topic_key": topic_key,
            "status": "skipped",
            "reason": "URI not configured",
            "items_processed": 0
        }
    
    logger.info(f"Starting ingestion for topic: {topic_config['name']}")
    
    # Create source instance
    source = NewsAPIaiTopicSource(
        topic_uri=topic_config['uri'],
        topic_name=topic_config['name'],
        topic_key=topic_key
    )
    
    # Prepare parameters
    params = {
        'max_articles': topic_config.get('max_articles', 200),
        'sort_by': topic_config.get('sort_by', 'date'),
        'days_back': topic_config.get('days_back', 1)
    }
    
    # Load storage
    storage = await AzureBlobStorageBlock.load(storage_block_name)
    
    timestamp = datetime.utcnow()
    date_path = timestamp.strftime('%Y/%m/%d')
    
    # Paths for this specific topic
    json_base_path = f"raw/{source.source_name}/{date_path}"
    parquet_path = f"processed-parquet/{source.source_name}/{date_path}/{topic_key}_{timestamp.strftime('%Y%m%d')}.parquet"
    
    # Schema for Parquet
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
        ('ingestion_timestamp', pa.timestamp('ms')),
        ('sentiment', pa.float64()),
        ('wgt', pa.float64()),
        ('image', pa.string())
    ])
    
    items_processed = 0
    batch_size = 100
    batch = []
    
    # Initialize Parquet writer buffer
    parquet_buffer = pa.BufferOutputStream()
    writer = None
    
    try:
        # Stream data from source
        async for raw_item in source.fetch_data_stream(params):
            # Transform item
            transformed = source.transform_data(raw_item)
            
            # Store individual JSON
            json_path = f"{json_base_path}/{transformed['doc_id']}.json"
            json_content = json.dumps(transformed, indent=2, default=str).encode()
            await storage.write_path(json_path, json_content)
            
            # Prepare for Parquet (extract metadata fields)
            parquet_record = {
                'doc_id': transformed['doc_id'],
                'title': transformed['title'],
                'content': transformed['content'],
                'description': transformed['description'],
                'link': transformed['link'],
                'published_at': transformed['published_at'],
                'source': transformed['source'],
                'source_type': transformed['source_type'],
                'topic_name': transformed['topic_name'],
                'topic_key': transformed['topic_key'],
                'categories': transformed['categories'],
                'ingestion_timestamp': transformed['ingestion_timestamp'],
                'sentiment': transformed.get('metadata', {}).get('sentiment'),
                'wgt': transformed.get('metadata', {}).get('wgt'),
                'image': transformed.get('metadata', {}).get('image')
            }
            
            batch.append(parquet_record)
            items_processed += 1
            
            # Write batch to Parquet when full
            if len(batch) >= batch_size:
                if writer is None:
                    writer = pq.ParquetWriter(parquet_buffer, schema)
                
                table = pa.Table.from_pylist(batch, schema=schema)
                writer.write_table(table)
                batch = []
                logger.info(f"{topic_key}: Written {items_processed} items to buffer")
        
        # Write remaining items
        if batch:
            if writer is None:
                writer = pq.ParquetWriter(parquet_buffer, schema)
            table = pa.Table.from_pylist(batch, schema=schema)
            writer.write_table(table)
        
        # Close writer and upload Parquet file
        if writer:
            writer.close()
            parquet_data = parquet_buffer.getvalue()
            await storage.write_path(parquet_path, parquet_data.to_pybytes())
        
        logger.info(f"Completed {topic_key}: {items_processed} items processed")
        
        return {
            "topic_key": topic_key,
            "topic_name": topic_config['name'],
            "status": "success",
            "items_processed": items_processed,
            "json_path": json_base_path,
            "parquet_path": parquet_path,
            "timestamp": timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing {topic_key}: {str(e)}")
        return {
            "topic_key": topic_key,
            "topic_name": topic_config['name'],
            "status": "error",
            "error": str(e),
            "items_processed": items_processed
        }

@task
async def create_combined_parquet(
    results: List[Dict[str, Any]],
    storage_block_name: str = "fon-data-lake"
) -> str:
    """
    Create a combined Parquet file from all successful topic ingestions
    """
    logger = get_run_logger()
    
    # Filter successful results
    successful_results = [r for r in results if r.get('status') == 'success' and r.get('items_processed', 0) > 0]
    
    if not successful_results:
        logger.warning("No successful topic ingestions to combine")
        return ""
    
    storage = await AzureBlobStorageBlock.load(storage_block_name)
    
    # Read all individual Parquet files and combine
    combined_tables = []
    
    for result in successful_results:
        parquet_path = result['parquet_path']
        logger.info(f"Reading {result['topic_key']} Parquet for combination")
        
        try:
            # Read the Parquet file
            parquet_bytes = await storage.read_path(parquet_path)
            table = pq.read_table(pa.BufferReader(parquet_bytes))
            combined_tables.append(table)
        except Exception as e:
            logger.error(f"Error reading {parquet_path}: {e}")
    
    if not combined_tables:
        logger.warning("No Parquet files could be read for combination")
        return ""
    
    # Combine all tables
    combined_table = pa.concat_tables(combined_tables)
    
    # Write combined Parquet
    timestamp = datetime.utcnow()
    date_path = timestamp.strftime('%Y/%m/%d')
    combined_path = f"processed-parquet/newsapi_ai_combined/{date_path}/all_topics_{timestamp.strftime('%Y%m%d')}.parquet"
    
    combined_buffer = pa.BufferOutputStream()
    writer = pq.ParquetWriter(combined_buffer, combined_table.schema)
    writer.write_table(combined_table)
    writer.close()
    
    await storage.write_path(combined_path, combined_buffer.getvalue().to_pybytes())
    
    logger.info(f"Created combined Parquet with {combined_table.num_rows} total articles")
    
    # Create artifact
    create_link_artifact(
        key="newsapi-combined-parquet",
        link=f"https://{storage.container_name}.blob.core.windows.net/{combined_path}",
        description=f"Combined {combined_table.num_rows} articles from {len(successful_results)} topics"
    )
    
    return combined_path

@flow(name="NewsAPI.ai Topics Daily Ingestion")
async def newsapi_topics_daily_flow() -> Dict[str, Any]:
    """
    Main flow that ingests all NewsAPI.ai topics in parallel
    Scheduled to run once daily
    """
    logger = get_run_logger()
    logger.info("Starting NewsAPI.ai daily topics ingestion")
    
    # Submit all topics in parallel
    futures = []
    for topic_key, config in TOPICS.items():
        logger.info(f"Submitting task for {topic_key}")
        future = ingest_single_topic.submit(topic_key, config)
        futures.append(future)
    
    # Wait for all to complete
    logger.info(f"Waiting for {len(futures)} parallel tasks to complete...")
    results = [f.result() for f in futures]
    
    # Create summary statistics
    total_articles = sum(r.get('items_processed', 0) for r in results)
    successful_topics = sum(1 for r in results if r.get('status') == 'success')
    failed_topics = sum(1 for r in results if r.get('status') == 'error')
    skipped_topics = sum(1 for r in results if r.get('status') == 'skipped')
    
    # Create rollup Parquet file
    combined_path = await create_combined_parquet(results)
    
    # Create summary artifact
    create_table_artifact(
        key="newsapi-daily-summary",
        table={
            "Date": datetime.utcnow().strftime('%Y-%m-%d'),
            "Topics Processed": successful_topics,
            "Topics Failed": failed_topics,
            "Topics Skipped": skipped_topics,
            "Total Articles": total_articles,
            "Combined Parquet": combined_path if combined_path else "N/A",
            "Timestamp": datetime.utcnow().isoformat()
        }
    )
    
    # Log individual topic results
    for result in results:
        if result.get('status') == 'success':
            logger.info(f"✅ {result['topic_key']}: {result['items_processed']} articles")
        elif result.get('status') == 'error':
            logger.error(f"❌ {result['topic_key']}: {result.get('error', 'Unknown error')}")
        else:
            logger.warning(f"⚠️  {result['topic_key']}: {result.get('reason', 'Skipped')}")
    
    return {
        "date": datetime.utcnow().strftime('%Y-%m-%d'),
        "total_articles": total_articles,
        "successful_topics": successful_topics,
        "failed_topics": failed_topics,
        "skipped_topics": skipped_topics,
        "combined_parquet": combined_path,
        "individual_results": results,
        "timestamp": datetime.utcnow().isoformat()
    }