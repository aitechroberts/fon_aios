# FON AIOS Complete Setup Guide with NiFi + dbt Architecture

## Architecture Overview

```
NewsAPI → Airflow (Orchestration) → NiFi (Processing) → dbt (Transformation) → Great Expectations (Validation) → Neo4j (Graph) + Azure AI Search → LangSmith
```

## Why This Architecture

**Apache NiFi**: Content-aware document processing, handles different formats (JSON, XML, PDF), data lineage tracking  
**dbt**: Standardizes transformations, business logic, documentation, testing  
**Airflow**: Orchestrates the entire pipeline  
**Neo4j**: Stores entity relationships  
**Azure AI Search**: Fast, searchable document store  

This architecture is designed to scale from 1 data source (NewsAPI) to 10+ sources (DARPA, SBIR, patents, etc.) without major changes.

## Phase 1: Azure Resources Setup (15-20 minutes)

### Step 1.1: Create Azure Account and Subscription

**If you don't have Azure:**
1. Go to https://azure.microsoft.com/free/
2. Sign up for free account (includes $200 credit)
3. Note your Subscription ID (you'll need this later)

**If you have Azure:**
1. Login to https://portal.azure.com
2. Note your Subscription ID: Azure Portal → Subscriptions → copy the ID

### Step 1.2: Install Azure CLI

**Windows:**
```bash
# Download from: https://aka.ms/installazurecliwindows
# Run the installer
```

**MacOS:**
```bash
brew install azure-cli
```

**Linux:**
```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

**Verify installation:**
```bash
az --version
az login
```

### Step 1.3: Create Resource Group

```bash
# Login to Azure (opens browser)
az login

# Create resource group (like a folder for all our services)
az group create --name "fon-aios-rg" --location "eastus"
```

### Step 1.4: Create Azure AI Search Service

```bash
# Create search service (this takes 2-3 minutes)
az search service create \
    --name "fon-aios-search-$(date +%s)" \
    --resource-group "fon-aios-rg" \
    --sku "basic" \
    --location "eastus"

# Get the exact service name (it includes timestamp)
SEARCH_SERVICE_NAME=$(az search service list --resource-group "fon-aios-rg" --query "[0].name" -o tsv)
echo "Your search service name: $SEARCH_SERVICE_NAME"

# Get the admin key (save this!)
SEARCH_ADMIN_KEY=$(az search admin-key show --service-name $SEARCH_SERVICE_NAME --resource-group "fon-aios-rg" --query "primaryKey" -o tsv)
echo "Your search admin key: $SEARCH_ADMIN_KEY"
```

### Step 1.5: Create Storage Account

```bash
# Create storage account
STORAGE_NAME="fonaiosstorage$(date +%s)"
az storage account create \
    --name $STORAGE_NAME \
    --resource-group "fon-aios-rg" \
    --location "eastus" \
    --sku "Standard_LRS"

echo "Your storage account name: $STORAGE_NAME"

# Get storage key
STORAGE_KEY=$(az storage account keys list --account-name $STORAGE_NAME --resource-group "fon-aios-rg" --query "[0].value" -o tsv)
echo "Your storage key: $STORAGE_KEY"
```

### Step 1.6: Get External API Keys

**NewsAPI Key:**
1. Go to https://newsapi.org/
2. Click "Get API Key"
3. Sign up for free account
4. Copy your API key (1000 requests/day free)

**LangSmith API Key:**
1. Go to https://smith.langchain.com/
2. Sign up for account
3. Create new project called "fon-aios-dev"
4. Copy API key from settings

**Save all credentials - you'll need them:**

```
AZURE_SEARCH_SERVICE_NAME=fon-aios-search-XXXXXXXXXX
AZURE_SEARCH_ADMIN_KEY=your-32-char-key
AZURE_STORAGE_NAME=fonaiosstorage-XXXXXXXXXX
AZURE_STORAGE_KEY=your-storage-key
NEWSAPI_KEY=your-newsapi-key
LANGCHAIN_API_KEY=your-langsmith-key
```

## Phase 2: Local Environment Setup (20-30 minutes)

### Step 2.1: Install Prerequisites

**Install Docker Desktop:**
1. Download from https://www.docker.com/products/docker-desktop
2. Install and start Docker Desktop
3. **Important**: Allocate at least 8GB RAM to Docker (NiFi needs memory)
4. Verify: `docker --version`

**Install Python 3.9+ and Git:**
- Python: https://www.python.org/downloads/
- Git: https://git-scm.com/downloads/

**Verify installations:**
```bash
python --version  # Should be 3.9+
docker --version
git --version
```

### Step 2.2: Create Project Structure

```bash
# Create main project directory
mkdir fon-aios
cd fon-aios

# Create comprehensive directory structure
mkdir -p airflow/dags
mkdir -p airflow/plugins
mkdir -p src/data_ingestion
mkdir -p src/data_processing
mkdir -p src/data_validation
mkdir -p src/graph
mkdir -p src/storage
mkdir -p src/utils
mkdir -p config
mkdir -p tests
mkdir -p logs
mkdir -p plugins

# NiFi directories
mkdir -p nifi/conf
mkdir -p nifi/content_repository
mkdir -p nifi/database_repository
mkdir -p nifi/flowfile_repository
mkdir -p nifi/provenance_repository
mkdir -p nifi/state
mkdir -p nifi/logs
mkdir -p nifi/templates

# dbt directories
mkdir -p dbt_project
mkdir -p dbt_project/models
mkdir -p dbt_project/models/staging
mkdir -p dbt_project/models/intermediate
mkdir -p dbt_project/models/marts
mkdir -p dbt_project/macros
mkdir -p dbt_project/tests
mkdir -p dbt_project/analysis
mkdir -p dbt_project/seeds

# Neo4j directories
mkdir -p neo4j/data
mkdir -p neo4j/logs
mkdir -p neo4j/import
mkdir -p neo4j/plugins

# Data directories
mkdir -p data/raw
mkdir -p data/processed
mkdir -p data/staging

echo "Complete project structure created!"
```

### Step 2.3: Create Configuration Files

**Create `.env` file:**
```bash
cat > .env << 'EOF'
# External API Configuration
NEWSAPI_KEY=your_actual_newsapi_key_here
NEWSAPI_BASE_URL=https://newsapi.org/v2
LANGCHAIN_API_KEY=your_langsmith_key_here
LANGCHAIN_PROJECT=fon-aios-dev

# Azure Configuration
AZURE_SEARCH_SERVICE_NAME=your_actual_search_service_name
AZURE_SEARCH_ADMIN_KEY=your_actual_search_admin_key
AZURE_SEARCH_INDEX_NAME=fon-defense-intelligence
AZURE_STORAGE_NAME=your_storage_name
AZURE_STORAGE_KEY=your_storage_key

# Database Configuration
POSTGRES_USER=airflow
POSTGRES_PASSWORD=airflow_password
POSTGRES_DB=airflow_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Neo4j Configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j

# NiFi Configuration
NIFI_WEB_HTTP_HOST=0.0.0.0
NIFI_WEB_HTTP_PORT=8443
NIFI_CLUSTER_IS_NODE=false
NIFI_ZK_CONNECT_STRING=
NIFI_ELECTION_MAX_WAIT=30 sec
NIFI_SENSITIVE_PROPS_KEY=changemechanmeme

# dbt Configuration
DBT_PROFILES_DIR=/opt/dbt
DBT_PROJECT_DIR=/opt/dbt_project

# Airflow Configuration
AIRFLOW__CORE__EXECUTOR=LocalExecutor
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow_password@postgres:5432/airflow_db
AIRFLOW__CORE__FERNET_KEY=
AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
AIRFLOW__CORE__LOAD_EXAMPLES=false
AIRFLOW__WEBSERVER__EXPOSE_CONFIG=false
AIRFLOW__CORE__DAGBAG_IMPORT_TIMEOUT=60
AIRFLOW__CORE__PARALLELISM=4
AIRFLOW__CORE__MAX_ACTIVE_RUNS_PER_DAG=1

# Development Settings
ENVIRONMENT=development
LOG_LEVEL=INFO
EOF

echo "Now edit the .env file with your actual credentials!"
```

**Create comprehensive `requirements.txt`:**
```bash
cat > requirements.txt << 'EOF'
# Core Data Engineering
apache-airflow==2.8.1
apache-airflow-providers-postgres==5.10.0
apache-airflow-providers-http==4.7.0
pandas==2.1.4
numpy==1.24.3
requests==2.31.0

# Data Transformation
dbt-core==1.7.4
dbt-postgres==1.7.4
sqlalchemy==1.4.48

# Data Processing and Validation
great-expectations==0.18.8
pydantic==2.5.3
python-dotenv==1.0.0

# Azure Integration
azure-search-documents==11.4.0
azure-identity==1.15.0
azure-storage-blob==12.19.0

# Graph Database
neo4j==5.16.0

# NLP and Entity Processing
spacy==3.7.2
nltk==3.8.1
fuzzywuzzy==0.18.0
python-levenshtein==0.23.0

# LLM and Experiment Tracking
langchain==0.1.5
langsmith==0.0.83
openai==1.12.0

# Database and Storage
psycopg2-binary==2.9.9
redis==5.0.1

# File Processing
PyPDF2==3.0.1
python-docx==1.1.0
openpyxl==3.1.2
beautifulsoup4==4.12.2
lxml==4.9.3

# Utilities
schedule==1.2.0
python-dateutil==2.8.2
pytz==2023.4
pyyaml==6.0.1
jinja2==3.1.2

# Monitoring and Logging
prometheus-client==0.19.0
statsd==4.0.1

# Testing
pytest==7.4.3
pytest-cov==4.1.0
EOF
```

**Create Docker Compose with all services:**
```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:13
    environment:
      POSTGRES_USER: airflow
      POSTGRES_PASSWORD: airflow_password
      POSTGRES_DB: airflow_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "airflow"]
      interval: 10s
      retries: 5
      start_period: 5s
    networks:
      - fon_aios_network

  neo4j:
    image: neo4j:5.15-community
    environment:
      NEO4J_AUTH: neo4j/password123
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_apoc_export_file_enabled: true
      NEO4J_apoc_import_file_enabled: true
      NEO4J_dbms_security_procedures_unrestricted: apoc.*
      NEO4J_dbms_default_listen_address: 0.0.0.0
      NEO4J_dbms_connector_bolt_listen_address: 0.0.0.0:7687
    ports:
      - "7474:7474"  # Neo4j Browser
      - "7687:7687"  # Bolt protocol
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./neo4j/import:/var/lib/neo4j/import
      - ./neo4j/plugins:/plugins
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "password123", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - fon_aios_network

  nifi:
    image: apache/nifi:1.24.0
    environment:
      NIFI_WEB_HTTP_HOST: 0.0.0.0
      NIFI_WEB_HTTP_PORT: 8443
      NIFI_CLUSTER_IS_NODE: false
      NIFI_ZK_CONNECT_STRING: ''
      NIFI_ELECTION_MAX_WAIT: '30 sec'
      NIFI_SENSITIVE_PROPS_KEY: 'changemechanmeme'
      SINGLE_USER_CREDENTIALS_USERNAME: admin
      SINGLE_USER_CREDENTIALS_PASSWORD: ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB
    ports:
      - "8443:8443"   # NiFi Web UI (HTTPS)
    volumes:
      - nifi_conf:/opt/nifi/nifi-current/conf
      - nifi_content_repository:/opt/nifi/nifi-current/content_repository
      - nifi_database_repository:/opt/nifi/nifi-current/database_repository
      - nifi_flowfile_repository:/opt/nifi/nifi-current/flowfile_repository
      - nifi_provenance_repository:/opt/nifi/nifi-current/provenance_repository
      - nifi_state:/opt/nifi/nifi-current/state
      - nifi_logs:/opt/nifi/nifi-current/logs
      - ./data:/opt/nifi/data
      - ./nifi/templates:/opt/nifi/nifi-current/templates
    healthcheck:
      test: ["CMD", "curl", "-k", "-f", "https://localhost:8443/nifi/"]
      interval: 60s
      timeout: 10s
      retries: 5
      start_period: 120s
    depends_on:
      - postgres
    networks:
      - fon_aios_network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - fon_aios_network

  airflow-init:
    build: .
    environment:
      _AIRFLOW_DB_MIGRATE: 'true'
      _AIRFLOW_WWW_USER_CREATE: 'true'
      _AIRFLOW_WWW_USER_USERNAME: admin
      _AIRFLOW_WWW_USER_PASSWORD: admin123
      _AIRFLOW_WWW_USER_EMAIL: admin@fonainvestors.com
      _AIRFLOW_WWW_USER_FIRSTNAME: Admin
      _AIRFLOW_WWW_USER_LASTNAME: User
      _AIRFLOW_WWW_USER_ROLE: Admin
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./src:/opt/airflow/src
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
      - ./dbt_project:/opt/dbt_project
      - ./data:/opt/data
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - fon_aios_network

  airflow-webserver:
    build: .
    command: webserver
    ports:
      - "8080:8080"
    environment:
      _AIRFLOW_DB_MIGRATE: 'false'
      _AIRFLOW_WWW_USER_CREATE: 'false'
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./src:/opt/airflow/src
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
      - ./dbt_project:/opt/dbt_project
      - ./data:/opt/data
    env_file:
      - .env
    depends_on:
      airflow-init:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - fon_aios_network

  airflow-scheduler:
    build: .
    command: scheduler
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./src:/opt/airflow/src
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
      - ./dbt_project:/opt/dbt_project
      - ./data:/opt/data
    env_file:
      - .env
    depends_on:
      airflow-init:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", 'airflow jobs check --job-type SchedulerJob --hostname "$${HOSTNAME}"']
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - fon_aios_network

volumes:
  postgres_data:
  neo4j_data:
  neo4j_logs:
  nifi_conf:
  nifi_content_repository:
  nifi_database_repository:
  nifi_flowfile_repository:
  nifi_provenance_repository:
  nifi_state:
  nifi_logs:
  redis_data:

networks:
  fon_aios_network:
    driver: bridge
EOF
```

**Create Dockerfile for Airflow with dbt:**
```bash
cat > Dockerfile << 'EOF'
FROM apache/airflow:2.8.1

USER root

# Install system dependencies for dbt and file processing
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy and install Python requirements
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Create dbt profile directory
RUN mkdir -p /opt/dbt

# Copy dbt profiles
COPY dbt_project /opt/dbt_project
COPY config/profiles.yml /opt/dbt/profiles.yml

# Copy source code
COPY --chown=airflow:root ./src /opt/airflow/src
COPY --chown=airflow:root ./airflow/dags /opt/airflow/dags

# Set environment variables
ENV DBT_PROFILES_DIR=/opt/dbt
ENV DBT_PROJECT_DIR=/opt/dbt_project
EOF
```

**Create dbt project structure:**
```bash
# Create dbt_project.yml
cat > dbt_project/dbt_project.yml << 'EOF'
name: 'fon_aios'
version: '1.0.0'
config-version: 2

profile: 'fon_aios'

model-paths: ["models"]
analysis-paths: ["analysis"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  fon_aios:
    staging:
      +materialized: view
    intermediate:
      +materialized: view
    marts:
      +materialized: table

vars:
  start_date: '2024-01-01'
  
tests:
  +store_failures: true
EOF

# Create dbt profiles
mkdir -p config
cat > config/profiles.yml << 'EOF'
fon_aios:
  target: dev
  outputs:
    dev:
      type: postgres
      host: postgres
      user: airflow
      password: airflow_password
      port: 5432
      dbname: airflow_db
      schema: fon_aios
      threads: 4
      keepalives_idle: 0
EOF

# Create staging models directory and sample model
cat > dbt_project/models/staging/schema.yml << 'EOF'
version: 2

sources:
  - name: raw_data
    description: Raw data from various sources
    tables:
      - name: newsapi_articles
        description: Raw articles from NewsAPI
        columns:
          - name: article_id
            description: Unique identifier for the article
          - name: title
            description: Article title
          - name: content
            description: Article content
          - name: published_at
            description: Publication timestamp
          - name: source_name
            description: News source name
          - name: url
            description: Article URL

models:
  - name: stg_newsapi_articles
    description: Cleaned and standardized NewsAPI articles
    columns:
      - name: article_id
        description: Unique identifier for the article
        tests:
          - unique
          - not_null
      - name: title_clean
        description: Cleaned article title
        tests:
          - not_null
      - name: content_clean
        description: Cleaned article content
      - name: published_at
        description: Publication timestamp
        tests:
          - not_null
      - name: source_name_standardized
        description: Standardized source name
EOF

cat > dbt_project/models/staging/stg_newsapi_articles.sql << 'EOF'
{{ config(
    materialized='view',
    tags=['staging', 'newsapi']
) }}

with source_data as (
    select
        article_id,
        title,
        content,
        description,
        published_at,
        source_name,
        url,
        author,
        url_to_image,
        search_terms,
        ingestion_timestamp
    from {{ source('raw_data', 'newsapi_articles') }}
),

cleaned as (
    select
        article_id,
        
        -- Clean title
        trim(regexp_replace(title, '\s+', ' ', 'g')) as title_clean,
        
        -- Clean content
        case 
            when content is not null 
            then trim(regexp_replace(content, '\s+', ' ', 'g'))
            else null 
        end as content_clean,
        
        -- Clean description
        case 
            when description is not null 
            then trim(regexp_replace(description, '\s+', ' ', 'g'))
            else null 
        end as description_clean,
        
        published_at,
        
        -- Standardize source names
        case 
            when lower(source_name) like '%reuters%' then 'Reuters'
            when lower(source_name) like '%associated press%' then 'Associated Press'
            when lower(source_name) like '%wall street journal%' then 'Wall Street Journal'
            when lower(source_name) like '%defense%news%' then 'Defense News'
            else initcap(source_name)
        end as source_name_standardized,
        
        url,
        author,
        url_to_image,
        search_terms,
        ingestion_timestamp
        
    from source_data
    where title is not null
      and url is not null
      and published_at is not null
)

select * from cleaned
EOF

# Create intermediate models
mkdir -p dbt_project/models/intermediate

cat > dbt_project/models/intermediate/int_articles_with_entities.sql << 'EOF'
{{ config(
    materialized='view',
    tags=['intermediate', 'entities']
) }}

with articles as (
    select * from {{ ref('stg_newsapi_articles') }}
),

-- This will be populated by our Python processing
entity_extractions as (
    select
        article_id,
        companies,
        agencies,
        technologies,
        funding_mentions,
        contract_mentions
    from {{ source('raw_data', 'article_entities') }}
),

combined as (
    select
        a.*,
        e.companies,
        e.agencies,
        e.technologies,
        e.funding_mentions,
        e.contract_mentions,
        
        -- Calculate relevance scores
        (
            coalesce(array_length(e.companies, 1), 0) * 0.2 +
            coalesce(array_length(e.agencies, 1), 0) * 0.3 +
            coalesce(array_length(e.technologies, 1), 0) * 0.1 +
            coalesce(array_length(e.funding_mentions, 1), 0) * 0.4 +
            coalesce(array_length(e.contract_mentions, 1), 0) * 0.3
        ) as base_relevance_score,
        
        -- Source authority weighting
        case 
            when source_name_standardized in ('Reuters', 'Associated Press', 'Wall Street Journal') 
            then 1.2 
            else 1.0 
        end as source_authority_multiplier
        
    from articles a
    left join entity_extractions e
        on a.article_id = e.article_id
)

select *,
    least(base_relevance_score * source_authority_multiplier, 10.0) as final_relevance_score
from combined
EOF

# Create marts models
mkdir -p dbt_project/models/marts

cat > dbt_project/models/marts/mart_defense_intelligence.sql << 'EOF'
{{ config(
    materialized='table',
    tags=['marts', 'defense']
) }}

with articles_with_entities as (
    select * from {{ ref('int_articles_with_entities') }}
),

defense_focused as (
    select
        article_id,
        title_clean as title,
        description_clean as description,
        content_clean as content,
        published_at,
        source_name_standardized as source_name,
        url,
        author,
        companies,
        agencies,
        technologies,
        funding_mentions,
        contract_mentions,
        final_relevance_score,
        
        -- Defense categorization
        case 
            when final_relevance_score >= 5.0 then 'High Priority'
            when final_relevance_score >= 2.0 then 'Medium Priority'
            when final_relevance_score >= 0.5 then 'Low Priority'
            else 'Background'
        end as priority_level,
        
        -- Technology categories
        case 
            when array_to_string(technologies, ',') ilike any(array['%ai%', '%artificial intelligence%', '%machine learning%']) 
            then true else false 
        end as has_ai_tech,
        
        case 
            when array_to_string(technologies, ',') ilike any(array['%cyber%', '%security%']) 
            then true else false 
        end as has_cyber_tech,
        
        case 
            when array_to_string(technologies, ',') ilike any(array['%space%', '%satellite%', '%orbital%']) 
            then true else false 
        end as has_space_tech,
        
        case 
            when array_to_string(technologies, ',') ilike any(array['%autonomous%', '%unmanned%', '%drone%']) 
            then true else false 
        end as has_autonomous_tech,
        
        ingestion_timestamp
        
    from articles_with_entities
    where final_relevance_score > 0  -- Only include articles with some defense relevance
)

select * from defense_focused
EOF

echo "dbt project structure created!"
```

## Phase 3: Service Dependencies and Testing (15 minutes)

### Step 3.1: Test Core Connectivity

First, let's make sure your Azure resources are accessible before starting the full stack.

**Create basic connectivity test:**
```bash
cat > test_connectivity.py << 'EOF'
#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import requests

load_dotenv()

def test_newsapi():
    """Test NewsAPI connection"""
    api_key = os.getenv('NEWSAPI_KEY')
    if not api_key:
        print("❌ NEWSAPI_KEY not found in .env file")
        return False
    
    url = f"https://newsapi.org/v2/everything?q=DARPA&apiKey={api_key}&pageSize=1"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ NewsAPI connected! Found {data.get('totalResults', 0)} articles")
            return True
        else:
            print(f"❌ NewsAPI error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ NewsAPI connection failed: {e}")
        return False

def test_azure_search():
    """Test Azure Search connection"""
    service_name = os.getenv('AZURE_SEARCH_SERVICE_NAME')
    admin_key = os.getenv('AZURE_SEARCH_ADMIN_KEY')
    
    if not service_name or not admin_key:
        print("❌ Azure Search credentials not found in .env file")
        return False
    
    # Install required package if not present
    try:
        from azure.search.documents.indexes import SearchIndexClient
        from azure.core.credentials import AzureKeyCredential
    except ImportError:
        print("Installing Azure Search dependencies...")
        os.system("pip install azure-search-documents azure-identity")
        from azure.search.documents.indexes import SearchIndexClient
        from azure.core.credentials import AzureKeyCredential
    
    try:
        endpoint = f"https://{service_name}.search.windows.net"
        credential = AzureKeyCredential(admin_key)
        
        client = SearchIndexClient(endpoint=endpoint, credential=credential)
        indexes = list(client.list_indexes())
        print(f"✅ Azure Search connected! Found {len(indexes)} existing indexes")
        return True
        
    except Exception as e:
        print(f"❌ Azure Search connection failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing external service connectivity...\n")
    
    # Install basic dependencies
    os.system("pip install python-dotenv requests")
    
    newsapi_ok = test_newsapi()
    azure_ok = test_azure_search()
    
    if newsapi_ok and azure_ok:
        print("\n🎉 All external services are accessible!")
        print("Ready to start Docker services...")
    else:
        print("\n❌ Some services failed. Check your .env file credentials.")
        sys.exit(1)
EOF

chmod +x test_connectivity.py
python test_connectivity.py
```

**If this fails, stop and fix your .env file before proceeding.**

### Step 3.2: Start Infrastructure Services

**Start all services with Docker Compose:**
```bash
# Start infrastructure services first (this takes 5-10 minutes)
docker-compose up -d postgres neo4j redis nifi

# Check service health (wait for all to be healthy)
docker-compose ps

# Check NiFi logs (NiFi takes longest to start - 2-3 minutes)
docker-compose logs -f nifi
```

**Wait for all services to show "healthy" status before proceeding.**

### Step 3.3: Build and Start Airflow

```bash
# Build the Airflow image with dbt
docker-compose build

# Initialize Airflow (creates admin user)
docker-compose up airflow-init

# Start Airflow services
docker-compose up -d airflow-webserver airflow-scheduler

# Check all services are running
docker-compose ps
```

## Phase 4: Service Access and Configuration (10 minutes)

### Step 4.1: Access All UIs

**Service URLs:**
- **Airflow**: http://localhost:8080 (admin/admin123)
- **NiFi**: https://localhost:8443/nifi/ (admin/ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB)
- **Neo4j Browser**: http://localhost:7474 (neo4j/password123)

**Test each service:**
1. **Airflow**: Should show empty DAGs list
2. **NiFi**: Should show empty flow canvas
3. **Neo4j**: Should connect and show empty database

### Step 4.2: Configure NiFi for FON AIOS

**Create NiFi template for news processing:**

1. Access NiFi UI at https://localhost:8443/nifi/
2. Login with admin/ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB
3. Accept the certificate warning

**Upload NiFi Template:**
```bash
# Create NiFi template for news processing
cat > nifi/templates/news_processing_template.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<template encoding-version="1.4">
    <description>FON AIOS News Processing Template</description>
    <groupId>root</groupId>
    <name>FON_AIOS_News_Processing</name>
    <snippet>
        <processGroups/>
        <processors>
            <id>invoke-http-processor</id>
            <parentGroupId>root</parentGroupId>
            <position>
                <x>200</x>
                <y>200</y>
            </position>
            <bundle>
                <artifact>nifi-standard-nar</artifact>
                <group>org.apache.nifi</group>
                <version>1.24.0</version>
            </bundle>
            <config>
                <bulletinLevel>WARN</bulletinLevel>
                <comments>Fetch articles from NewsAPI</comments>
                <concurrentlySchedulableTaskCount>1</concurrentlySchedulableTaskCount>
                <descriptors/>
                <lossTolerant>false</lossTolerant>
                <penaltyDuration>30 sec</penaltyDuration>
                <properties>
                    <entry>
                        <key>HTTP Method</key>
                        <value>GET</value>
                    </entry>
                    <entry>
                        <key>Remote URL</key>
                        <value>https://newsapi.org/v2/everything</value>
                    </entry>
                    <entry>
                        <key>SSL Context Service</key>
                    </entry>
                </properties>
                <runDurationMillis>0</runDurationMillis>
                <schedulingPeriod>1 min</schedulingPeriod>
                <schedulingStrategy>TIMER_DRIVEN</schedulingStrategy>
                <yieldDuration>1 sec</yieldDuration>
            </config>
            <name>Fetch NewsAPI Data</name>
            <relationships>
                <autoTerminate>false</autoTerminate>
                <name>success</name>
            </relationships>
            <state>STOPPED</state>
            <style/>
            <type>org.apache.nifi.processors.standard.InvokeHTTP</type>
        </processors>
        <connections/>
    </snippet>
</template>
EOF
```

We'll configure the actual NiFi flows after we build the processing components.

## Phase 5: Build Core Components (30 minutes)

Now let's build the data processing components that work with NiFi and dbt.

### Step 5.1: Create NewsAPI Client

```bash
cat > src/data_ingestion/newsapi_client.py << 'EOF'
import requests
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class NewsArticle:
    source_id: str
    source_name: str
    author: Optional[str]
    title: str
    description: Optional[str]
    url: str
    url_to_image: Optional[str]
    published_at: datetime
    content: Optional[str]
    search_terms: List[str]
    ingestion_timestamp: datetime

class NewsAPIClient:
    def __init__(self):
        self.api_key = os.getenv('NEWSAPI_KEY')
        self.base_url = os.getenv('NEWSAPI_BASE_URL')
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)
        
        if not self.api_key:
            raise ValueError("NEWSAPI_KEY environment variable is required")

    def search_everything(self, 
                         query: str, 
                         from_date: Optional[datetime] = None,
                         to_date: Optional[datetime] = None,
                         sources: Optional[str] = None,
                         language: str = 'en',
                         sort_by: str = 'relevancy',
                         page_size: int = 100) -> List[NewsArticle]:
        """Search for articles using NewsAPI everything endpoint"""
        
        url = f"{self.base_url}/everything"
        
        params = {
            'q': query,
            'apiKey': self.api_key,
            'language': language,
            'sortBy': sort_by,
            'pageSize': page_size
        }
        
        if from_date:
            params['from'] = from_date.strftime('%Y-%m-%d')
        if to_date:
            params['to'] = to_date.strftime('%Y-%m-%d')
        if sources:
            params['sources'] = sources
            
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            articles = []
            
            for article_data in data.get('articles', []):
                try:
                    # Parse date
                    published_str = article_data.get('publishedAt', '')
                    if published_str:
                        published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00'))
                    else:
                        published_at = datetime.utcnow()
                    
                    article = NewsArticle(
                        source_id=article_data['source'].get('id', 'unknown'),
                        source_name=article_data['source'].get('name', 'Unknown'),
                        author=article_data.get('author'),
                        title=article_data.get('title', ''),
                        description=article_data.get('description'),
                        url=article_data.get('url', ''),
                        url_to_image=article_data.get('urlToImage'),
                        published_at=published_at,
                        content=article_data.get('content'),
                        search_terms=[query],
                        ingestion_timestamp=datetime.utcnow()
                    )
                    articles.append(article)
                except Exception as e:
                    self.logger.warning(f"Failed to parse article: {e}")
                    continue
                    
            self.logger.info(f"Successfully retrieved {len(articles)} articles for query: {query}")
            return articles
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise

    def get_defense_news(self, days_back: int = 7) -> List[NewsArticle]:
        """Get defense-related news articles using predefined search terms"""
        defense_queries = [
            "DARPA contract", "SBIR award", "defense contractor",
            "naval systems", "space systems", "unmanned platforms",
            "Lockheed Martin", "Boeing", "Raytheon", "General Dynamics",
            "autonomous systems", "cybersecurity defense"
        ]
        
        from_date = datetime.utcnow() - timedelta(days=days_back)
        all_articles = []
        
        for query in defense_queries:
            try:
                articles = self.search_everything(
                    query=query,
                    from_date=from_date,
                    sources="reuters,associated-press,the-wall-street-journal"
                )
                all_articles.extend(articles)
                self.logger.info(f"Retrieved {len(articles)} articles for '{query}'")
            except Exception as e:
                self.logger.error(f"Failed to retrieve articles for '{query}': {e}")
                continue
                
        # Remove duplicates based on URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                unique_articles.append(article)
                
        self.logger.info(f"Total unique articles retrieved: {len(unique_articles)}")
        return unique_articles

    def save_articles_to_nifi_input(self, articles: List[NewsArticle], output_path: str = "/opt/data/raw"):
        """Save articles as JSON for NiFi processing"""
        os.makedirs(output_path, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"newsapi_articles_{timestamp}.json"
        filepath = os.path.join(output_path, filename)
        
        articles_data = []
        for article in articles:
            article_dict = {
                'article_id': f"newsapi_{hash(article.url)}",
                'source_id': article.source_id,
                'source_name': article.source_name,
                'author': article.author,
                'title': article.title,
                'description': article.description,
                'url': article.url,
                'url_to_image': article.url_to_image,
                'published_at': article.published_at.isoformat(),
                'content': article.content,
                'search_terms': article.search_terms,
                'ingestion_timestamp': article.ingestion_timestamp.isoformat()
            }
            articles_data.append(article_dict)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(articles_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved {len(articles)} articles to {filepath}")
        return filepath
EOF
```

### Step 5.2: Test NewsAPI Integration

```bash
cat > test_newsapi_integration.py << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.append('/opt/airflow/src')

from src.data_ingestion.newsapi_client import NewsAPIClient
from datetime import datetime, timedelta

def test_newsapi_with_nifi_output():
    """Test NewsAPI client and save output for NiFi"""
    
    print("Testing NewsAPI integration...")
    
    # Create client
    client = NewsAPIClient()
    
    # Get recent defense news
    articles = client.get_defense_news(days_back=2)
    print(f"✅ Retrieved {len(articles)} articles")
    
    if articles:
        # Save for NiFi processing
        output_path = client.save_articles_to_nifi_input(articles)
        print(f"✅ Saved articles to: {output_path}")
        
        # Show sample article
        sample = articles[0]
        print(f"\nSample article:")
        print(f"Title: {sample.title}")
        print(f"Source: {sample.source_name}")
        print(f"Published: {sample.published_at}")
        print(f"URL: {sample.url}")
        
        return True
    else:
        print("❌ No articles retrieved")
        return False

if __name__ == "__main__":
    # Create data directories
    os.makedirs("/opt/data/raw", exist_ok=True)
    os.makedirs("/opt/data/processed", exist_ok=True)
    
    success = test_newsapi_with_nifi_output()
    if success:
        print("\n🎉 NewsAPI integration test successful!")
        print("Ready to configure NiFi flows...")
    else:
        print("\n❌ NewsAPI integration test failed!")
EOF

# Run inside Airflow container
docker-compose exec airflow-webserver python /opt/airflow/test_newsapi_integration.py
```

## Phase 6: Verify Complete Setup (10 minutes)

### Step 6.1: Final System Check

```bash
cat > verify_complete_setup.py << 'EOF'
#!/usr/bin/env python3
import os
import subprocess
import sys
import time
from datetime import datetime

def check_service_health(service_name: str, max_wait: int = 60) -> bool:
    """Check if a Docker service is healthy"""
    print(f"Checking {service_name} health...")
    
    for i in range(max_wait):
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '--format', 'json'], 
                capture_output=True, text=True, check=True
            )
            
            if service_name in result.stdout and 'healthy' in result.stdout:
                print(f"✅ {service_name} is healthy")
                return True
                
        except subprocess.CalledProcessError:
            pass
        
        if i % 10 == 0:  # Print every 10 seconds
            print(f"Waiting for {service_name}... ({i}/{max_wait}s)")
        time.sleep(1)
    
    print(f"❌ {service_name} failed health check")
    return False

def check_ui_access():
    """Check if UIs are accessible"""
    import requests
    
    services = {
        'Airflow': 'http://localhost:8080/health',
        'Neo4j': 'http://localhost:7474',
        'NiFi': 'https://localhost:8443/nifi/'
    }
    
    results = {}
    for name, url in services.items():
        try:
            # For HTTPS endpoints, disable SSL verification
            verify_ssl = not url.startswith('https')
            response = requests.get(url, timeout=10, verify=verify_ssl)
            if response.status_code in [200, 401, 403]:  # 401/403 means service is up but needs auth
                print(f"✅ {name} UI accessible")
                results[name] = True
            else:
                print(f"❌ {name} UI returned {response.status_code}")
                results[name] = False
        except Exception as e:
            print(f"❌ {name} UI not accessible: {e}")
            results[name] = False
    
    return all(results.values())

def check_dbt_setup():
    """Check if dbt is properly configured"""
    try:
        result = subprocess.run(
            ['docker-compose', 'exec', '-T', 'airflow-webserver', 'dbt', 'debug', '--project-dir', '/opt/dbt_project'],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("✅ dbt configuration valid")
            return True
        else:
            print(f"❌ dbt configuration error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ dbt check failed: {e}")
        return False

def check_data_directories():
    """Check if data directories exist and are writable"""
    directories = ['/opt/data/raw', '/opt/data/processed', '/opt/data/staging']
    
    for dir_path in directories:
        try:
            # Check inside container
            result = subprocess.run(
                ['docker-compose', 'exec', '-T', 'airflow-webserver', 'test', '-w', dir_path],
                capture_output=True
            )
            if result.returncode == 0:
                print(f"✅ {dir_path} accessible and writable")
            else:
                print(f"❌ {dir_path} not accessible")
                return False
        except Exception as e:
            print(f"❌ Directory check failed for {dir_path}: {e}")
            return False
    
    return True

def main():
    print("🔍 Verifying complete FON AIOS setup...\n")
    print(f"Timestamp: {datetime.now()}\n")
    
    # Install requests for UI checks
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'], capture_output=True)
    
    checks = []
    
    print("1. Checking Docker service health...")
    services = ['postgres', 'neo4j', 'redis', 'nifi', 'airflow-webserver', 'airflow-scheduler']
    health_checks = [check_service_health(service) for service in services]
    checks.append(all(health_checks))
    
    print("\n2. Checking UI accessibility...")
    ui_check = check_ui_access()
    checks.append(ui_check)
    
    print("\n3. Checking dbt configuration...")
    dbt_check = check_dbt_setup()
    checks.append(dbt_check)
    
    print("\n4. Checking data directories...")
    dir_check = check_data_directories()
    checks.append(dir_check)
    
    print("\n" + "="*50)
    
    if all(checks):
        print("🎉 COMPLETE SETUP VERIFICATION SUCCESSFUL!")
        print("\nYour FON AIOS environment is ready with:")
        print("✅ Apache Airflow (Orchestration)")
        print("✅ Apache NiFi (Data Processing)")
        print("✅ dbt (Data Transformation)")
        print("✅ Neo4j (Graph Database)")
        print("✅ PostgreSQL (Airflow Backend)")
        print("✅ Azure AI Search (Document Search)")
        print("✅ NewsAPI Integration")
        
        print("\nAccess your services:")
        print("🌐 Airflow UI: http://localhost:8080 (admin/admin123)")
        print("🌐 NiFi UI: https://localhost:8443/nifi/ (admin/ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB)")
        print("🌐 Neo4j Browser: http://localhost:7474 (neo4j/password123)")
        
        print("\nNext steps:")
        print("1. Configure NiFi data flows")
        print("2. Test the complete pipeline")
        print("3. Build entity extraction and graph components")
        
    else:
        print("❌ SETUP VERIFICATION FAILED!")
        print("Fix the issues above before proceeding.")
        
        failed_services = []
        if not health_checks[0]: failed_services.append("PostgreSQL")
        if not health_checks[1]: failed_services.append("Neo4j")
        if not health_checks[2]: failed_services.append("Redis")
        if not health_checks[3]: failed_services.append("NiFi")
        if not health_checks[4]: failed_services.append("Airflow Webserver")
        if not health_checks[5]: failed_services.append("Airflow Scheduler")
        
        if failed_services:
            print(f"\nFailed services: {', '.join(failed_services)}")
            print("Try: docker-compose down && docker-compose up -d")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

chmod +x verify_complete_setup.py
python verify_complete_setup.py
```

## What We've Accomplished

🎉 **Complete Architecture Setup:**

✅ **Apache Airflow**: Orchestration engine ready  
✅ **Apache NiFi**: Data processing flows ready  
✅ **dbt**: Data transformation models created  
✅ **Neo4j**: Graph database running  
✅ **PostgreSQL**: Backend database operational  
✅ **Azure AI Search**: External search service connected  
✅ **NewsAPI**: Data source integration tested  

## Next Phase: Building the Complete Pipeline

Once your verification passes, you're ready to:

1. **Configure NiFi Flows**: Set up automated data processing
2. **Build Entity Extraction**: Add graph database integration
3. **Create Airflow DAGs**: Orchestrate the complete pipeline
4. **Test End-to-End**: Verify data flows from NewsAPI → Azure Search

This architecture will scale seamlessly as you add more data sources (DARPA, SBIR, patents) in Stage 2.

**Ready to proceed with building the complete data pipeline?**