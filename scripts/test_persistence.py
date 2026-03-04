#!/usr/bin/env python3
"""
Persistence Test Script
Populates dummy data, then tests if it survives Supabase restarts
"""
import os
import time
import subprocess
from supabase import create_client

url = "http://127.0.0.1:54421"
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def clear_test_data():
    """Clear any existing test documents"""
    supabase = create_client(url, key)
    supabase.table('documents').delete().ilike('file_name', 'test_document_%').execute()
    print("🧹 Cleared existing test data")

def create_dummy_data(run_id):
    """Create 10 dummy document records"""
    supabase = create_client(url, key)
    
    dummy_docs = []
    for i in range(1, 11):
        dummy_docs.append({
            'file_name': f'test_document_{run_id}_{i}.pdf',
            'file_hash': f'test_hash_{run_id}_{i}' * 4,
            'file_size_bytes': 1000 * i,
            'file_type': 'pdf',
            'current_path': f'/test/path/document_{run_id}_{i}.pdf',
            'document_mode': 'document',
            'is_conversation': False,
            'ai_summary': f'This is test document number {i} from run {run_id}',
            'ai_category': 'other',
            'extracted_text': f'Test content for document {i}',
            'page_count': i,
            'processing_status': 'completed'
        })
    
    result = supabase.table('documents').insert(dummy_docs).execute()
    print(f"✅ Created {len(result.data)} dummy documents")
    return len(result.data)

def check_data():
    """Check if data exists"""
    supabase = create_client(url, key)
    result = supabase.table('documents').select('id', count='exact').execute()
    return result.count

def test_restart():
    """Test restart sequence"""
    print("\n" + "="*60)
    print("🔄 TESTING PERSISTENCE")
    print("="*60)
    
    # Step 0: Clear old test data
    print("\n0️⃣ Clearing old test data...")
    clear_test_data()
    time.sleep(1)
    
    # Step 1: Create dummy data
    print("\n1️⃣ Creating 10 dummy documents...")
    count_before = create_dummy_data(1)
    time.sleep(2)
    
    # Step 2: Verify it's there
    print("\n2️⃣ Verifying data exists...")
    count = check_data()
    if count != count_before:
        print(f"❌ Data mismatch! Expected {count_before}, got {count}")
        return False
    print(f"✅ Verified: {count} documents in DB")
    
    # Step 3: Stop Supabase
    print("\n3️⃣ Stopping Supabase...")
    subprocess.run(['supabase', 'stop'], check=True)
    time.sleep(3)
    
    # Step 4: Start Supabase
    print("\n4️⃣ Starting Supabase...")
    subprocess.run(['supabase', 'start'], check=True)
    time.sleep(10)  # Wait for health checks
    
    # Step 5: Check if data survived
    print("\n5️⃣ Checking if data persisted...")
    time.sleep(2)  # Give it a moment to fully initialize
    count_after = check_data()
    
    if count_after == count_before:
        print(f"✅ SUCCESS! Data persisted: {count_after} documents")
        return True
    else:
        print(f"❌ FAILURE! Data lost. Before: {count_before}, After: {count_after}")
        return False

if __name__ == "__main__":
    # Run test multiple times
    for attempt in range(1, 4):
        print(f"\n{'='*60}")
        print(f"TEST RUN #{attempt}")
        print(f"{'='*60}")
        
        success = test_restart()
        
        if not success:
            print(f"\n❌ Test #{attempt} FAILED. Stopping tests.")
            break
        
        if attempt < 3:
            print(f"\n⏸️  Waiting 5 seconds before next test...")
            time.sleep(5)
    
    print(f"\n{'='*60}")
    print("🏁 PERSISTENCE TEST COMPLETE")
    print(f"{'='*60}")
