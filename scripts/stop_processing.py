#!/usr/bin/env python3
"""
Safely stop the processing script.
"""
import subprocess
import signal
import os

def stop_processing():
    """Stop all processing scripts."""
    print("="*80)
    print("🛑 STOPPING PROCESSING SCRIPTS")
    print("="*80)
    
    # Find processes
    result = subprocess.run(
        ['ps', 'aux'],
        capture_output=True,
        text=True
    )
    
    processes = []
    for line in result.stdout.split('\n'):
        if 'process_unprocessed_by_hash.py' in line or 'process_all_gdrive_documents.py' in line:
            parts = line.split()
            if len(parts) > 1:
                pid = parts[1]
                processes.append((pid, line))
    
    if not processes:
        print("\n✅ No processing scripts running")
        return
    
    print(f"\n📊 Found {len(processes)} process(es):")
    for pid, line in processes:
        print(f"   PID {pid}: {line[:80]}")
    
    # Stop them
    stopped = 0
    for pid, _ in processes:
        try:
            os.kill(int(pid), signal.SIGTERM)  # Graceful stop
            print(f"   ✅ Sent stop signal to PID {pid}")
            stopped += 1
        except Exception as e:
            print(f"   ⚠️  Error stopping PID {pid}: {e}")
    
    print(f"\n✅ Stopped {stopped} process(es)")
    print("\n💡 Processing can be resumed later with:")
    print("   python3 scripts/process_unprocessed_by_hash.py")

if __name__ == "__main__":
    stop_processing()
