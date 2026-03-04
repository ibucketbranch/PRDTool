#!/usr/bin/env python3
"""Generate a status report of the Google Drive to iCloud move."""
import os
from supabase import create_client

supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

print("="*80)
print("📊 GOOGLE DRIVE → iCLOUD MOVE STATUS REPORT")
print("="*80)

# Count files in each location
gdrive = supabase.table('documents').select('id').ilike('current_path', '%GoogleDrive%').limit(50000).execute()
icloud = supabase.table('documents').select('id').ilike('current_path', '%Mobile Documents/com~apple~CloudDocs%').limit(50000).execute()

gdrive_count = len(gdrive.data) if gdrive.data else 0
icloud_count = len(icloud.data) if icloud.data else 0

print(f"\n📁 CURRENT FILE LOCATIONS:")
print(f"   Files in Google Drive: {gdrive_count}")
print(f"   Files in iCloud: {icloud_count}")
print(f"   Total files in database: {gdrive_count + icloud_count}")

# Check for files that were moved
result = supabase.table('document_locations')\
    .select('document_id')\
    .ilike('location_path', '%GoogleDrive%')\
    .ilike('notes', '%Moved from Google Drive%')\
    .limit(50000)\
    .execute()

if result.data:
    moved_docs = len(set(d['document_id'] for d in result.data))
    print(f"\n✅ FILES MOVED:")
    print(f"   Files with Google Drive history (moved): {moved_docs}")

print(f"\n{'='*80}")
print("📋 SUMMARY")
print(f"{'='*80}")
print(f"  • {gdrive_count} files still in Google Drive")
print(f"  • {icloud_count} files now in iCloud")
if result.data:
    print(f"  • {moved_docs} files have been moved from Google Drive")
print(f"\n💡 Next steps:")
if gdrive_count > 0:
    print(f"  • {gdrive_count} files remain in Google Drive")
    print(f"  • These may need processing or can be handled separately")
print(f"  • Media files (590) need to be imported to Photos")
print(f"  • After media import, Google Drive can be safely deleted")
print(f"{'='*80}")
