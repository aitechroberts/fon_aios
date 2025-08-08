# blocks/azure_openai.py
import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from prefect.blocks.core import Block
from typing import Optional

load_dotenv()

class AzureOpenAICredentials(Block):
    """Block for Azure OpenAI configuration"""
    
    _block_type_name = "azure-openai-credentials"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5VvdN2gHgbNPAoQaCATGqa/2d1dc96b616ab29e02062f90cfb1ca53/azure.png"
    
    endpoint: str = Field(
        description="Azure OpenAI endpoint URL",
        # example="https://your-resource.openai.azure.com/"
    )
    api_key: str = Field(
        description="Azure OpenAI API key",
        is_secret=True
    )
    embedding_deployment: str = Field(
        description="Name of the embedding model deployment",
        example="text-embedding-ada-002"
    )
    api_version: str = Field(
        description="API version"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "endpoint": "https://your-resource.openai.azure.com/",
                "api_key": "***secret***",
                "embedding_deployment": "text-embedding-ada-002",
                "api_version": "2024-10-21" # or latest version
            }
        }

async def setup_azure_openai_block():
    """Create Azure OpenAI block"""
    
    azure_openai = AzureOpenAICredentials(
        endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    )
    
    await azure_openai.save("azure-openai", overwrite=True)
    print("✅ Created 'azure-openai' block")
    return True

if __name__ == "__main__":
    asyncio.run(setup_azure_openai_block())