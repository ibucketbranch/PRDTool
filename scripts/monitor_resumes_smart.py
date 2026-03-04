#!/usr/bin/env python3
"""
Live monitor for AI resume processing progress (AI-driven).
Counts unique documents with ai_category='employment'.
Displays recent AI-suggested folder structures.
"""
import os
import time
from supabase import create_client
from datetime import datetime

supabase_url = "http://127.0.0.1:54421"
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(supabase_url, supabase_key)

def get_status():
    """Get current status for AI-identified resumes."""
    result = supabase.table('documents').select(
        'id,file_name,file_hash,updated_at,suggested_folder_structure'
    ).eq(
        'ai_category', 'employment'
    ).order('updated_at', desc=True).execute()
    
    if not result.data:
        return []
    
    unique = {}
    for doc in result.data:
        file_hash = doc.get('file_hash')
        if file_hash and file_hash not in unique:
            unique[file_hash] = doc
    return list(unique.values())

def display_status(data, last_count):
    current_count = len(data)
    bar_length = 50
    bar = "█" * min(bar_length, current_count) + "░" * max(0, bar_length - current_count)

    print("\033[2J\033[H", end="")
    print("=" * 80)
    print("🤖 LIVE AI RESUME MONITOR (category-driven)")
    print("=" * 80)
    print(f"Resumes (AI-identified, unique): {current_count}")
    print(f"[{bar}]")
    print("")
    print("Most recently processed (last 5):")
    for i, doc in enumerate(data[:5], 1):
        name = doc.get('file_name', 'Unknown')[:55]
        struct = doc.get('suggested_folder_structure', 'N/A')
        updated = doc.get('updated_at', '')[:19] if doc.get('updated_at') else 'N/A'
        print(f"  {i}. {name}")
        print(f"     📁 {struct}")
        print(f"     ⏰ {updated}")
    print("")
    print(f"🕐 Last update: {datetime.now().strftime('%H:%M:%S')}")
    print("Press Ctrl+C to stop monitoring")
    return current_count

def main():
    print("Starting AI-driven resumewatch...")
    time.sleep(2)
    last_count = 0
    try:
        while True:
            data = get_status()
            last_count = display_status(data, last_count)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n✅ Monitoring stopped.")
        print(f"Final count: {last_count} unique AI-identified resumes")
if __name__ == "__main__":
    main()
