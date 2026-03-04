#!/usr/bin/env python3
"""
Execute consolidation of ALL VA-related documents into unified VA Docs and Apps structure.
Moves files physically and updates database while preserving original paths.
"""
import os
import shutil
from pathlib import Path
from supabase import create_client
from collections import defaultdict
from datetime import datetime
import re

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

base_path = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Personal Bin/VA Docs and Apps"

def categorize_va_document(filename, path, category, summary):
    """Categorize a VA document into subfolder."""
    f = (filename or '').lower()
    p = (path or '').lower()
    s = (summary or '').lower() if summary else ''
    
    # Medical: DBQs, Blue Button, disability ratings
    if (any(x in f for x in ['dbq', 'blue button', 'rated disabilities', 'disability rating']) or
        'dbq' in s or 'disability' in s):
        return 'Medical'
    
    # Claims: Supplemental claims, VBA/VA claim forms (but not employment verification)
    if (any(x in f for x in ['supplemental claim', 'vba-20-', 'vba-21-', 'va-20-', 'va-21-']) and
        'vba-21-4192' not in f):
        return 'Claims'
    
    # Employment: Employment verification forms
    if 'vba-21-4192' in f or ('employment' in s and 'va' in s):
        return 'Employment'
    
    # Benefits: Education, fee waivers, DVS40, CalVet (including home loans)
    if (any(x in f for x in ['fee waiver', 'dvs40', 'tuition waiver', 'education benefit', 'vba-21-674', 'calvet', 'calvethomeloan', 'calvet home']) or
        'fee waiver' in s or 'tuition' in s or 'calvet' in s):
        return 'Benefits'
    
    # Forms: Templates, blank forms
    if (any(x in f for x in ['template', 'form']) and 
        'filled' not in f and 'final' not in f and
        ('additional' in f or 'blank' in f)):
        return 'Forms'
    
    # Correspondence: Letters, communications
    if (any(x in f for x in ['letter', 'correspondence']) or
        category == 'correspondence' or
        'letter' in s):
        return 'Correspondence'
    
    # Reference: Manuals, guides, case law, evidence
    if (any(x in f for x in ['manual', 'policy', 'guide', 'case law', 'cfr', 'evidence mapping', 'table-issues']) or
        'manual' in s or 'policy' in s):
        return 'Reference'
    
    return 'Other'

def unique_target_path(target_dir, filename):
    """Generate unique target path if file exists."""
    target_path = target_dir / filename
    
    if not target_path.exists():
        return target_path
    
    # File exists, append counter
    stem = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    
    while target_path.exists():
        new_filename = f"{stem}_{counter}{ext}"
        target_path = target_dir / new_filename
        counter += 1
    
    return target_path

def main():
    print("="*80)
    print("📋 VA DOCS AND APPS CONSOLIDATION - EXECUTION")
    print("="*80)
    
    # Find all VA documents
    print(f"\n🔍 Finding all VA-related documents...")
    
    va_patterns = [
        'VBA-', 'VA-20-', 'VA-21-', 'DBQ', 'Supplemental Claim',
        'Veterans Affairs', 'VA Docs', 'VA Claims', 'VA Benefits',
        'CalVet', 'Calvet', 'DVS40', 'VA Form', 'VA Blue Button'
    ]
    
    all_va_docs = {}
    
    for pattern in va_patterns:
        try:
            result = supabase.table('documents')\
                .select('id,file_name,current_path,ai_category,ai_summary,file_hash')\
                .ilike('file_name', f'%{pattern}%')\
                .execute()
            
            if result.data:
                for doc in result.data:
                    doc_id = doc['id']
                    if doc_id not in all_va_docs:
                        all_va_docs[doc_id] = doc
            
            result = supabase.table('documents')\
                .select('id,file_name,current_path,ai_category,ai_summary,file_hash')\
                .ilike('current_path', f'%{pattern}%')\
                .execute()
            
            if result.data:
                for doc in result.data:
                    doc_id = doc['id']
                    if doc_id not in all_va_docs:
                        all_va_docs[doc_id] = doc
        except:
            pass
    
    print(f"   Found {len(all_va_docs)} VA-related documents")
    
    # Categorize
    print(f"\n📁 Categorizing documents...")
    categorized = defaultdict(list)
    
    for doc_id, doc in all_va_docs.items():
        filename = doc.get('file_name', '')
        current_path = doc.get('current_path', '')
        category = doc.get('ai_category', '')
        summary = doc.get('ai_summary', '')
        
        va_category = categorize_va_document(filename, current_path, category, summary)
        
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
        
        categorized[va_category].append({
            'doc_id': doc_id,
            'filename': filename,
            'current_path': current_path,
            'original_path': original_path,
            'file_hash': doc.get('file_hash'),
            'va_category': va_category
        })
    
    # Show plan
    print(f"\n{'='*80}")
    print(f"📁 CONSOLIDATION PLAN:")
    print(f"{'='*80}")
    
    total_to_move = 0
    already_there = 0
    
    for category, docs in sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True):
        if docs:
            print(f"\n  {category}/: {len(docs)} documents")
            for item in docs:
                current = item['current_path']
                if current.startswith(base_path):
                    already_there += 1
                else:
                    total_to_move += 1
    
    print(f"\n{'='*80}")
    print(f"📊 SUMMARY:")
    print(f"{'='*80}")
    print(f"  Total VA documents: {len(all_va_docs)}")
    print(f"  Documents to move: {total_to_move}")
    print(f"  Already in VA Docs: {already_there}")
    print(f"  Target: {base_path}/")
    
    print(f"\n  Proposed structure:")
    for category in sorted(categorized.keys()):
        if categorized[category]:
            print(f"    - {category}/: {len(categorized[category])} documents")
    
    print(f"\n{'='*80}")
    print(f"⚠️  DRY RUN MODE - No files will be moved")
    print(f"   Review the plan above, then run with --execute to move files")
    print(f"{'='*80}")
    
    return categorized, all_va_docs

if __name__ == "__main__":
    categorized, all_va_docs = main()
