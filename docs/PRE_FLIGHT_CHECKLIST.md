# Pre-Flight Checklist - Before Processing Documents

## ✅ MUST COMPLETE BEFORE STARTING

### 1. Safety System Verification
- [ ] Health check passes: `./scripts/health_check.py`
- [ ] Backup system works: `python3 scripts/auto_backup.py`
- [ ] Safety wrapper tested: Stop/Start preserves data
- [ ] Document count verified: `python3 scripts/simple_count.py`

### 2. Database State
- [ ] Supabase is running: `supabase status`
- [ ] Connection works: `psql` test succeeds
- [ ] Current document count recorded (baseline)

### 3. Code State
- [ ] On dev branch: `TC-DEV-*`
- [ ] All safety scripts committed
- [ ] Processing code has latest fixes (IndirectObject sanitization)

### 4. Resource Check
- [ ] Docker has enough memory (check Docker Desktop)
- [ ] No other heavy processes running
- [ ] Disk space available for backups

## 🚀 Ready to Process

Once all checks pass:
1. Start 5 workers (not more - tested limit)
2. Monitor with `./scripts/health_check.py` every hour
3. Let backups run automatically (every 30 min)
4. Never manually restart Supabase without safety wrapper

## ⚠️ Emergency Procedures

**If processing hangs:**
- Check health: `./scripts/health_check.py`
- Check workers: `ps aux | grep process.py`
- If DB is down: Use safety wrapper to restart
- Never use `--no-backup` flag

**If data seems lost:**
- Check backups: `ls -lh ~/.document_system/backups/`
- Restore from latest: See `docs/DATA_PROTECTION.md`
