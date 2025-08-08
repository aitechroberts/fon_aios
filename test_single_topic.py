# test_single_topic.py
import asyncio
import os
from dotenv import load_dotenv
from flows.ingestion.newsapi_single_topic_flow import newsapi_single_topic_flow
from config.newsapi_ai_topics import TEST_TOPIC

load_dotenv()

async def test_single_topic():
    """Test single topic ingestion with 100 articles"""
    
    print("="*60)
    print("NewsAPI.ai Single Topic Test")
    print("="*60)
    
    # Check configuration
    api_key = os.getenv("NEWSAPI_AI_KEY")
    if not api_key:
        print("❌ NEWSAPI_AI_KEY not found in .env")
        return

    if TEST_TOPIC['defense_technology']['uri'].startswith("YOUR_"):
        print("❌ Topic URI not configured in config/newsapi_topics.py")
        print("   Please update TEST_TOPIC['uri'] with your actual topic URI")
        return
    
    print(f"✅ API Key found")
    print(f"✅ Topic configured: {TEST_TOPIC['defense_technology']['name']}")
    print(f"   URI: {TEST_TOPIC['defense_technology']['uri'][:20]}...")
    print(f"\nFetching maximum 100 articles...")
    print("-"*60)
    
    # Run the flow
    result = await newsapi_single_topic_flow(
        max_articles=100,
    )
    
    print("\n" + "="*60)
    print("Results:")
    print(f"Status: {result.get('status', 'unknown')}")
    print(f"Articles processed: {result.get('items_processed', 0)}")
    print(f"Parquet path: {result.get('parquet_path', 'N/A')}")
    
    if result.get('items_processed', 0) > 0:
        print("\n✅ Test successful!")
        print("\nNext steps:")
        print("1. Check Azure Storage for the Parquet file")
        print("2. Verify the NLP processing automation triggers")
        print("3. Check Azure AI Search for indexed documents")
    else:
        print("\n❌ No articles processed")
        if 'error' in result:
            print(f"Error: {result['error']}")

if __name__ == "__main__":
    asyncio.run(test_single_topic())