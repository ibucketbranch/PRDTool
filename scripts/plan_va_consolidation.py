#!/usr/bin/env python3
"""
Plan consolidation of ALL VA-related documents into a unified VA Docs and Apps structure.
"""
import os
from supabase import create_client
from collections import defaultdict

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

print("="*80)
print("📋 PLAN: VA DOCS AND APPS CONSOLIDATION")
print("="*80)

# Search for ALL VA-related content
va_keywords = [
    'VBA', 'DBQ', 'Veterans Affairs', 'VA-', 'VA_', 'Supplemental Claim',
    'VA Claim', 'Veterans', 'VA Docs', 'CalVet', 'Calvet', 'DVS40',
    'VA Benefits', 'VA Disability', 'VA Form', 'VA Blue Button'
]

all_va_docs = {}
search_reasons = defaultdict(list)

print(f"\n🔍 Searching for ALL VA-related documents...")

for keyword in va_keywords:
    try:
        # Search filename
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .ilike('file_name', f'%{keyword}%')\
            .execute()
        
        if result.data:
            for doc in result.data:
                doc_id = doc['id']
                if doc_id not in all_va_docs:
                    all_va_docs[doc_id] = doc
                search_reasons[doc_id].append(f'filename_{keyword}')
        
        # Search current_path
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .ilike('current_path', f'%{keyword}%')\
            .execute()
        
        if result.data:
            for doc in result.data:
                doc_id = doc['id']
                if doc_id not in all_va_docs:
                    all_va_docs[doc_id] = doc
                search_reasons[doc_id].append(f'path_{keyword}')
    except Exception as e:
        print(f"   Error with '{keyword}': {e}")

# Also search document_locations
print(f"\n🔍 Searching original paths...")
try:
    result = supabase.table('document_locations')\
        .select('document_id,location_path')\
        .or_('location_path.ilike.%VA%,location_path.ilike.%Veterans%,location_path.ilike.%CalVet%,location_path.ilike.%Calvet%')\
        .limit(200)\
        .execute()
    
    if result.data:
        doc_ids = list(set([loc['document_id'] for loc in result.data]))
        
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
except:
    # Try individual queries
    for pattern in ['VA', 'Veterans', 'CalVet', 'Calvet']:
        try:
            result = supabase.table('document_locations')\
                .select('document_id')\
                .ilike('location_path', f'%{pattern}%')\
                .limit(100)\
                .execute()
            
            if result.data:
                doc_ids = [loc['document_id'] for loc in result.data]
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
        except:
            pass

print(f"\n📊 Found {len(all_va_docs)} total VA-related documents")

# Get original paths and categorize
print(f"\n📍 Fetching details and categorizing...")
docs_with_details = {}

# Categorize into subfolders
va_categories = {
    'Claims': [],           # VA claims forms, supplemental claims
    'Medical': [],          # DBQs, medical records, Blue Button reports
    'Benefits': [],         # Education benefits, fee waivers
    'Forms': [],            # VA forms (templates, blank)
    'Correspondence': [],   # Letters, communications
    'Reference': [],        # Policy manuals, guides, case law
    'Employment': [],       # Employment verification forms
    'Other': []             # Everything else
}

for doc_id, doc in all_va_docs.items():
    filename = doc.get('file_name', '').lower()
    path = doc.get('current_path', '').lower()
    category = doc.get('ai_category', '')
    summary = doc.get('ai_summary', '').lower()
    
    # Get original path
    try:
        loc_result = supabase.table('document_locations')\
            .select('location_path')\
            .eq('document_id', doc_id)\
            .eq('location_type', 'original')\
            .limit(1)\
            .execute()
        
        original_path = None
        if loc_result.data:
            original_path = loc_result.data[0].get('location_path')
    except:
        original_path = None
    
    # Categorize
    va_category = 'Other'
    
    if any(x in filename for x in ['dbq', 'blue button', 'medical', 'disability', 'rated']) or 'medical' in category:
        va_category = 'Medical'
    elif any(x in filename for x in ['claim', 'supplemental', 'vba-20-', 'vba-21-', 'va-20-', 'va-21-']):
        va_category = 'Claims'
    elif any(x in filename for x in ['fee waiver', 'dvs40', 'education', 'tuition', 'vba-21-674']):
        va_category = 'Benefits'
    elif any(x in filename for x in ['template', 'form']) and 'filled' not in filename:
        va_category = 'Forms'
    elif any(x in filename for x in ['letter', 'correspondence']) or category == 'correspondence':
        va_category = 'Correspondence'
    elif any(x in filename for x in ['manual', 'policy', 'guide', 'case law', 'cfr', 'evidence mapping']):
        va_category = 'Reference'
    elif any(x in filename for x in ['employment', 'vba-21-4192']):
        va_category = 'Employment'
    
    va_categories[va_category].append({
        'doc_id': doc_id,
        'filename': doc.get('file_name'),
        'current_path': doc.get('current_path'),
        'original_path': original_path,
        'ai_category': category,
        'summary': doc.get('ai_summary', '')[:150]
    })

# Show plan
print(f"\n{'='*80}")
print(f"📁 PROPOSED VA DOCS AND APPS STRUCTURE:")
print(f"{'='*80}")

base_path = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Personal Bin/VA Docs and Apps"

for category, docs in sorted(va_categories.items(), key=lambda x: len(x[1]), reverse=True):
    if docs:
        print(f"\n📁 {category}/ ({len(docs)} documents)")
        for item in docs[:5]:
            print(f"   - {item['filename']}")
        if len(docs) > 5:
            print(f"   ... and {len(docs) - 5} more")

print(f"\n{'='*80}")
print(f"📊 SUMMARY:")
print(f"{'='*80}")
print(f"  Total VA-related documents: {len(all_va_docs)}")
print(f"  Proposed structure: {base_path}/")
for category, docs in va_categories.items():
    if docs:
        print(f"    - {category}/: {len(docs)} documents")

print(f"\n{'='*80}")
print(f"💡 NEXT STEPS:")
print(f"{'='*80}")
print(f"  1. Review the categorization above")
print(f"  2. I can create a script to move all VA documents to this structure")
print(f"  3. Update database with new paths")
print(f"  4. Preserve original paths in document_locations")
print(f"{'='*80}")
