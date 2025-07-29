#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv(".local.env")

def test_newsapi():
    """Test NewsAPI connection"""
    api_key = os.getenv('NEWSAPI_KEY')
    if not api_key or api_key.startswith('REPLACE_WITH'):
        print("❌ NEWSAPI_KEY not configured in .env file")
        return False
    
    url = f"https://newsapi.org/v2/everything?q=DARPA&apiKey={api_key}&pageSize=1"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ NewsAPI connected! Found {data.get('totalResults', 0)} articles")
            return True
        else:
            print(f"❌ NewsAPI error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ NewsAPI connection failed: {e}")
        return False

def test_azure_search():
    """Test Azure Search connection"""
    service_name = os.getenv('AZURE_SEARCH_SERVICE_NAME')
    admin_key = os.getenv('AZURE_SEARCH_ADMIN_KEY')
    
    if not service_name or service_name.startswith('REPLACE_WITH'):
        print("❌ Azure Search credentials not configured in .env file")
        return False
    
    try:
        from azure.search.documents.indexes import SearchIndexClient
        from azure.core.credentials import AzureKeyCredential
        
        endpoint = f"https://{service_name}.search.windows.net"
        credential = AzureKeyCredential(admin_key)
        
        client = SearchIndexClient(endpoint=endpoint, credential=credential)
        indexes = list(client.list_indexes())
        print(f"✅ Azure Search connected! Found {len(indexes)} existing indexes")
        return True
        
    except Exception as e:
        print(f"❌ Azure Search connection failed: {e}")
        return False

def check_env_file():
    """Check if .env file has been properly configured"""
    required_vars = [
        'NEWSAPI_KEY',
        'AZURE_SEARCH_SERVICE_NAME', 
        'AZURE_SEARCH_ADMIN_KEY'
    ]
    
    missing = []
    placeholder = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        elif value.startswith('REPLACE_WITH'):
            placeholder.append(var)
    
    if missing:
        print(f"❌ Missing environment variables: {missing}")
        return False
    
    if placeholder:
        print(f"❌ Placeholder values need to be replaced: {placeholder}")
        print("Please edit your .env file with actual credentials")
        return False
    
    print("✅ All required environment variables configured")
    return True

if __name__ == "__main__":
    print("🔍 Testing Azure connectivity...\n")
    
    # Check .env file first
    env_ok = check_env_file()
    if not env_ok:
        print("\n❌ Please configure your .env file before testing connectivity")
        sys.exit(1)
    
    # Install basic dependencies for testing
    print("Installing basic dependencies...")
    os.system("uv pip install python-dotenv requests azure-search-documents azure-identity")
    
    print("\nTesting connections...")
    newsapi_ok = test_newsapi()
    azure_ok = test_azure_search()
    
    if newsapi_ok and azure_ok:
        print("\n🎉 All external services are accessible!")
        print("Ready to install full dependencies and start Docker services...")
    else:
        print("\n❌ Some services failed. Check your .env file credentials.")
        sys.exit(1)
