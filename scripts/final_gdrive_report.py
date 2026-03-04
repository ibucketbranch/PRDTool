#!/usr/bin/env python3
"""
Final comprehensive report on Google Drive processing.
"""
import os
from collections import defaultdict
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

def generate_final_report():
    """Generate comprehensive final report."""
    print("="*80)
    print("📋 FINAL GOOGLE DRIVE PROCESSING REPORT")
    print("="*80)
    
    # Count files in Google Drive
    print(f"\n🔍 Scanning Google Drive...")
    files_by_type = defaultdict(int)
    total_size = 0
    
    important_exts = ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf']
    
    for root, dirs, files in os.walk(google_drive_path):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for file in files:
            if file.startswith('.'):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in important_exts:
                files_by_type[ext] += 1
                try:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
                except:
                    pass
    
    print(f"\n📁 FILES IN GOOGLE DRIVE:")
    total_files = 0
    for ext in important_exts:
        count = files_by_type.get(ext, 0)
        total_files += count
        print(f"   {ext}: {count:,} files")
    print(f"   Total: {total_files:,} files ({total_size / (1024**3):.2f} GB)")
    
    # Count processed files
    print(f"\n📊 FILES PROCESSED INTO DATABASE:")
    
    processed_by_type = {}
    for ext in important_exts:
        try:
            result = supabase.table('documents')\
                .select('id', count='exact')\
                .ilike('current_path', f'%{google_drive_path}%')\
                .ilike('file_name', f'%{ext}')\
                .execute()
            
            processed_by_type[ext] = result.count if hasattr(result, 'count') else len(result.data) if result.data else 0
        except:
            processed_by_type[ext] = 0
    
    total_processed = 0
    for ext in important_exts:
        gdrive_count = files_by_type.get(ext, 0)
        processed = processed_by_type.get(ext, 0)
        total_processed += processed
        pct = (processed / gdrive_count * 100) if gdrive_count > 0 else 0
        status = "✅" if pct >= 90 else "⚠️" if pct >= 50 else "❌"
        print(f"   {status} {ext}: {processed:,} / {gdrive_count:,} ({pct:.1f}%)")
    
    # Check files with Google Drive history (moved files)
    print(f"\n📊 FILES WITH GOOGLE DRIVE HISTORY (Including moved files):")
    try:
        result = supabase.table('document_locations')\
            .select('document_id')\
            .ilike('location_path', f'%{google_drive_path}%')\
            .execute()
        
        moved_count = len(set([loc['document_id'] for loc in result.data])) if result.data else 0
        print(f"   Total files with Google Drive history: {moved_count:,}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 SUMMARY")
    print(f"{'='*80}")
    print(f"  Total files in Google Drive: {total_files:,}")
    print(f"  Processed (currently in Google Drive): {total_processed:,} ({total_processed/total_files*100:.1f}%)")
    print(f"  Remaining: {total_files - total_processed:,} ({100-total_processed/total_files*100:.1f}%)")
    
    # Safety assessment
    print(f"\n{'='*80}")
    print("🛡️  SAFETY ASSESSMENT FOR DELETION")
    print(f"{'='*80}")
    
    completion_rate = (total_processed / total_files * 100) if total_files > 0 else 0
    
    if completion_rate >= 95:
        print(f"  ✅ SAFE TO DELETE - {completion_rate:.1f}% processed")
        print(f"     Almost all files are accounted for in the database")
    elif completion_rate >= 80:
        print(f"  ⚠️  MOSTLY SAFE - {completion_rate:.1f}% processed")
        print(f"     Most files are accounted for, but {total_files - total_processed:,} files remain")
        print(f"     Consider processing remaining files before deletion")
    else:
        print(f"  ❌ NOT SAFE - Only {completion_rate:.1f}% processed")
        print(f"     {total_files - total_processed:,} files need processing before deletion")
    
    print(f"\n{'='*80}")
    print("✅ Final report complete")
    print(f"{'='*80}")

if __name__ == "__main__":
    generate_final_report()
