# PRD: Folder Consolidation Enhancement for TheConversation

## Problem Statement
The existing `smart_consolidate_all_categories.py` creates redundant similar folders because it uses exact keyword matching without fuzzy similarity detection. Result: "Resume", "Resumes", "Resume_Docs", "Resume_1" all get created as separate folders instead of consolidating into one canonical folder.

## Existing Code Reference (READ-ONLY)
Location: `/Users/michaelvalderrama/Websites/PRDTool/scripts/`
- `folder_analyzer.py` - Folder analysis infrastructure
- `smart_consolidate_all_categories.py` - Category-based consolidation (has hardcoded mappings)
- `consolidate_resumes_smart.py` - Resume-specific consolidation

## Goals
1. Add fuzzy matching to detect similar folder names
2. Create a canonical folder registry that persists across runs
3. Implement "get-or-create" logic: reuse existing folders before creating new ones
4. Support dry-run mode to preview consolidation before executing

---

## Tasks

### Phase 1: Fuzzy Name Matching Module
- [x] Create `organizer/fuzzy_matcher.py` with functions to compare folder name similarity
- [x] Use `difflib.SequenceMatcher` or `rapidfuzz` library for fuzzy matching
- [x] Implement `normalize_folder_name(name)` - lowercase, remove underscores/numbers, singularize
- [x] Implement `are_similar_folders(name1, name2, threshold=0.8)` - returns True if similarity >= threshold
- [x] Add unit tests for edge cases: "Resume" vs "Resumes", "Tax_2023" vs "Tax", "Documents_1" vs "Documents"

### Phase 2: Canonical Folder Registry
- [x] Create `organizer/canonical_registry.py` with a `CanonicalRegistry` class
- [x] Implement `register_folder(path)` - adds folder to registry, detects if similar folder already exists
- [x] Implement `get_canonical_folder(proposed_name)` - returns existing similar folder or None
- [x] Implement `get_or_create(category, name)` - main entry point, returns canonical path
- [x] Store registry in JSON file (`.organizer/canonical_folders.json`) for persistence

### Phase 3: Integration with Existing Categories
- [x] Create `organizer/category_mapper.py` that imports CONSOLIDATION_CATEGORIES from existing code pattern
- [x] Enhance category matching to use fuzzy registry lookup before creating new folders
- [x] Implement `suggest_canonical_path(file_path, file_name, ai_category)` that respects existing folders

### Phase 4: Consolidation Planner (Dry Run)
- [x] Create `organizer/consolidation_planner.py` that scans existing folder structure
- [x] Identify folder groups that should be merged (e.g., ["Resume", "Resumes", "Resume_Docs"] → "Resumes")
- [x] Generate a consolidation plan as JSON with: source folders, target folder, files to move
- [x] Output human-readable summary: "Found 5 Resume-like folders with 47 files → consolidate to Employment/Resumes"

### Phase 5: CLI with Preview
- [x] Create `organizer/cli.py` with argparse
- [x] `--scan` - analyze current folder structure, show similar folder groups
- [x] `--plan` - generate consolidation plan without executing
- [x] `--threshold 0.85` - set similarity threshold (default 0.8)
- [x] `--output plan.json` - save plan to file

### Phase 6: Safe Execution with Safety Checks
- [x] Add `--execute` flag to CLI that requires explicit confirmation
- [x] Implement pre-execution safety checks:
  - [x] Verify plan file exists and is valid JSON
  - [x] Show summary of what will happen (folders, files to move)
  - [x] Require explicit "yes" confirmation (not just Enter)
  - [x] Create backup of consolidation plan before execution
- [x] Implement atomic file operations:
  - [x] Move one folder group at a time (all or nothing per group)
  - [x] Verify each move succeeded before proceeding
  - [x] Stop on first error and report what was completed
- [x] Create detailed execution log:
  - [x] Log file: `.organizer/execution_log_YYYYMMDD_HHMMSS.json`
  - [x] Record: timestamp, source path, target path, file count, status (success/failed)
  - [x] Include rollback instructions in log (how to undo moves)
- [x] Update database integration:
  - [x] Update `document_locations` table when files move
  - [x] Mark old location as `location_type='previous'`
  - [x] Update `current_path` in `documents` table
  - [x] Update `canonical_folder` and `rename_status='done'` for moved files
- [x] Progress reporting:
  - [x] Show progress bar or "X/Y folder groups completed"
  - [x] Real-time status updates during execution
- [x] Post-execution verification:
  - [x] Verify all files are accessible at new locations
  - [x] Check that no files were lost
  - [x] Generate execution summary report

---

## Example Output

### Dry Run (Scan)

```
$ python -m organizer --scan --threshold 0.8

📊 FOLDER SIMILARITY ANALYSIS
============================

Found 3 similar folder groups:

Group 1: Resume-related (5 folders, 47 files)
  - /iCloud/Resume/           (12 files)
  - /iCloud/Resumes/          (8 files)  
  - /iCloud/Resume_Docs/      (15 files)
  - /iCloud/Old/Resume/       (7 files)
  - /iCloud/Work/Resumes_2023/ (5 files)
  → Suggested canonical: Employment/Resumes/

Group 2: Tax-related (3 folders, 23 files)
  - /iCloud/Taxes/            (15 files)
  - /iCloud/Tax_2023/         (5 files)
  - /iCloud/Tax Returns/      (3 files)
  → Suggested canonical: Finances Bin/Taxes/

Run with --plan to generate full consolidation plan.
```

### Execution (Live)

```
$ python -m organizer --execute --plan my_plan.json

🛡️  EXECUTION SAFETY CHECK
============================

⚠️  WARNING: This will move files and folders on disk.

📊 CONSOLIDATION PLAN SUMMARY:
   - 3 folder groups to consolidate
   - 70 files total to move
   - Target: Employment/Resumes/, Finances Bin/Taxes/, Contracts/

Are you absolutely sure you want to proceed? Type 'yes' to confirm: yes

✅ Confirmed. Creating backup of plan...
✅ Backup saved to: .organizer/plan_backup_20260120_143022.json

📦 EXECUTING CONSOLIDATION
============================

[1/3] Group 1: Resume-related (5 folders, 47 files)
  ✅ Moving Resume/ → Employment/Resumes/ (12 files)
  ✅ Moving Resumes/ → Employment/Resumes/ (8 files)
  ✅ Moving Resume_Docs/ → Employment/Resumes/ (15 files)
  ✅ Moving Old/Resume/ → Employment/Resumes/ (7 files)
  ✅ Moving Work/Resumes_2023/ → Employment/Resumes/ (5 files)
  ✅ Group 1 complete: 47/47 files moved successfully

[2/3] Group 2: Tax-related (3 folders, 23 files)
  ✅ Moving Taxes/ → Finances Bin/Taxes/ (15 files)
  ✅ Moving Tax_2023/ → Finances Bin/Taxes/ (5 files)
  ✅ Moving Tax Returns/ → Finances Bin/Taxes/ (3 files)
  ✅ Group 2 complete: 23/23 files moved successfully

[3/3] Group 3: Contract-related (2 folders, 0 files)
  ✅ Group 3 complete: 0/0 files moved (empty folders)

✅ VERIFICATION COMPLETE
============================
  - All 70 files verified at new locations
  - Database updated: 70 document records migrated
  - Execution log saved: .organizer/execution_log_20260120_143045.json

📊 FINAL SUMMARY
============================
  ✅ 3 folder groups consolidated
  ✅ 70 files moved successfully
  ✅ 0 errors
  ✅ 0 files lost

🔄 Rollback information saved to execution log.
```

## Success Criteria
- [x] Similar folders detected with configurable threshold
- [x] Canonical registry persists between runs
- [x] Dry run shows exactly what would change
- [x] Execution requires explicit confirmation (safety first)
- [x] All file moves are logged with rollback instructions
- [x] Database updated automatically when files move
- [x] Verification confirms no files lost after execution
