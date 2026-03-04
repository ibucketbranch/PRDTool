# Operational Guidelines - The Conversation Project

## ⚠️ CRITICAL RULES - NEVER VIOLATE

### Database Operations

1. **NEVER run `supabase stop --no-backup`**
   - This explicitly wipes the database
   - Use `supabase stop` (with backup) or `supabase db reset` only if absolutely necessary

2. **ALWAYS backup before restarting**
   - Run `./scripts/backup_db.sh` BEFORE any `supabase stop/start`
   - Verify backup file exists and has size > 0

3. **Check connection before assuming DB is dead**
   - Run `psql postgresql://postgres:postgres@127.0.0.1:54422/postgres -c "SELECT 1;"` first
   - Check Docker: `docker ps | grep supabase`
   - Check Supabase status: `supabase status`

4. **If DB appears down, troubleshoot in this order:**
   - Check Docker Desktop is running
   - Check `supabase status`
   - Check connection with `psql`
   - Check logs: `supabase logs db`
   - **ONLY THEN** consider restart (with backup first!)

### Processing Operations

1. **Never kill workers without checking progress**
   - Check `scripts/simple_count.py` first
   - Save progress before killing

2. **Always use dev branch for changes**
   - Branch naming: `TC-DEV-<three-words>-V0.x`
   - Test on dev before merging to main

3. **Monitor resource usage**
   - 5 workers max (to avoid crashing Docker)
   - Watch Docker Desktop memory usage

## Backup Strategy

- Automatic backups before any destructive operation
- Manual backups: `./scripts/backup_db.sh`
- Backup location: `~/.document_system/backups/`
- Retention: Last 5 backups

## Recovery Procedure

If data is lost:
1. Check `~/.document_system/backups/` for latest `.sql` file
2. Restore: `psql postgresql://postgres:postgres@127.0.0.1:54422/postgres < backup_file.sql`
3. Verify: `scripts/simple_count.py`
