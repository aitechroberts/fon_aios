# FON AIOS Prefect Pipeline

## Directory Structure
fon_aios/
├── flows/
│   ├── ingestion/
│   │   └── ingest_daily_news.py
│   ├── processing/
│   │   └── nlp_gpu_flow.py
│   └── knowledge_graph/
│       └── graph_update_flow.py
├── tasks/                  # new helper lib
│   ├── __init__.py
│   ├── hashing.py          # _hash()
│   └── nlp_micro.py        # embed(), ner(), coref(), relations()
└── prefect.yaml
Azure Resources
```bash

```