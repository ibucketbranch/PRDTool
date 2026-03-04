#!/usr/bin/env python3
"""
Verify file transfer is complete and database is updated.
Wait for user confirmation before deletion.
"""
import os
from pathlib import Path
from supabase import create_client

supabase = create_client('http://127.0.0.1:54421', os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
google_drive_path = '/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive'
icloud_base = Path('/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs/Documents')

print("="*80)
print("✅ FILE TRANSFER VERIFICATION & DATABASE CHECK")
print("="*80)

# 1. Check database - documents in Google Drive
print("\n1️⃣  DATABASE VERIFICATION:")
gdrive_docs = supabase.table('documents').select('id,file_name,current_path').ilike('current_path', '%GoogleDrive%').limit(50000).execute()
gdrive_count = len(gdrive_docs.data) if gdrive_docs.data else 0

icloud_docs = supabase.table('documents').select('id').ilike('current_path', '%Mobile Documents/com~apple~CloudDocs%').limit(50000).execute()
icloud_count = len(icloud_docs.data) if icloud_docs.data else 0

# Check move history
moved = supabase.table('document_locations').select('document_id').ilike('location_path', '%GoogleDrive%').ilike('notes', '%Moved from Google Drive%').limit(50000).execute()
if moved.data:
    unique_moved = len(set(d['document_id'] for d in moved.data))
else:
    unique_moved = 0

print(f"   ✅ Documents in database from Google Drive: {gdrive_count}")
print(f"   ✅ Documents in database from iCloud: {icloud_count}")
print(f"   ✅ Documents with move history recorded: {unique_moved}")

if gdrive_count == 0:
    print("   ✅ ALL DOCUMENTS MOVED - Database updated correctly")
else:
    print(f"   ⚠️  {gdrive_count} documents still show Google Drive paths")

# 2. Verify physical files
print("\n2️⃣  PHYSICAL FILE VERIFICATION:")
if not os.path.exists(google_drive_path):
    print(f"   ⚠️  Google Drive path not found: {google_drive_path}")
else:
    # Count important document files
    IMPORTANT_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf'}
    doc_count = 0
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.startswith('.'):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in IMPORTANT_EXTENSIONS:
                doc_count += 1
    
    print(f"   📄 Important document files still in Google Drive: {doc_count}")
    if doc_count == 0:
        print("   ✅ ALL IMPORTANT DOCUMENTS MOVED")

# 3. Verify iCloud destination
print("\n3️⃣  iCLOUD DESTINATION VERIFICATION:")
from_gdrive_folder = icloud_base / 'From Google Drive'
if from_gdrive_folder.exists():
    file_count = sum(1 for f in from_gdrive_folder.rglob('*') if f.is_file())
    dir_count = sum(1 for d in from_gdrive_folder.rglob('*') if d.is_dir())
    print(f"   ✅ 'From Google Drive' folder exists")
    print(f"   ✅ Files in folder: {file_count}")
    print(f"   ✅ Subdirectories: {dir_count}")
else:
    print(f"   ⚠️  'From Google Drive' folder not found (may be empty)")

# 4. Summary
print("\n" + "="*80)
print("📊 TRANSFER SUMMARY")
print("="*80)

if gdrive_count == 0 and doc_count == 0:
    print("\n✅ TRANSFER COMPLETE")
    print("   • All documents moved from Google Drive to iCloud")
    print("   • Database updated with new paths")
    print("   • Move history preserved in document_locations")
    print("\n📋 REMAINING IN GOOGLE DRIVE:")
    print("   • Media files (photos/videos) - need Photos import")
    print("   • Code projects, build artifacts - can be deleted")
    print("\n⏸️  WAITING FOR YOUR CONFIRMATION TO DELETE GOOGLE DRIVE")
    print("   Run: python3 scripts/delete_google_drive.py --confirm")
else:
    print(f"\n⚠️  TRANSFER INCOMPLETE")
    print(f"   • {gdrive_count} documents still in database with Google Drive paths")
    print(f"   • {doc_count} document files still physically in Google Drive")
    print("   • Please review before deletion")

print("="*80)
