from prefect import flow, task, get_run_logger
from prefect.artifacts import create_link_artifact, create_table_artifact
from prefect.blocks.system import Secret
from prefect.transactions import transaction
from prefect_azure.blob_storage import AzureBlobStorageBlock
from azure.storage.blob import BlobClient
from typing import Dict, List, Optional, Any, Iterator
from datetime import datetime, timedelta
import httpx
import feedparser
import json
import hashlib
import pyarrow as pa
import pyarrow.parquet as pq
import os
import itertools
from abc import ABC, abstractmethod

class DataSource(ABC):
    """Abstract base class for data sources"""
    
    @abstractmethod
    async def fetch_data_stream(self, params: Dict[str, Any]) -> Iterator[Dict]:
        """Stream data instead of loading all at once"""
        pass
    
    @abstractmethod
    def transform_data(self, raw_item: Dict) -> Dict:
        """Transform a single item"""
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

@task(retries=3, retry_delay_seconds=60)
async def stream_and_store_data(
    source: DataSource,
    params: Dict[str, Any],
    storage_block_name: str = "fon-data-lake"
) -> Dict[str, Any]:
    """Stream data and store as both JSON (for provenance) and Parquet (for bulk processing)"""
    logger = get_run_logger()
    storage = await AzureBlobStorageBlock.load(storage_block_name)
    
    timestamp = datetime.utcnow()
    date_path = timestamp.strftime('%Y/%m/%d')
    
    # Paths for both formats
    json_base_path = f"raw/{source.source_name}/{date_path}"
    parquet_path = f"processed-parquet/{source.source_name}/{date_path}/{source.source_name}_{timestamp.strftime('%Y%m%d')}.parquet"
    
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
        ('categories', pa.list_(pa.string())),
        ('ingestion_timestamp', pa.timestamp('ms'))
    ])
    
    items_processed = 0
    batch_size = 100  # Write Parquet in chunks
    batch = []
    
    # Initialize Parquet writer
    parquet_buffer = pa.BufferOutputStream()
    writer = None
    
    try:
        # Stream data from source
        async for raw_item in source.fetch_data_stream(params):
            # Transform item
            transformed = source.transform_data(raw_item)
            
            # Store individual JSON with transaction
            with transaction():
                json_path = f"{json_base_path}/{transformed['id']}.json"
                json_content = json.dumps(transformed, indent=2).encode()
                await storage.write_path(json_path, json_content)
            
            # Add to batch for Parquet
            batch.append(transformed)
            items_processed += 1
            
            # Write batch to Parquet when full
            if len(batch) >= batch_size:
                if writer is None:
                    writer = pq.ParquetWriter(parquet_buffer, schema)
                
                # Convert batch to Arrow table
                table = pa.Table.from_pylist(batch, schema=schema)
                writer.write_table(table)
                batch = []
                
                logger.info(f"Written {items_processed} items to Parquet buffer")
        
        # Write remaining items
        if batch:
            if writer is None:
                writer = pq.ParquetWriter(parquet_buffer, schema)
            table = pa.Table.from_pylist(batch, schema=schema)
            writer.write_table(table)
        
        # Close writer and upload Parquet file
        if writer:
            writer.close()
            
            with transaction():
                parquet_data = parquet_buffer.getvalue()
                await storage.write_path(parquet_path, parquet_data.to_pybytes())
        
        # Create artifacts
        create_table_artifact(
            key=f"{source.source_name}-ingestion-summary",
            table={
                "Source": source.source_name,
                "Items Processed": items_processed,
                "JSON Path": json_base_path,
                "Parquet Path": parquet_path,
                "Timestamp": timestamp.isoformat()
            }
        )
        
        logger.info(f"Completed ingestion: {items_processed} items stored")
        
        return {
            "source": source.source_name,
            "items_processed": items_processed,
            "json_path": json_base_path,
            "parquet_path": parquet_path,
            "timestamp": timestamp.isoformat(),
            "params": params
        }
        
    except Exception as e:
        logger.error(f"Error in stream_and_store_data: {str(e)}")
        raise

@flow(name="Base Ingestion Flow", persist_result=True)
async def base_ingestion_flow(
    source_class: str,
    source_params: Optional[Dict[str, Any]] = None,
    lookback_days: int = 7
) -> Dict[str, Any]:
    """Parameterized base flow for any data source"""
    logger = get_run_logger()
    
    # Dynamic source loading
    module = __import__(f"flows.ingestion.{source_class}", fromlist=[source_class])
    SourceClass = getattr(module, source_class)
    source = SourceClass()
    
    # Default parameters
    if source_params is None:
        source_params = {
            "start_date": (datetime.utcnow() - timedelta(days=lookback_days)).isoformat(),
            "end_date": datetime.utcnow().isoformat()
        }
    
    # Execute streaming ingestion pipeline
    result = await stream_and_store_data(source, source_params)
    
    return result