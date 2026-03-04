#!/bin/bash
# Database Backup Script - ALWAYS RUN BEFORE ANY RESTART
# Usage: ./scripts/backup_db.sh

BACKUP_DIR="$HOME/.document_system/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

mkdir -p "$BACKUP_DIR"

echo "💾 Creating database backup..."
# Use pg_dump from Supabase container to avoid version mismatch
docker exec supabase_db_TheConversation pg_dump -U postgres postgres > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "✅ Backup created: $BACKUP_FILE ($SIZE)"
    
    # Keep only last 5 backups
    ls -t "$BACKUP_DIR"/db_backup_*.sql | tail -n +6 | xargs rm -f 2>/dev/null
    echo "   (Kept last 5 backups)"
else
    echo "❌ Backup FAILED!"
    exit 1
fi
