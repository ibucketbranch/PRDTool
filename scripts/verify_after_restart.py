#!/usr/bin/env python3
"""
Verify Test Data After Real Restart
Run this AFTER you restart everything to verify data survived
"""
import os
from supabase import create_client

SUPABASE_URL = 'http://127.0.0.1:54421'
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

print("="*80)
print("🔍 VERIFYING TEST DATA AFTER REAL RESTART")
print("="*80)
print()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Count REAL_TEST documents
result = supabase.table('documents').select('id, file_name, created_at', count='exact').ilike('file_name', 'REAL_TEST_%').execute()
count = result.count if hasattr(result, 'count') else len(result.data)

print(f"📊 REAL_TEST Documents Found: {count}/100")
print()

if count == 0:
    print("❌ NO TEST DOCUMENTS FOUND!")
    print("   Data loss detected!")
    print()
    exit(1)
elif count < 100:
    print(f"⚠️  PARTIAL DATA LOSS!")
    print(f"   Expected: 100 documents")
    print(f"   Found: {count} documents")
    print(f"   Lost: {100 - count} documents")
    print()
    exit(1)
else:
    # Show sample documents
    print("✅ ALL 100 DOCUMENTS FOUND!")
    print()
    print("📄 Sample Documents (first 10):")
    print("-"*80)
    sample = supabase.table('documents').select('file_name, created_at').ilike('file_name', 'REAL_TEST_%').limit(10).execute()
    for i, doc in enumerate(sample.data, 1):
        print(f"{i:3d}. {doc['file_name']}")
        print(f"     Created: {doc.get('created_at', 'N/A')}")
        print()
    
    print("="*80)
    print("✅ PROOF: DATA SURVIVED REAL RESTART")
    print("="*80)
    print()
    print(f"   Documents Before Restart: 100")
    print(f"   Documents After Restart:  {count}")
    print(f"   Data Loss: 0 documents")
    print(f"   Persistence Rate: 100%")
    print()
    print("🛡️  System protection VERIFIED!")
    print()
