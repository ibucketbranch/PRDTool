#!/usr/bin/env python3
"""
Focused report on actual VA claims documents, excluding false positives.
Identifies potential mis-categorizations.
"""
import os
from supabase import create_client
from collections import defaultdict

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

print("="*80)
print("🎯 VA CLAIMS DOCUMENTS - FOCUSED REPORT")
print("="*80)

# Actual VA-related patterns (excluding false positives like "Valderrama")
va_patterns = [
    'VBA-',           # VA forms like VBA-20-0995
    'VA-20-',         # VA form numbers
    'VA-21-',         # VA form numbers
    'DBQ',            # Disability Benefits Questionnaire
    'Supplemental Claim',
    'Veterans Affairs',
    'VA Claims',
    'VA Docs'
]

all_va_docs = {}
search_reasons = defaultdict(list)

print(f"\n🔍 Searching for actual VA claims documents...")

for pattern in va_patterns:
    try:
        # Search filename
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .ilike('file_name', f'%{pattern}%')\
            .execute()
        
        if result.data:
            print(f"   '{pattern}' in filename: {len(result.data)} documents")
            for doc in result.data:
                doc_id = doc['id']
                if doc_id not in all_va_docs:
                    all_va_docs[doc_id] = doc
                search_reasons[doc_id].append(f'filename_{pattern}')
        
        # Search current_path
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .ilike('current_path', f'%{pattern}%')\
            .execute()
        
        if result.data:
            for doc in result.data:
                doc_id = doc['id']
                if doc_id not in all_va_docs:
                    all_va_docs[doc_id] = doc
                search_reasons[doc_id].append(f'path_{pattern}')
    except Exception as e:
        print(f"   Error with '{pattern}': {e}")

# Also search document_locations for original paths
print(f"\n🔍 Searching original paths...")
try:
    result = supabase.table('document_locations')\
        .select('document_id,location_path')\
        .ilike('location_path', '%VA Docs%')\
        .execute()
    
    if result.data:
        doc_ids = list(set([loc['document_id'] for loc in result.data]))
        print(f"   Found {len(doc_ids)} documents with 'VA Docs' in original path")
        
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
                    search_reasons[doc_id].append('original_path_VA Docs')
except Exception as e:
    print(f"   Error: {e}")

print(f"\n📊 Found {len(all_va_docs)} unique VA claims documents")

# Get original paths and categorize
print(f"\n📍 Fetching details...")
docs_with_details = {}
for doc_id, doc in all_va_docs.items():
    try:
        loc_result = supabase.table('document_locations')\
            .select('location_path,location_type')\
            .eq('document_id', doc_id)\
            .eq('location_type', 'original')\
            .limit(1)\
            .execute()
        
        original_path = None
        if loc_result.data:
            original_path = loc_result.data[0].get('location_path')
        
        docs_with_details[doc_id] = {
            'doc': doc,
            'original_path': original_path,
            'reasons': search_reasons.get(doc_id, [])
        }
    except:
        docs_with_details[doc_id] = {
            'doc': doc,
            'original_path': None,
            'reasons': search_reasons.get(doc_id, [])
        }

# Group by category
by_category = defaultdict(list)
for doc_id, details in docs_with_details.items():
    category = details['doc'].get('ai_category', 'uncategorized')
    by_category[category].append((doc_id, details))

print(f"\n{'='*80}")
print(f"📊 VA CLAIMS DOCUMENTS BY CATEGORY")
print(f"{'='*80}")
for category, docs in sorted(by_category.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"  {category}: {len(docs)} documents")

# Identify potential mis-categorizations
print(f"\n{'='*80}")
print(f"⚠️  POTENTIAL MIS-CATEGORIZATIONS")
print(f"{'='*80}")

# VA claims documents should probably be 'legal_document' or have a specific VA category
# Check for VA forms/docs in wrong categories
mis_categorized = []
for doc_id, details in docs_with_details.items():
    doc = details['doc']
    category = doc.get('ai_category', 'uncategorized')
    filename = doc.get('file_name', '').lower()
    path = doc.get('current_path', '').lower()
    
    # VA forms (VBA-20-*, VBA-21-*, VA-20-*, VA-21-*) should be legal_document
    is_va_form = any(x in filename for x in ['vba-20-', 'vba-21-', 'va-20-', 'va-21-', 'dbq'])
    is_va_path = 'va docs' in path or 'veterans affairs' in path or 'va claims' in path
    
    if (is_va_form or is_va_path) and category not in ['legal_document', 'medical_record']:
        mis_categorized.append((doc_id, details, 'Should be legal_document or medical_record'))
    elif is_va_form and category == 'other':
        mis_categorized.append((doc_id, details, 'VA form categorized as "other"'))

if mis_categorized:
    print(f"\n  Found {len(mis_categorized)} potentially mis-categorized documents:")
    for i, (doc_id, details, reason) in enumerate(mis_categorized[:20], 1):
        doc = details['doc']
        print(f"\n  {i}. {doc.get('file_name', 'Unknown')}")
        print(f"     Current Category: {doc.get('ai_category', 'N/A')}")
        print(f"     Issue: {reason}")
        print(f"     Path: {doc.get('current_path', 'N/A')[:80]}...")
else:
    print(f"\n  ✅ No obvious mis-categorizations found")

# Show all documents
print(f"\n{'='*80}")
print(f"📋 ALL VA CLAIMS DOCUMENTS:")
print(f"{'='*80}")

for i, (doc_id, details) in enumerate(list(docs_with_details.items())[:100], 1):
    doc = details['doc']
    reasons = details['reasons']
    orig_path = details['original_path']
    
    print(f"\n{i}. {doc.get('file_name', 'Unknown')}")
    print(f"   🔍 Found by: {', '.join(reasons[:3])}")
    print(f"   📍 Current: {doc.get('current_path', 'N/A')[:90]}...")
    if orig_path:
        print(f"   📍 Original: {orig_path[:90]}...")
    print(f"   🏷️  Category: {doc.get('ai_category', 'N/A')}")

if len(docs_with_details) > 100:
    print(f"\n   ... and {len(docs_with_details) - 100} more")

print(f"\n{'='*80}")
print(f"✅ TOTAL: {len(docs_with_details)} VA claims documents")
print(f"{'='*80}")
