#!/usr/bin/env python3
"""
Automated Backup System - Runs in background, doesn't block processing
Runs hourly via cron, or can be called after batches
"""
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
import sys

# Add scripts directory to path for lock_manager
sys.path.insert(0, str(Path(__file__).parent))
from lock_manager import update_backup

BACKUP_DIR = Path.home() / '.document_system' / 'backups'
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def get_document_count():
    """Quick check of document count"""
    try:
        result = subprocess.run(
            ['psql', 'postgresql://postgres:postgres@127.0.0.1:54422/postgres', 
             '-t', '-c', 'SELECT COUNT(*) FROM documents;'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except:
        pass
    return 0

def create_backup():
    """Create backup if documents exist"""
    count = get_document_count()
    
    if count == 0:
        print("⏭️  No documents to backup. Skipping.")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = BACKUP_DIR / f"db_backup_{timestamp}.sql"
    
    print(f"💾 Creating backup ({count} documents)...")
    # Use pg_dump from Supabase container to avoid version mismatch
    result = subprocess.run(
        ['docker', 'exec', 'supabase_db_TheConversation', 
         'pg_dump', '-U', 'postgres', 'postgres'],
        stdout=open(backup_file, 'w'),
        stderr=subprocess.PIPE,
        timeout=300  # 5 min max
    )
    
    if result.returncode == 0:
        size = backup_file.stat().st_size / 1024 / 1024
        print(f"✅ Backup created: {backup_file.name} ({size:.2f} MB)")
        
        # Update lock file
        update_backup(count)
        
        # Keep only last 10 backups
        backups = sorted(BACKUP_DIR.glob('db_backup_*.sql'), key=lambda x: x.stat().st_mtime, reverse=True)
        for old_backup in backups[10:]:
            old_backup.unlink()
            print(f"   🗑️  Removed old backup: {old_backup.name}")
    else:
        print(f"❌ Backup failed: {result.stderr.decode()}")

if __name__ == "__main__":
    create_backup()
