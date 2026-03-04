#!/usr/bin/env python3
"""
Health Check - Validates database state before operations
"""
import subprocess
import sys
from pathlib import Path

# Add scripts directory to path for lock_manager
sys.path.insert(0, str(Path(__file__).parent))
from lock_manager import update_health_check

def check_connection():
    """Test if database is accessible"""
    try:
        result = subprocess.run(
            ['psql', 'postgresql://postgres:postgres@127.0.0.1:54422/postgres', 
             '-c', 'SELECT 1;'],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False

def get_document_count():
    """Get current document count"""
    try:
        result = subprocess.run(
            ['psql', 'postgresql://postgres:postgres@127.0.0.1:54422/postgres', 
             '-t', '-c', 'SELECT COUNT(*) FROM documents;'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except:
        pass
    return -1

def check_docker():
    """Check if Docker is running"""
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def main():
    print("🏥 Health Check...")
    
    # Check Docker
    if not check_docker():
        print("❌ Docker is not running!")
        sys.exit(1)
    print("✅ Docker is running")
    
    # Check connection
    if not check_connection():
        print("❌ Database not accessible!")
        sys.exit(1)
    print("✅ Database is accessible")
    
    # Check document count
    count = get_document_count()
    if count < 0:
        print("⚠️  Could not retrieve document count")
    else:
        print(f"✅ Document count: {count}")
    
    print("\n✅ All health checks passed")
    
    # Update lock file
    update_health_check()

if __name__ == "__main__":
    main()
