#!/usr/bin/env python3
"""
PROOF OF DATA PERSISTENCE - Show all test documents exist
"""
import os
from supabase import create_client

SUPABASE_URL = 'http://127.0.0.1:54421'
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*80)
print("🔍 PROOF: Test Documents in Database")
print("="*80)

# Count test documents
result = supabase.table('documents').select('id', count='exact').ilike('file_name', 'STRESS_TEST_%').execute()
count = result.count if hasattr(result, 'count') else len(result.data)

print(f"\n📊 TEST DOCUMENTS FOUND: {count}/100")
print()

if count > 0:
    # Get first 20 to show
    result = supabase.table('documents').select('file_name, file_hash, ai_summary, created_at').ilike('file_name', 'STRESS_TEST_%').limit(20).execute()
    
    print("📄 Sample Documents (showing first 20):")
    print("-"*80)
    for i, doc in enumerate(result.data, 1):
        print(f"{i:3d}. {doc['file_name']}")
        print(f"     Hash: {doc['file_hash'][:50]}...")
        print(f"     Created: {doc.get('created_at', 'N/A')}")
        print()
    
    if count > 20:
        print(f"... and {count - 20} more test documents")
    
    print("\n" + "="*80)
    print("✅ PROOF: Test documents exist in database")
    print("="*80)
else:
    print("❌ NO TEST DOCUMENTS FOUND!")
    print("   Run: python3 scripts/stress_test_persistence.py")
