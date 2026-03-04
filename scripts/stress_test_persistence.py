#!/usr/bin/env python3
"""
COMPREHENSIVE STRESS TEST - 100 Documents, Full System Restart
Tests data persistence through multiple restart cycles
"""
import os
import sys
import time
import subprocess
import random
import string
from pathlib import Path
from datetime import datetime
from supabase import create_client

# Configuration
SUPABASE_URL = 'http://127.0.0.1:54421'
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def generate_unique_id():
    """Generate unique ID for test documents"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

def clear_test_data():
    """Clear all test documents"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = supabase.table('documents').delete().ilike('file_name', 'STRESS_TEST_%').execute()
    print(f"🧹 Cleared existing test data")

def create_100_documents():
    """Create 100 dummy documents"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    documents = []
    
    print("📝 Creating 100 test documents...")
    for i in range(1, 101):
        unique_id = generate_unique_id()
        doc = {
            'file_name': f'STRESS_TEST_{unique_id}_{i}.pdf',
            'file_hash': f'stress_test_hash_{unique_id}_{i}' * 3,  # Make it long enough
            'file_size_bytes': 1000 * i,
            'file_type': 'pdf',
            'current_path': f'/test/stress/path/document_{unique_id}_{i}.pdf',
            'document_mode': 'document',
            'is_conversation': False,
            'ai_summary': f'This is stress test document #{i} with unique ID {unique_id}. Created at {datetime.now().isoformat()}',
            'ai_category': random.choice(['financial', 'legal', 'project_file', 'other']),
            'extracted_text': f'Test content for stress test document {i}. Unique identifier: {unique_id}',
            'page_count': i % 50 + 1,  # 1-50 pages
            'processing_status': 'completed',
            'created_at': datetime.now().isoformat()
        }
        documents.append(doc)
    
    # Insert in batches of 20
    inserted = 0
    for batch_start in range(0, len(documents), 20):
        batch = documents[batch_start:batch_start + 20]
        result = supabase.table('documents').insert(batch).execute()
        inserted += len(result.data)
        print(f"   ✅ Inserted batch {batch_start//20 + 1}/5 ({inserted}/100)")
    
    return inserted

def verify_documents(expected_count):
    """Verify document count matches expected"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = supabase.table('documents').select('id', count='exact').ilike('file_name', 'STRESS_TEST_%').execute()
    count = result.count if hasattr(result, 'count') else len(result.data)
    
    if count == expected_count:
        print(f"✅ VERIFIED: {count} documents found (expected {expected_count})")
        return True
    else:
        print(f"❌ MISMATCH: Found {count} documents, expected {expected_count}")
        return False

def check_db_connection():
    """Check if database is accessible"""
    try:
        result = subprocess.run(
            ['psql', 'postgresql://postgres:postgres@127.0.0.1:54422/postgres', 
             '-c', 'SELECT 1;'],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False

def safe_supabase_stop():
    """Stop Supabase using safety wrapper"""
    script_dir = Path(__file__).parent
    result = subprocess.run(
        ['bash', '-c', f'source {script_dir}/safety_wrapper.sh && safe_supabase_stop'],
        capture_output=True, text=True, timeout=60
    )
    return result.returncode == 0, result.stdout, result.stderr

def safe_supabase_start():
    """Start Supabase using safety wrapper"""
    script_dir = Path(__file__).parent
    result = subprocess.run(
        ['bash', '-c', f'source {script_dir}/safety_wrapper.sh && safe_supabase_start'],
        capture_output=True, text=True, timeout=120
    )
    return result.returncode == 0, result.stdout, result.stderr

def wait_for_db(max_wait=30):
    """Wait for database to become accessible"""
    for i in range(max_wait):
        if check_db_connection():
            return True
        time.sleep(1)
    return False

def test_cycle(cycle_num):
    """Run one complete test cycle"""
    print(f"\n{'='*80}")
    print(f"🔄 TEST CYCLE #{cycle_num}")
    print(f"{'='*80}\n")
    
    # Step 1: Verify initial state
    print("1️⃣  Verifying initial document count...")
    if not verify_documents(100):
        print("❌ FAILED: Initial verification failed!")
        return False
    
    # Step 2: Create backup
    print("\n2️⃣  Creating backup before restart...")
    script_dir = Path(__file__).parent
    backup_result = subprocess.run(
        [sys.executable, str(script_dir / 'auto_backup.py')],
        capture_output=True, text=True, timeout=300
    )
    if backup_result.returncode == 0:
        print("✅ Backup created successfully")
    else:
        print(f"⚠️  Backup warning: {backup_result.stderr}")
    
    # Step 3: Stop Supabase
    print("\n3️⃣  Stopping Supabase (using safety wrapper)...")
    success, stdout, stderr = safe_supabase_stop()
    if success:
        print("✅ Supabase stopped")
    else:
        print(f"⚠️  Stop output: {stdout}")
        if stderr:
            print(f"   Stderr: {stderr}")
    
    # Step 4: Wait a moment
    print("\n4️⃣  Waiting 5 seconds...")
    time.sleep(5)
    
    # Step 5: Start Supabase
    print("\n5️⃣  Starting Supabase (using safety wrapper)...")
    success, stdout, stderr = safe_supabase_start()
    if not success:
        print(f"❌ Failed to start: {stderr}")
        return False
    print("✅ Supabase start command executed")
    
    # Step 6: Wait for DB to be ready
    print("\n6️⃣  Waiting for database to be ready...")
    if not wait_for_db(30):
        print("❌ Database did not become accessible!")
        return False
    print("✅ Database is accessible")
    
    # Step 7: Verify documents still exist
    print("\n7️⃣  Verifying documents persisted...")
    time.sleep(2)  # Give it a moment to fully initialize
    if not verify_documents(100):
        print("❌ FAILED: Documents did not persist!")
        return False
    
    print(f"\n✅ TEST CYCLE #{cycle_num} PASSED!")
    return True

def main():
    print("="*80)
    print("🔥 COMPREHENSIVE STRESS TEST - 100 Documents")
    print("="*80)
    print("\nThis test will:")
    print("  1. Create 100 dummy documents")
    print("  2. Run 3 complete restart cycles")
    print("  3. Verify data persists through all restarts")
    print("\n⚠️  This will restart Supabase multiple times!")
    print("\n🚀 Starting test in 3 seconds...")
    time.sleep(3)
    
    try:
        # Step 0: Clear old test data
        print("\n0️⃣  Clearing old test data...")
        clear_test_data()
        time.sleep(1)
        
        # Step 1: Create 100 documents
        print("\n" + "="*80)
        print("STEP 1: Creating 100 test documents")
        print("="*80)
        count = create_100_documents()
        if count != 100:
            print(f"❌ Failed to create all documents! Only {count}/100 created.")
            return
        
        time.sleep(2)
        
        # Step 2: Verify initial creation
        print("\n" + "="*80)
        print("STEP 2: Verifying initial creation")
        print("="*80)
        if not verify_documents(100):
            print("❌ Initial verification failed!")
            return
        
        # Step 3: Run 3 test cycles
        print("\n" + "="*80)
        print("STEP 3: Running 3 restart cycles")
        print("="*80)
        
        all_passed = True
        for cycle in range(1, 4):
            if not test_cycle(cycle):
                all_passed = False
                break
            time.sleep(3)  # Brief pause between cycles
        
        # Final verification
        print("\n" + "="*80)
        print("FINAL VERIFICATION")
        print("="*80)
        final_check = verify_documents(100)
        
        if all_passed and final_check:
            print("\n" + "="*80)
            print("🎉 ALL TESTS PASSED!")
            print("="*80)
            print("✅ 100 documents created")
            print("✅ All 3 restart cycles passed")
            print("✅ Data persisted through all restarts")
            print("✅ System is robust and protected")
            print("="*80)
        else:
            print("\n" + "="*80)
            print("❌ TEST FAILED")
            print("="*80)
            print("Data loss detected. System needs investigation.")
            print("="*80)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
