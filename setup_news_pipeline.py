# setup_modular_pipeline.py
import asyncio
import os
import subprocess
from dotenv import load_dotenv

async def main():
    """Setup modular event-driven pipeline"""
    
    load_dotenv()
    
    print("🚀 FON AIOS Modular Pipeline Setup")
    print("=" * 50)
    print("\nArchitecture:")
    print("  Ingestion → JSON (by source) + Parquet → Event → Embeddings → Azure Search")
    print("=" * 50)
    
    # Step 1: Check environment variables
    print("\n1️⃣ Checking environment variables...")
    required_vars = [
        "AZURE_STORAGE_CONNECTION_STRING",
        "AZURE_SEARCH_SERVICE_NAME", 
        "AZURE_SEARCH_ADMIN_KEY",
        "NEWSAPI_KEY",
        "OPENAI_API_KEY",
        "PREFECT_API_KEY",
        "PREFECT_API_URL"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return
    else:
        print("✅ All environment variables found")
    
    # Step 2: Login to Prefect Cloud
    print("\n2️⃣ Logging into Prefect Cloud...")
    try:
        subprocess.run(["prefect", "cloud", "login", "--key", os.getenv("PREFECT_API_KEY")], check=True)
        print("✅ Logged into Prefect Cloud")
    except subprocess.CalledProcessError:
        print("❌ Failed to login to Prefect Cloud")
        return
    
    # Step 3: Create work pool
    print("\n3️⃣ Creating Prefect Managed work pool...")
    try:
        subprocess.run([
            "prefect", "work-pool", "create", 
            "managed-ingestion-pool", 
            "--type", "prefect:managed"
        ], check=True)
        print("✅ Created managed work pool")
    except subprocess.CalledProcessError as e:
        if "already exists" in str(e):
            print("ℹ️ Work pool already exists")
        else:
            print("❌ Failed to create work pool")
            return
    
    # Step 4: Setup storage blocks
    print("\n4️⃣ Setting up storage blocks...")
    try:
        from blocks.setup_storage import setup_blocks
        await setup_blocks()
    except Exception as e:
        print(f"❌ Failed to setup blocks: {e}")
        return
    
    # Step 5: Test ingestion flow
    print("\n5️⃣ Testing news ingestion flow...")
    try:
        from flows.ingestion.news_ingestion_modular import news_ingestion_flow
        
        test_result = await news_ingestion_flow(
            query="DARPA",
            lookback_days=1
        )
        
        if test_result["status"] == "success":
            print(f"✅ Ingestion test successful!")
            print(f"   - Articles: {test_result['articles_count']}")
            print(f"   - Sources: {', '.join(test_result['sources'][:3])}...")
            print(f"   - Parquet: {test_result['parquet_path']}")
            
            # Save parquet path for embeddings test
            test_parquet = test_result['parquet_path']
        else:
            print("❌ Ingestion test failed")
            return
    except Exception as e:
        print(f"❌ Ingestion test failed: {e}")
        return
    
    # Step 6: Test embeddings flow
    print("\n6️⃣ Testing embeddings flow...")
    try:
        from flows.processing.embeddings_flow import embeddings_processing_flow
        
        embed_result = await embeddings_processing_flow(
            parquet_path=test_parquet
        )
        
        if embed_result["status"] == "success":
            print(f"✅ Embeddings test successful!")
            print(f"   - Processed: {embed_result['articles_processed']}")
            print(f"   - Indexed: {embed_result['articles_indexed']}")
        else:
            print("❌ Embeddings test failed")
            return
    except Exception as e:
        print(f"❌ Embeddings test failed: {e}")
        return
    
    # Step 7: Deploy flows with event triggers
    print("\n7️⃣ Creating deployments with event triggers...")
    try:
        from deployments.deploy_event_driven import deploy_event_driven_pipeline
        await deploy_event_driven_pipeline()
    except Exception as e:
        print(f"❌ Failed to create deployments: {e}")
        return
    
    print("\n✅ Setup complete!")
    print("\n📊 What's been deployed:")
    print("1. Ingestion flows (3 sectors) - Store JSON by source + Parquet")
    print("2. Embeddings flow - Auto-triggers on ingestion completion")
    print("3. Event automation - Links the flows together")
    
    print("\n🔄 Pipeline flow:")
    print("1. NewsAPI → Group by source → JSON files")
    print("2. All articles → Parquet file (compressed)")
    print("3. Event trigger → Read Parquet")
    print("4. Generate embeddings → Index to Azure Search")
    
    print("\n📈 Benefits of this architecture:")
    print("• Modular: Easy to add new sources")
    print("• Efficient: Parquet is 5-10x smaller and faster")
    print("• Observable: JSON files for debugging")
    print("• Scalable: Event-driven processing")
    
    print("\n💡 Next steps:")
    print("1. Monitor at: https://app.prefect.cloud")
    print("2. Add more sources (RSS, Reddit, etc.)")
    print("3. Check source-specific JSONs for quality")
    print("4. Query Azure Search for embedded articles")

if __name__ == "__main__":
    asyncio.run(main())