#!/usr/bin/env python3
"""Quick status check of processing."""
import os
import subprocess
from supabase import create_client

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

google_drive_path = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"

# Check if process is running
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
is_running = 'process_unprocessed_by_hash.py' in result.stdout

# Count processed files
try:
    result = supabase.table('documents')\
        .select('id')\
        .ilike('current_path', f'%{google_drive_path}%')\
        .limit(50000)\
        .execute()
    processed = len(result.data) if result.data else 0
except:
    processed = 0

# Count total important files
important_exts = ['.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.rtf']
total = 0
for root, dirs, files in os.walk(google_drive_path):
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for file in files:
        if file.startswith('.'):
            continue
        ext = os.path.splitext(file)[1].lower()
        if ext in important_exts:
            total += 1

remaining = total - processed
percentage = (processed / total * 100) if total > 0 else 0

print("="*60)
print("📊 PROCESSING STATUS")
print("="*60)
print(f"Status: {'🟢 RUNNING' if is_running else '⏸️  NOT RUNNING'}")
print(f"Processed: {processed:,} / {total:,} ({percentage:.1f}%)")
print(f"Remaining: {remaining:,} files")
print("="*60)
