# utils/monitor_credits.py
from prefect import get_client
import asyncio

async def check_credit_usage():
    async with get_client() as client:
        # Get work pool status
        pool = await client.read_work_pool("managed-ingestion-pool")
        
        # Monitor in Prefect Cloud UI under:
        # Work Pools → managed-ingestion-pool → Usage
        
        print(f"Work Pool: {pool.name}")
        print(f"Type: {pool.type}")
        print("Check Prefect Cloud UI for credit usage")

if __name__ == "__main__":
    asyncio.run(check_credit_usage())