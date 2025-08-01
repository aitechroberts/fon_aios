from prefect import flow, task, get_run_logger
from prefect.blocks.system import Secret
from prefect.artifacts import create_table_artifact, create_markdown_artifact
from prefect.transactions import transaction
from prefect_azure.blob_storage import AzureBlobStorageBlock
from prefect.task_runners import ConcurrentTaskRunner
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents import Document
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchField, SearchFieldDataType,
    VectorSearch, VectorSearchProfile, HnswAlgorithmConfiguration
)
from azure.core.credentials import AzureKeyCredential
from typing import List, Dict, Any
import json
import duckdb
import os
from datetime import datetime

@task(retries=2, retry_delay_seconds=300)
async def load_documents_from_parquet(parquet_paths: List[str]) -> List[Document]:
    """Load documents from Parquet files using DuckDB"""
    logger = get_run_logger()
    
    # Initialize DuckDB with Azure extension
    conn = duckdb.connect()
    conn.execute("INSTALL azure")
    conn.execute("LOAD azure")
    
    # Configure Azure credentials
    storage_account = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
    storage_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
    
    conn.execute(f"""
        CREATE SECRET azure_secret (
            TYPE AZURE,
            CONNECTION_STRING 'DefaultEndpointsProtocol=https;AccountName={storage_account};AccountKey={storage_key}'
        )
    """)
    
    documents = []
    
    for path in parquet_paths:
        try:
            # Query Parquet file directly from Azure
            azure_path = f"azure://fon-data-lake/{path}"
            query = f"""
                SELECT doc_id, title, content, description, link, 
                       published_at, source, source_type, categories
                FROM parquet_scan('{azure_path}')
                WHERE content IS NOT NULL AND content != ''
            """
            
            results = conn.execute(query).fetchall()
            
            for row in results:
                doc = Document(
                    page_content=f"{row[1]}\n\n{row[2]}",  # title + content
                    metadata={
                        'id': row[0],
                        'title': row[1],
                        'description': row[3],
                        'link': row[4],
                        'published_at': row[5],
                        'source': row[6],
                        'source_type': row[7],
                        'categories': row[8] or []
                    }
                )
                documents.append(doc)
                
        except Exception as e:
            logger.error(f"Error loading {path}: {str(e)}")
    
    conn.close()
    logger.info(f"Loaded {len(documents)} documents from {len(parquet_paths)} Parquet files")
    return documents

@task(
    retries=3,
    retry_delay_seconds=600,
    tags=["gpu-required"],
    timeout_seconds=3600
)
async def extract_graph_elements_with_embeddings(
    documents: List[Document],
    batch_size: int = 10
) -> List[Dict[str, Any]]:
    """Extract entities, relationships, and generate embeddings"""
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
            "Organization", "Location", "Event", "Contract",
            "Agency", "Program", "System"
        ],
        allowed_relationships=[
            "PARTNERS_WITH", "COMPETES_WITH", "EMPLOYS",
            "DEVELOPS", "USES", "FUNDED_BY", "ACQUIRED",
            "LOCATED_IN", "PARTICIPATES_IN", "AWARDS",
            "SUPPLIES", "INTEGRATES_WITH"
        ],
        node_properties=["description", "type", "industry", "sector"],
        relationship_properties=["since", "value", "description", "status"],
        strict_mode=False
    )
    
    # Initialize embeddings model
    embeddings_model = OpenAIEmbeddings(api_key=openai_key.get())
    
    # Process in batches
    all_enriched_docs = []
    
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} of {len(documents)//batch_size + 1}")
        
        try:
            # Extract graph elements
            graph_docs = await transformer.aconvert_to_graph_documents(batch)
            
            # Generate embeddings for the batch
            texts = [doc.page_content for doc in batch]
            embeddings = await embeddings_model.aembed_documents(texts)
            
            # Combine everything
            for doc, graph_doc, embedding in zip(batch, graph_docs, embeddings):
                # Extract entities list for Azure Search
                entities = []
                entity_types = {}
                
                for node in graph_doc.nodes:
                    entities.append(node.id)
                    entity_type = node.type
                    if entity_type not in entity_types:
                        entity_types[entity_type] = []
                    entity_types[entity_type].append(node.id)
                
                enriched_doc = {
                    'doc_id': doc.metadata['id'],
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'embedding': embedding,
                    'entities': entities,
                    'entities_by_type': entity_types,
                    'graph': {
                        'nodes': [
                            {
                                'id': node.id,
                                'type': node.type,
                                'properties': node.properties
                            } for node in graph_doc.nodes
                        ],
                        'relationships': [
                            {
                                'source': rel.source.id,
                                'target': rel.target.id,
                                'type': rel.type,
                                'properties': rel.properties
                            } for rel in graph_doc.relationships
                        ]
                    }
                }
                
                all_enriched_docs.append(enriched_doc)
                
        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")
            # Continue with next batch
    
    # Create processing summary
    total_entities = sum(len(doc['entities']) for doc in all_enriched_docs)
    total_relationships = sum(len(doc['graph']['relationships']) for doc in all_enriched_docs)
    
    create_table_artifact(
        key="nlp-processing-summary",
        table={
            "Documents Processed": len(documents),
            "Enriched Documents": len(all_enriched_docs),
            "Total Entities Extracted": total_entities,
            "Total Relationships": total_relationships,
            "Average Entities per Doc": total_entities / len(all_enriched_docs) if all_enriched_docs else 0,
            "Processing Timestamp": datetime.utcnow().isoformat()
        }
    )
    
    return all_enriched_docs

@task
async def create_azure_search_index() -> str:
    """Create or update Azure AI Search index with vector support"""
    logger = get_run_logger()
    
    service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
    admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "fon-defense-intelligence")
    
    endpoint = f"https://{service_name}.search.windows.net"
    credential = AzureKeyCredential(admin_key)
    
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    
    # Define the index schema
    fields = [
        SimpleField(name="doc_id", type=SearchFieldDataType.String, key=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SearchField(name="source", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="source_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="published_at", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        
        # Entity fields for filtering
        SearchField(name="entities", type=SearchFieldDataType.Collection(SearchFieldDataType.String), 
                   filterable=True, facetable=True),
        SearchField(name="companies", type=SearchFieldDataType.Collection(SearchFieldDataType.String), 
                   filterable=True, facetable=True),
        SearchField(name="technologies", type=SearchFieldDataType.Collection(SearchFieldDataType.String), 
                   filterable=True, facetable=True),
        SearchField(name="agencies", type=SearchFieldDataType.Collection(SearchFieldDataType.String), 
                   filterable=True, facetable=True),
        
        # Vector field
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="hnsw-profile"
        ),
    ]
    
    # Configure vector search
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
    
    # Create the index
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search
    )
    
    # Create or update
    try:
        index_client.create_or_update_index(index)
        logger.info(f"Created/updated index: {index_name}")
    except Exception as e:
        logger.error(f"Error creating index: {str(e)}")
        raise
    
    return index_name

@task
async def index_to_azure_search(
    enriched_docs: List[Dict[str, Any]],
    index_name: str
) -> int:
    """Index documents to Azure AI Search with vectors and entities"""
    logger = get_run_logger()
    
    service_name = os.getenv("AZURE_SEARCH_SERVICE_NAME")
    admin_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
    
    endpoint = f"https://{service_name}.search.windows.net"
    credential = AzureKeyCredential(admin_key)
    
    search_client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential
    )
    
    documents_indexed = 0
    batch_size = 100
    
    for i in range(0, len(enriched_docs), batch_size):
        batch = enriched_docs[i:i+batch_size]
        
        # Prepare documents for indexing
        search_docs = []
        for doc in batch:
            # Extract entity types
            companies = doc['entities_by_type'].get('Company', [])
            technologies = doc['entities_by_type'].get('Technology', [])
            agencies = doc['entities_by_type'].get('Agency', []) + doc['entities_by_type'].get('Organization', [])
            
            search_doc = {
                'doc_id': doc['doc_id'],
                'content': doc['content'],
                'title': doc['metadata'].get('title', ''),
                'source': doc['metadata'].get('source', ''),
                'source_type': doc['metadata'].get('source_type', ''),
                'published_at': doc['metadata'].get('published_at'),
                'entities': doc['entities'],
                'companies': companies,
                'technologies': technologies,
                'agencies': agencies,
                'content_vector': doc['embedding']
            }
            search_docs.append(search_doc)
        
        # Index with transaction
        with transaction():
            result = search_client.upload_documents(documents=search_docs)
            documents_indexed += len([r for r in result if r.succeeded])
    
    logger.info(f"Indexed {documents_indexed} documents to Azure Search")
    return documents_indexed

@task
async def store_processed_data(
    enriched_data: List[Dict[str, Any]]
) -> str:
    """Store processed data with graph info back to ADLS"""
    logger = get_run_logger()
    storage = await AzureBlobStorageBlock.load("fon-processed-data")
    
    timestamp = datetime.utcnow()
    file_path = f"nlp_processed/{timestamp.strftime('%Y/%m/%d')}/processed_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
    
    with transaction():
        # Remove embeddings before storing (they're in Azure Search)
        storage_data = []
        for doc in enriched_data:
            storage_doc = {
                'doc_id': doc['doc_id'],
                'metadata': doc['metadata'],
                'entities': doc['entities'],
                'entities_by_type': doc['entities_by_type'],
                'graph': doc['graph']
            }
            storage_data.append(storage_doc)
        
        await storage.write_path(
            path=file_path,
            content=json.dumps(storage_data, indent=2).encode()
        )
    
    # Create artifact
    blob_url = f"https://{storage.container_name}.blob.core.windows.net/{file_path}"
    create_link_artifact(
        key="processed-data-location",
        link=blob_url,
        description=f"Stored {len(enriched_data)} processed documents with graph data"
    )
    
    return file_path

@flow(
    name="NLP Processing Pipeline",
    task_runner=ConcurrentTaskRunner(),
    persist_result=True,
    result_storage="fon-processed-data"
)
async def nlp_processing_pipeline(
    parquet_paths: List[str],
    batch_size: int = 10
) -> Dict[str, Any]:
    """Main NLP processing flow using LangChain GraphTransformer and Azure AI Search"""
    logger = get_run_logger()
    logger.info(f"Starting NLP processing for {len(parquet_paths)} Parquet files")
    
    # Load documents from Parquet
    documents = await load_documents_from_parquet(parquet_paths)
    
    if not documents:
        logger.warning("No documents to process")
        return {"status": "no_data", "processed": 0}
    
    # Create or update Azure Search index
    index_name = await create_azure_search_index()
    
    # Extract graph elements and generate embeddings using GPU
    enriched_docs = await extract_graph_elements_with_embeddings.with_options(
        infrastructure="gpu-nlp-infra"
    )(documents, batch_size)
    
    # Index to Azure AI Search
    indexed_count = await index_to_azure_search(enriched_docs, index_name)
    
    # Store processed data (without embeddings)
    output_path = await store_processed_data(enriched_docs)
    
    return {
        "status": "success",
        "processed": len(documents),
        "enriched": len(enriched_docs),
        "indexed": indexed_count,
        "output_path": output_path,
        "timestamp": datetime.utcnow().isoformat()
    }