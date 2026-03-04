#!/usr/bin/env python3
"""
Comprehensive search for all VA-related documents in the database.
Searches paths, filenames, categories, and content.
"""
import os
from supabase import create_client
from collections import defaultdict

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

print("="*80)
print("🔍 COMPREHENSIVE VA DOCUMENTS SEARCH")
print("="*80)

all_va_docs = {}
search_reasons = defaultdict(list)

# 1. Search by current_path
print(f"\n1️⃣ Searching current_path for VA-related paths...")
try:
    result = supabase.table('documents')\
        .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
        .ilike('current_path', '%VA%')\
        .execute()
    
    if result.data:
        print(f"   Found {len(result.data)} documents with 'VA' in current_path")
        for doc in result.data:
            doc_id = doc['id']
            all_va_docs[doc_id] = doc
            search_reasons[doc_id].append('path')
except Exception as e:
    print(f"   Error: {e}")

# 2. Search by filename
print(f"\n2️⃣ Searching filenames for VA-related names...")
try:
    result = supabase.table('documents')\
        .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
        .ilike('file_name', '%VA%')\
        .execute()
    
    if result.data:
        print(f"   Found {len(result.data)} documents with 'VA' in filename")
        for doc in result.data:
            doc_id = doc['id']
            if doc_id not in all_va_docs:
                all_va_docs[doc_id] = doc
            search_reasons[doc_id].append('filename')
except Exception as e:
    print(f"   Error: {e}")

# 3. Search document_locations for VA paths
print(f"\n3️⃣ Searching document_locations for VA-related original paths...")
try:
    result = supabase.table('document_locations')\
        .select('document_id,location_path,location_type')\
        .ilike('location_path', '%VA%')\
        .execute()
    
    if result.data:
        print(f"   Found {len(result.data)} location records with 'VA' in path")
        doc_ids = list(set([loc['document_id'] for loc in result.data]))
        
        # Get documents
        batch_size = 50
        for i in range(0, len(doc_ids), batch_size):
            batch = doc_ids[i:i+batch_size]
            docs_result = supabase.table('documents')\
                .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
                .in_('id', batch)\
                .execute()
            
            if docs_result.data:
                for doc in docs_result.data:
                    doc_id = doc['id']
                    if doc_id not in all_va_docs:
                        all_va_docs[doc_id] = doc
                    search_reasons[doc_id].append('original_path')
except Exception as e:
    print(f"   Error: {e}")

# 4. Search for Veterans Affairs, VBA, DBQ, etc.
print(f"\n4️⃣ Searching for VA-related keywords in filenames...")
keywords = ['VBA', 'DBQ', 'Veterans', 'Supplemental', 'Claim', 'Denial', 'Evidence']
for keyword in keywords:
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .ilike('file_name', f'%{keyword}%')\
            .execute()
        
        if result.data:
            print(f"   '{keyword}': Found {len(result.data)} documents")
            for doc in result.data:
                doc_id = doc['id']
                if doc_id not in all_va_docs:
                    all_va_docs[doc_id] = doc
                search_reasons[doc_id].append(f'keyword_{keyword}')
    except Exception as e:
        print(f"   Error with '{keyword}': {e}")

# 5. Search for potentially mis-categorized documents
print(f"\n5️⃣ Checking for potentially mis-categorized VA documents...")
# Look for legal_document, medical_record, or other categories that might contain VA docs
categories_to_check = ['legal_document', 'medical_record', 'other', 'correspondence']
for category in categories_to_check:
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .eq('ai_category', category)\
            .or_('file_name.ilike.%VA%,current_path.ilike.%VA%,file_name.ilike.%Veterans%,file_name.ilike.%VBA%,file_name.ilike.%DBQ%')\
            .limit(100)\
            .execute()
        
        if result.data:
            print(f"   Category '{category}' with VA keywords: {len(result.data)} documents")
            for doc in result.data:
                doc_id = doc['id']
                if doc_id not in all_va_docs:
                    all_va_docs[doc_id] = doc
                search_reasons[doc_id].append(f'category_{category}')
    except Exception as e:
        # Try simpler query if OR doesn't work
        try:
            result = supabase.table('documents')\
                .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
                .eq('ai_category', category)\
                .ilike('file_name', '%VA%')\
                .limit(100)\
                .execute()
            
            if result.data:
                for doc in result.data:
                    doc_id = doc['id']
                    if doc_id not in all_va_docs:
                        all_va_docs[doc_id] = doc
                    search_reasons[doc_id].append(f'category_{category}')
        except:
            pass

# 6. Get original paths for all found documents
print(f"\n6️⃣ Fetching original paths and location history...")
docs_with_locations = {}
for doc_id in list(all_va_docs.keys())[:200]:  # Limit to first 200 to avoid timeout
    try:
        loc_result = supabase.table('document_locations')\
            .select('location_path,location_type,discovered_at')\
            .eq('document_id', doc_id)\
            .order('discovered_at', desc=False)\
            .execute()
        
        if loc_result.data:
            original_path = None
            for loc in loc_result.data:
                if loc.get('location_type') == 'original':
                    original_path = loc.get('location_path')
                    break
            
            docs_with_locations[doc_id] = {
                'original_path': original_path,
                'all_locations': loc_result.data
            }
    except:
        pass

print(f"\n{'='*80}")
print(f"📊 COMPREHENSIVE RESULTS")
print(f"{'='*80}")
print(f"  Total unique VA-related documents found: {len(all_va_docs)}")

# Group by category
by_category = defaultdict(list)
for doc_id, doc in all_va_docs.items():
    category = doc.get('ai_category', 'uncategorized')
    by_category[category].append((doc_id, doc))

print(f"\n📋 Documents by Category:")
for category, docs in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"  {category}: {len(docs)} documents")

# Show all documents
print(f"\n{'='*80}")
print(f"📋 ALL VA-RELATED DOCUMENTS:")
print(f"{'='*80}")

for i, (doc_id, doc) in enumerate(list(all_va_docs.items())[:100], 1):  # Show first 100
    reasons = search_reasons.get(doc_id, [])
    print(f"\n{i}. {doc.get('file_name', 'Unknown')}")
    print(f"   🔍 Found by: {', '.join(reasons)}")
    print(f"   📍 Current Path: {doc.get('current_path', 'N/A')[:100]}...")
    
    if doc_id in docs_with_locations:
        orig = docs_with_locations[doc_id].get('original_path')
        if orig:
            print(f"   📍 Original Path: {orig[:100]}...")
    
    print(f"   🏷️  Category: {doc.get('ai_category', 'N/A')}")
    
    summary = doc.get('ai_summary', '')
    if summary and len(summary) > 0:
        print(f"   📝 Summary: {summary[:150]}...")

if len(all_va_docs) > 100:
    print(f"\n   ... and {len(all_va_docs) - 100} more documents")

print(f"\n{'='*80}")
print(f"✅ SEARCH COMPLETE")
print(f"{'='*80}")
