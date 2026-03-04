#!/usr/bin/env python3
"""Quick status checker for batch processing"""
import os
from file_tracker import FileTracker

try:
    tracker = FileTracker()
    
    print("\n" + "="*70)
    print("  📊 PROCESSING STATUS")
    print("="*70 + "\n")
    
    summary = tracker.get_processing_summary()
    
    if summary:
        total_files = sum(row.get('file_count', 0) or 0 for row in summary)
        total_messages = sum(row.get('total_messages', 0) or 0 for row in summary)
        
        print(f"Total files tracked: {total_files}")
        print(f"Total messages extracted: {total_messages}\n")
        
        for row in summary:
            status = row['status']
            count = row['file_count']
            print(f"  {status.upper():12s}: {count:4d} files")
        
        print("\n" + "="*70)
        
        # Show recent files
        print("\n📋 Recent Files:\n")
        files = tracker.get_files_for_review()
        for f in files[:5]:
            print(f"  • {f['file_name'][:50]}")
            print(f"    Status: {f['status']} | {f['error_message'] or 'No error'}")
            print()
    else:
        print("⏳ Processing just started or no database connection")
        print("   Check back in a few minutes...")
    
    print("\n💡 Tips:")
    print("   • Run: python status.py")
    print("   • View DB: http://localhost:54423")
    print("   • Check logs: ls -lt processing_log_*.txt | head -1")
    print()

except Exception as e:
    print(f"\n⚠️  Could not connect to database: {e}")
    print("   Make sure Supabase is running: supabase start")
    print()
