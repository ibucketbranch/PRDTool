# Implementation Plan: Safety System

## Current Status

### ✅ Already Implemented:
1. **`scripts/safety_wrapper.sh`** - ✅ EXISTS
   - Intercepts `supabase stop` commands
   - Auto-creates backup before stop
   - Validates data after start
   - Status: **WORKING** (tested)

2. **`scripts/auto_backup.py`** - ✅ EXISTS (needs scheduling)
   - Creates backups using Docker container pg_dump
   - Keeps last 10 backups
   - Status: **WORKING** (manual execution only)

3. **`scripts/health_check.py`** - ✅ EXISTS
   - Validates Docker, DB connection, document count
   - Status: **WORKING** (tested)

4. **`docs/DATA_PROTECTION.md`** - ✅ EXISTS
   - Operational rules and procedures
   - Status: **COMPLETE**

### ❌ Missing:
1. **`.supabase/.lock`** - State tracking file
2. **Scheduled backups** - Auto-backup runs hourly + after batches

---

## Proposed Implementation

### 1. `.supabase/.lock` - State Tracking File

**Purpose:** Track critical state to prevent accidental data loss

**Format:** JSON file with:
```json
{
  "last_backup": "2026-01-09T09:04:20",
  "last_backup_count": 10,
  "last_health_check": "2026-01-09T09:05:00",
  "processing_active": true,
  "last_processed_count": 10,
  "warnings": []
}
```

**Integration Points:**
- `auto_backup.py` updates `last_backup` after successful backup
- `health_check.py` updates `last_health_check` timestamp
- `process.py` updates `processing_active` and `last_processed_count`
- `safety_wrapper.sh` checks lock file before stop operations

**Safety Rules:**
- If `processing_active: true` and last update > 1 hour old → WARNING
- If `last_backup` > 2 hours old → WARNING
- If warnings exist → Block dangerous operations

---

### 2. Scheduled Backups

**Option A: Cron Job (Recommended)**
- Add to user's crontab: `0 * * * * /path/to/auto_backup.py`
- Runs every hour automatically
- Pros: Simple, reliable, OS-managed
- Cons: Requires manual crontab setup

**Option B: Background Daemon**
- Python script runs continuously, sleeps 3600s
- Pros: Self-contained, no crontab needed
- Cons: Requires process management

**Option C: Integration with `process.py`**
- Call `auto_backup.py` after every N documents (e.g., 500)
- Pros: Automatic during processing
- Cons: Only runs during active processing

**Recommendation:** **Option A + Option C** (cron for hourly + batch triggers)

---

### 3. Enhanced Safety Wrapper

**Additions:**
- Check `.supabase/.lock` before stop
- Warn if processing is active
- Warn if backup is stale (>2 hours)
- Require explicit confirmation if warnings exist

---

## Implementation Steps (Pending Approval)

1. **Create `.supabase/.lock` file structure**
   - Initialize with current state
   - Add lock file management functions

2. **Update `auto_backup.py`**
   - Update lock file after successful backup
   - Add batch trigger support (callable from `process.py`)

3. **Update `health_check.py`**
   - Update lock file timestamp
   - Check lock file for warnings

4. **Update `safety_wrapper.sh`**
   - Read lock file before stop
   - Enforce warnings/confirmations

5. **Update `process.py`**
   - Update lock file: `processing_active = True` at start
   - Call `auto_backup.py` after every 500 documents
   - Update `processing_active = False` on completion/error

6. **Create cron setup script**
   - `scripts/setup_cron.sh` - Adds hourly backup to crontab

7. **Update documentation**
   - Add lock file explanation to `DATA_PROTECTION.md`

---

## Questions for Approval

1. **Lock file location:** `.supabase/.lock` or `~/.document_system/.lock`?
   - Recommendation: `.supabase/.lock` (project-specific)

2. **Backup frequency:** Hourly + after 500 docs, or different schedule?
   - Current plan: Hourly + every 500 docs

3. **Warning behavior:** Block operations or just warn?
   - Recommendation: Warn + require explicit override flag

4. **Cron setup:** Auto-install or manual instructions?
   - Recommendation: Provide script, user runs it

---

## Approval Required

Please review and approve:
- [ ] Lock file approach and location
- [ ] Backup scheduling strategy
- [ ] Warning/blocking behavior
- [ ] Implementation steps

**DO NOT PROCEED until approved.**
