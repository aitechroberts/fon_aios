# deployments/deploy_event_driven.py
from prefect import serve
from prefect.deployments import Deployment
from prefect.server.schemas.schedules import CronSchedule
from prefect.events import DeploymentEventTrigger
from flows.ingestion.newsapi_ingestion import news_ingestion_flow
from flows.processing.embeddings_flow import embeddings_processing_flow
import asyncio

async def deploy_event_driven_pipeline():
    """Deploy ingestion and embeddings with event-driven triggers"""
    
    print("🚀 Setting up event-driven pipeline")
    print("=" * 50)
    
    newsapi_query = ""

    # 1. Deploy NewsAPI ingestion flows for different sectors
    news_deployment = await news_ingestion_flow.to_deployment(
        name="newsapi-defense-ingestion",
        work_pool_name="managed-ingestion-pool",
        schedule=CronSchedule(cron="0 6 * * *"),  # Every day at 6 AM
        parameters={
            "query": f"{newsapi_query}",
            "lookback_days": 1
        },
        tags=["ingestion", "newsapi", "defense"],
        description="Ingest defense sector news"
    )
    
    
    # 2. Deploy embeddings processing flow with event triggers
    embeddings_deployment = await embeddings_processing_flow.to_deployment(
        name="embeddings-processor",
        work_pool_name="newsapi-pool",  # Can use same pool
        triggers=[
            DeploymentEventTrigger(
                enabled=True,
                name="process-embeddings-after-ingestion",
                description="Trigger embeddings when any ingestion completes",
                match={
                    "prefect.flow-run.Completed": {
                        "prefect.flow.name": "News Ingestion"
                    }
                },
                # Pass the parquet_path from the completed flow
                parameters={
                    "parquet_path": "{{ event.resource.result.parquet_path }}"
                }
            )
        ],
        tags=["processing", "embeddings", "event-driven"],
        description="Generate embeddings and index to Azure Search"
    )
    
    # Apply all deployments
    await news_deployment.apply()
    await embeddings_deployment.apply()
    
    print("\n✅ Event-driven pipeline deployed!")
    print("\n📊 Deployment Summary:")
    print("Ingestion Flows (Scheduled):")
    print("  - newsapi-defense-ingestion: Every 6 hours")
    print("  - newsapi-healthcare-ingestion: Twice daily")
    print("  - newsapi-manufacturing-ingestion: Once daily")
    print("\nProcessing Flow (Event-triggered):")
    print("  - embeddings-processor: Triggers automatically after each ingestion")
    print("\n🔄 Flow:")
    print("  1. Ingestion runs on schedule")
    print("  2. Stores JSON by source + creates Parquet")
    print("  3. Embeddings flow auto-triggers on completion")
    print("  4. Reads Parquet, generates embeddings, indexes to Search")

async def deploy_batch_embeddings():
    """Optional: Deploy a scheduled batch embeddings processor"""
    
    # For processing multiple ingestions at once
    batch_embeddings = await embeddings_processing_flow.to_deployment(
        name="embeddings-batch-processor",
        work_pool_name="managed-ingestion-pool",
        schedule=CronSchedule(cron="0 */12 * * *"),  # Every 12 hours
        parameters={
            # Will need to implement logic to find unprocessed parquet files
            "parquet_paths": []  # Populated dynamically
        },
        tags=["processing", "embeddings", "batch"],
        description="Batch process embeddings for all recent ingestions"
    )
    
    await batch_embeddings.apply()
    print("\n✅ Optional batch processor deployed (runs every 12 hours)")

if __name__ == "__main__":
    asyncio.run(deploy_event_driven_pipeline())
    
    # Uncomment if you want batch processing too
    asyncio.run(deploy_batch_embeddings())