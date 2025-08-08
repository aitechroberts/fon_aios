# blocks/azure_search.py
import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from prefect.blocks.core import Block

load_dotenv()

class AzureAISearchCredentials(Block):
    """Block for Azure AI Search configuration"""
    
    _block_type_name = "azure-search-credentials"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5VvdN2gHgbNPAoQaCATGqa/2d1dc96b616ab29e02062f90cfb1ca53/azure.png"
    
    service_name: str = Field(
        description="Azure AI Search service name (without .search.windows.net)"
    )
    admin_key: str = Field(
        description="Azure AI Search admin key",
        is_secret=True
    )
    index_name: str = Field(
        description="Default index name"
    )
    
    @property
    def endpoint(self) -> str:
        """Construct the full endpoint URL"""
        return f"https://{self.service_name}.search.windows.net"
    
    class Config:
        schema_extra = {
            "example": {
                "service_name": "your-search-service",
                "admin_key": "***secret***",
                "index_name": "fon-defense-intelligence"
            }
        }

async def setup_azure_search_block():
    """Create Azure AI Search block"""
    
    azure_search = AzureAISearchCredentials(
        service_name=os.getenv("AZURE_SEARCH_SERVICE_NAME"),
        admin_key=os.getenv("AZURE_SEARCH_ADMIN_KEY"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME")
    )
    
    await azure_search.save("azure-search", overwrite=True)
    print("✅ Created 'azure-search' block")
    return True

if __name__ == "__main__":
    asyncio.run(setup_azure_search_block())