# setup_all_blocks.py
import asyncio
import os
from dotenv import load_dotenv
import sys

# Add blocks directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

async def setup_all_blocks():
    """Set up all Prefect blocks and secrets"""
    
    print("Setting up all Prefect Blocks and Secrets")
    print("="*60)
    
    # Storage blocks (already exist, but let's verify)
    print("\n1. Storage Blocks (already configured):")
    from blocks.storage import setup_storage_blocks
    try:
        await setup_storage_blocks()
    except Exception as e:
        print(f"   Storage blocks may already exist: {e}")
    
    # Azure OpenAI block
    print("\n2. Azure OpenAI Block:")
    from blocks.azure_openai import setup_azure_openai_block
    await setup_azure_openai_block()
    
    # Azure Search block
    print("\n3. Azure AI Search Block:")
    from blocks.azure_search import setup_azure_search_block
    await setup_azure_search_block()
    
    # NewsAPI.ai secret
    print("\n4. NewsAPI.ai Secret:")
    from blocks.newsapi_secret import setup_newsapi_secret
    await setup_newsapi_secret()
    
    print("\n" + "="*60)
    print("✅ All blocks and secrets configured!")
    print("\nYou can now access them in your flows:")
    print("  - Storage: AzureBlobStorageContainer.load('fon-data-lake')")
    print("  - OpenAI: AzureOpenAICredentials.load('azure-openai')")
    print("  - Search: AzureAISearchCredentials.load('azure-search')")
    print("  - NewsAPI: Secret.load('newsapi-ai-key')")

if __name__ == "__main__":
    asyncio.run(setup_all_blocks())