#!/bin/bash
# Setup hourly backup cron job
# Usage: ./scripts/setup_cron.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_SCRIPT="$PROJECT_DIR/scripts/auto_backup.py"
PYTHON_VENV="$PROJECT_DIR/venv/bin/python3"

# Check if cron job already exists
CRON_CMD="0 * * * * cd $PROJECT_DIR && $PYTHON_VENV $BACKUP_SCRIPT >> ~/.document_system/cron_backup.log 2>&1"

if crontab -l 2>/dev/null | grep -q "auto_backup.py"; then
    echo "✅ Cron job already exists"
    crontab -l | grep "auto_backup.py"
else
    echo "📅 Adding hourly backup cron job..."
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo "✅ Cron job added!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep "auto_backup.py"
fi
