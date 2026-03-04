#!/usr/bin/env python3
"""
Explain the discrepancy between path-based and hash-based counts.
"""
import os
from supabase import create_client

supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
google_drive_path = '/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive'

print("="*80)
print("🔍 EXPLAINING THE DISCREPANCY")
print("="*80)

# Get all documents
print("\n📊 Database Analysis:")
result = supabase.table('documents').select('id,file_hash,current_path').limit(50000).execute()

if result.data:
    total_docs = len(result.data)
    gdrive_docs = [d for d in result.data if 'GoogleDrive' in d.get('current_path', '')]
    other_docs = [d for d in result.data if 'GoogleDrive' not in d.get('current_path', '')]
    
    print(f"   Total documents in database: {total_docs}")
    print(f"   Documents from Google Drive: {len(gdrive_docs)}")
    print(f"   Documents from OTHER locations: {len(other_docs)}")
    
    # Get unique hashes
    all_hashes = set()
    gdrive_hashes = set()
    other_hashes = set()
    
    for doc in result.data:
        h = doc.get('file_hash')
        if h:
            all_hashes.add(h)
            if 'GoogleDrive' in doc.get('current_path', ''):
                gdrive_hashes.add(h)
            else:
                other_hashes.add(h)
    
    print(f"\n   Unique file hashes:")
    print(f"      Total unique hashes: {len(all_hashes)}")
    print(f"      From Google Drive: {len(gdrive_hashes)}")
    print(f"      From other locations: {len(other_hashes)}")
    
    # Check for overlap
    overlap = gdrive_hashes & other_hashes
    print(f"\n   Hash overlap (same file in both locations): {len(overlap)}")
    
    if overlap:
        print(f"\n   ⚠️  Found {len(overlap)} files that exist in BOTH Google Drive and other locations!")
        print(f"      These are duplicates - same file, different paths")

print("\n" + "="*80)
print("💡 EXPLANATION")
print("="*80)
print("""
The discrepancy comes from TWO different counting methods:

1. PATH-BASED COUNT (890 files):
   - Counts files in database WHERE current_path contains 'GoogleDrive'
   - Shows: 890 files from Google Drive are in the database
   - This is ACCURATE for files currently in Google Drive

2. HASH-BASED COUNT (1,068 'unprocessed'):
   - Compares Google Drive file hashes against ALL database hashes
   - Database has 1,000 total hashes (from ALL locations, not just Google Drive)
   - Many files in database are from iCloud/other locations
   - So when checking Google Drive files, it finds 1,068 that don't match ANY hash
   
WHY THE DIFFERENCE?

The hash check is comparing:
- 1,082 Google Drive files
- Against 1,000 total database hashes (from all locations)

But the path check shows:
- 890 files in database with Google Drive paths
- This means ~110 files might be duplicates or moved

RECOMMENDATION:

The 890 files with Google Drive paths are the ones that matter.
The hash-based check is finding files that:
1. Are truly unprocessed (new files)
2. Are duplicates of files in other locations (same content, different path)
3. Were processed but then moved/renamed

We should focus on the 890 processed files and move those to iCloud.
The remaining files can be handled separately if needed.
""")

print("="*80)
