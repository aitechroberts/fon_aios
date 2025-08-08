# setup_prefect_blocks.py
import asyncio
import os
from dotenv import load_dotenv
from prefect_azure import AzureBlobStorageCredentials
from prefect_azure.blob_storage import AzureBlobStorageContainer

load_dotenv()

async def setup_storage_blocks():
    """Create the required Azure storage blocks in Prefect"""
    
    print("Setting up Prefect Azure Storage Blocks...")
    
    # Get Azure credentials from environment
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    
    if not connection_string:
        print("❌ AZURE_STORAGE_CONNECTION_STRING not found in .env")
        print("Format: DefaultEndpointsProtocol=https;AccountName=YOUR_ACCOUNT;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net")
        return False
    
    try:
        # Create Azure credentials block
        azure_creds = AzureBlobStorageCredentials(
            connection_string=connection_string
        )
        await azure_creds.save("azure-storage-creds", overwrite=True)
        print("✅ Created 'azure-storage-creds' block")
        
        # Create Data Lake storage block - pointing to your existing container
        data_lake_block = AzureBlobStorageContainer(
            container_name="aios-data-lake",  # Your existing container
            credentials=azure_creds,
            base_folder="raw-data/"
        )
        await data_lake_block.save("fon-data-lake", overwrite=True)
        print("✅ Created 'fon-data-lake' block (pointing to aios-data-lake/raw-data/)")
        
        # Create Processed Data storage block - same container, different folder
        processed_block = AzureBlobStorageContainer(
            container_name="aios-data-lake",  # Same existing container
            credentials=azure_creds,
            base_folder="processed-data/"
        )
        await processed_block.save("fon-processed-data", overwrite=True)
        print("✅ Created 'fon-processed-data' block (pointing to aios-data-lake/processed-data/)")
        
        print("\n✅ All storage blocks created successfully!")
        print("Both blocks point to your existing 'aios-data-lake' container")
        return True
        
    except Exception as e:
        print(f"❌ Error creating blocks: {e}")
        return False

async def verify_blocks():
    """Verify the blocks can be loaded"""
    try:
        from prefect_azure.blob_storage import AzureBlobStorageContainer
        
        # Try to load the blocks (not creating new containers, just loading the block configurations)
        data_lake = await AzureBlobStorageContainer.load("fon-data-lake")
        processed = await AzureBlobStorageContainer.load("fon-processed-data")
        
        print("\n✅ Verification successful - blocks can be loaded")
        print(f"  Data Lake block: Container '{data_lake.container_name}', Folder '{data_lake.base_folder}'")
        print(f"  Processed block: Container '{processed.container_name}', Folder '{processed.base_folder}'")
        return True
        
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        return False

async def main():
    # Check environment
    print("Checking environment variables...")
    
    required_vars = [
        "AZURE_STORAGE_CONNECTION_STRING",
        "NEWSAPI_AI_KEY"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            print(f"❌ Missing: {var}")
        else:
            print(f"✅ Found: {var}")
    
    if missing:
        print(f"\n❌ Please add missing variables to .env file")
        return
    
    print("\n" + "="*60)
    
    # Setup blocks
    success = await setup_storage_blocks()
    
    if success:
        # Verify they work
        await verify_blocks()
        
        print("\n" + "="*60)
        print("Next steps:")
        print("1. Run your test again: python test_newsapi_topics.py")
        print("2. Check Prefect UI for the created blocks")
        print("3. Your data will be stored in the existing 'aios-data-lake' container")

if __name__ == "__main__":
    asyncio.run(main())