#!/usr/bin/env python3
"""
Live monitor for resume processing progress.
Shows real-time updates every 5 seconds.
Counts unique files (by hash) and excludes duplicates.
"""

import os
import time
import sys
from supabase import create_client
from datetime import datetime
from collections import defaultdict

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Target is unique resumes (by hash), not total files processed
TARGET = 97  # Unique resume documents

def get_status():
    """Get current processing status - returns unique files only."""
    result = supabase.table('documents').select(
        'id,file_name,file_hash,updated_at'
    ).or_('file_name.ilike.%resume%,current_path.ilike.%resume%').eq(
        'ai_category', 'employment'
    ).order('updated_at', desc=True).execute()
    
    if not result.data:
        return []
    
    # Count unique files by hash (exclude duplicates)
    unique_files = {}
    for doc in result.data:
        file_hash = doc.get('file_hash')
        if file_hash and file_hash not in unique_files:
            unique_files[file_hash] = doc
    
    # Return list of unique documents (most recent per hash)
    return list(unique_files.values())

def display_status(data, last_count):
    """Display current status with progress bar."""
    current_count = len(data)
    progress = (current_count / TARGET) * 100 if TARGET > 0 else 0
    bar_length = 50
    filled = int(bar_length * current_count / TARGET) if TARGET > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)
    
    # Clear screen
    print("\033[2J\033[H", end="")
    
    print("=" * 80)
    print("📊 LIVE RESUME PROCESSING MONITOR")
    print("=" * 80)
    print("")
    print(f"Progress: {current_count}/{TARGET} unique resumes ({progress:.1f}%)")
    print(f"[{bar}]")
    print("")
    print("ℹ️  Counting unique files only (duplicates excluded)")
    print("")
    
    if current_count > last_count:
        print(f"✅ +{current_count - last_count} new unique resume(s) processed!")
    elif current_count == last_count and current_count > 0:
        print("⏳ Processing... (checking for updates...)")
    elif current_count == 0:
        print("⏳ Waiting for processing to start...")
    
    print("")
    print("Most recently processed (last 5):")
    for i, doc in enumerate(data[:5], 1):
        name = doc.get('file_name', 'Unknown')[:55]
        updated = doc.get('updated_at', '')[:19] if doc.get('updated_at') else 'N/A'
        hash_short = doc.get('file_hash', '')[:12] + '...' if doc.get('file_hash') else 'N/A'
        print(f"  {i}. {name}")
        print(f"     ⏰ {updated} | 🔑 {hash_short}")
    
    print("")
    print(f"🕐 Last update: {datetime.now().strftime('%H:%M:%S')}")
    print("")
    print("Press Ctrl+C to stop monitoring")
    
    return current_count

def main():
    print("Starting monitor...")
    time.sleep(2)
    
    last_count = 0
    iteration = 0
    
    try:
        while True:
            iteration += 1
            data = get_status()
            last_count = display_status(data, last_count)
            
            if last_count >= TARGET:
                print("")
                print(f"🎉 PROCESSING COMPLETE! All {TARGET} unique resumes processed!")
                print("")
                break
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped.")
        print(f"Final count: {last_count}/{TARGET} unique resumes")
        if last_count >= TARGET:
            print("🎉 All unique resumes processed!")

if __name__ == "__main__":
    main()
