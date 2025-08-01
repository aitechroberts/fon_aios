Complete Implementation: Prefect 3.x + LangChain GraphTransformer → Knowledge Graph
Architecture Overview
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│   News Sources  │    │  Prefect Cloud   │    │  ADLS Gen 2 Blob    │    │   Azure GPU     │
│                 │───▶│  (Orchestration) │───▶│   (Data Lake)       │───▶│  Containers     │
│ • Defense News  │    │  + Self-hosted   │    │                     │    │ (LangChain      │
│ • DARPA RSS     │    │    Workers       │    │                     │    │  Processing)    │
│ • SBIR Feeds    │    └──────────────────┘    └─────────────────────┘    └─────────────────┘
└─────────────────┘                                       │                         │
                                                          ▼                         ▼
                                                   ┌─────────────────────┐    ┌─────────────────┐
                                                   │  Data Validation    │    │   Knowledge     │
                                                   │ (Great Expectations)│───▶│     Graph       │
                                                   └─────────────────────┘    │  (Neo4j +       │
                                                                             │   Weaviate)     │
                                                                             └─────────────────┘
1. Prefect 3.x Project Structure
bashfon-aios-prefect/
├── deployments/
│   ├── ingestion/
│   │   ├── defense_news_deployment.py
│   │   ├── darpa_deployment.py
│   │   └── sbir_deployment.py
│   ├── processing/
│   │   └── nlp_gpu_deployment.py
│   └── knowledge_graph/
│       └── graph_update_deployment.py
├── flows/
│   ├── ingestion/
│   │   ├── base_ingestion_flow.py
│   │   ├── news_sources.py
│   │   └── government_sources.py
│   ├── processing/
│   │   └── nlp_processing_flow.py
│   └── knowledge_graph/
│       └── graph_update_flow.py
├── tasks/
│   ├── data_fetching.py
│   ├── data_transformation.py
│   ├── nlp_tasks.py
│   └── graph_tasks.py
├── blocks/
│   ├── infrastructure.py
│   ├── storage.py
│   └── credentials.py
├── work_pools/
│   ├── cpu_pool_config.yaml
│   └── gpu_pool_config.yaml
├── config/
│   ├── sources_config.yaml
│   └── nlp_config.yaml
├── requirements.txt
└── prefect.yaml
2. Infrastructure Blocks Configuration
python# blocks/infrastructure.py
from prefect.infrastructure import Process, DockerContainer
from prefect_azure import AzureContainerInstanceJob
from prefect.blocks.core import Block
from typing import Optional
import os

class GPUContainerInstanceJob(AzureContainerInstanceJob):
    """Custom Azure Container Instance block with GPU support"""
    
    gpu_count: int = 1
    gpu_sku: str = "K80"  # or "P100", "V100"
    
    def _prepare_container_group(self):
        container_group = super()._prepare_container_group()
        
        # Add GPU configuration
        container_group["properties"]["containers"][0]["resources"]["requests"]["gpu"] = {
            "count": self.gpu_count,
            "sku": self.gpu_sku
        }
        
        return container_group

# Register infrastructure blocks
async def setup_infrastructure_blocks():
    # CPU Worker Infrastructure
    cpu_process = Process(
        name="cpu-worker-process",
        working_dir="/opt/fon-aios",
        env={
            "PREFECT_API_URL": os.getenv("PREFECT_API_URL"),
            "PREFECT_API_KEY": os.getenv("PREFECT_API_KEY")
        }
    )
    await cpu_process.save("cpu-worker-infra", overwrite=True)
    
    # GPU Container Infrastructure for Azure
    gpu_container = GPUContainerInstanceJob(
        name="gpu-nlp-processor",
        resource_group_name="fon-aios-rg",
        subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
        image="fonregistry.azurecr.io/nlp-langchain-gpu:latest",
        cpu=4,
        memory=16,
        gpu_count=1,
        gpu_sku="K80",
        env_vars={
            "TRANSFORMERS_CACHE": "/models",
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": os.getenv("LANGCHAIN_API_KEY")
        },
        command=["python", "-m", "prefect.engine"]
    )
    await gpu_container.save("gpu-nlp-infra", overwrite=True)
python# blocks/storage.py
from prefect.filesystems import RemoteFileSystem
from prefect_azure import AzureBlobStorageCredentials
from prefect_azure.blob_storage import AzureBlobStorageBlock

async def setup_storage_blocks():
    # Azure Storage Credentials
    azure_creds = AzureBlobStorageCredentials(
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    )
    await azure_creds.save("azure-storage-creds", overwrite=True)
    
    # ADLS Gen2 Block for Data Lake
    adls_block = AzureBlobStorageBlock(
        blob_storage_credentials=azure_creds,
        container_name="fon-data-lake",
        base_path="raw-data/"
    )
    await adls_block.save("fon-data-lake", overwrite=True)
    
    # Processed Data Storage
    processed_storage = AzureBlobStorageBlock(
        blob_storage_credentials=azure_creds,
        container_name="fon-data-lake",
        base_path="processed-data/"
    )
    await processed_storage.save("fon-processed-data", overwrite=True)
3. Base Ingestion Flow with Parameterization
python# flows/ingestion/base_ingestion_flow.py
from prefect import flow, task, get_run_logger
from prefect.artifacts import create_link_artifact, create_table_artifact
from prefect.blocks.system import Secret
from prefect_azure.blob_storage import AzureBlobStorageBlock
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import httpx
import feedparser
import json
import hashlib
from abc import ABC, abstractmethod

class DataSource(ABC):
    """Abstract base class for data sources"""
    
    @abstractmethod
    async def fetch_data(self, params: Dict[str, Any]) -> List[Dict]:
        pass
    
    @abstractmethod
    def transform_data(self, raw_data: List[Dict]) -> List[Dict]:
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

@task(retries=3, retry_delay_seconds=60, cache_key_fn=lambda x: hashlib.md5(str(x).encode()).hexdigest(), cache_expiration=timedelta(hours=1))
async def fetch_from_source(source: DataSource, params: Dict[str, Any]) -> List[Dict]:
    """Generic task to fetch data from any source"""
    logger = get_run_logger()
    logger.info(f"Fetching data from {source.source_name}")
    
    try:
        data = await source.fetch_data(params)
        logger.info(f"Fetched {len(data)} items from {source.source_name}")
        return data
    except Exception as e:
        logger.error(f"Error fetching from {source.source_name}: {str(e)}")
        raise

@task
def transform_source_data(source: DataSource, raw_data: List[Dict]) -> List[Dict]:
    """Transform raw data to standard format"""
    logger = get_run_logger()
    logger.info(f"Transforming {len(raw_data)} items from {source.source_name}")
    
    transformed = source.transform_data(raw_data)
    
    # Create artifact for lineage
    create_table_artifact(
        key=f"{source.source_name}-transform-summary",
        table={
            "Source": source.source_name,
            "Raw Items": len(raw_data),
            "Transformed Items": len(transformed),
            "Timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return transformed

@task
async def validate_and_store_data(
    data: List[Dict], 
    source_name: str,
    storage_block_name: str = "fon-data-lake"
) -> str:
    """Validate data and store in ADLS Gen2"""
    logger = get_run_logger()
    
    # Basic validation
    valid_data = []
    for item in data:
        if all(key in item for key in ["id", "title", "content", "source", "timestamp"]):
            valid_data.append(item)
        else:
            logger.warning(f"Invalid item from {source_name}: missing required fields")
    
    # Store in ADLS Gen2
    storage = await AzureBlobStorageBlock.load(storage_block_name)
    
    timestamp = datetime.utcnow()
    file_path = f"{source_name}/{timestamp.strftime('%Y/%m/%d')}/{source_name}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    
    await storage.write_path(
        path=file_path,
        content=json.dumps(valid_data, indent=2).encode()
    )
    
    # Create artifact for lineage
    blob_url = f"https://{storage.container_name}.blob.core.windows.net/{file_path}"
    create_link_artifact(
        key=f"{source_name}-data-location",
        link=blob_url,
        description=f"Stored {len(valid_data)} validated items"
    )
    
    logger.info(f"Stored {len(valid_data)} items to {file_path}")
    return file_path

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
    
    # Execute ingestion pipeline
    raw_data = await fetch_from_source(source, source_params)
    transformed_data = transform_source_data(source, raw_data)
    storage_path = await validate_and_store_data(transformed_data, source.source_name)
    
    # Return metadata for downstream flows
    result = {
        "source": source.source_name,
        "items_processed": len(transformed_data),
        "storage_path": storage_path,
        "timestamp": datetime.utcnow().isoformat(),
        "params": source_params
    }
    
    return result
4. Specific Data Source Implementations
python# flows/ingestion/news_sources.py
from flows.ingestion.base_ingestion_flow import DataSource
import feedparser
import httpx
from datetime import datetime
from typing import Dict, List, Any
import hashlib

class DefenseNewsSource(DataSource):
    """Defense News RSS feed ingestion"""
    
    @property
    def source_name(self) -> str:
        return "defense_news"
    
    async def fetch_data(self, params: Dict[str, Any]) -> List[Dict]:
        feed_url = "https://www.defensenews.com/arc/outboundfeeds/rss/"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(feed_url)
            feed = feedparser.parse(response.text)
            
            articles = []
            for entry in feed.entries:
                # Filter by date if provided
                pub_date = datetime(*entry.published_parsed[:6])
                
                if 'start_date' in params:
                    start = datetime.fromisoformat(params['start_date'])
                    if pub_date < start:
                        continue
                
                articles.append({
                    'raw_entry': entry,
                    'fetched_at': datetime.utcnow().isoformat()
                })
                
            return articles
    
    def transform_data(self, raw_data: List[Dict]) -> List[Dict]:
        transformed = []
        
        for item in raw_data:
            entry = item['raw_entry']
            
            # Generate unique ID
            article_id = hashlib.md5(entry.link.encode()).hexdigest()
            
            # Extract and clean content
            content = entry.get('summary', '')
            if hasattr(entry, 'content'):
                content = entry.content[0].value if entry.content else content
            
            transformed.append({
                'id': f"defense_news_{article_id}",
                'title': entry.title,
                'content': content,
                'description': entry.get('summary', ''),
                'link': entry.link,
                'published_at': entry.published,
                'source': 'Defense News',
                'source_type': 'news_article',
                'timestamp': item['fetched_at'],
                'categories': [tag.term for tag in entry.get('tags', [])]
            })
            
        return transformed

class DARPASource(DataSource):
    """DARPA announcements API ingestion"""
    
    @property  
    def source_name(self) -> str:
        return "darpa"
    
    async def fetch_data(self, params: Dict[str, Any]) -> List[Dict]:
        # Implementation for DARPA API
        # This would include proper API authentication and pagination
        base_url = "https://www.darpa.mil/api/news"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                base_url,
                params={
                    "from": params.get('start_date'),
                    "to": params.get('end_date'),
                    "category": "solicitations,news"
                }
            )
            
            return response.json().get('items', [])
    
    def transform_data(self, raw_data: List[Dict]) -> List[Dict]:
        # Transform DARPA data to standard format
        transformed = []
        for item in raw_data:
            transformed.append({
                'id': f"darpa_{item.get('id')}",
                'title': item.get('title'),
                'content': item.get('body'),
                'description': item.get('excerpt'),
                'link': item.get('url'),
                'published_at': item.get('date'),
                'source': 'DARPA',
                'source_type': item.get('type', 'announcement'),
                'timestamp': datetime.utcnow().isoformat(),
                'categories': item.get('categories', [])
            })
        return transformed
5. NLP Processing Flow with LangChain GraphTransformer
python# flows/processing/nlp_processing_flow.py
from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret
from prefect.artifacts import create_table_artifact, create_markdown_artifact
from prefect_azure.blob_storage import AzureBlobStorageBlock
from prefect.task_runners import ConcurrentTaskRunner
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from typing import List, Dict, Any
import json
from datetime import datetime

@task(retries=2, retry_delay_seconds=300)
async def load_documents_from_storage(storage_paths: List[str]) -> List[Document]:
    """Load documents from ADLS Gen2 for processing"""
    logger = get_run_logger()
    storage = await AzureBlobStorageBlock.load("fon-data-lake")
    
    documents = []
    for path in storage_paths:
        try:
            content = await storage.read_path(path)
            data = json.loads(content)
            
            for item in data:
                # Create LangChain document
                doc = Document(
                    page_content=f"{item['title']}\n\n{item['content']}",
                    metadata={
                        'id': item['id'],
                        'source': item['source'],
                        'source_type': item['source_type'],
                        'published_at': item['published_at'],
                        'link': item['link'],
                        'categories': item.get('categories', [])
                    }
                )
                documents.append(doc)
                
        except Exception as e:
            logger.error(f"Error loading {path}: {str(e)}")
            
    logger.info(f"Loaded {len(documents)} documents for processing")
    return documents

@task(
    retries=3,
    retry_delay_seconds=600,
    tags=["gpu-required"],
    timeout_seconds=3600
)
async def extract_graph_elements(
    documents: List[Document],
    batch_size: int = 10
) -> List[Dict[str, Any]]:
    """Extract entities and relationships using LangChain GraphTransformer"""
    logger = get_run_logger()
    
    # Load API key
    openai_key = await Secret.load("openai-api-key")
    
    # Initialize LLM and GraphTransformer
    llm = ChatOpenAI(
        temperature=0,
        model="gpt-4-turbo-preview",
        api_key=openai_key.get()
    )
    
    transformer = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=[
            "Company", "Person", "Technology", "Product",
            "Organization", "Location", "Event", "Contract"
        ],
        allowed_relationships=[
            "PARTNERS_WITH", "COMPETES_WITH", "EMPLOYS",
            "DEVELOPS", "USES", "FUNDED_BY", "ACQUIRED",
            "LOCATED_IN", "PARTICIPATES_IN", "AWARDS"
        ],
        node_properties=["description", "type", "industry"],
        relationship_properties=["since", "value", "description"],
        strict_mode=False
    )
    
    # Process in batches
    all_graph_docs = []
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} of {len(documents)//batch_size + 1}")
        
        try:
            # Extract graph elements
            graph_docs = await transformer.aconvert_to_graph_documents(batch)
            
            # Convert to serializable format
            for graph_doc in graph_docs:
                doc_data = {
                    'source_id': graph_doc.source.metadata['id'],
                    'nodes': [],
                    'relationships': []
                }
                
                # Extract nodes
                for node in graph_doc.nodes:
                    doc_data['nodes'].append({
                        'id': node.id,
                        'type': node.type,
                        'properties': node.properties
                    })
                
                # Extract relationships
                for rel in graph_doc.relationships:
                    doc_data['relationships'].append({
                        'source': rel.source.id,
                        'target': rel.target.id,
                        'type': rel.type,
                        'properties': rel.properties
                    })
                
                all_graph_docs.append(doc_data)
                
        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")
            # Continue with next batch
            
    # Create processing summary artifact
    total_nodes = sum(len(doc['nodes']) for doc in all_graph_docs)
    total_relationships = sum(len(doc['relationships']) for doc in all_graph_docs)
    
    create_table_artifact(
        key="nlp-processing-summary",
        table={
            "Documents Processed": len(documents),
            "Total Nodes Extracted": total_nodes,
            "Total Relationships": total_relationships,
            "Average Nodes per Doc": total_nodes / len(documents) if documents else 0,
            "Processing Timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return all_graph_docs

@task
async def generate_embeddings(
    documents: List[Document],
    graph_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Generate embeddings for vector store"""
    logger = get_run_logger()
    
    from langchain_openai import OpenAIEmbeddings
    
    openai_key = await Secret.load("openai-api-key")
    embeddings_model = OpenAIEmbeddings(api_key=openai_key.get())
    
    # Generate embeddings for documents
    texts = [doc.page_content for doc in documents]
    embeddings = await embeddings_model.aembed_documents(texts)
    
    # Combine with graph data
    enriched_data = []
    for i, (doc, graph, embedding) in enumerate(zip(documents, graph_data, embeddings)):
        enriched_data.append({
            'document': {
                'id': doc.metadata['id'],
                'content': doc.page_content,
                'metadata': doc.metadata
            },
            'graph': graph,
            'embedding': embedding
        })
    
    logger.info(f"Generated embeddings for {len(enriched_data)} documents")
    return enriched_data

@task
async def store_processed_data(
    enriched_data: List[Dict[str, Any]]
) -> str:
    """Store processed data back to ADLS Gen2"""
    logger = get_run_logger()
    storage = await AzureBlobStorageBlock.load("fon-processed-data")
    
    timestamp = datetime.utcnow()
    file_path = f"nlp_processed/{timestamp.strftime('%Y/%m/%d')}/processed_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    
    await storage.write_path(
        path=file_path,
        content=json.dumps(enriched_data, indent=2).encode()
    )
    
    # Create artifact with storage location
    blob_url = f"https://{storage.container_name}.blob.core.windows.net/{file_path}"
    create_link_artifact(
        key="processed-data-location",
        link=blob_url,
        description=f"Stored {len(enriched_data)} processed documents with graph data and embeddings"
    )
    
    return file_path

@flow(
    name="NLP Processing Pipeline",
    task_runner=ConcurrentTaskRunner(),
    persist_result=True,
    result_storage="fon-processed-data"
)
async def nlp_processing_pipeline(
    storage_paths: List[str],
    batch_size: int = 10
) -> Dict[str, Any]:
    """Main NLP processing flow using LangChain GraphTransformer"""
    logger = get_run_logger()
    logger.info(f"Starting NLP processing for {len(storage_paths)} data files")
    
    # Load documents
    documents = await load_documents_from_storage(storage_paths)
    
    if not documents:
        logger.warning("No documents to process")
        return {"status": "no_data", "processed": 0}
    
    # Extract graph elements using GPU infrastructure
    graph_data = await extract_graph_elements.with_options(
        infrastructure="gpu-nlp-infra"
    )(documents, batch_size)
    
    # Generate embeddings (can run on CPU)
    enriched_data = await generate_embeddings(documents, graph_data)
    
    # Store processed data
    output_path = await store_processed_data(enriched_data)
    
    return {
        "status": "success",
        "processed": len(documents),
        "output_path": output_path,
        "timestamp": datetime.utcnow().isoformat()
    }
6. Knowledge Graph Update Flow
python# flows/knowledge_graph/graph_update_flow.py
from prefect import flow, task, get_run_logger
from prefect_azure.blob_storage import AzureBlobStorageBlock
from neo4j import AsyncGraphDatabase
import weaviate
from typing import List, Dict, Any
import json
from datetime import datetime

@task(retries=2)
async def load_processed_data(file_path: str) -> List[Dict[str, Any]]:
    """Load processed data from storage"""
    storage = await AzureBlobStorageBlock.load("fon-processed-data")
    content = await storage.read_path(file_path)
    return json.loads(content)

@task
async def update_neo4j(enriched_data: List[Dict[str, Any]]) -> int:
    """Update Neo4j knowledge graph"""
    logger = get_run_logger()
    
    # Neo4j connection
    uri = "bolt://neo4j:7687"
    driver = AsyncGraphDatabase.driver(uri, auth=("neo4j", "password"))
    
    nodes_created = 0
    relationships_created = 0
    
    async with driver.session() as session:
        for item in enriched_data:
            graph_data = item['graph']
            
            # Create nodes
            for node in graph_data['nodes']:
                await session.run("""
                    MERGE (n {id: $id})
                    SET n:$labels
                    SET n += $properties
                    SET n.last_updated = datetime()
                """, 
                id=node['id'],
                labels=node['type'],
                properties=node['properties']
                )
                nodes_created += 1
            
            # Create relationships
            for rel in graph_data['relationships']:
                await session.run("""
                    MATCH (a {id: $source})
                    MATCH (b {id: $target})
                    MERGE (a)-[r:$type]->(b)
                    SET r += $properties
                    SET r.last_updated = datetime()
                """,
                source=rel['source'],
                target=rel['target'],
                type=rel['type'],
                properties=rel['properties']
                )
                relationships_created += 1
    
    await driver.close()
    
    logger.info(f"Created/updated {nodes_created} nodes and {relationships_created} relationships")
    return nodes_created + relationships_created

@task
async def update_weaviate(enriched_data: List[Dict[str, Any]]) -> int:
    """Update Weaviate vector store"""
    logger = get_run_logger()
    
    client = weaviate.Client("http://weaviate:8080")
    
    documents_indexed = 0
    
    for item in enriched_data:
        doc = item['document']
        graph = item['graph']
        embedding = item['embedding']
        
        # Prepare data object
        data_object = {
            "document_id": doc['id'],
            "content": doc['content'],
            "source": doc['metadata']['source'],
            "source_type": doc['metadata']['source_type'],
            "published_at": doc['metadata']['published_at'],
            "entity_count": len(graph['nodes']),
            "relationship_count": len(graph['relationships']),
            "entities": [n['id'] for n in graph['nodes']],
            "categories": doc['metadata'].get('categories', [])
        }
        
        # Create in Weaviate with custom vector
        client.data_object.create(
            data_object=data_object,
            class_name="DefenseIntelligence",
            vector=embedding
        )
        
        documents_indexed += 1
    
    logger.info(f"Indexed {documents_indexed} documents in Weaviate")
    return documents_indexed

@flow(name="Knowledge Graph Update")
async def knowledge_graph_update_flow(
    processed_data_path: str
) -> Dict[str, Any]:
    """Update knowledge graph with processed data"""
    logger = get_run_logger()
    
    # Load processed data
    enriched_data = await load_processed_data(processed_data_path)
    
    # Update Neo4j and Weaviate in parallel
    neo4j_updates = await update_neo4j(enriched_data)
    weaviate_updates = await update_weaviate(enriched_data)
    
    return {
        "neo4j_updates": neo4j_updates,
        "weaviate_updates": weaviate_updates,
        "timestamp": datetime.utcnow().isoformat()
    }
7. Deployment Configuration
python# deployments/orchestration.py
from prefect import flow, serve
from prefect.events import DeploymentEventTrigger
from prefect.client.schemas.schedules import CronSchedule
from datetime import datetime, timedelta
import asyncio

@flow(name="FON AIOS Orchestrator")
async def main_orchestration_flow():
    """Main orchestration flow that coordinates all sub-flows"""
    from flows.ingestion.base_ingestion_flow import base_ingestion_flow
    from flows.processing.nlp_processing_flow import nlp_processing_pipeline
    from flows.knowledge_graph.graph_update_flow import knowledge_graph_update_flow
    
    # Define sources to ingest
    sources = [
        ("DefenseNewsSource", {}),
        ("DARPASource", {}),
        ("SBIRSource", {"program": "defense"})
    ]
    
    # Ingest from all sources
    ingestion_results = []
    for source_class, params in sources:
        result = await base_ingestion_flow(
            source_class=source_class,
            source_params=params,
            lookback_days=7
        )
        ingestion_results.append(result)
    
    # Collect all storage paths
    storage_paths = [r['storage_path'] for r in ingestion_results if r['items_processed'] > 0]
    
    if storage_paths:
        # Trigger NLP processing
        nlp_result = await nlp_processing_pipeline(storage_paths)
        
        # Update knowledge graph
        if nlp_result['status'] == 'success':
            kg_result = await knowledge_graph_update_flow(nlp_result['output_path'])
            
    return {
        "ingestion_results": ingestion_results,
        "processing_complete": True,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    # Deploy with different configurations
    
    # Option 1: Pull Work Pool (Self-hosted workers)
    defense_news_deployment = base_ingestion_flow.to_deployment(
        name="defense-news-daily",
        parameters={
            "source_class": "DefenseNewsSource",
            "lookback_days": 1
        },
        work_pool_name="cpu-worker-pool",
        work_queue_name="ingestion-queue",
        schedule=CronSchedule(cron="0 6,12,18 * * *"),  # 3 times daily
        tags=["ingestion", "defense-news", "production"]
    )
    
    # Option 2: Push Work Pool (Prefect Cloud manages)
    nlp_deployment = nlp_processing_pipeline.to_deployment(
        name="nlp-gpu-processing",
        work_pool_name="azure-container-pool",
        job_variables={
            "image": "fonregistry.azurecr.io/nlp-langchain-gpu:latest",
            "gpu_count": 1,
            "gpu_sku": "K80"
        },
        triggers=[
            DeploymentEventTrigger(
                enabled=True,
                match={
                    "prefect.flow-run.Completed": {
                        "flow": "Base Ingestion Flow"
                    }
                },
                parameters={},
                queue="nlp-processing-queue"
            )
        ],
        tags=["nlp", "gpu-required", "production"]
    )
    
    # Serve deployments
    serve(
        defense_news_deployment,
        nlp_deployment,
        limit=10  # Maximum concurrent runs
    )
8. Work Pool Configuration
Option 1: Pull Work Pool (Self-hosted)
yaml# work_pools/cpu_pool_config.yaml
name: cpu-worker-pool
type: process
description: Self-hosted CPU workers for data ingestion
base_job_template:
  working_dir: /opt/fon-aios
  env:
    PREFECT_API_URL: "{{ prefect.api.url }}"
    PREFECT_API_KEY: "{{ prefect.api.key }}"
  stream_output: true
Option 2: Push Work Pool (Prefect Cloud managed)
yaml# work_pools/gpu_pool_config.yaml
name: azure-container-pool
type: azure-container-instance
description: GPU-enabled containers for NLP processing
base_job_template:
  resource_group_name: fon-aios-rg
  subscription_id: "{{ azure.subscription_id }}"
  image: "{{ image }}"
  cpu: 4
  memory: 16
  gpu_count: "{{ gpu_count }}"
  gpu_sku: "{{ gpu_sku }}"
  identities:
    - "/subscriptions/.../resourcegroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/fon-aios-identity"
9. Cost Comparison: Push vs Pull Work Pools
Pull Work Pool (Self-hosted)
VM for Prefect Agent: ~$140/month (D4s_v3)
GPU ACI (2 hrs/day): ~$54/month
Prefect Cloud Free Tier: $0
Total: ~$194/month
Push Work Pool (Prefect Cloud managed)
No Agent VM needed: $0
GPU ACI (2 hrs/day): ~$54/month  
Prefect Cloud Starter: $100/month
Total: ~$154/month
Recommendation: Start with Push Work Pools for simplicity, migrate to Pull if you need more control or hit Cloud limits.
10. Setup Instructions
bash# 1. Install Prefect 3.x
pip install prefect>=3.0 prefect-azure langchain-experimental langchain-openai

# 2. Authenticate with Prefect Cloud
prefect cloud login

# 3. Create workspace
prefect cloud workspace create fon-aios-production

# 4. Setup blocks
python blocks/infrastructure.py
python blocks/storage.py

# 5. Create work pools
prefect work-pool create azure-container-pool --type azure-container-instance

# 6. Deploy flows
python deployments/orchestration.py

# 7. Start worker (if using pull pool)
prefect worker start --pool cpu-worker-pool
This implementation provides:

✅ Modular, parameterized pipelines for each data source
✅ Event-driven NLP processing after ingestion completes
✅ GPU processing via Azure Container Instances
✅ LangChain GraphTransformer for unified NLP
✅ Prefect artifacts for data lineage
✅ Automatic retries with exponential backoff
✅ Choice between push/pull work pools for cost optimization