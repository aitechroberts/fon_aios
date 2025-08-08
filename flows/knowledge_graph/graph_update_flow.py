from prefect import flow, task, get_run_logger
from prefect.transactions import transaction
from prefect_azure.blob_storage import AzureBlobStorageBlock
from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any
import json
from datetime import datetime
import os


@task(retries=2)
async def load_processed_data(file_path: str) -> List[Dict[str, Any]]:
    """Load processed data from storage"""
    storage = await AzureBlobStorageBlock.load("fon-processed-data")
    content = await storage.read_path(file_path)
    return json.loads(content)

@task
async def generate_node_embeddings(graph_data: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """Generate embeddings for graph nodes (entities)"""
    logger = get_run_logger()
    
    from langchain_openai import OpenAIEmbeddings
    from prefect.blocks.system import Secret
    
    openai_key = await Secret.load("openai-api-key")
    embeddings_model = OpenAIEmbeddings(api_key=openai_key.get())
    
    # Collect unique entities and their descriptions
    entity_texts = {}
    for item in graph_data:
        for node in item['graph']['nodes']:
            if node['id'] not in entity_texts:
                # Create text representation of entity
                text_parts = [node['id'], node['type']]
                if 'description' in node['properties']:
                    text_parts.append(node['properties']['description'])
                entity_texts[node['id']] = " - ".join(text_parts)
    
    # Generate embeddings
    logger.info(f"Generating embeddings for {len(entity_texts)} unique entities")
    
    entity_ids = list(entity_texts.keys())
    texts = list(entity_texts.values())
    
    embeddings = await embeddings_model.aembed_documents(texts)
    
    return dict(zip(entity_ids, embeddings))

@task
async def update_neo4j_with_vectors(
    graph_data: List[Dict[str, Any]],
    entity_embeddings: Dict[str, List[float]]
) -> Dict[str, int]:
    """Update Neo4j knowledge graph with vectors"""
    logger = get_run_logger()
    
    # Neo4j connection
    uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    nodes_created = 0
    relationships_created = 0
    vectors_added = 0
    
    async with driver.session() as session:
        # Create constraints if not exists
        await session.run("""
            CREATE CONSTRAINT entity_id IF NOT EXISTS
            FOR (n:Entity) REQUIRE n.id IS UNIQUE
        """)
        
        # Create vector index if not exists
        await session.run("""
            CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
            FOR (n:Entity) ON (n.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 1536,
                `vector.similarity_function`: 'cosine'
            }}
        """)
        
        # Process each document's graph
        for item in graph_data:
            doc_id = item['doc_id']
            
            # Create document node
            with transaction():
                await session.run("""
                    MERGE (d:Document {id: $doc_id})
                    SET d.source = $source,
                        d.published_at = datetime($published_at),
                        d.last_updated = datetime()
                """,
                doc_id=doc_id,
                source=item['metadata']['source'],
                published_at=item['metadata']['published_at']
                )
            
            # Create entity nodes with vectors
            for node in item['graph']['nodes']:
                entity_id = node['id']
                embedding = entity_embeddings.get(entity_id)
                
                with transaction():
                    if embedding:
                        await session.run("""
                            MERGE (n:Entity {id: $id})
                            SET n:$label
                            SET n += $properties
                            SET n.embedding = $embedding
                            SET n.last_updated = datetime()
                        """,
                        id=entity_id,
                        label=node['type'],
                        properties=node['properties'],
                        embedding=embedding
                        )
                        vectors_added += 1
                    else:
                        await session.run("""
                            MERGE (n:Entity {id: $id})
                            SET n:$label
                            SET n += $properties
                            SET n.last_updated = datetime()
                        """,
                        id=entity_id,
                        label=node['type'],
                        properties=node['properties']
                        )
                    
                    nodes_created += 1
                
                # Link to document
                with transaction():
                    await session.run("""
                        MATCH (d:Document {id: $doc_id})
                        MATCH (n:Entity {id: $entity_id})
                        MERGE (d)-[:MENTIONS]->(n)
                    """,
                    doc_id=doc_id,
                    entity_id=entity_id
                    )
            
            # Create relationships
            for rel in item['graph']['relationships']:
                with transaction():
                    await session.run(f"""
                        MATCH (a:Entity {{id: $source}})
                        MATCH (b:Entity {{id: $target}})
                        MERGE (a)-[r:{rel['type']}]->(b)
                        SET r += $properties
                        SET r.last_updated = datetime()
                        SET r.source_doc = $doc_id
                    """,
                    source=rel['source'],
                    target=rel['target'],
                    properties=rel['properties'],
                    doc_id=doc_id
                    )
                    relationships_created += 1
    
    await driver.close()
    
    logger.info(f"Neo4j update complete - Nodes: {nodes_created}, Relationships: {relationships_created}, Vectors: {vectors_added}")
    
    return {
        "nodes_created": nodes_created,
        "relationships_created": relationships_created,
        "vectors_added": vectors_added
    }

@flow(name="Knowledge Graph Update")
async def knowledge_graph_update_flow(
    processed_data_path: str
) -> Dict[str, Any]:
    """Update knowledge graph with processed data"""
    logger = get_run_logger()
    
    # Load processed data
    graph_data = await load_processed_data(processed_data_path)
    
    # Generate embeddings for entities
    entity_embeddings = await generate_node_embeddings(graph_data)
    
    # Update Neo4j with vectors
    neo4j_stats = await update_neo4j_with_vectors(graph_data, entity_embeddings)
    
    return {
        "documents_processed": len(graph_data),
        "entity_embeddings_generated": len(entity_embeddings),
        "neo4j_updates": neo4j_stats,
        "timestamp": datetime.utcnow().isoformat()
    }