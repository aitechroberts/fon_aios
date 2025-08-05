# blocks/setup_storage.py
from prefect_azure import AzureBlobStorageCredentials
from prefect_azure.blob_storage import AzureBlobStorageBlock
from prefect.blocks.system import Secret
import os
import asyncio

async def setup_blocks():
    """Setup blocks for hybrid managed/ACI architecture"""
    
    # Azure Storage Credentials
    azure_creds = AzureBlobStorageCredentials(
        connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    )
    await azure_creds.save("azure-storage-creds", overwrite=True)
    
    # ADLS Gen2 Block for Data Lake
    adls_block = AzureBlobStorageBlock(
        blob_storage_credentials=azure_creds,
        container_name="fon-data-lake",
        base_path="raw-data/"
    )
    await adls_block.save("fon-data-lake", overwrite=True)
    
    # Processed Data Storage
    processed_storage = AzureBlobStorageBlock(
        blob_storage_credentials=azure_creds,
        container_name="fon-data-lake", 
        base_path="processed-data/"
    )
    await processed_storage.save("fon-processed-data", overwrite=True)
    
    # API Keys as Secrets
    await Secret(value=os.getenv("OPENAI_API_KEY")).save("openai-api-key", overwrite=True)
    await Secret(value=os.getenv("NEWSAPI_KEY")).save("newsapi-key", overwrite=True)
    await Secret(value=os.getenv("AZURE_SEARCH_ADMIN_KEY")).save("azure-search-key", overwrite=True)
    
    print("✅ Storage blocks and secrets created successfully!")

if __name__ == "__main__":
    asyncio.run(setup_blocks())