#!/usr/bin/env python3
"""
Move ALL VA-related documents to consolidated VA Docs and Apps structure.
Updates database and preserves original paths.
"""
import os
import shutil
import sys
from pathlib import Path
from supabase import create_client
from collections import defaultdict
from datetime import datetime

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

base_path = "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents/Personal Bin/VA Docs and Apps"

def categorize_va_document(filename, path, category, summary):
    """Categorize a VA document into subfolder."""
    f = (filename or '').lower()
    p = (path or '').lower()
    s = (summary or '').lower() if summary else ''
    
    if any(x in f for x in ['dbq', 'blue button', 'rated disabilities']):
        return 'Medical'
    if any(x in f for x in ['supplemental claim', 'vba-20-', 'vba-21-', 'va-20-', 'va-21-']) and 'vba-21-4192' not in f:
        return 'Claims'
    if 'vba-21-4192' in f:
        return 'Employment'
    if any(x in f for x in ['fee waiver', 'dvs40', 'tuition', 'calvet']):
        return 'Benefits'
    if 'template' in f and 'filled' not in f and 'additional' in f:
        return 'Forms'
    if 'letter' in f or category == 'correspondence':
        return 'Correspondence'
    if any(x in f for x in ['manual', 'case law', 'cfr', 'evidence mapping']):
        return 'Reference'
    return 'Other'

def unique_target_path(target_dir, filename):
    """Generate unique target path if file exists."""
    target_path = target_dir / filename
    if not target_path.exists():
        return target_path
    
    stem = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    while target_path.exists():
        new_filename = f"{stem}_{counter}{ext}"
        target_path = target_dir / new_filename
        counter += 1
    return target_path

def main():
    dry_run = '--execute' not in sys.argv
    
    print("="*80)
    if dry_run:
        print("📋 VA DOCS CONSOLIDATION - DRY RUN")
    else:
        print("📋 VA DOCS CONSOLIDATION - EXECUTING MOVES")
    print("="*80)
    
    # Find all VA documents
    print(f"\n🔍 Finding all VA-related documents...")
    
    va_patterns = ['VBA-', 'VA-20-', 'VA-21-', 'DBQ', 'Supplemental Claim', 'Veterans Affairs', 'VA Docs', 'VA Claims', 'CalVet', 'Calvet', 'DVS40']
    all_va_docs = {}
    
    for pattern in va_patterns:
        try:
            result = supabase.table('documents')\
                .select('id,file_name,current_path,ai_category,ai_summary,file_hash')\
                .ilike('file_name', f'%{pattern}%')\
                .execute()
            if result.data:
                for doc in result.data:
                    all_va_docs[doc['id']] = doc
            
            result = supabase.table('documents')\
                .select('id,file_name,current_path,ai_category,ai_summary,file_hash')\
                .ilike('current_path', f'%{pattern}%')\
                .execute()
            if result.data:
                for doc in result.data:
                    if doc['id'] not in all_va_docs:
                        all_va_docs[doc['id']] = doc
        except:
            pass
    
    print(f"   Found {len(all_va_docs)} VA-related documents")
    
    # Categorize
    categorized = defaultdict(list)
    for doc_id, doc in all_va_docs.items():
        va_category = categorize_va_document(
            doc.get('file_name'),
            doc.get('current_path'),
            doc.get('ai_category'),
            doc.get('ai_summary')
        )
        
        try:
            loc_result = supabase.table('document_locations')\
                .select('location_path')\
                .eq('document_id', doc_id)\
                .eq('location_type', 'original')\
                .limit(1)\
                .execute()
            original_path = loc_result.data[0].get('location_path') if loc_result.data else None
        except:
            original_path = None
        
        categorized[va_category].append({
            'doc_id': doc_id,
            'filename': doc.get('file_name'),
            'current_path': doc.get('current_path'),
            'original_path': original_path,
            'file_hash': doc.get('file_hash'),
            'va_category': va_category
        })
    
    # Execute moves
    moved = 0
    skipped = 0
    errors = 0
    
    print(f"\n{'='*80}")
    print(f"📦 MOVING FILES:")
    print(f"{'='*80}")
    
    for category, docs in sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True):
        if not docs:
            continue
        
        target_dir = Path(base_path) / category
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📁 {category}/ ({len(docs)} documents):")
        
        for item in docs:
            current_path = item['current_path']
            filename = item['filename']
            
            # Skip if already in target location
            if current_path.startswith(base_path):
                print(f"   ✓ {filename} (already in VA Docs)")
                skipped += 1
                continue
            
            source_path = Path(current_path)
            if not source_path.exists():
                print(f"   ⚠️  {filename} - Source file not found")
                errors += 1
                continue
            
            target_file = unique_target_path(target_dir, filename)
            
            if dry_run:
                print(f"   → {filename}")
                print(f"      From: {current_path[:80]}...")
                print(f"      To:   {target_file}")
                moved += 1
            else:
                try:
                    # Move file
                    shutil.move(str(source_path), str(target_file))
                    
                    # Update database
                    new_path = str(target_file)
                    old_path = current_path
                    
                    # Update current_path
                    supabase.table('documents')\
                        .update({'current_path': new_path})\
                        .eq('id', item['doc_id'])\
                        .execute()
                    
                    # Record old path as 'previous'
                    supabase.table('document_locations')\
                        .insert({
                            'document_id': item['doc_id'],
                            'location_path': old_path,
                            'location_type': 'previous',
                            'discovered_at': datetime.now().isoformat(),
                            'verified_at': datetime.now().isoformat(),
                            'is_accessible': False,
                            'notes': f'Moved to VA Docs consolidation: {category}/'
                        })\
                        .execute()
                    
                    print(f"   ✅ {filename}")
                    moved += 1
                    
                except PermissionError:
                    print(f"   ⚠️  {filename} - Permission denied (may be in use)")
                    errors += 1
                except Exception as e:
                    print(f"   ❌ {filename} - Error: {e}")
                    errors += 1
    
    print(f"\n{'='*80}")
    if dry_run:
        print(f"📊 DRY RUN COMPLETE")
    else:
        print(f"✅ CONSOLIDATION COMPLETE")
    print(f"{'='*80}")
    print(f"  Total documents: {len(all_va_docs)}")
    print(f"  Moved: {moved}")
    print(f"  Skipped (already there): {skipped}")
    print(f"  Errors: {errors}")
    print(f"\n  Target structure: {base_path}/")
    for category in sorted(categorized.keys()):
        if categorized[category]:
            print(f"    - {category}/: {len(categorized[category])} documents")
    print(f"{'='*80}")
    
    if dry_run:
        print(f"\n💡 To execute moves, run: python3 {sys.argv[0]} --execute")
    else:
        print(f"\n✅ All VA documents consolidated into VA Docs and Apps structure")
        print(f"   Original paths preserved in document_locations table")

if __name__ == "__main__":
    main()
