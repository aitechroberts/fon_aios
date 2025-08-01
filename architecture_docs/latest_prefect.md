┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│   News Sources  │    │  Prefect Cloud   │    │  ADLS Gen 2 Blob    │    │   Azure GPU     │
│                 │───▶│  (Orchestration) │───▶│   (Data Lake)       │───▶│  Containers     │
│ • Defense News  │    │  + Self-hosted   │    │ • JSON (provenance) │    │ (LangChain      │
│ • DARPA RSS     │    │    Workers       │    │ • Parquet (bulk)    │    │  Processing)    │
│ • SBIR Feeds    │    └──────────────────┘    └─────────────────────┘    └─────────────────┘
└─────────────────┘                                       │                         │
▼                         ▼
┌─────────────────────┐    ┌─────────────────┐
│  Data Validation    │    │   Knowledge     │
│ (Great Expectations)│───▶│     Graph       │
└─────────────────────┘    │  (Neo4j +       │
│   Azure Search) │
└─────────────────┘

## 1. Prefect 3.x Project Structure
```bash
fon-aios-prefect/
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
├── automations/
│   └── nlp_trigger.yaml
├── requirements.txt
├── prefect.yaml
└── README.md