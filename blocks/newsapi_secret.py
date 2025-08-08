# blocks/newsapi_secret.py
import asyncio
import os
from dotenv import load_dotenv
from prefect.blocks.system import Secret

load_dotenv()

async def setup_newsapi_secret():
    """Create NewsAPI.ai API key secret"""
    
    newsapi_key = os.getenv("NEWSAPI_AI_KEY")
    
    if not newsapi_key:
        print("❌ NEWSAPI_AI_KEY not found in .env")
        return False
    
    secret = Secret(value=newsapi_key)
    await secret.save("newsapi-ai-key", overwrite=True)
    print("✅ Created 'newsapi-ai-key' secret")
    return True

if __name__ == "__main__":
    asyncio.run(setup_newsapi_secret())