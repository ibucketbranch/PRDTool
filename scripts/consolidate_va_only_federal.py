#!/usr/bin/env python3
"""
Consolidate ONLY federal VA (VA.gov) documents - NOT CalVet (California Veterans).
CalVet is state-level and should be kept separate.
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

def is_calvet_document(filename, path, summary):
    """Check if document is CalVet (California) not federal VA."""
    f = (filename or '').lower()
    p = (path or '').lower()
    s = (summary or '').lower() if summary else ''
    
    calvet_indicators = [
        'calvet', 'cal vet', 'california department of veterans',
        'dvs40', 'california veterans', 'ca vet'
    ]
    
    return any(indicator in f or indicator in p or indicator in s for indicator in calvet_indicators)

def categorize_va_document(filename, path, category, summary):
    """Categorize a FEDERAL VA document into subfolder."""
    f = (filename or '').lower()
    p = (path or '').lower()
    s = (summary or '').lower() if summary else ''
    
    # Skip CalVet
    if is_calvet_document(filename, path, summary):
        return None
    
    # Medical: DBQs, Blue Button, disability ratings
    if any(x in f for x in ['dbq', 'blue button', 'rated disabilities', 'disability rating']):
        return 'Medical'
    
    # Claims: Supplemental claims, VBA/VA claim forms (but not employment verification)
    if (any(x in f for x in ['supplemental claim', 'vba-20-', 'vba-21-', 'va-20-', 'va-21-']) and
        'vba-21-4192' not in f):
        return 'Claims'
    
    # Employment: Employment verification forms
    if 'vba-21-4192' in f:
        return 'Employment'
    
    # Benefits: Education, fee waivers (federal VA only)
    if any(x in f for x in ['vba-21-674', 'va education', 'va benefit']):
        return 'Benefits'
    
    # Forms: Templates, blank forms (federal VA)
    if 'template' in f and 'filled' not in f and 'additional' in f:
        return 'Forms'
    
    # Correspondence: Letters, communications (federal VA)
    if ('letter' in f or category == 'correspondence') and 'calvet' not in f:
        return 'Correspondence'
    
    # Reference: Manuals, guides, case law, evidence
    if any(x in f for x in ['manual', 'case law', 'cfr', 'evidence mapping', 'table-issues']):
        return 'Reference'
    
    # Other VA-related (but not CalVet)
    if any(x in f for x in ['veterans affairs', 'va-', 'vba-']) or 'va' in p:
        return 'Other'
    
    return None

def is_google_drive_path(path):
    """Check if path is in Google Drive."""
    if not path:
        return False
    path_lower = path.lower()
    return 'googledrive' in path_lower or 'google drive' in path_lower

def is_icloud_path(path):
    """Check if path is already in iCloud."""
    if not path:
        return False
    return 'com~apple~CloudDocs' in path or 'Mobile Documents' in path

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
        print("📋 FEDERAL VA DOCS CONSOLIDATION - DRY RUN")
        print("   (CalVet EXCLUDED)")
        print("   Step 1: Reorganize iCloud files into VA Docs structure")
        print("   Step 2: Move Google Drive files to iCloud VA Docs")
    else:
        print("📋 FEDERAL VA DOCS CONSOLIDATION - EXECUTING")
        print("   (CalVet EXCLUDED)")
        print("   Step 1: Reorganizing iCloud files into VA Docs structure")
        print("   Step 2: Moving Google Drive files to iCloud VA Docs")
    print("="*80)
    
    # Find all VA documents (federal VA patterns only, excluding CalVet)
    print(f"\n🔍 Finding federal VA-related documents (excluding CalVet)...")
    
    va_patterns = [
        'VBA-', 'VA-20-', 'VA-21-', 'DBQ', 'Supplemental Claim',
        'Veterans Affairs', 'VA Docs', 'VA Claims', 'VA Benefits',
        'VA Form', 'VA Blue Button'
    ]
    
    all_va_docs = {}
    calvet_docs = []
    
    for pattern in va_patterns:
        try:
            result = supabase.table('documents')\
                .select('id,file_name,current_path,ai_category,ai_summary,file_hash')\
                .ilike('file_name', f'%{pattern}%')\
                .execute()
            
            if result.data:
                for doc in result.data:
                    # Filter out CalVet
                    if is_calvet_document(doc.get('file_name'), doc.get('current_path'), doc.get('ai_summary')):
                        calvet_docs.append(doc)
                    else:
                        all_va_docs[doc['id']] = doc
            
            result = supabase.table('documents')\
                .select('id,file_name,current_path,ai_category,ai_summary,file_hash')\
                .ilike('current_path', f'%{pattern}%')\
                .execute()
            
            if result.data:
                for doc in result.data:
                    if doc['id'] not in all_va_docs:
                        if is_calvet_document(doc.get('file_name'), doc.get('current_path'), doc.get('ai_summary')):
                            calvet_docs.append(doc)
                        else:
                            all_va_docs[doc['id']] = doc
        except:
            pass
    
    print(f"   Found {len(all_va_docs)} federal VA documents")
    print(f"   Excluded {len(calvet_docs)} CalVet documents (California, not federal VA)")
    
    # Categorize
    categorized = defaultdict(list)
    uncategorized = []
    
    for doc_id, doc in all_va_docs.items():
        va_category = categorize_va_document(
            doc.get('file_name'),
            doc.get('current_path'),
            doc.get('ai_category'),
            doc.get('ai_summary')
        )
        
        if va_category is None:
            uncategorized.append(doc)
            continue
        
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
    
    if uncategorized:
        print(f"\n   ⚠️  {len(uncategorized)} documents found but not clearly VA-related:")
        for doc in uncategorized[:5]:
            print(f"      - {doc.get('file_name')}")
        if len(uncategorized) > 5:
            print(f"      ... and {len(uncategorized) - 5} more")
    
    # Execute moves
    moved = 0
    moved_from_google = 0
    moved_from_icloud = 0
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
            
            # Determine move type
            from_google_drive = is_google_drive_path(current_path)
            from_icloud = is_icloud_path(current_path) and not current_path.startswith(base_path)
            
            if not from_google_drive and not from_icloud:
                print(f"   ⊘ {filename} (not in Google Drive or iCloud, skipping)")
                skipped += 1
                continue
            
            target_file = unique_target_path(target_dir, filename)
            
            if dry_run:
                move_type = "Google Drive → iCloud" if from_google_drive else "iCloud reorganization"
                print(f"   → {filename}")
                print(f"      From: {current_path[:80]}...")
                print(f"      To:   {target_file}")
                print(f"      Type: {move_type}")
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
                    
                    if from_google_drive:
                        print(f"   ✅ {filename} (moved from Google Drive)")
                        moved_from_google += 1
                    else:
                        print(f"   ✅ {filename} (reorganized within iCloud)")
                        moved_from_icloud += 1
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
    print(f"  Federal VA documents found: {len(all_va_docs)}")
    print(f"  CalVet documents excluded: {len(calvet_docs)}")
    print(f"  Total moved: {moved}")
    if not dry_run:
        print(f"    - From Google Drive → iCloud: {moved_from_google}")
        print(f"    - Reorganized within iCloud: {moved_from_icloud}")
    print(f"  Skipped (already in VA Docs/other): {skipped}")
    print(f"  Errors: {errors}")
    print(f"\n  Target structure: {base_path}/")
    for category in sorted(categorized.keys()):
        if categorized[category]:
            print(f"    - {category}/: {len(categorized[category])} documents")
    print(f"{'='*80}")
    
    if dry_run:
        print(f"\n💡 To execute moves, run: python3 {sys.argv[0]} --execute")
    else:
        print(f"\n✅ All federal VA documents consolidated into VA Docs and Apps structure")
        print(f"   CalVet documents remain in their current locations (California state, not federal VA)")
        
        # Clean up empty folders after moving files
        print(f"\n🧹 Cleaning up empty folders...")
        try:
            import subprocess
            result = subprocess.run(
                ['python3', 'scripts/cleanup_empty_folders.py', '--execute', '--force-empty'],
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                print(f"   ✅ Empty folders cleaned up")
            else:
                print(f"   ⚠️  Cleanup had issues (non-critical)")
        except Exception as e:
            print(f"   ⚠️  Could not clean up empty folders: {e}")

if __name__ == "__main__":
    main()
