from datetime import datetime, timezone
import json, pyarrow as pa, pyarrow.dataset as ds
from prefect import flow, task, transaction, get_run_logger
from prefect.artifacts import create_table_artifact
from prefect_azure.blob_storage import AzureBlobStorageBlock
from tasks.hashing import hash_url   # NEW

RAW = AzureBlobStorageBlock.load("fon-data-lake")

@task(retries=3, retry_delay_seconds=15)
async def write_raw(article: dict, source: str):
    doc_id = hash_url(article["url"])
    ts = datetime.fromisoformat(article["publishedAt"]).astimezone(timezone.utc)
    path = f"raw/{source}/{ts:%Y/%m/%d}/{doc_id}.json"
    async with transaction(key=f"adls-{doc_id}"):
        await RAW.write_path(path, json.dumps(article).encode())
    return {**article, "doc_id": doc_id, "source": source, "utc_ts": ts.isoformat()}

@task
def append_parquet(rows: list[dict]):
    if not rows:
        return
    day_path = f"processed-parquet/{rows[0]['source']}/{rows[0]['utc_ts'][:10]}/day.parquet"
    tbl = pa.Table.from_pylist(rows)
    ds.write_dataset(tbl, base_dir=f"abfs://{day_path}", format="parquet",
                     existing_data_behavior="overwrite_or_ignore", max_rows_per_file=200_000)
    # ── Artifact for lineage ───────────────────────────
    create_table_artifact(tbl.slice(0, min(20, tbl.num_rows)), description="Sample of daily Parquet roll‑up")

@flow
def daily_ingestion(news_batch: list[dict], source: str = "defense-news"):
    logger = get_run_logger()
    enriched = [write_raw.submit(a, source).result() for a in news_batch]
    append_parquet(enriched)
    logger.info("Daily ingestion completed → %s articles", len(enriched))