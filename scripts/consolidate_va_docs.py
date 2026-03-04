#!/usr/bin/env python3
"""
Consolidate ALL VA-related documents into unified VA Docs and Apps structure.
Moves files and updates database while preserving original paths.
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
    filename_lower = filename.lower() if filename else ''
    path_lower = path.lower() if path else ''
    summary_lower = summary.lower() if summary else ''
    
    # Medical: DBQs, Blue Button, disability ratings
    if (any(x in filename_lower for x in ['dbq', 'blue button', 'rated disabilities', 'disability rating']) or
        'dbq' in summary_lower or 'disability' in summary_lower):
        return 'Medical'
    
    # Claims: Supplemental claims, VBA/VA claim forms (but not employment verification)
    if (any(x in filename_lower for x in ['supplemental claim', 'vba-20-', 'vba-21-', 'va-20-', 'va-21-']) and
        'vba-21-4192' not in filename_lower):
        return 'Claims'
    
    # Employment: Employment verification forms
    if 'vba-21-4192' in filename_lower or ('employment' in summary_lower and 'va' in summary_lower):
        return 'Employment'
    
    # Benefits: Education, fee waivers, DVS40
    if (any(x in filename_lower for x in ['fee waiver', 'dvs40', 'tuition waiver', 'education benefit', 'vba-21-674', 'calvet']) or
        'fee waiver' in summary_lower or 'tuition' in summary_lower):
        return 'Benefits'
    
    # Forms: Templates, blank forms
    if (any(x in filename_lower for x in ['template', 'form']) and 
        'filled' not in filename_lower and 'final' not in filename_lower and
        'additional' in filename_lower):
        return 'Forms'
    
    # Correspondence: Letters, communications
    if (any(x in filename_lower for x in ['letter', 'correspondence']) or
        category == 'correspondence' or
        'letter' in summary_lower):
        return 'Correspondence'
    
    # Reference: Manuals, guides, case law, evidence
    if (any(x in filename_lower for x in ['manual', 'policy', 'guide', 'case law', 'cfr', 'evidence mapping', 'table-issues']) or
        'manual' in summary_lower or 'policy' in summary_lower):
        return 'Reference'
    
    return 'Other'

def main():
    print("="*80)
    print("📋 VA DOCS AND APPS CONSOLIDATION")
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
    
    # Categorize and plan moves
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
    for category, docs in sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True):
        if docs:
            print(f"\n  {category}/: {len(docs)} documents")
            total_to_move += len(docs)
            for item in docs[:5]:
                current = item['current_path']
                if not current.startswith(base_path):
                    print(f"    → {item['filename']}")
                    print(f"      From: {current[:80]}...")
                else:
                    print(f"    ✓ {item['filename']} (already in VA Docs)")
            if len(docs) > 5:
                print(f"    ... and {len(docs) - 5} more")
    
    print(f"\n{'='*80}")
    print(f"📊 SUMMARY:")
    print(f"{'='*80}")
    print(f"  Total VA documents: {len(all_va_docs)}")
    print(f"  Documents to move: {total_to_move}")
    print(f"  Target structure: {base_path}/")
    print(f"\n  Subfolders:")
    for category in sorted(categorized.keys()):
        if categorized[category]:
            print(f"    - {category}/: {len(categorized[category])} documents")
    
    print(f"\n{'='*80}")
    print(f"✅ Plan complete. Ready to execute moves.")
    print(f"{'='*80}")
    
    return categorized, all_va_docs

if __name__ == "__main__":
    categorized, all_va_docs = main()
