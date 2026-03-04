#!/usr/bin/env python3
"""
Deep check of folder history - find ALL files that were ever in a folder,
even if paths don't match exactly.
"""
import os
import sys
from supabase import create_client
from pathlib import Path

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

def normalize_path(path):
    """Normalize path for comparison."""
    if not path:
        return ""
    # Remove trailing spaces, normalize separators
    return path.strip().replace('\\', '/')

def find_all_files_from_folder(folder_path):
    """Find ALL files that were ever in this folder using multiple search strategies."""
    print("="*80)
    print(f"🔍 DEEP HISTORY CHECK: {folder_path}")
    print("="*80)
    
    folder_normalized = normalize_path(folder_path)
    folder_name = os.path.basename(folder_normalized.rstrip('/'))
    
    print(f"\n📋 Search strategies:")
    print(f"   1. Exact path match")
    print(f"   2. Folder name match")
    print(f"   3. Parent folder match")
    print(f"   4. All document_locations (original/previous)")
    
    all_found = {}
    
    # Strategy 1: Exact path match (with and without trailing space)
    print(f"\n1️⃣  Exact path search...")
    search_terms = [
        folder_path,
        folder_path.rstrip(),
        folder_path.rstrip() + ' ',
        folder_normalized,
    ]
    
    for term in search_terms:
        try:
            # Check current_path
            result = supabase.table('documents')\
                .select('id,file_name,current_path')\
                .ilike('current_path', f'%{term}%')\
                .execute()
            
            if result.data:
                for doc in result.data:
                    all_found[doc['id']] = {
                        'file_name': doc['file_name'],
                        'current_path': doc['current_path'],
                        'found_via': 'current_path',
                        'search_term': term
                    }
            
            # Check document_locations
            result = supabase.table('document_locations')\
                .select('document_id,location_path,location_type')\
                .ilike('location_path', f'%{term}%')\
                .execute()
            
            if result.data:
                doc_ids = list(set([loc['document_id'] for loc in result.data]))
                docs_result = supabase.table('documents')\
                    .select('id,file_name,current_path')\
                    .in_('id', doc_ids)\
                    .execute()
                
                for doc in docs_result.data:
                    if doc['id'] not in all_found:
                        all_found[doc['id']] = {
                            'file_name': doc['file_name'],
                            'current_path': doc['current_path'],
                            'found_via': 'document_locations',
                            'search_term': term
                        }
        except Exception as e:
            print(f"   ⚠️  Error with term '{term}': {e}")
    
    # Strategy 2: Folder name match (just the folder name)
    print(f"\n2️⃣  Folder name search: '{folder_name}'...")
    try:
        result = supabase.table('document_locations')\
            .select('document_id,location_path,location_type')\
            .ilike('location_path', f'%{folder_name}%')\
            .execute()
        
        if result.data:
            # Filter to only those that actually contain this folder
            for loc in result.data:
                loc_path = normalize_path(loc['location_path'])
                if folder_name.lower() in loc_path.lower():
                    doc_id = loc['document_id']
                    if doc_id not in all_found:
                        docs_result = supabase.table('documents')\
                            .select('id,file_name,current_path')\
                            .eq('id', doc_id)\
                            .execute()
                        
                        if docs_result.data:
                            doc = docs_result.data[0]
                            all_found[doc_id] = {
                                'file_name': doc['file_name'],
                                'current_path': doc['current_path'],
                                'found_via': 'folder_name_match',
                                'original_location': loc['location_path'],
                                'location_type': loc['location_type']
                            }
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Strategy 3: Get ALL document_locations and manually check
    print(f"\n3️⃣  Comprehensive document_locations scan...")
    try:
        # Get all locations that might be related
        result = supabase.table('document_locations')\
            .select('document_id,location_path,location_type,notes')\
            .limit(10000)\
            .execute()
        
        if result.data:
            print(f"   Scanning {len(result.data)} location records...")
            matches = []
            for loc in result.data:
                loc_path = normalize_path(loc['location_path'])
                # Check if this path contains our folder
                if folder_normalized.lower() in loc_path.lower() or folder_name.lower() in loc_path.lower():
                    # Verify it's actually this folder (not just similar name)
                    if folder_name.lower() in loc_path.lower():
                        matches.append(loc)
            
            if matches:
                print(f"   Found {len(matches)} potential matches")
                doc_ids = list(set([m['document_id'] for m in matches]))
                docs_result = supabase.table('documents')\
                    .select('id,file_name,current_path')\
                    .in_('id', doc_ids)\
                    .execute()
                
                docs_by_id = {doc['id']: doc for doc in docs_result.data}
                
                for match in matches:
                    doc_id = match['document_id']
                    if doc_id not in all_found:
                        doc = docs_by_id.get(doc_id)
                        if doc:
                            all_found[doc_id] = {
                                'file_name': doc['file_name'],
                                'current_path': doc['current_path'],
                                'found_via': 'comprehensive_scan',
                                'original_location': match['location_path'],
                                'location_type': match['location_type'],
                                'notes': match.get('notes')
                            }
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Report findings
    print(f"\n{'='*80}")
    print(f"📊 RESULTS:")
    print(f"{'='*80}")
    
    if all_found:
        print(f"\n✅ Found {len(all_found)} files that were in this folder:")
        print(f"\n")
        
        for doc_id, info in sorted(all_found.items(), key=lambda x: x[1]['file_name']):
            print(f"📄 {info['file_name']}")
            print(f"   Current location: {info['current_path']}")
            if 'original_location' in info:
                print(f"   Original/Previous: {info['original_location']}")
                print(f"   Location type: {info.get('location_type', 'unknown')}")
            print(f"   Found via: {info['found_via']}")
            if info.get('notes'):
                print(f"   Notes: {info['notes']}")
            print()
    else:
        print(f"\n❌ NO FILES FOUND")
        print(f"\n   This means:")
        print(f"   - Files were never processed from this folder")
        print(f"   - OR files were deleted before being processed")
        print(f"   - OR folder was created but never used")
        print(f"\n   The folder was effectively empty.")
    
    print(f"{'='*80}")
    
    return all_found

if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder = sys.argv[1]
        find_all_files_from_folder(folder)
    else:
        # Check the deleted folders
        folders_to_check = [
            "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/VA Docs and Apps/2024-2025 Activities/Original AD Medical Records ",
            "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/VA Docs and Apps/2024-2025 Activities/VA Forms",
            "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Personal Bin/VA Docs and Apps/Supplemental Claim (Denial)/Evidence",
        ]
        
        for folder in folders_to_check:
            find_all_files_from_folder(folder)
            print("\n\n")
