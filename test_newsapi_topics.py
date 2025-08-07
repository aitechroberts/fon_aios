# test_newsapi_topics.py
import asyncio
from flows.ingestion.newsapi_topics_flow import newsapi_topics_daily_flow
from config.newsapi_ai_topics import TOPICS

async def test_topics_flow():
    """Test the daily topics ingestion flow"""
    
    print("Testing NewsAPI.ai Topics Flow")
    print("="*60)
    
    # Check configuration
    configured = sum(1 for t in TOPICS.values() if not t['uri'].startswith("YOUR_"))
    print(f"Topics configured: {configured}/{len(TOPICS)}")
    
    if configured == 0:
        print("❌ No topics configured! Please add topic URIs to config/newsapi_topics.py")
        return
    
    # Run the flow
    result = await newsapi_topics_daily_flow()
    
    print("\n" + "="*60)
    print("Flow Results:")
    print(f"Total articles: {result['total_articles']}")
    print(f"Successful topics: {result['successful_topics']}")
    print(f"Failed topics: {result['failed_topics']}")
    print(f"Combined Parquet: {result['combined_parquet']}")
    
    print("\nIndividual Results:")
    for r in result['individual_results']:
        status_icon = "✅" if r['status'] == 'success' else "❌"
        print(f"{status_icon} {r['topic_key']}: {r.get('items_processed', 0)} articles")

if __name__ == "__main__":
    asyncio.run(test_topics_flow())