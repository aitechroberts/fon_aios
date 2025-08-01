import duckdb
from prefect import flow, task, get_run_logger
from tasks.nlp_micro import embed, ner, coref, relations

@task
def load_daily(day: str, source: str):
    con = duckdb.connect()
    con.execute("INSTALL azure; LOAD azure;")
    return con.sql(f"""
        SELECT content, doc_id FROM parquet_scan('azure://<account>.blob.core.windows.net/fon-data-lake/processed-parquet/{source}/{day}/*.parquet')
    """).fetchall()

@task
def enrich(records):
    out = []
    for text, doc_id in records:
        vec = embed(text)
        ents = ner(text)
        coref(text)  # side‑effect resolves clusters; omitted variable
        rels = relations(text, ents, coref)
        out.append({"doc_id": doc_id, "content": text, "vector": vec, "entities": [e.text for e in ents]})
    return out

@flow
def nlp_processing_pipeline(day: str, source: str = "defense-news"):
    rows = load_daily(day, source)
    return enrich(rows)