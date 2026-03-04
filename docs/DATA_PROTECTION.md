# Data Protection Protocol

## 🚨 NEVER DO THESE THINGS

1. **NEVER** run `supabase stop --no-backup`
2. **NEVER** run `supabase db reset` without backup
3. **NEVER** restart Supabase without checking health first
4. **NEVER** assume database is dead without verifying

## ✅ ALWAYS DO THESE THINGS

1. **ALWAYS** run `./scripts/health_check.py` before any operation
2. **ALWAYS** use `safe_supabase_stop` (not raw `supabase stop`)
3. **ALWAYS** verify backup exists before destructive operations
4. **ALWAYS** check document count after restart

## 🔄 Standard Procedures

### Before Restarting Supabase:
```bash
# 1. Health check
./scripts/health_check.py

# 2. Manual backup (if needed)
./scripts/backup_db.sh

# 3. Safe stop
source scripts/safety_wrapper.sh
safe_supabase_stop

# 4. Safe start
safe_supabase_start
```

### Automated Backups:
- Runs every hour (cron) - Setup: `./scripts/setup_cron.sh`
- Runs after every 500 documents processed (automatic)
- Keeps last 10 backups
- Location: `~/.document_system/backups/`
- Updates `.supabase/.lock` after each backup

### Lock File (`.supabase/.lock`):
- Tracks: last backup time, document count, processing status, warnings
- Checked by safety wrapper before stop operations
- Updated by: `auto_backup.py`, `health_check.py`, `process.py`
- Prevents operations if warnings exist (requires explicit override)

## 🛡️ Safety Mechanisms

1. **Safety Wrapper**: Intercepts dangerous commands, checks lock file
2. **Health Checks**: Validates state before operations, updates lock file
3. **Auto-Backup**: Runs hourly (cron) + after every 500 documents
4. **Lock File** (`.supabase/.lock`): Tracks state, prevents dangerous operations
5. **Document Count Tracking**: Monitors data state

## 📊 Recovery Procedure

If data is lost:
1. Check `~/.document_system/backups/` for latest `.sql`
2. Restore: `psql postgresql://postgres:postgres@127.0.0.1:54422/postgres < backup_file.sql`
3. Verify: `./scripts/simple_count.py`
