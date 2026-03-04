#!/usr/bin/env python3
"""
Create Fresh Test Data - For REAL manual restart test
Creates 100 test documents with clear timestamp, then waits for user to restart
"""
import os
import sys
import time
import random
import string
from pathlib import Path
from datetime import datetime
from supabase import create_client

SUPABASE_URL = 'http://127.0.0.1:54421'
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

def generate_unique_id():
    """Generate unique ID for test documents"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))

def clear_test_data():
    """Clear all test documents"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = supabase.table('documents').delete().ilike('file_name', 'REAL_TEST_%').execute()
    print(f"🧹 Cleared old test data")

def create_100_documents():
    """Create 100 dummy documents with REAL_TEST prefix"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    documents = []
    
    creation_time = datetime.now()
    print(f"📝 Creating 100 FRESH test documents...")
    print(f"   Creation time: {creation_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    for i in range(1, 101):
        unique_id = generate_unique_id()
        doc = {
            'file_name': f'REAL_TEST_{unique_id}_{i}.pdf',
            'file_hash': f'real_test_hash_{unique_id}_{i}' * 3,
            'file_size_bytes': 1000 * i,
            'file_type': 'pdf',
            'current_path': f'/test/real/path/document_{unique_id}_{i}.pdf',
            'document_mode': 'document',
            'is_conversation': False,
            'ai_summary': f'REAL TEST document #{i} created at {creation_time.isoformat()}. Unique ID: {unique_id}',
            'ai_category': random.choice(['financial', 'legal', 'project_file', 'other']),
            'extracted_text': f'REAL TEST content for document {i}. Created: {creation_time.isoformat()}. ID: {unique_id}',
            'page_count': i % 50 + 1,
            'processing_status': 'completed',
            'created_at': creation_time.isoformat()
        }
        documents.append(doc)
    
    # Insert in batches of 20
    inserted = 0
    for batch_start in range(0, len(documents), 20):
        batch = documents[batch_start:batch_start + 20]
        result = supabase.table('documents').insert(batch).execute()
        inserted += len(result.data)
        print(f"   ✅ Inserted batch {batch_start//20 + 1}/5 ({inserted}/100)")
    
    return inserted, creation_time

def verify_documents():
    """Verify document count"""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    result = supabase.table('documents').select('id, file_name, created_at', count='exact').ilike('file_name', 'REAL_TEST_%').execute()
    count = result.count if hasattr(result, 'count') else len(result.data)
    
    if count > 0:
        first_doc = result.data[0]
        created_time = first_doc.get('created_at', 'N/A')
        print(f"✅ VERIFIED: {count} documents found")
        print(f"   First document created: {created_time}")
        return True, count, created_time
    else:
        print(f"❌ NO DOCUMENTS FOUND!")
        return False, 0, None

if __name__ == "__main__":
    print("="*80)
    print("🔥 CREATING FRESH TEST DATA FOR REAL RESTART TEST")
    print("="*80)
    print()
    
    # Step 1: Clear old test data
    print("STEP 1: Clearing old test data...")
    clear_test_data()
    time.sleep(1)
    print()
    
    # Step 2: Create 100 fresh documents
    print("STEP 2: Creating 100 fresh test documents...")
    inserted, creation_time = create_100_documents()
    print()
    
    if inserted != 100:
        print(f"❌ Failed to create all documents! Only {inserted}/100 created.")
        sys.exit(1)
    
    # Step 3: Verify
    print("STEP 3: Verifying documents...")
    time.sleep(2)
    success, count, created_time = verify_documents()
    print()
    
    if not success or count != 100:
        print(f"❌ Verification failed! Found {count}/100 documents.")
        sys.exit(1)
    
    # Step 4: Show proof
    print("="*80)
    print("✅ FRESH TEST DATA CREATED AND VERIFIED")
    print("="*80)
    print()
    print(f"📊 Documents Created: {count}/100")
    print(f"🕐 Creation Time: {creation_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📝 Prefix: REAL_TEST_*")
    print()
    print("="*80)
    print("🚨 READY FOR REAL RESTART TEST")
    print("="*80)
    print()
    print("NOW YOU CAN:")
    print("  1. Shut down Docker Desktop completely")
    print("  2. Restart your computer (optional)")
    print("  3. Start Docker Desktop")
    print("  4. Start Supabase: supabase start")
    print("  5. Run verification: python3 scripts/verify_after_restart.py")
    print()
    print("The 100 test documents are NOW in the database.")
    print("Shut everything down and restart when ready!")
    print()
