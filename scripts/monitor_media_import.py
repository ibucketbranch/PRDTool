#!/usr/bin/env python3
"""Monitor media import progress."""
import os
import subprocess

log_file = "/tmp/media_import.log"

print("="*80)
print("📊 MEDIA IMPORT MONITOR")
print("="*80)

# Check if process is running
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
is_running = 'import_all_media_to_photos.py' in result.stdout

if is_running:
    print("\n🟢 Import: RUNNING")
else:
    print("\n⏸️  Import: COMPLETED or STOPPED")

# Check log file
if os.path.exists(log_file):
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Count imported
    imported = content.count("✅ Imported")
    failed = content.count("❌ Failed")
    
    # Find current file being processed
    lines = content.split('\n')
    current_file = None
    for line in reversed(lines[-50:]):
        if 'Importing:' in line:
            current_file = line.split('Importing:')[-1].strip()
            break
    
    print(f"\n📊 Progress:")
    print(f"   ✅ Imported: {imported}")
    print(f"   ❌ Failed: {failed}")
    
    if current_file:
        print(f"\n🔄 Currently processing:")
        print(f"   {current_file}")
    
    # Show recent activity
    print(f"\n📝 Recent activity:")
    for line in lines[-10:]:
        if line.strip() and ('Importing:' in line or '✅' in line or '❌' in line or 'SUMMARY' in line):
            print(f"   {line[:100]}")
else:
    print("\n⚠️  Log file not found")

print(f"\n💡 To see full log:")
print(f"   tail -f {log_file}")
print("="*80)
