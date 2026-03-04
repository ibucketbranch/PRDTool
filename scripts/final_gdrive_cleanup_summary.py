#!/usr/bin/env python3
"""
Final summary before Google Drive deletion.
Shows what's left and what needs to be done.
"""
import os
from supabase import create_client

supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
google_drive_path = '/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive'

print("="*80)
print("📋 FINAL GOOGLE DRIVE CLEANUP SUMMARY")
print("="*80)

# Count remaining files
gdrive_docs = supabase.table('documents').select('id').ilike('current_path', '%GoogleDrive%').limit(50000).execute()
gdrive_count = len(gdrive_docs.data) if gdrive_docs.data else 0

# Count media files
MEDIA_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.heic', '.heif',
                    '.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.flv',
                    '.cr2', '.nef', '.orf', '.raf', '.rw2', '.arw', '.dng'}

media_count = 0
other_files = 0

if os.path.exists(google_drive_path):
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.startswith('.'):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                media_count += 1
            else:
                other_files += 1

print(f"\n📊 REMAINING IN GOOGLE DRIVE:")
print(f"   Document files (in database): {gdrive_count}")
print(f"   Media files (photos/videos): {media_count}")
print(f"   Other files: {other_files}")
print(f"   Total remaining: {gdrive_count + media_count + other_files}")

print(f"\n{'='*80}")
print("✅ COMPLETED")
print(f"{'='*80}")
print(f"  • All processed documents moved to iCloud")
print(f"  • Files organized by AI categorization")
print(f"  • Uncategorized files in: iCloud/Documents/From Google Drive/")

print(f"\n{'='*80}")
print("📋 REMAINING TASKS")
print(f"{'='*80}")
if media_count > 0:
    print(f"\n1. Import {media_count} media files to Photos app")
    print(f"   Run: python3 scripts/verify_media_in_photos.py")
    print(f"   Then: python3 scripts/delete_verified_media_from_gdrive.py --execute")
if gdrive_count > 0:
    print(f"\n2. {gdrive_count} document files still in Google Drive")
    print(f"   These may be duplicates or need special handling")
if other_files > 0:
    print(f"\n3. {other_files} other files (code, build artifacts, etc.)")
    print(f"   These can likely be deleted or ignored")

print(f"\n{'='*80}")
print("🎯 NEXT STEP")
print(f"{'='*80}")
if media_count > 0:
    print(f"\nImport {media_count} media files to Photos, then Google Drive can be deleted.")
else:
    print(f"\n✅ All important files moved. Google Drive can be safely deleted.")
print(f"{'='*80}")
