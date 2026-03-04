#!/usr/bin/env python3
"""
Check Supabase database for documents originally from the VA Evidence folder.
"""
import os
from supabase import create_client

target_path = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/VA Docs and Apps/Supplemental Claim (Denial)/Evidence"

# Connect to Supabase
supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

print("="*80)
print("🔍 CHECKING SUPABASE FOR VA EVIDENCE FOLDER FILES")
print("="*80)
print(f"\nTarget path: {target_path}")

# Query 1: Check current_path
print(f"\n1️⃣ Checking 'current_path' field...")
try:
    result = supabase.table('documents')\
        .select('id,file_name,current_path,file_hash,ai_category,created_at')\
        .ilike('current_path', f'%{target_path}%')\
        .execute()
    
    current_path_matches = result.data if result.data else []
    print(f"   Found {len(current_path_matches)} documents with path in current_path")
except Exception as e:
    print(f"   Error: {e}")
    current_path_matches = []

# Query 2: Check document_locations for original path
print(f"\n2️⃣ Checking 'document_locations' table for original paths...")
try:
    # First get all location records that match
    locations_result = supabase.table('document_locations')\
        .select('document_id,location_path,location_type,discovered_at')\
        .ilike('location_path', f'%{target_path}%')\
        .execute()
    
    location_matches = locations_result.data if locations_result.data else []
    print(f"   Found {len(location_matches)} location records matching path")
    
    # Now get the actual documents for these locations
    doc_ids = [loc['document_id'] for loc in location_matches]
    original_path_docs = []
    
    if doc_ids:
        # Query in batches
        batch_size = 100
        for i in range(0, len(doc_ids), batch_size):
            batch = doc_ids[i:i+batch_size]
            docs_result = supabase.table('documents')\
                .select('id,file_name,current_path,file_hash,ai_category,created_at')\
                .in_('id', batch)\
                .execute()
            
            if docs_result.data:
                original_path_docs.extend(docs_result.data)
        
        print(f"   Found {len(original_path_docs)} documents with original path matching")
except Exception as e:
    print(f"   Error: {e}")
    original_path_docs = []
    location_matches = []

# Combine and deduplicate
all_docs = {}
for doc in current_path_matches:
    all_docs[doc['id']] = doc

for doc in original_path_docs:
    if doc['id'] not in all_docs:
        all_docs[doc['id']] = doc

# Get location info for all found docs
print(f"\n3️⃣ Getting location history for found documents...")
docs_with_locations = []
for doc_id, doc in all_docs.items():
    try:
        loc_result = supabase.table('document_locations')\
            .select('location_path,location_type,discovered_at')\
            .eq('document_id', doc_id)\
            .order('discovered_at', desc=False)\
            .execute()
        
        locations = loc_result.data if loc_result.data else []
        
        # Find original path
        original_path = None
        for loc in locations:
            if loc['location_type'] == 'original':
                original_path = loc['location_path']
                break
        
        docs_with_locations.append({
            'doc': doc,
            'original_path': original_path,
            'current_path': doc.get('current_path'),
            'all_locations': locations
        })
    except:
        docs_with_locations.append({
            'doc': doc,
            'original_path': None,
            'current_path': doc.get('current_path'),
            'all_locations': []
        })

print(f"\n{'='*80}")
print(f"📊 SUMMARY")
print(f"{'='*80}")
print(f"  Total unique documents found: {len(docs_with_locations)}")
print(f"  Documents with original path matching: {len([d for d in docs_with_locations if d['original_path'] and target_path in d['original_path']])}")
print(f"  Documents with current path matching: {len([d for d in docs_with_locations if target_path in d['current_path']])}")

if docs_with_locations:
    print(f"\n📋 DOCUMENTS FOUND:")
    print(f"{'='*80}")
    
    for i, item in enumerate(docs_with_locations[:20], 1):  # Show first 20
        doc = item['doc']
        print(f"\n{i}. {doc.get('file_name', 'Unknown')}")
        print(f"   ID: {doc.get('id')}")
        print(f"   Hash: {doc.get('file_hash', '')[:16]}...")
        print(f"   Category: {doc.get('ai_category', 'N/A')}")
        print(f"   Created: {doc.get('created_at', 'N/A')[:19] if doc.get('created_at') else 'N/A'}")
        
        if item['original_path']:
            print(f"   📍 Original Path: {item['original_path']}")
        if item['current_path']:
            print(f"   📍 Current Path: {item['current_path']}")
        
        if item['all_locations']:
            print(f"   📍 Location History ({len(item['all_locations'])} locations):")
            for loc in item['all_locations'][:3]:
                print(f"      - {loc.get('location_type', 'unknown')}: {loc.get('location_path', 'N/A')}")
            if len(item['all_locations']) > 3:
                print(f"      ... and {len(item['all_locations']) - 3} more")
    
    if len(docs_with_locations) > 20:
        print(f"\n   ... and {len(docs_with_locations) - 20} more documents")
else:
    print(f"\n❌ No documents found in database for this path")
    print(f"   This could mean:")
    print(f"   - Files were never processed/ingested")
    print(f"   - Files were deleted before processing")
    print(f"   - Path has changed")

print(f"\n{'='*80}")
