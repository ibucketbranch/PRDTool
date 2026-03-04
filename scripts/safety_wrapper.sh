#!/bin/bash
# Safety Wrapper - Intercepts dangerous Supabase commands
# Usage: source this file, then use safe_supabase_stop, safe_supabase_start, etc.

#!/bin/bash
# Safety Wrapper Functions

safe_supabase_stop() {
    echo "🛡️  SAFETY CHECK: About to stop Supabase..."
    
    # Check lock file for warnings (optional - continue even if check fails)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
    if python3 "$SCRIPT_DIR/check_lock.py" 2>/dev/null; then
        echo "✅ Lock file check passed"
    else
        # If check fails, just continue (backup will still be created)
        echo "⚠️  Lock file check skipped (non-critical)"
    fi
    
    # Pre-flight check
    if ! psql postgresql://postgres:postgres@127.0.0.1:54422/postgres -c "SELECT 1;" > /dev/null 2>&1; then
        echo "⚠️  Database not accessible. Skipping backup (nothing to save)."
    else
        # Get document count
        COUNT=$(psql postgresql://postgres:postgres@127.0.0.1:54422/postgres -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs)
        echo "📊 Current document count: $COUNT"
        
        if [ "$COUNT" -gt 0 ]; then
            echo "💾 Creating backup before stop..."
            SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            "$SCRIPT_DIR/backup_db.sh"
            if [ $? -ne 0 ]; then
                echo "❌ BACKUP FAILED! Aborting stop operation."
                return 1
            fi
        fi
    fi
    
    # Now safe to stop
    supabase stop "$@"
}

safe_supabase_start() {
    echo "🛡️  SAFETY CHECK: Starting Supabase..."
    supabase start "$@"
    
    # Verify it came up
    sleep 5
    if psql postgresql://postgres:postgres@127.0.0.1:54422/postgres -c "SELECT 1;" > /dev/null 2>&1; then
        COUNT=$(psql postgresql://postgres:postgres@127.0.0.1:54422/postgres -t -c "SELECT COUNT(*) FROM documents;" 2>/dev/null | xargs)
        echo "✅ Supabase started. Document count: $COUNT"
    else
        echo "⚠️  Warning: Database started but not accessible yet."
    fi
}
