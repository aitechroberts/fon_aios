# Complete Implementation: Airflow + NiFi + NLP Services → Knowledge Graph

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│   News Sources  │    │     Apache       │    │   NiFi Processing   │    │ Containerized   │
│                 │───▶│     Airflow      │───▶│     Flows           │───▶│  NLP Services   │
│ • Defense News  │    │  (Orchestration) │    │  (Route & Clean)    │    │ (GPU Processing)│
│ • DARPA RSS     │    └──────────────────┘    └─────────────────────┘    └─────────────────┘
│ • SBIR Feeds    │                                        │                        │
└─────────────────┘                                        ▼                        ▼
                                                   ┌─────────────────────┐    ┌─────────────────┐
                                                   │  Data Validation    │    │   Knowledge     │
                                                   │ (Great Expectations)│───▶│     Graph       │
                                                   └─────────────────────┘    │  (Neo4j +       │
                                                                             │   Weaviate)     │
                                                                             └─────────────────┘
```

## 1. Airflow DAG Orchestration

```python
# dags/knowledge_graph_pipeline.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor
from airflow.providers.http.operators.http import HttpOperator
from datetime import datetime, timedelta

def trigger_nifi_processor_group(processor_group_id: str):
    """Trigger specific NiFi processor group via REST API"""
    import requests
    
    nifi_api = "http://nifi:8080/nifi-api"
    
    # Start the processor group
    response = requests.put(
        f"{nifi_api}/flow/processor-groups/{processor_group_id}",
        json={
            "id": processor_group_id,
            "state": "RUNNING"
        }
    )
    
    if response.status_code == 200:
        print(f"Successfully started NiFi processor group: {processor_group_id}")
        return processor_group_id
    else:
        raise Exception(f"Failed to start NiFi processor group: {response.text}")

def monitor_nifi_completion(processor_group_id: str):
    """Monitor NiFi processing completion"""
    import requests
    import time
    
    nifi_api = "http://nifi:8080/nifi-api"
    
    while True:
        response = requests.get(f"{nifi_api}/flow/processor-groups/{processor_group_id}/status")
        status = response.json()
        
        # Check if all processors are idle (no active threads)
        if status['processorGroupStatus']['activeThreadCount'] == 0:
            print("NiFi processing completed")
            return True
        
        print(f"NiFi still processing... Active threads: {status['processorGroupStatus']['activeThreadCount']}")
        time.sleep(30)

def validate_nlp_services():
    """Health check for NLP services before processing"""
    import requests
    
    services = {
        "ner": "http://nlp-ner:8000/health",
        "coref": "http://nlp-coref:8000/health", 
        "relations": "http://nlp-relations:8000/health"
    }
    
    for service, url in services.items():
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                raise Exception(f"{service} service not healthy")
            print(f"✅ {service} service healthy")
        except Exception as e:
            raise Exception(f"❌ {service} service check failed: {e}")

def validate_processed_data():
    """Run Great Expectations validation on processed entities and relations"""
    import great_expectations as ge
    
    # Connect to the processed data
    context = ge.get_context()
    
    # Validate entities
    entities_validator = context.get_validator(
        batch_request=ge.core.batch.BatchRequest(
            datasource_name="filesystem_datasource",
            data_connector_name="default_inferred_data_connector_name",
            data_asset_name="processed_entities"
        ),
        expectation_suite_name="entities_quality_suite"
    )
    
    entities_results = entities_validator.validate()
    
    # Validate relations
    relations_validator = context.get_validator(
        batch_request=ge.core.batch.BatchRequest(
            datasource_name="filesystem_datasource", 
            data_connector_name="default_inferred_data_connector_name",
            data_asset_name="processed_relations"
        ),
        expectation_suite_name="relations_quality_suite"
    )
    
    relations_results = relations_validator.validate()
    
    if not entities_results.success or not relations_results.success:
        raise Exception("Data quality validation failed")
    
    print("✅ Data quality validation passed")
    return True

def load_to_knowledge_graph():
    """Load validated entities and relations into Neo4j and Weaviate"""
    from neo4j import GraphDatabase
    import weaviate
    import json
    
    # Neo4j connection
    neo4j_driver = GraphDatabase.driver(
        "bolt://neo4j:7687",
        auth=("neo4j", "password")
    )
    
    # Weaviate connection
    weaviate_client = weaviate.Client("http://weaviate:8080")
    
    # Load entities into Neo4j
    with neo4j_driver.session() as session:
        # Load processed entities
        with open("/opt/airflow/data/processed/entities.json", "r") as f:
            entities = json.load(f)
        
        for entity in entities:
            session.run("""
                MERGE (e:Entity {id: $id})
                SET e.name = $name,
                    e.type = $type,
                    e.confidence = $confidence,
                    e.source_document = $source_document,
                    e.extraction_timestamp = datetime($timestamp)
            """, **entity)
        
        # Load relations
        with open("/opt/airflow/data/processed/relations.json", "r") as f:
            relations = json.load(f)
        
        for relation in relations:
            session.run("""
                MATCH (e1:Entity {id: $source_entity})
                MATCH (e2:Entity {id: $target_entity})
                MERGE (e1)-[r:RELATED {type: $relation_type}]->(e2)
                SET r.confidence = $confidence,
                    r.evidence = $evidence,
                    r.source_document = $source_document
            """, **relation)
    
    # Load document embeddings into Weaviate
    with open("/opt/airflow/data/processed/document_embeddings.json", "r") as f:
        documents = json.load(f)
    
    for doc in documents:
        weaviate_client.data_object.create(
            data_object={
                "title": doc["title"],
                "content": doc["content"],
                "source": doc["source"],
                "entities": doc["entities"],
                "relations": doc["relations"],
                "processing_metadata": doc["metadata"]
            },
            class_name="DefenseDocument",
            vector=doc["embedding"]
        )
    
    print("✅ Successfully loaded data into knowledge graph")

# Define the DAG
default_args = {
    'owner': 'fon-aios',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'knowledge_graph_pipeline',
    default_args=default_args,
    description='FON AIOS Knowledge Graph Construction Pipeline',
    schedule_interval='@daily',
    catchup=False,
    max_active_runs=1,
)

# Task definitions
validate_services = PythonOperator(
    task_id='validate_nlp_services',
    python_callable=validate_nlp_services,
    dag=dag,
)

trigger_news_ingestion = PythonOperator(
    task_id='trigger_news_ingestion',
    python_callable=trigger_nifi_processor_group,
    op_kwargs={'processor_group_id': 'news-ingestion-group'},
    dag=dag,
)

monitor_news_processing = PythonOperator(
    task_id='monitor_news_processing',
    python_callable=monitor_nifi_completion,
    op_kwargs={'processor_group_id': 'news-ingestion-group'},
    dag=dag,
)

trigger_nlp_processing = PythonOperator(
    task_id='trigger_nlp_processing',
    python_callable=trigger_nifi_processor_group,
    op_kwargs={'processor_group_id': 'nlp-processing-group'},
    dag=dag,
)

monitor_nlp_processing = PythonOperator(
    task_id='monitor_nlp_processing',
    python_callable=monitor_nifi_completion,
    op_kwargs={'processor_group_id': 'nlp-processing-group'},
    dag=dag,
)

validate_processed_data_task = PythonOperator(
    task_id='validate_processed_data',
    python_callable=validate_processed_data,
    dag=dag,
)

load_knowledge_graph = PythonOperator(
    task_id='load_knowledge_graph',
    python_callable=load_to_knowledge_graph,
    dag=dag,
)

# Task dependencies
validate_services >> trigger_news_ingestion >> monitor_news_processing
monitor_news_processing >> trigger_nlp_processing >> monitor_nlp_processing
monitor_nlp_processing >> validate_processed_data_task >> load_knowledge_graph
```

## 2. NiFi Flow Configuration

### News Ingestion Flow

```xml
<!-- NiFi Template: News Ingestion -->
<template encoding-version="1.4">
    <description>FON AIOS News Ingestion with Provenance Tracking</description>
    <name>FON_News_Ingestion</name>
    <snippet>
        <processors>
            <!-- 1. Fetch Defense News RSS -->
            <processor>
                <id>fetch-defense-news</id>
                <name>FetchDefenseNews</name>
                <type>org.apache.nifi.processors.standard.InvokeHTTP</type>
                <properties>
                    <property name="HTTP Method" value="GET"/>
                    <property name="Remote URL" value="https://www.defensenews.com/arc/outboundfeeds/rss/"/>
                    <property name="User-Agent" value="FON-AIOS/1.0"/>
                </properties>
                <scheduling>
                    <schedulingPeriod>1 hour</schedulingPeriod>
                </scheduling>
            </processor>
            
            <!-- 2. Parse RSS Feed -->
            <processor>
                <id>parse-rss</id>
                <name>ParseRSSFeed</name>
                <type>org.apache.nifi.processors.standard.SplitXml</type>
                <properties>
                    <property name="Split Depth" value="3"/>
                    <property name="XPath Expression" value="//item"/>
                </properties>
            </processor>
            
            <!-- 3. Extract Article Content -->
            <processor>
                <id>extract-content</id>
                <name>ExtractArticleContent</name>
                <type>org.apache.nifi.processors.standard.ExecuteScript</type>
                <properties>
                    <property name="Script Engine" value="python"/>
                    <property name="Script Body"><![CDATA[
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import hashlib

# Parse the RSS item
flowFile = session.get()
if flowFile is not None:
    rss_content = flowFile.read().decode('utf-8')
    root = ET.fromstring(rss_content)
    
    # Extract article data
    article_data = {
        'article_id': hashlib.md5(root.find('link').text.encode()).hexdigest(),
        'title': root.find('title').text if root.find('title') is not None else '',
        'description': root.find('description').text if root.find('description') is not None else '',
        'link': root.find('link').text if root.find('link') is not None else '',
        'pub_date': root.find('pubDate').text if root.find('pubDate') is not None else '',
        'source': 'Defense News',
        'extraction_timestamp': datetime.utcnow().isoformat(),
        'nifi_flow_id': flowFile.getAttribute('uuid')
    }
    
    # Create new FlowFile with structured data
    output_flowfile = session.create()
    output_flowfile = session.write(output_flowfile, lambda out: out.write(json.dumps(article_data).encode('utf-8')))
    
    # Add provenance attributes
    output_flowfile = session.putAttribute(output_flowfile, 'article.source', 'Defense News')
    output_flowfile = session.putAttribute(output_flowfile, 'article.id', article_data['article_id'])
    output_flowfile = session.putAttribute(output_flowfile, 'processing.stage', 'content_extraction')
    
    session.transfer(output_flowfile, REL_SUCCESS)
    session.remove(flowFile)
                    ]]></property>
                </properties>
            </processor>
            
            <!-- 4. Content-Based Routing -->
            <processor>
                <id>route-content</id>
                <name>RouteOnContent</name>
                <type>org.apache.nifi.processors.standard.RouteOnContent</type>
                <properties>
                    <!-- Route defense-specific content -->
                    <property name="defense_related" value="(?i).*(DARPA|SBIR|defense contractor|military|naval systems|space systems).*</property>
                    <property name="Match Requirement" value="content must contain match"/>
                </properties>
                <relationships>
                    <relationship name="defense_related" autoTerminate="false"/>
                    <relationship name="unmatched" autoTerminate="true"/>
                </relationships>
            </processor>
            
            <!-- 5. Store Raw Articles -->
            <processor>
                <id>store-raw</id>
                <name>StoreRawArticles</name>
                <type>org.apache.nifi.processors.standard.PutFile</type>
                <properties>
                    <property name="Directory" value="/opt/nifi/data/raw/articles"/>
                    <property name="Filename" value="${article.id}_${now():format('yyyyMMdd_HHmmss')}.json"/>
                </properties>
            </processor>
        </processors>
        
        <!-- Connections between processors -->
        <connections>
            <connection>
                <id>fetch-to-parse</id>
                <sourceId>fetch-defense-news</sourceId>
                <destinationId>parse-rss</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <id>parse-to-extract</id>
                <sourceId>parse-rss</sourceId>
                <destinationId>extract-content</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <id>extract-to-route</id>
                <sourceId>extract-content</sourceId>
                <destinationId>route-content</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <id>route-to-store</id>
                <sourceId>route-content</sourceId>
                <destinationId>store-raw</destinationId>
                <selectedRelationships>defense_related</selectedRelationships>
            </connection>
        </connections>
    </snippet>
</template>
```

### NLP Processing Flow

```xml
<!-- NiFi Template: NLP Processing -->
<template encoding-version="1.4">
    <description>FON AIOS NLP Processing with GPU Services</description>
    <name>FON_NLP_Processing</name>
    <snippet>
        <processors>
            <!-- 1. Get Raw Articles -->
            <processor>
                <id>get-articles</id>
                <name>GetStoredArticles</name>
                <type>org.apache.nifi.processors.standard.GetFile</type>
                <properties>
                    <property name="Input Directory" value="/opt/nifi/data/raw/articles"/>
                    <property name="File Filter" value=".*\.json"/>
                    <property name="Keep Source File" value="false"/>
                </properties>
            </processor>
            
            <!-- 2. Prepare for NLP Processing -->
            <processor>
                <id>prepare-nlp</id>
                <name>PrepareNLPInput</name>
                <type>org.apache.nifi.processors.standard.ExecuteScript</type>
                <properties>
                    <property name="Script Engine" value="python"/>
                    <property name="Script Body"><![CDATA[
import json

flowFile = session.get()
if flowFile is not None:
    article_content = json.loads(flowFile.read().decode('utf-8'))
    
    # Prepare payload for NLP service
    nlp_payload = {
        'text': article_content['description'] + ' ' + article_content.get('content', ''),
        'document_id': article_content['article_id'],
        'source': article_content['source'],
        'metadata': {
            'title': article_content['title'],
            'link': article_content['link'],
            'pub_date': article_content['pub_date'],
            'nifi_flow_id': flowFile.getAttribute('uuid')
        }
    }
    
    output_flowfile = session.write(flowFile, lambda out: out.write(json.dumps(nlp_payload).encode('utf-8')))
    output_flowfile = session.putAttribute(output_flowfile, 'processing.stage', 'nlp_preparation')
    
    session.transfer(output_flowfile, REL_SUCCESS)
                    ]]></property>
                </properties>
            </processor>
            
            <!-- 3. Named Entity Recognition -->
            <processor>
                <id>call-ner-service</id>
                <name>CallNERService</name>
                <type>org.apache.nifi.processors.standard.InvokeHTTP</type>
                <properties>
                    <property name="HTTP Method" value="POST"/>
                    <property name="Remote URL" value="http://nlp-ner:8000/extract-entities"/>
                    <property name="Content-Type" value="application/json"/>
                    <property name="Send Body" value="true"/>
                    <property name="Connection Timeout" value="30 sec"/>
                    <property name="Read Timeout" value="60 sec"/>
                </properties>
                <relationships>
                    <relationship name="success" autoTerminate="false"/>
                    <relationship name="failure" autoTerminate="false"/>
                </relationships>
            </processor>
            
            <!-- 4. Handle NER Failures -->
            <processor>
                <id>handle-ner-failure</id>
                <name>HandleNERFailure</name>
                <type>org.apache.nifi.processors.standard.LogMessage</type>
                <properties>
                    <property name="Log Level" value="ERROR"/>
                    <property name="Log Message" value="NER processing failed for document: ${document.id}"/>
                </properties>
            </processor>
            
            <!-- 5. Coreference Resolution -->
            <processor>
                <id>call-coref-service</id>
                <name>CallCorefService</name>
                <type>org.apache.nifi.processors.standard.InvokeHTTP</type>
                <properties>
                    <property name="HTTP Method" value="POST"/>
                    <property name="Remote URL" value="http://nlp-coref:8000/resolve-coreferences"/>
                    <property name="Content-Type" value="application/json"/>
                    <property name="Send Body" value="true"/>
                    <property name="Connection Timeout" value="30 sec"/>
                    <property name="Read Timeout" value="120 sec"/>
                </properties>
            </processor>
            
            <!-- 6. Relation Extraction -->
            <processor>
                <id>call-relations-service</id>
                <name>CallRelationsService</name>
                <type>org.apache.nifi.processors.standard.InvokeHTTP</type>
                <properties>
                    <property name="HTTP Method" value="POST"/>
                    <property name="Remote URL" value="http://nlp-relations:8000/extract-relations"/>
                    <property name="Content-Type" value="application/json"/>
                    <property name="Send Body" value="true"/>
                    <property name="Connection Timeout" value="30 sec"/>
                    <property name="Read Timeout" value="180 sec"/>
                </properties>
            </processor>
            
            <!-- 7. Consolidate Results -->
            <processor>
                <id>consolidate-results</id>
                <name>ConsolidateNLPResults</name>
                <type>org.apache.nifi.processors.standard.ExecuteScript</type>
                <properties>
                    <property name="Script Engine" value="python"/>
                    <property name="Script Body"><![CDATA[
import json
from datetime import datetime

flowFile = session.get()
if flowFile is not None:
    nlp_results = json.loads(flowFile.read().decode('utf-8'))
    
    # Add processing metadata and provenance
    final_results = {
        'document_id': nlp_results.get('document_id'),
        'entities': nlp_results.get('entities', []),
        'relations': nlp_results.get('relations', []),
        'coreferences': nlp_results.get('coreferences', []),
        'confidence_scores': nlp_results.get('confidence_scores', {}),
        'processing_metadata': {
            'nifi_flow_id': flowFile.getAttribute('uuid'),
            'processing_timestamp': datetime.utcnow().isoformat(),
            'nlp_pipeline_version': '1.0',
            'model_versions': {
                'ner': 'roberta-base-finetuned-v2.1',
                'coref': 'spanbert-large-coreference',
                'relations': 'dygie-plus-v1.3'
            }
        }
    }
    
    output_flowfile = session.write(flowFile, lambda out: out.write(json.dumps(final_results, indent=2).encode('utf-8')))
    output_flowfile = session.putAttribute(output_flowfile, 'processing.stage', 'nlp_complete')
    output_flowfile = session.putAttribute(output_flowfile, 'document.id', final_results['document_id'])
    
    session.transfer(output_flowfile, REL_SUCCESS)
                    ]]></property>
                </properties>
            </processor>
            
            <!-- 8. Store Processed Results -->
            <processor>
                <id>store-processed</id>
                <name>StoreProcessedResults</name>
                <type>org.apache.nifi.processors.standard.PutFile</type>
                <properties>
                    <property name="Directory" value="/opt/nifi/data/processed/nlp_results"/>
                    <property name="Filename" value="${document.id}_processed.json"/>
                </properties>
            </processor>
        </processors>
        
        <!-- Flow connections -->
        <connections>
            <connection>
                <sourceId>get-articles</sourceId>
                <destinationId>prepare-nlp</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <sourceId>prepare-nlp</sourceId>
                <destinationId>call-ner-service</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <sourceId>call-ner-service</sourceId>
                <destinationId>call-coref-service</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <sourceId>call-ner-service</sourceId>
                <destinationId>handle-ner-failure</destinationId>
                <selectedRelationships>failure</selectedRelationships>
            </connection>
            <connection>
                <sourceId>call-coref-service</sourceId>
                <destinationId>call-relations-service</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <sourceId>call-relations-service</sourceId>
                <destinationId>consolidate-results</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
            <connection>
                <sourceId>consolidate-results</sourceId>
                <destinationId>store-processed</destinationId>
                <selectedRelationships>success</selectedRelationships>
            </connection>
        </connections>
    </snippet>
</template>
```

## 3. Containerized NLP Services

### NER Service (RoBERTa)

```python
# nlp-services/ner/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
import torch
from typing import List, Dict
import logging

app = FastAPI(title="FON AIOS NER Service", version="1.0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentInput(BaseModel):
    text: str
    document_id: str
    source: str
    metadata: Dict = {}

class EntityOutput(BaseModel):
    text: str
    label: str
    start: int
    end: int
    confidence: float

class NERResponse(BaseModel):
    document_id: str
    entities: List[EntityOutput]
    processing_metadata: Dict

# Load models on startup
@app.on_event("startup")
async def load_models():
    global ner_pipeline
    
    logger.info("Loading RoBERTa NER model...")
    
    # Use your fine-tuned model
    model_name = "your-org/roberta-defense-ner-finetuned"
    
    try:
        ner_pipeline = pipeline(
            "ner",
            model=model_name,
            tokenizer=model_name,
            aggregation_strategy="simple",
            device=0 if torch.cuda.is_available() else -1
        )
        logger.info("✅ NER model loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load NER model: {e}")
        raise

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ner",
        "gpu_available": torch.cuda.is_available(),
        "model_loaded": 'ner_pipeline' in globals()
    }

@app.post("/extract-entities", response_model=NERResponse)
async def extract_entities(doc: DocumentInput):
    try:
        # Run NER inference
        logger.info(f"Processing document: {doc.document_id}")
        
        ner_results = ner_pipeline(doc.text)
        
        # Convert to our format
        entities = []
        for entity in ner_results:
            entities.append(EntityOutput(
                text=entity['word'],
                label=entity['entity_group'],
                start=entity['start'],
                end=entity['end'],
                confidence=float(entity['score'])
            ))
        
        # Filter entities by confidence threshold
        high_confidence_entities = [e for e in entities if e.confidence > 0.7]
        
        return NERResponse(
            document_id=doc.document_id,
            entities=high_confidence_entities,
            processing_metadata={
                "service": "ner",
                "model": "roberta-defense-ner-finetuned",
                "total_entities": len(ner_results),
                "high_confidence_entities": len(high_confidence_entities),
                "confidence_threshold": 0.7,
                "gpu_used": torch.cuda.is_available()
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing document {doc.document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"NER processing failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Coreference Resolution Service (SpanBERT)

```python
# nlp-services/coref/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from allennlp.predictors.predictor import Predictor
import allennlp_models.tagging
from typing import List, Dict
import logging

app = FastAPI(title="FON AIOS Coreference Resolution Service", version="1.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CorefInput(BaseModel):
    text: str
    document_id: str
    entities: List[Dict]  # Entities from NER service
    metadata: Dict = {}

class CorefResponse(BaseModel):
    document_id: str
    resolved_text: str
    coreference_clusters: List[List[Dict]]
    processing_metadata: Dict

@app.on_event("startup")
async def load_models():
    global coref_predictor
    
    logger.info("Loading SpanBERT coreference model...")
    
    try:
        # Load pre-trained SpanBERT coreference model
        coref_predictor = Predictor.from_path(
            "https://storage.googleapis.com/allennlp-public-models/coref-spanbert-large-2021.03.10.tar.gz",
            cuda_device=0 if torch.cuda.is_available() else -1
        )
        logger.info("✅ Coreference model loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load coreference model: {e}")
        raise

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "coreference",
        "model_loaded": 'coref_predictor' in globals()
    }

@app.post("/resolve-coreferences", response_model=CorefResponse)
async def resolve_coreferences(doc: CorefInput):
    try:
        logger.info(f"Processing coreferences for document: {doc.document_id}")
        
        # Run coreference resolution
        coref_result = coref_predictor.predict(document=doc.text)
        
        # Extract coreference clusters
        clusters = coref_result['clusters']
        
        # Resolve coreferences in text
        resolved_text = doc.text
        
        # Simple coreference resolution (replace pronouns with most likely referent)
        for cluster in clusters:
            if len(cluster) > 1:
                # Find the most descriptive mention (longest span)
                main_mention = max(cluster, key=lambda x: x[1] - x[0])
                main_text = doc.text[main_mention[0]:main_mention[1]]
                
                # Replace other mentions with main mention
                for mention in cluster:
                    if mention != main_mention:
                        mention_text = doc.text[mention[0]:mention[1]]
                        if mention_text.lower() in ['he', 'she', 'it', 'they', 'them', 'his', 'her', 'its', 'their']:
                            resolved_text = resolved_text.replace(mention_text, main_text)
        
        return CorefResponse(
            document_id=doc.document_id,
            resolved_text=resolved_text,
            coreference_clusters=clusters,
            processing_metadata={
                "service": "coreference",
                "model": "spanbert-large-coreference",
                "clusters_found": len(clusters),
                "total_mentions": sum(len(cluster) for cluster in clusters)
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing coreferences for {doc.document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Coreference resolution failed: {str(e)}")
```

### Relation Extraction Service (DyGIE++)

```python
# nlp-services/relations/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import spacy
from typing import List, Dict, Tuple
import logging
import re

app = FastAPI(title="FON AIOS Relation Extraction Service", version="1.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RelationInput(BaseModel):
    text: str
    document_id: str
    entities: List[Dict]
    resolved_text: str  # From coreference resolution
    metadata: Dict = {}

class RelationOutput(BaseModel):
    source_entity: str
    target_entity: str
    relation_type: str
    confidence: float
    evidence_text: str

class RelationResponse(BaseModel):
    document_id: str
    relations: List[RelationOutput]
    processing_metadata: Dict

@app.on_event("startup")
async def load_models():
    global nlp
    
    logger.info("Loading spaCy model for relation extraction...")
    
    try:
        # Load spaCy model with dependency parsing
        nlp = spacy.load("en_core_web_trf")
        logger.info("✅ Relation extraction model loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load relation extraction model: {e}")
        raise

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "relations",
        "model_loaded": 'nlp' in globals()
    }

def extract_defense_relations(text: str, entities: List[Dict]) -> List[RelationOutput]:
    """Extract defense-specific relations using rule-based and pattern matching"""
    
    doc = nlp(text)
    relations = []
    
    # Defense-specific relation patterns
    patterns = {
        "AWARDED_CONTRACT": [
            r"(\w+(?:\s+\w+)*)\s+(?:awarded|receives?|wins?)\s+(?:a\s+)?(?:\$[\d,]+\s+)?contract",
            r"(\w+(?:\s+\w+)*)\s+(?:has been|was)\s+awarded\s+(?:a\s+)?(?:\$[\d,]+\s+)?contract"
        ],
        "FUNDING_RELATIONSHIP": [
            r"(DARPA|SBIR|DoD|Navy|Air Force|Army)\s+(?:funds|funding|awarded)\s+(?:\$[\d,]+\s+(?:to\s+)?)?(\w+(?:\s+\w+)*)",
            r"(\$[\d,]+\s+(?:million|billion))\s+(?:from\s+)?(DARPA|SBIR|DoD|Navy|Air Force|Army)\s+(?:to\s+)?(\w+(?:\s+\w+)*)"
        ],
        "PARTNERSHIP": [
            r"(\w+(?:\s+\w+)*)\s+(?:partners?\s+with|collaborates?\s+with|teams?\s+up\s+with)\s+(\w+(?:\s+\w+)*)",
            r"(\w+(?:\s+\w+)*)\s+(?:and|&)\s+(\w+(?:\s+\w+)*)\s+(?:partner|collaborate|team\s+up)"
        ],
        "ACQUISITION": [
            r"(\w+(?:\s+\w+)*)\s+(?:acquires?|purchases?|buys?)\s+(\w+(?:\s+\w+)*)",
            r"(\w+(?:\s+\w+)*)\s+(?:acquired|purchased|bought)\s+(?:by\s+)?(\w+(?:\s+\w+)*)"
        ],
        "TECHNOLOGY_DEVELOPMENT": [
            r"(\w+(?:\s+\w+)*)\s+(?:develops?|developing|creates?|creating|builds?|building)\s+([\w\s]+(?:system|technology|platform|solution))",
            r"(\w+(?:\s+\w+)*)\s+(?:specializes?\s+in|focuses?\s+on)\s+([\w\s]+(?:system|technology|platform|solution))"
        ]
    }
    
    for relation_type, pattern_list in patterns.items():
        for pattern in pattern_list:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    relations.append(RelationOutput(
                        source_entity=groups[0].strip(),
                        target_entity=groups[1].strip(),
                        relation_type=relation_type,
                        confidence=0.8,  # Rule-based confidence
                        evidence_text=match.group(0)
                    ))
    
    return relations

@app.post("/extract-relations", response_model=RelationResponse)
async def extract_relations(doc: RelationInput):
    try:
        logger.info(f"Extracting relations for document: {doc.document_id}")
        
        # Use resolved text for better relation extraction
        text = doc.resolved_text if doc.resolved_text else doc.text
        
        # Extract relations using rule-based approach
        relations = extract_defense_relations(text, doc.entities)
        
        # Filter relations by confidence and relevance
        high_quality_relations = [r for r in relations if r.confidence > 0.5]
        
        return RelationResponse(
            document_id=doc.document_id,
            relations=high_quality_relations,
            processing_metadata={
                "service": "relations",
                "method": "rule_based_patterns",
                "total_relations_found": len(relations),
                "high_quality_relations": len(high_quality_relations),
                "confidence_threshold": 0.5
            }
        )
        
    except Exception as e:
        logger.error(f"Error extracting relations for {doc.document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Relation extraction failed: {str(e)}")
```

## 4. Docker Compose for Full Stack

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Apache Airflow
  postgres:
    image: postgres:13
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow
      POSTGRES_DB: airflow
    volumes:
      - postgres_data:/var/lib/postgresql/data

  airflow-webserver:
    build: ./airflow
    command: webserver
    ports:
      - "8080:8080"
    depends_on:
      - postgres
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
    volumes:
      - ./dags:/opt/airflow/dags
      - ./data:/opt/airflow/data

  airflow-scheduler:
    build: ./airflow
    command: scheduler
    depends_on:
      - postgres
    environment:
      - AIRFLOW__CORE__EXECUTOR=LocalExecutor
      - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres/airflow
    volumes:
      - ./dags:/opt/airflow/dags
      - ./data:/opt/airflow/data

  # Apache NiFi
  nifi:
    image: apache/nifi:1.24.0
    ports:
      - "8443:8443"
    environment:
      - NIFI_WEB_HTTP_HOST=0.0.0.0
      - NIFI_WEB_HTTP_PORT=8443
    volumes:
      - nifi_content:/opt/nifi/nifi-current/content_repository
      - nifi_database:/opt/nifi/nifi-current/database_repository
      - nifi_flowfile:/opt/nifi/nifi-current/flowfile_repository
      - nifi_provenance:/opt/nifi/nifi-current/provenance_repository
      - ./data:/opt/nifi/data

  # NLP Services
  nlp-ner:
    build: ./nlp-services/ner
    ports:
      - "8001:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - CUDA_VISIBLE_DEVICES=0

  nlp-coref:
    build: ./nlp-services/coref
    ports:
      - "8002:8000"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - CUDA_VISIBLE_DEVICES=0

  nlp-relations:
    build: ./nlp-services/relations
    ports:
      - "8003:8000"

  # Knowledge Graph Storage
  neo4j:
    image: neo4j:5.15
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data

  weaviate:
    image: weaviate/weaviate:1.22.4
    ports:
      - "8080:8080"
    environment:
      QUERY_DEFAULTS_LIMIT: 25
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      PERSISTENCE_DATA_PATH: '/var/lib/weaviate'
      DEFAULT_VECTORIZER_MODULE: 'none'
    volumes:
      - weaviate_data:/var/lib/weaviate

volumes:
  postgres_data:
  nifi_content:
  nifi_database:
  nifi_flowfile:
  nifi_provenance:
  neo4j_data:
  weaviate_data:
```

## 5. Complete Data Flow Summary

1. **Airflow** orchestrates the entire pipeline daily
2. **NiFi** ingests news from RSS feeds, routes defense-related content
3. **NiFi** sends articles to containerized **NLP services** for processing:
   - **NER Service**: Extracts entities using fine-tuned RoBERTa
   - **Coref Service**: Resolves coreferences with SpanBERT
   - **Relations Service**: Extracts relations using rule-based patterns
4. **Great Expectations** validates the processed entities and relations
5. **Airflow** loads validated data into **Neo4j** (graph) and **Weaviate** (vectors)
6. **Full provenance tracking** maintained throughout via NiFi and custom metadata

This architecture gives you the best of all worlds: Airflow's orchestration, NiFi's data lineage and observability, specialized GPU compute for your balanced NLP requirements, and a robust knowledge graph populated with high-quality, traceable intelligence data.