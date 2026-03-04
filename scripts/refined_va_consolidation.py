#!/usr/bin/env python3
"""
Refined plan for consolidating ALL actual VA-related documents.
Filters out false positives like "Valderrama" containing "VA".
"""
import os
from supabase import create_client
from collections import defaultdict
import re

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

print("="*80)
print("📋 REFINED VA DOCS AND APPS CONSOLIDATION PLAN")
print("="*80)

# Actual VA patterns (excluding false positives)
va_patterns = [
    r'VBA-\d',           # VBA-20-0995, VBA-21-4138
    r'VA-\d',            # VA-20-0995, VA-21-8940
    r'\bDBQ\b',          # Disability Benefits Questionnaire
    r'Supplemental Claim',
    r'Veterans Affairs',
    r'VA Docs',
    r'VA Claims',
    r'VA Benefits',
    r'VA Disability',
    r'VA Form',
    r'VA Blue Button',
    r'CalVet',
    r'Calvet',
    r'DVS40',            # CalVet form
    r'VBA Form'
]

all_va_docs = {}
search_reasons = defaultdict(list)

print(f"\n🔍 Searching for actual VA-related documents (filtering false positives)...")

# Search with patterns
for pattern in va_patterns:
    try:
        # Search filename
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .ilike('file_name', f'%{pattern.replace(r"\b", "").replace(r"\d", "")}%')\
            .execute()
        
        if result.data:
            # Filter false positives
            for doc in result.data:
                filename = doc.get('file_name', '')
                # Skip if it's just "Valderrama" or similar false positives
                if re.search(pattern, filename, re.IGNORECASE):
                    doc_id = doc['id']
                    if doc_id not in all_va_docs:
                        all_va_docs[doc_id] = doc
                    search_reasons[doc_id].append(f'filename_{pattern}')
        
        # Search current_path
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash,ai_category,ai_summary')\
            .ilike('current_path', f'%{pattern.replace(r"\b", "").replace(r"\d", "")}%')\
            .execute()
        
        if result.data:
            for doc in result.data:
                path = doc.get('current_path', '')
                if re.search(pattern, path, re.IGNORECASE):
                    doc_id = doc['id']
                    if doc_id not in all_va_docs:
                        all_va_docs[doc_id] = doc
                    search_reasons[doc_id].append(f'path_{pattern}')
    except Exception as e:
        print(f"   Error with '{pattern}': {e}")

# Also search for paths containing VA-related folders
va_path_patterns = ['VA Docs', 'Veterans Affairs', 'VA Claims', 'VA Benefits', 'CalVet', 'Calvet']
for pattern in va_path_patterns:
    try:
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
    except:
        pass

print(f"\n📊 Found {len(all_va_docs)} actual VA-related documents (after filtering)")

# Get original paths and categorize
print(f"\n📍 Categorizing into VA Docs and Apps structure...")
docs_with_details = []

va_categories = {
    'Claims': [],           # VA claims forms, supplemental claims, appeals
    'Medical': [],          # DBQs, medical records, Blue Button reports, disability ratings
    'Benefits': [],         # Education benefits, fee waivers, DVS40 forms
    'Forms': [],            # VA forms (templates, blank forms)
    'Correspondence': [],   # Letters, communications from/to VA
    'Reference': [],        # Policy manuals, guides, case law, evidence mapping
    'Employment': [],      # Employment verification forms (VBA-21-4192)
    'Other': []             # Everything else VA-related
}

for doc_id, doc in all_va_docs.items():
    filename = doc.get('file_name', '').lower()
    path = doc.get('current_path', '').lower()
    category = doc.get('ai_category', '')
    summary = doc.get('ai_summary', '').lower() if doc.get('ai_summary') else ''
    
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
    
    # Smart categorization
    va_category = 'Other'
    
    # Medical: DBQs, Blue Button, disability ratings, medical records
    if (any(x in filename for x in ['dbq', 'blue button', 'rated disabilities', 'disability rating']) or
        'medical' in category or
        'dbq' in summary or 'disability' in summary):
        va_category = 'Medical'
    
    # Claims: Supplemental claims, VBA forms for claims, appeals
    elif (any(x in filename for x in ['supplemental claim', 'vba-20-', 'vba-21-', 'va-20-', 'va-21-', 'claim']) or
          'supplemental' in summary or 'claim' in summary):
        # But not employment verification
        if 'vba-21-4192' not in filename.lower():
            va_category = 'Claims'
    
    # Benefits: Education, fee waivers, DVS40
    elif (any(x in filename for x in ['fee waiver', 'dvs40', 'tuition waiver', 'education benefit', 'vba-21-674']) or
          'fee waiver' in summary or 'tuition' in summary):
        va_category = 'Benefits'
    
    # Forms: Templates, blank forms
    elif (any(x in filename for x in ['template', 'form']) and 
          'filled' not in filename and 'final' not in filename):
        va_category = 'Forms'
    
    # Correspondence: Letters, communications
    elif (any(x in filename for x in ['letter', 'correspondence', 'communication']) or
          category == 'correspondence' or
          'letter' in summary):
        va_category = 'Correspondence'
    
    # Reference: Manuals, guides, case law, evidence
    elif (any(x in filename for x in ['manual', 'policy', 'guide', 'case law', 'cfr', 'evidence mapping', 'table-issues']) or
          'manual' in summary or 'policy' in summary):
        va_category = 'Reference'
    
    # Employment: Employment verification
    elif ('vba-21-4192' in filename.lower() or 'employment' in summary):
        va_category = 'Employment'
    
    va_categories[va_category].append({
        'doc_id': doc_id,
        'filename': doc.get('file_name'),
        'current_path': doc.get('current_path'),
        'original_path': original_path,
        'ai_category': category,
        'summary': doc.get('ai_summary', '')[:150] if doc.get('ai_summary') else ''
    })

# Show detailed plan
print(f"\n{'='*80}")
print(f"📁 PROPOSED VA DOCS AND APPS STRUCTURE:")
print(f"{'='*80}")

base_path = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Personal Bin/VA Docs and Apps"

for category, docs in sorted(va_categories.items(), key=lambda x: len(x[1]), reverse=True):
    if docs:
        print(f"\n📁 {category}/ ({len(docs)} documents)")
        for item in docs[:10]:
            print(f"   - {item['filename']}")
            if item['original_path']:
                print(f"     Original: {item['original_path'][:80]}...")
        if len(docs) > 10:
            print(f"   ... and {len(docs) - 10} more")

print(f"\n{'='*80}")
print(f"📊 CONSOLIDATION SUMMARY:")
print(f"{'='*80}")
print(f"  Total VA-related documents: {len(all_va_docs)}")
print(f"  Base path: {base_path}/")
print(f"\n  Proposed subfolders:")
for category, docs in sorted(va_categories.items(), key=lambda x: len(x[1]), reverse=True):
    if docs:
        print(f"    - {category}/: {len(docs)} documents")

print(f"\n{'='*80}")
print(f"✅ Ready to create consolidation script")
print(f"{'='*80}")
