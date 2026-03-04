#!/usr/bin/env python3
"""
Monitor the processing script progress by reading the log file.
"""
import os
import re
import time

log_file = "/tmp/gdrive_hash_processing.log"

def count_processed_from_log():
    """Count processed files from log."""
    if not os.path.exists(log_file):
        return None, None, None
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
        
        # Count "✅ Processed" lines
        processed = len(re.findall(r'✅ Processed', content))
        
        # Count "❌ Error" or "❌ Exception" lines
        errors = len(re.findall(r'❌ (Error|Exception)', content))
        
        # Find current file being processed
        current_file = None
        lines = content.split('\n')
        for line in reversed(lines[-50:]):  # Check last 50 lines
            match = re.search(r'\[(\d+)/(\d+)\] Processing: (.+)', line)
            if match:
                current_num, total_num, filename = match.groups()
                current_file = f"[{current_num}/{total_num}] {filename}"
                break
        
        return processed, errors, current_file
    except Exception as e:
        return None, None, None

def main():
    print("="*80)
    print("📊 PROCESSING MONITOR")
    print("="*80)
    
    if not os.path.exists(log_file):
        print("\n⚠️  Log file not found. Processing may not have started yet.")
        print(f"   Expected: {log_file}")
        return
    
    processed, errors, current_file = count_processed_from_log()
    
    if processed is None:
        print("\n⚠️  Could not read log file")
        return
    
    print(f"\n📊 Progress:")
    print(f"   ✅ Processed: {processed} files")
    print(f"   ❌ Errors: {errors} files")
    
    if current_file:
        print(f"\n🔄 Currently processing:")
        print(f"   {current_file}")
    
    # Show last few lines
    print(f"\n📝 Recent activity:")
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-10:]:
                line = line.strip()
                if line and ('Processing:' in line or '✅' in line or '❌' in line or 'SUMMARY' in line):
                    print(f"   {line[:100]}")
    except:
        pass
    
    print(f"\n💡 To see full log:")
    print(f"   tail -f {log_file}")
    print(f"\n💡 To check if still running:")
    print(f"   ps aux | grep process_unprocessed_by_hash")

if __name__ == "__main__":
    main()
