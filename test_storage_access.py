# test_storage_access.py
import asyncio
from prefect_azure.blob_storage import AzureBlobStorageContainer
from azure.storage.blob import BlobServiceClient
import os
from dotenv import load_dotenv

load_dotenv()

async def test_storage_access():
    """Test if we can access the storage and list files"""
    
    print("Testing Azure Storage Access")
    print("="*60)
    
    # Method 1: Using Prefect block
    print("\n1. Testing Prefect Storage Block:")
    try:
        storage = await AzureBlobStorageContainer.load("fon-data-lake")
        print(f"✅ Loaded storage block")
        print(f"   Container: {storage.container_name}")
        print(f"   Base folder: {storage.base_folder}")
        
        # Try to list files
        print("\n   Listing files in processed-parquet/:")
        files = await storage.list_blobs(folder="processed-parquet/")
        for i, file in enumerate(files[:5]):  # Show first 5
            print(f"   - {file}")
            
    except Exception as e:
        print(f"❌ Prefect block error: {e}")
    
    # Method 2: Direct Azure SDK
    print("\n2. Testing Direct Azure SDK:")
    try:
        conn_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        blob_service = BlobServiceClient.from_connection_string(conn_string)
        container_client = blob_service.get_container_client("aios-data-lake")
        
        print("✅ Connected via Azure SDK")
        print("\n   Listing blobs with 'parquet' in path:")
        blobs = container_client.list_blobs()
        count = 0
        for blob in blobs:
            if 'parquet' in blob.name:
                print(f"   - {blob.name}")
                count += 1
                if count >= 5:
                    break
                    
    except Exception as e:
        print(f"❌ Direct SDK error: {e}")

if __name__ == "__main__":
    asyncio.run(test_storage_access())