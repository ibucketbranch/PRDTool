#!/usr/bin/env python3
"""
Check the status of the document processing script.
Shows progress and estimated completion.
"""
import os
import subprocess
import time
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

def check_process_running():
    """Check if process_all_gdrive_documents.py is running."""
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        if 'process_all_gdrive_documents.py' in result.stdout:
            return True
    except:
        pass
    return False

def count_processed_files():
    """Count how many Google Drive files are processed."""
    try:
        result = supabase.table('documents')\
            .select('id,file_name,current_path')\
            .ilike('current_path', f'%{google_drive_path}%')\
            .limit(50000)\
            .execute()
        
        if result.data:
            return len(result.data)
    except:
        pass
    return 0

def count_total_important_files():
    """Count total important files in Google Drive."""
    important_exts = ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf']
    count = 0
    
    try:
        for root, dirs, files in os.walk(google_drive_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.startswith('.'):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in important_exts:
                    count += 1
    except:
        pass
    
    return count

def main():
    print("="*80)
    print("📊 PROCESSING STATUS CHECK")
    print("="*80)
    
    # Check if process is running
    is_running = check_process_running()
    
    if is_running:
        print("\n✅ Processing script is RUNNING")
    else:
        print("\n⏸️  Processing script is NOT running")
    
    # Count files
    print("\n📊 Current Status:")
    processed = count_processed_files()
    total = count_total_important_files()
    
    print(f"   Processed: {processed:,} files")
    print(f"   Total important files: {total:,} files")
    
    if total > 0:
        percentage = (processed / total * 100)
        remaining = total - processed
        print(f"   Progress: {percentage:.1f}%")
        print(f"   Remaining: {remaining:,} files")
    
    print("\n" + "="*80)
    
    if is_running:
        print("\n💡 Processing is in progress. Check again in a few minutes.")
        print("   Run: python3 scripts/check_processing_status.py")
    else:
        print("\n💡 Processing appears to be complete or not started.")
        print("   Run: python3 scripts/final_gdrive_report.py for detailed report")
    
    print("="*80)

if __name__ == "__main__":
    main()
