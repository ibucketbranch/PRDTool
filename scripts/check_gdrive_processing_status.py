#!/usr/bin/env python3
"""
Check status of Google Drive processing - see what's been processed.
"""
import os
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

def check_status():
    """Check what's been processed from Google Drive."""
    print("="*80)
    print("📊 GOOGLE DRIVE PROCESSING STATUS")
    print("="*80)
    
    # Count files in Google Drive by type
    print(f"\n🔍 Scanning Google Drive...")
    files_by_type = {}
    important_exts = ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf']
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.startswith('.'):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in important_exts:
                files_by_type[ext] = files_by_type.get(ext, 0) + 1
    
    print(f"\n📁 Files in Google Drive:")
    for ext in important_exts:
        count = files_by_type.get(ext, 0)
        print(f"   {ext}: {count:,} files")
    
    # Count files in database from Google Drive
    print(f"\n📊 Files in database (from Google Drive):")
    
    db_counts = {}
    for ext in important_exts:
        try:
            result = supabase.table('documents')\
                .select('id', count='exact')\
                .ilike('current_path', f'%{google_drive_path}%')\
                .ilike('file_name', f'%{ext}')\
                .execute()
            
            db_counts[ext] = result.count if hasattr(result, 'count') else len(result.data) if result.data else 0
        except:
            db_counts[ext] = 0
    
    for ext in important_exts:
        gdrive_count = files_by_type.get(ext, 0)
        db_count = db_counts.get(ext, 0)
        pct = (db_count / gdrive_count * 100) if gdrive_count > 0 else 0
        print(f"   {ext}: {db_count:,} / {gdrive_count:,} ({pct:.1f}%)")
    
    # Also check by file_hash matching (files that were moved)
    print(f"\n📊 Total files processed (including moved):")
    try:
        result = supabase.table('document_locations')\
            .select('document_id')\
            .ilike('location_path', f'%{google_drive_path}%')\
            .execute()
        
        moved_count = len(set([loc['document_id'] for loc in result.data])) if result.data else 0
        print(f"   Files with Google Drive history: {moved_count:,}")
    except:
        pass
    
    print(f"\n{'='*80}")
    print("✅ Status check complete")
    print(f"{'='*80}")

if __name__ == "__main__":
    check_status()
