# 🛡️ RULE #1: NEVER DELETE OR MOVE FILES

## The Absolute Rule

**RULE #1: The document processing system MUST NEVER delete, move, rename, or modify files on disk.**

### What This Means

✅ **ALLOWED:**
- Read files (extract text, analyze content)
- Update database records (categorization, metadata)
- Create new database records
- Log operations

❌ **NEVER ALLOWED:**
- `os.remove()` - Delete files
- `os.unlink()` - Delete files  
- `shutil.move()` - Move files
- `shutil.copy()` followed by delete - Move files
- `Path.unlink()` - Delete files
- Any file system modification operations

## Enforcement

### Code Level

1. **No file deletion imports in core processing:**
   ```python
   # document_processor.py - ALLOWED
   import os  # For os.path.exists, os.stat (read-only)
   
   # document_processor.py - NOT ALLOWED
   # import shutil  # NO - would enable file moves
   # os.remove()   # NO - would delete files
   ```

2. **Explicit safety assertions:**
   ```python
   # In document_processor.py
   assert True, "SAFETY RULE #1: This method must NEVER delete or move files"
   ```

3. **Code review checks:**
   ```bash
   # Must return NO RESULTS for these patterns in document_processor.py:
   grep -i "remove\|delete\|move\|unlink\|shutil" document_processor.py
   ```

### Script Level

**`reprocess_by_priority.py`** - ✅ SAFE
- No file operations
- Only calls `process_document()` which is read-only
- Updates database only

**`document_processor.py`** - ✅ SAFE  
- Read-only file operations only
- No imports of `shutil`
- No `os.remove()`, `os.unlink()`, etc.

### Separate Scripts (Require Explicit Flags)

File moving/deletion is ONLY in separate scripts that:
1. Have explicit names (`apply_canonical_moves.py`, `delete_duplicate_pdfs.py`)
2. Default to DRY-RUN mode
3. Require explicit flags (`--execute`, `--process`) to actually operate
4. Are completely separate from processing/reprocessing

## Violations

If you find ANY file deletion or movement code in:
- `document_processor.py`
- `reprocess_by_priority.py`  
- Any core processing script

**THIS IS A CRITICAL BUG** and violates Rule #1.

## Testing

To verify Rule #1 compliance:

```bash
# Check core processing - must return NOTHING
grep -i "remove\|delete\|move\|unlink\|shutil" document_processor.py
grep -i "remove\|delete\|move\|unlink\|shutil" scripts/reprocess_by_priority.py

# If you see ANY results, Rule #1 is violated
```

## User Protection

**The user's files are sacred. No processing, reprocessing, or categorization script may ever modify, move, or delete files on disk.**

**This is the #1 rule and must never be violated.**
