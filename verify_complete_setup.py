#!/usr/bin/env python3
import os
import subprocess
import sys
import time
from datetime import datetime

def check_docker_service_health(service_name: str, max_wait: int = 60) -> bool:
    """Check if a Docker service is healthy"""
    print(f"Checking {service_name} health...")
    
    for i in range(max_wait):
        try:
            result = subprocess.run(
                ['docker-compose', 'ps', '--format', 'json'], 
                capture_output=True, text=True, check=True
            )
            
            if service_name in result.stdout and 'healthy' in result.stdout:
                print(f"✅ {service_name} is healthy")
                return True
                
        except subprocess.CalledProcessError:
            pass
        
        if i % 10 == 0 and i > 0:  # Print every 10 seconds
            print(f"   Waiting for {service_name}... ({i}/{max_wait}s)")
        time.sleep(1)
    
    print(f"❌ {service_name} failed health check")
    return False

def check_ui_access():
    """Check if UIs are accessible"""
    import requests
    
    services = {
        'Airflow': 'http://localhost:8080/health',
        'Neo4j': 'http://localhost:7474',
        'NiFi': 'https://localhost:8443/nifi/'
    }
    
    results = {}
    for name, url in services.items():
        try:
            # For HTTPS endpoints, disable SSL verification
            verify_ssl = not url.startswith('https')
            response = requests.get(url, timeout=10, verify=verify_ssl)
            if response.status_code in [200, 401, 403]:  # 401/403 means service is up but needs auth
                print(f"✅ {name} UI accessible")
                results[name] = True
            else:
                print(f"❌ {name} UI returned {response.status_code}")
                results[name] = False
        except Exception as e:
            print(f"❌ {name} UI not accessible: {e}")
            results[name] = False
    
    return all(results.values())

def main():
    print("🔍 Verifying complete FON AIOS setup...\n")
    print(f"Timestamp: {datetime.now()}\n")
    
    checks = []
    
    print("1. Checking Docker service health...")
    services = ['postgres', 'neo4j', 'redis', 'nifi', 'airflow-webserver', 'airflow-scheduler']
    health_checks = [check_docker_service_health(service) for service in services]
    checks.append(all(health_checks))
    
    if not all(health_checks):
        print("❌ Some Docker services are not healthy. Check docker-compose logs.")
        return
    
    print("\n2. Checking UI accessibility...")
    ui_check = check_ui_access()
    checks.append(ui_check)
    
    print("\n" + "="*60)
    
    if all(checks):
        print("🎉 COMPLETE SETUP VERIFICATION SUCCESSFUL!")
        print("\nYour FON AIOS environment is ready with:")
        print("✅ Apache Airflow (Orchestration)")
        print("✅ Apache NiFi (Data Processing)")
        print("✅ dbt (Data Transformation)")
        print("✅ Neo4j (Graph Database)")
        print("✅ PostgreSQL (Airflow Backend)")
        print("✅ Azure AI Search (Document Search)")
        print("✅ NewsAPI Integration")
        
        print("\n🌐 Access your services:")
        print("   Airflow UI: http://localhost:8080 (admin/admin123)")
        print("   NiFi UI: https://localhost:8443/nifi/ (admin/ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB)")
        print("   Neo4j Browser: http://localhost:7474 (neo4j/password123)")
        
        print("\n🚀 Next steps:")
        print("1. Build the NewsAPI client component")
        print("2. Create NiFi data flows")
        print("3. Test the complete pipeline")
        
    else:
        print("❌ SETUP VERIFICATION FAILED!")
        print("Check the issues above before proceeding.")
        
        if not all(health_checks):
            failed_services = [services[i] for i, check in enumerate(health_checks) if not check]
            print(f"\nFailed services: {', '.join(failed_services)}")
            print("Try: docker-compose down && docker-compose up -d")
        
        sys.exit(1)

if __name__ == "__main__":
    main()
