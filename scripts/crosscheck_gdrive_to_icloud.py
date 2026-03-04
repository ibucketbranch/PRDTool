#!/usr/bin/env python3
"""
Cross-check database: What was moved from Google Drive to iCloud?
Verify all moves are properly tracked.
"""
import os
from collections import defaultdict
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

def get_moved_files():
    """Get all files that were moved from Google Drive to iCloud."""
    print("="*80)
    print("🔍 CROSS-CHECK: Google Drive → iCloud Moves")
    print("="*80)
    
    print(f"\n📊 Loading database records...")
    
    # Get all documents currently in iCloud
    print(f"   1. Finding files currently in iCloud...")
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path,file_hash')\
            .ilike('current_path', '%com~apple~CloudDocs%')\
            .limit(50000)\
            .execute()
        
        icloud_files = {}
        if result.data:
            for doc in result.data:
                icloud_files[doc['id']] = {
                    'file_name': doc.get('file_name'),
                    'current_path': doc.get('current_path'),
                    'file_hash': doc.get('file_hash')
                }
        
        print(f"      Found {len(icloud_files)} files currently in iCloud")
    except Exception as e:
        print(f"      ⚠️  Error: {e}")
        return {}
    
    # Get document_locations for these files
    print(f"   2. Checking location history...")
    moved_files = []
    no_history = []
    
    doc_ids = list(icloud_files.keys())
    batch_size = 100
    
    for i in range(0, len(doc_ids), batch_size):
        batch = doc_ids[i:i+batch_size]
        
        try:
            # Get all location records for these documents
            result = supabase.table('document_locations')\
                .select('document_id,location_path,location_type,notes')\
                .in_('document_id', batch)\
                .execute()
            
            if result.data:
                # Group by document_id
                locations_by_doc = defaultdict(list)
                for loc in result.data:
                    locations_by_doc[loc['document_id']].append(loc)
                
                # Check each document
                for doc_id in batch:
                    if doc_id not in icloud_files:
                        continue
                    
                    doc_info = icloud_files[doc_id]
                    locations = locations_by_doc.get(doc_id, [])
                    
                    # Check if any location is Google Drive
                    google_drive_locations = []
                    original_path = None
                    
                    for loc in locations:
                        loc_path = loc.get('location_path', '')
                        if 'GoogleDrive' in loc_path or 'Google Drive' in loc_path:
                            google_drive_locations.append({
                                'path': loc_path,
                                'type': loc.get('location_type'),
                                'notes': loc.get('notes')
                            })
                        
                        if loc.get('location_type') == 'original':
                            original_path = loc_path
                    
                    if google_drive_locations:
                        moved_files.append({
                            'doc_id': doc_id,
                            'file_name': doc_info['file_name'],
                            'current_path': doc_info['current_path'],
                            'file_hash': doc_info['file_hash'],
                            'google_drive_locations': google_drive_locations,
                            'original_path': original_path
                        })
                    else:
                        # Check if original_path is Google Drive
                        if original_path and ('GoogleDrive' in original_path or 'Google Drive' in original_path):
                            moved_files.append({
                                'doc_id': doc_id,
                                'file_name': doc_info['file_name'],
                                'current_path': doc_info['current_path'],
                                'file_hash': doc_info['file_hash'],
                                'google_drive_locations': [{'path': original_path, 'type': 'original'}],
                                'original_path': original_path
                            })
                        else:
                            no_history.append({
                                'doc_id': doc_id,
                                'file_name': doc_info['file_name'],
                                'current_path': doc_info['current_path']
                            })
        except Exception as e:
            print(f"      ⚠️  Error processing batch: {e}")
    
    print(f"      Found {len(moved_files)} files moved from Google Drive to iCloud")
    print(f"      Found {len(no_history)} files in iCloud with no Google Drive history")
    
    return moved_files, no_history

def analyze_moves(moved_files):
    """Analyze the moves by folder."""
    print(f"\n{'='*80}")
    print("📊 ANALYSIS: Google Drive → iCloud Moves")
    print(f"{'='*80}")
    
    # Group by source folder
    by_source_folder = defaultdict(list)
    by_dest_folder = defaultdict(list)
    
    for move in moved_files:
        # Extract source folder
        gdrive_locs = move['google_drive_locations']
        if gdrive_locs:
            source_path = gdrive_locs[0]['path']
            # Extract folder from path
            if '/My Drive/' in source_path:
                source_folder = source_path.split('/My Drive/')[-1]
                source_folder = '/'.join(source_folder.split('/')[:-1])  # Remove filename
                if not source_folder:
                    source_folder = '(root)'
            else:
                source_folder = 'Unknown'
            
            by_source_folder[source_folder].append(move)
        
        # Extract destination folder
        dest_path = move['current_path']
        if '/Personal Bin/' in dest_path:
            dest_folder = dest_path.split('/Personal Bin/')[-1]
            dest_folder = '/'.join(dest_folder.split('/')[:-1])  # Remove filename
            if not dest_folder:
                dest_folder = '(root)'
        elif '/Documents/' in dest_path:
            dest_folder = dest_path.split('/Documents/')[-1]
            dest_folder = '/'.join(dest_folder.split('/')[:-1])
            if not dest_folder:
                dest_folder = '(root)'
        else:
            dest_folder = 'Other'
        
        by_dest_folder[dest_folder].append(move)
    
    # Report by source folder
    print(f"\n📁 MOVES BY SOURCE FOLDER (Google Drive):")
    for folder, moves in sorted(by_source_folder.items(), key=lambda x: len(x[1]), reverse=True)[:30]:
        print(f"\n  📁 {folder}: {len(moves)} files")
        for move in moves[:5]:
            print(f"     → {move['file_name']}")
            print(f"        Now in: {move['current_path'].split('/')[-2] if '/' in move['current_path'] else 'Unknown'}")
        if len(moves) > 5:
            print(f"     ... and {len(moves) - 5} more")
    
    # Report by destination folder
    print(f"\n{'='*80}")
    print(f"📁 MOVES BY DESTINATION FOLDER (iCloud):")
    for folder, moves in sorted(by_dest_folder.items(), key=lambda x: len(x[1]), reverse=True)[:30]:
        print(f"\n  📁 {folder}: {len(moves)} files")
        for move in moves[:5]:
            print(f"     ← {move['file_name']}")
            if move['google_drive_locations']:
                source = move['google_drive_locations'][0]['path']
                source_folder = source.split('/My Drive/')[-1] if '/My Drive/' in source else source
                print(f"        From: {source_folder[:80]}...")
        if len(moves) > 5:
            print(f"     ... and {len(moves) - 5} more")
    
    return by_source_folder, by_dest_folder

def verify_tracking(moved_files):
    """Verify that moves are properly tracked."""
    print(f"\n{'='*80}")
    print("✅ VERIFICATION: Move Tracking")
    print(f"{'='*80}")
    
    properly_tracked = 0
    missing_original = 0
    missing_previous = 0
    
    for move in moved_files:
        has_original = False
        has_previous = False
        
        for loc in move['google_drive_locations']:
            if loc['type'] == 'original':
                has_original = True
            if loc['type'] == 'previous':
                has_previous = True
        
        if has_original or has_previous:
            properly_tracked += 1
            if not has_original:
                missing_original += 1
            if not has_previous:
                missing_previous += 1
    
    print(f"\n  Properly tracked: {properly_tracked}/{len(moved_files)}")
    if missing_original:
        print(f"  ⚠️  Missing 'original' location: {missing_original}")
    if missing_previous:
        print(f"  ⚠️  Missing 'previous' location: {missing_previous}")
    
    return properly_tracked, missing_original, missing_previous

def main():
    moved_files, no_history = get_moved_files()
    
    if not moved_files:
        print(f"\n❌ No files found that were moved from Google Drive to iCloud")
        return
    
    # Analyze moves
    by_source, by_dest = analyze_moves(moved_files)
    
    # Verify tracking
    properly_tracked, missing_original, missing_previous = verify_tracking(moved_files)
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Total files moved from Google Drive to iCloud: {len(moved_files)}")
    print(f"  Files in iCloud with no Google Drive history: {len(no_history)}")
    print(f"  Properly tracked: {properly_tracked}/{len(moved_files)}")
    print(f"  Source folders: {len(by_source)}")
    print(f"  Destination folders: {len(by_dest)}")
    
    if no_history:
        print(f"\n⚠️  FILES IN iCLOUD WITH NO GOOGLE DRIVE HISTORY:")
        print(f"   (These may have been processed directly from iCloud or other sources)")
        for item in no_history[:10]:
            print(f"   - {item['file_name']}")
        if len(no_history) > 10:
            print(f"   ... and {len(no_history) - 10} more")
    
    print(f"\n{'='*80}")
    print("✅ Cross-check complete")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
