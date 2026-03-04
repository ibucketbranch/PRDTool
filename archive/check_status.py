#!/usr/bin/env python3
"""Quick status check"""
import json
from pathlib import Path
from supabase import create_client

# Check progress file
progress_file = Path.home() / '.document_system' / 'batch_progress.json'
if progress_file.exists():
    with open(progress_file) as f:
        progress = json.load(f)
    print(f"✅ Progress file found!")
    print(f"   Processed: {progress.get('total_processed', 0)} files")
    print(f"   Files: {len(progress.get('processed_files', []))}")
else:
    print(f"❌ No progress file yet")

# Check database
try:
    supabase = create_client(
        'http://127.0.0.1:54421',
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0'
    )
    result = supabase.table('documents').select('id', count='exact').execute()
    print(f"\n✅ Database connected!")
    print(f"   Documents in DB: {result.count if hasattr(result, 'count') else 'unknown'}")
except Exception as e:
    print(f"\n❌ Database error: {e}")
