# test_embeddings_flow.py
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv
from flows.processing.embeddings_flow import embeddings_processing_flow

load_dotenv()

async def verify_azure_openai_config():
    """Verify Azure OpenAI configuration"""
    
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
    ]
    
    all_present = True
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            print(f"❌ Missing: {var}")
            all_present = False
        else:
            if var == "AZURE_OPENAI_API_KEY":
                print(f"✅ {var}: ***hidden***")
            else:
                print(f"✅ {var}: {value}")
    
    return all_present

async def test_embeddings():
    """Test the embeddings flow with Azure OpenAI"""
    
    print("="*60)
    print("Testing Embeddings Processing Flow (Azure OpenAI)")
    print("="*60)
    
    # Verify Azure OpenAI config
    print("\n1. Checking Azure OpenAI configuration...")
    if not await verify_azure_openai_config():
        print("\n❌ Please add missing Azure OpenAI credentials to .env")
        return
    
    # Also verify Azure Search config
    print("\n2. Checking Azure Search configuration...")
    if not os.getenv("AZURE_SEARCH_SERVICE_NAME") or not os.getenv("AZURE_SEARCH_ADMIN_KEY"):
        print("❌ Missing Azure Search configuration")
        return
    
    print("\n3. Enter the parquet file path from your ingestion run:")
    print("   Example: raw-data/processed-parquet/newsapi_ai_defense_technology/2025/08/07/newsapi_ai_defense_technology_20250807_200206.parquet")
    
    parquet_path = input("   Path: ").strip()
    
    if not parquet_path:
        print("❌ No path provided")
        return
    
    print(f"\n4. Running embeddings flow with Azure OpenAI...")
    print("-"*60)
    
    try:
        result = await embeddings_processing_flow(
            parquet_path=parquet_path,
            batch_size=20
        )
        
        print("\n" + "="*60)
        print("Results:")
        print(f"Status: {result.get('status')}")
        print(f"Articles processed: {result.get('articles_processed', 0)}")
        print(f"Articles indexed: {result.get('articles_indexed', 0)}")
        
        if result.get('status') == 'success':
            print("\n✅ Azure OpenAI embeddings test successful!")
        else:
            print(f"\n❌ Test failed: {result}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_embeddings())