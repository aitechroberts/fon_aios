from prefect.filesystems import RemoteFileSystem
from prefect_azure import AzureBlobStorageCredentials
from prefect_azure.blob_storage import AzureBlobStorageBlock
import os

async def setup_storage_blocks():
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