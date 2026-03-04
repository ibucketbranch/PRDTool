# PRD: Organizer Dashboard

## Problem Statement
Users need a visual interface to:
- See what types of files they have and how many
- Search for documents using natural language queries (e.g., "Show me a file that is a verizon bill from 2024?")
- View file locations and contextual information from the database
- Understand their document organization at a glance

## Glossary

These terms are the product's shared vocabulary. All agents, dashboard UI,
documentation, and code should use them consistently.

| Term | Definition |
|------|------------|
| **Scan** | The agent examines a file's name, metadata, and content to understand what it is. Read-only — no files are moved. Output: classification signals (keywords, date signals, domain context, confidence score). |
| **Filing** | Moving a file from the In-Box to its correct bin for the first time. The file has no prior routing record. A filing creates a new routing record capturing provenance (source, destination, matched keywords, confidence, timestamp). |
| **Filed** | A file that has been successfully placed in its correct bin by the agent. It has a routing record in the system. The agent considers it "done" unless it drifts or is returned to In-Box. |
| **Routing** | The decision logic that determines which bin a file belongs in, given its signals. A routing can be *proposed* (queued for review) or *executed* (auto-moved). Routing is the brain; filing is the action. |
| **Re-routing** | A previously filed file needs a different destination. The user moves it back to In-Box. The agent detects the prior routing record, routes it to a new destination, marks the old record as `corrected`, and learns from the correction. |
| **Rescan** | The agent re-examines files that are already filed — in-place, without requiring the user to move anything. Used when routing rules change, taxonomy is updated, or the user wants a second opinion. Flags files that would now route differently under current rules. |
| **Drift** | A filed file has moved away from its known-good location without the agent's involvement (e.g., accidental drag-and-drop in Finder). The ReFileMe-Agent detects drift by comparing current locations against routing history. |
| **Scatter** | Files that exist outside their correct bin according to the taxonomy. Unlike drift (which compares against routing history), scatter compares against taxonomy rules. A file can be scattered without ever having been filed by the agent. |
| **In-Box** | The single intake point for all file processing. New files go here for first-time filing. Previously filed files go here for re-routing. There is no separate Out-Box — In-Box handles both cases. The agent determines whether a file is new or returning based on routing history. |
| **Bin** | A top-level organizational category (e.g., Work Bin, Finances Bin, VA, Archive). Bins are the root containers of the taxonomy. Locked bins cannot be renamed, moved, or merged by the agent. |
| **Confidence** | A score (0.0–1.0) representing how certain the agent is about a routing decision. Filename matches score higher (0.92+) than content matches (0.80). Files above `min_auto_confidence` (default 0.95) may be auto-executed; below that threshold they are queued for review. |
| **Proposed Action** | A routing decision that has been queued for user review but not yet executed. The user can approve, reject, or modify it via the dashboard. |
| **Auto-execute** | When enabled, the agent automatically executes routing decisions that meet or exceed the `min_auto_confidence` threshold. Lower-confidence decisions are still queued for review. |
| **Model Tier** | The LLM capability level assigned to a task. **T1 Fast** (8B models, ~3s) handles high-volume decisions like classification and yes/no validation. **T2 Smart** (14B models, ~10s) handles complex reasoning like dedup analysis and domain detection. **T3 Cloud** (480B/671B, ~15-30s) handles the hardest problems and is opt-in. |
| **Escalation** | When a lower-tier LLM returns confidence below the `escalation_threshold`, the task is automatically re-sent to the next tier up. Chain: T1 → T2 → T3 → keyword fallback. Prevents wasting a big model on easy files while ensuring hard files get the reasoning they need. |
| **Graceful Degradation** | The system's ability to keep working when LLMs are unavailable. If Ollama is down, all agents fall back to keyword/rule-based logic. If a preferred model isn't loaded, the next available model handles it. The user never sees a broken agent — just a less-smart one. |
| **Enrichment** | LLM-powered extraction of structured metadata from file content: document type, dates, people, organizations, topics, and a plain-English summary. Enrichment data powers natural language search without needing a vector database. |
| **Explainability** | Every LLM-powered decision includes a `reason` field — a natural language explanation of why the agent made that choice. Visible in the dashboard so users can see and trust the agent's reasoning, not just its output. |

## Solution: Web Dashboard
A web-based dashboard that:
1. **Statistics View** - Shows file type counts, category distributions, date ranges
2. **Natural Language Search** - Query documents using contextual info from Supabase
3. **Document Browser** - View files with paths, AI categories, entities, dates
4. **Integration** - Uses existing Supabase database with all the rich context

## Features

### 1. File Type Statistics Dashboard
- **Category breakdown** - Show counts by `ai_category` (e.g., "Tax Documents: 45", "VA Claims: 23")
- **Date distribution** - Files by year (from `key_dates[]` and metadata)
- **Context bins** - Files organized by `folder_hierarchy`
- **Visual charts** - Bar charts, pie charts for visual representation
- **Quick filters** - Filter by category, date range, context bin

### 2. Natural Language Search
- **Query examples:**
  - "Show me a file that is a verizon bill from 2024?"
  - "Find all tax documents from 2023"
  - "Show me VA claims documents"
  - "Find invoices from Amazon"
- **Search across:**
  - `ai_category` and `ai_subcategories`
  - `ai_summary` (full-text search)
  - `entities` JSONB (people, organizations, amounts)
  - `key_dates[]` (date matching)
  - `file_name` and `current_path`
- **Results display:**
  - File name with clickable path
  - AI category and summary
  - Key entities extracted (people, dates, amounts)
  - Date information
  - Path location

### 3. Document Browser
- **List view** - Browse all documents with:
  - File name
  - Full path (clickable to open in Finder)
  - AI category
  - Date information
  - Key entities
  - Context bin
- **Filters and sorting:**
  - Filter by category, date range, context bin
  - Sort by name, date, category, path
  - Search by keyword

### 4. Empty Folders Detection & Management
- **Detect empty folders** - Folders that are now empty after files were moved:
  - Scan for folders with zero files
  - Check if files were recently moved from these folders (check execution logs, `document_locations` with `location_type='previous'`)
  - Show empty folder with: folder path, original file count, when files were moved
- **Determine if original folder location was correct:**
  - Check if folder name matches AI category of files that were moved
  - Check if folder was in correct location (matches `folder_hierarchy` patterns)
  - Check if folder name is canonical (matches `canonical_registry`)
  - Analyze: Was this folder structure correct before files were moved?
- **Smart folder restoration:**
  - **If original folder was CORRECT:**
    - Show: "Original folder was correctly named/located"
    - Option: "Restore files to original folder" - moves files back
    - Option: "Keep files in new location, remove empty folder"
    - Option: "Keep empty folder for future use"
  - **If original folder was INCORRECT (duplicate/misnamed):**
    - Show: "Original folder was misnamed/duplicate"
    - Option: "Remove empty folder" (recommended)
    - Option: "Keep folder for reference"
- **Show empty folders view:**
  - List of empty folders with:
    - Folder path
    - Original file count (before consolidation)
    - Files that were moved (with new locations)
    - Assessment: "Correct location" or "Incorrect/duplicate"
    - Actions: "Restore files", "Remove folder", "Keep folder"
- **Bulk operations:**
  - Select multiple empty folders
  - "Remove all empty duplicate folders"
  - "Restore all to correct original folders"

### 5. Orphaned Files Detection & Restoration
- **Detect orphaned files** - Files that exist on disk but aren't in the database:
  - Scans specified directories (e.g., iCloud Drive root)
  - Finds files not tracked in Supabase
  - Shows file path, size, date
  - Option to "Add to database" (run analysis)
- **Detect missing files** - Files in database but path doesn't exist:
  - Query all `documents` table entries
  - Verify `current_path` exists on disk using `verify_file_accessible()`
  - Mark as "missing" if file doesn't exist
  - Update `is_accessible` flag in `document_locations` table
- **Restore orphaned files to original location:**
  - **For files IN database** (known files):
    - Query `document_locations` table for original path history
    - Check `location_type` ('primary', 'previous', 'current')
    - Show "Original location: /path/to/original/folder"
    - Option to "Restore to original location"
    - If original location doesn't exist, suggest nearest similar location
  - **For files NOT in database** (unknown files):
    - Analyze file content to determine category (use DocumentProcessor)
    - Use AI to suggest location based on:
      - File name patterns
      - File content/type (e.g., .plist files → Preferences folder)
      - Similar files nearby
      - Category matching (e.g., "com.apple.DocumentsApp.plist" → Library/Preferences/)
    - Show "Suggested location: /path/suggested"
    - Option to "Move to suggested location" or "Keep where it is"
- **Smart location detection:**
  - **By file type**: `.plist` → Library/Preferences/, `.pdf` → Documents/
  - **By filename**: Check if similar files exist in nearby folders
  - **By content**: Analyze content to determine category
  - **By database history**: If file hash matches, use original location
- **Show orphaned files view:**
  - List of orphaned files (not in DB) with:
    - Current location
    - Suggested location (AI-powered)
    - "Analyze & Suggest" button
    - "Move to suggested location" button
  - List of missing files (in DB but path doesn't exist) with:
    - Current path (doesn't exist)
    - Original location from `document_locations` table
    - "Restore to original" or "Update Path" option
  - Summary count: "X orphaned files, Y missing files"
- **Actions:**
  - For orphaned files: "Analyze & Suggest Location" - runs DocumentProcessor + location inference
  - For orphaned files: "Move to Suggested Location" - moves file to AI-suggested location
  - For missing files: "Restore to Original" - uses `document_locations.original_path`
  - For missing files: "Remove from DB" or "Update Path" (if moved elsewhere)
  - Bulk operations: Select multiple files, restore/analyze all

### 5. Integration Points
- **Use existing Supabase database** - Query `documents` table
- **Use existing context** - All AI analysis already stored:
  - `ai_category`, `ai_subcategories`
  - `ai_summary`
  - `entities` (JSONB)
  - `key_dates[]`
  - `folder_hierarchy[]`
  - `current_path`
- **No new analysis needed** - Dashboard is read-only, uses existing data

## Technical Stack

### Frontend
- **Framework**: Next.js (React) - matches existing `PRDTool/landing` pattern
- **UI Library**: Tailwind CSS + shadcn/ui components
- **Charts**: Recharts or Chart.js for visualizations
- **Search**: Client-side filtering + Supabase querying

### Backend/API
- **Supabase Client** - Direct queries from frontend (or API route for complex queries)
- **Natural Language Processing** - Parse user queries to extract:
  - Category keywords (e.g., "verizon bill" → `ai_category: "utility_bill"`)
  - Date keywords (e.g., "from 2024" → filter `key_dates[]`)
  - Entity keywords (e.g., "verizon" → search `entities.organizations`)

### Database Queries
- **Statistics**: `SELECT ai_category, COUNT(*) FROM documents GROUP BY ai_category`
- **Search**: Full-text search on `ai_summary`, `file_name`, plus JSONB queries on `entities`
- **Date filtering**: Query `key_dates[]` array and metadata dates

## Tasks

### Phase 1: Setup & Database Integration
- [x] Create `dashboard/` directory in TheConversation
- [x] Set up Next.js app with TypeScript
- [x] Configure Supabase client connection
- [x] Create API routes for database queries
- [x] Test database connection and query data

### Phase 2: Statistics Dashboard
- [x] Create statistics API endpoint:
  - Category counts
  - Date distribution (by year)
  - Context bin counts
- [x] Build statistics UI component:
  - Category breakdown with counts
  - Date distribution chart
  - Context bin overview
- [x] Add filtering (by category, date range)
- [x] Make charts interactive (click to filter)

### Phase 3: Natural Language Search
- [x] Create search API endpoint:
  - Parse natural language queries
  - Extract keywords: category, date, entity, organization
  - Build Supabase query with filters
- [x] Build search UI:
  - Search input with example queries
  - Results list with file info
  - Clickable paths to open files
- [x] Display search results:
  - File name
  - Full path (clickable)
  - AI category and summary
  - Key entities (people, organizations, dates)
  - Date information

### Phase 4: Document Browser
- [x] Create document list API endpoint:
  - Get all documents with pagination
  - Support filtering and sorting
- [x] Build document browser UI:
  - Table/list view with columns
  - Filters sidebar (category, date, context bin)
  - Sort controls
  - Pagination
- [x] Add "Open in Finder" functionality (macOS)

### Phase 5: Empty Folders Detection & Management
- [x] Create empty folders API endpoint:
  - `GET /api/empty-folders` - Find empty folders after consolidation
  - `GET /api/empty-folders/{folder}/history` - Get files that were moved from folder
  - `POST /api/empty-folders/{folder}/assess` - Assess if original folder location was correct
  - `POST /api/empty-folders/{folder}/restore` - Restore files to original folder
  - `POST /api/empty-folders/{folder}/remove` - Remove empty folder
- [x] Implement folder assessment logic:
  - Check folder name vs AI categories of moved files
  - Check if folder location matches `folder_hierarchy` patterns
  - Check if folder name is in canonical registry
  - Determine: "Correct location" vs "Incorrect/duplicate"
- [x] Query execution logs and `document_locations`:
  - Find folders that had files moved (check `location_type='previous'`)
  - Track which files came from which folders
  - Show file movement history
- [x] Build empty folders UI:
  - Tab/section for "Empty Folders"
  - List with: folder path, original file count, files moved, assessment
  - "Restore Files" button (if folder was correct)
  - "Remove Folder" button (if folder was duplicate/incorrect)
  - "Keep Folder" option
  - Bulk selection and operations
- [x] Integrate with existing systems:
  - Use execution logs to track file movements
  - Query `document_locations` for file history
  - Use `canonical_registry` to check folder names
  - Use category mapping to assess folder correctness

### Phase 6: Orphaned Files Detection & Restoration
- [x] Create orphaned files API endpoint:
  - `GET /api/orphaned` - Find files on disk not in database
  - `GET /api/missing` - Find files in database with missing paths
  - `POST /api/orphaned/analyze` - Analyze orphaned file (add to DB)
  - `POST /api/orphaned/suggest-location` - Suggest location for orphaned file
  - `POST /api/orphaned/restore` - Move orphaned file to suggested/original location
  - `POST /api/missing/get-original` - Get original path from `document_locations` table
  - `POST /api/missing/restore` - Restore missing file to original location
  - `POST /api/missing/remove` - Remove missing file from DB
  - `POST /api/missing/update-path` - Update path for moved file
- [x] Implement location suggestion logic:
  - Check if file hash exists in database → use `document_locations` for original path
  - For unknown files: Analyze file type, name, content to suggest location
  - Use existing category mapping from `organizer/category_mapper.py`
  - Check `folder_hierarchy` patterns for similar files
  - AI-powered suggestion using file metadata (e.g., ".plist" → Library/Preferences/)
- [x] Build orphaned files UI:
  - Tab/section for "Orphaned Files" and "Missing Files"
  - For orphaned files:
    - List with: file name, current path, suggested location, confidence
    - "Analyze & Suggest Location" button
    - "Move to Suggested Location" button
    - Show reasoning for suggestion
  - For missing files:
    - List with: file name, missing path, original location (from DB)
    - "Restore to Original" button
    - "Remove" or "Update Path" option
  - Bulk selection and operations
- [x] Integrate with existing systems:
  - Use `verify_file_accessible()` from `organizer/post_verification.py`
  - Use `scan_folder_for_files()` to find orphaned files
  - Use `DocumentProcessor` to analyze orphaned files
  - Query `document_locations` table for location history
  - Use file hash matching to find original locations

### Phase 7: Polish & UX
- [x] Add loading states and error handling
- [x] Responsive design (mobile-friendly)
- [x] Add example queries in search placeholder
- [x] Add tooltips and help text
- [x] Optimize queries for performance

### Phase 8: Ralphy Execution Backlog (Complete)
- [x] Integrate dashboard inbox-process API tests into `dashboard/__tests__`
- [x] Move workspace file to repo root as `PRDTool.code-workspace`
- [x] Wire Ralphy to execute only unchecked tasks in this phase by default
  - `.cursor/rules/prd-driven-execution.mdc` (alwaysApply)
  - `prompts/07_ralphy_full_cycle.md` (full-cycle prompt)
- [x] Add `GET /api/agents` endpoint — returns all known agents with status
  - Query `launchd` for `com.prdtool.*` services
  - Read agent `state.json` for last cycle, proposal counts
  - Return: `agent_id`, `label`, `status` (running/stopped), `last_cycle`, `last_status`, `pending_actions`
- [x] Add `POST /api/agents` endpoint — manual agent controls
  - Actions: `run-once` (trigger single cycle), `start`, `stop`, `restart`
  - `run-once` calls `python3 -m organizer --agent-once`
  - `start`/`stop`/`restart` call `launchctl` via `organizer.launchd_agent`
- [x] Add agent audit endpoint `GET /api/agents/audit`
  - Discover all `com.prdtool.*` launchd services (not just known labels)
  - Scan for any running `python3 -m organizer` processes via `pgrep`/`ps`
  - Report: found services, PID, uptime, config path, unexpected processes
- [x] Add `Agents` dashboard page
  - List all agents with live status badges (running/stopped/error)
  - "Run Now" button per agent (calls `POST /api/agents` with `run-once`)
  - Start / Stop / Restart controls per agent
  - Last cycle summary: timestamp, status, proposal count
  - Queue summary widget: pending moves, empty-folder keep/review/prune counts
- [x] Add agent audit panel to Agents page
  - "Audit Running Agents" button (calls `GET /api/agents/audit`)
  - Shows discovered services, PIDs, any unexpected processes
  - Highlights mismatches (registered vs actually running)
- [x] Add docs section for "Runbook: agent ops from UI"

### Phase 9: Upstream Refresh Discipline
- [x] Sync with `upstream/main` on a regular cadence
- [x] Run smoke tests after upstream sync (`dashboard` + organizer tests)
- [x] Log upstream delta summary in `docs/` before starting next dev wave

### Phase 10: Inbox Router in Continuous Agent

> Requirements: [docs/INBOX_ROUTER_REQUIREMENTS.md](docs/INBOX_ROUTER_REQUIREMENTS.md)

- [x] Add date signals to `InboxProcessor._classify()`
  - Parse `mtime`/`ctime`; extract 4-digit years from filename; use date for temporal category hints (e.g., tax year)
- [x] Add content-based category mapping
  - Integrate `CategoryMapper` or taxonomy lookup in `_classify()` to assign taxonomy-aligned categories (tax_doc, project_artifact, personal, etc.)
- [x] Resolve destination from taxonomy
  - Map classified category to folder path via `ROOT_TAXONOMY.json` + `canonical_registry`; ensure destination is a valid taxonomy path
- [x] Convert `InboxRouting` to `ProposedAction`
  - In `_process_inbox()`, build `ProposedAction` with `action_type="inbox_file_move"`, `source_folder` = file path, `target_folder` = destination path
- [x] Merge inbox proposals into queue
  - Extend `proposed_actions` with inbox `ProposedAction`s before writing `pending_{cycle_id}.json`
- [x] Defer execution to queue processor
  - When `auto_execute` is False: only add to queue. When True: execute high-confidence inbox routings; add low-confidence to queue
- [x] Wire `_execute_high_confidence_groups` for inbox
  - Ensure execution path handles `action_type="inbox_file_move"` (file move, not folder move)
- [x] Update cycle summary
  - Include inbox proposal count in queue, inbox auto-executed count
- [x] Add tests
  - `test_continuous_agent.py`: inbox proposals appear in queue
  - `test_organizer_inbox.py`: date + content signals affect classification

---

### Build Order (LLM-Native Phases)

> **Architecture reference:** `.cursor/plans/llm-native_agent_rewrite_8edaa799.plan.md`
> Cross-check all implementation against that plan's architecture diagram and
> tier map. If a task contradicts the plan, flag it — do not silently diverge.
>
> Phases 12-15 depend on the LLM Engine from Phase 16.1. **Phase 16.1 must be
> built before any LLM-native agent phase.** Phase 11 has no LLM dependency
> and can be built in any order.
>
> **Required build sequence:**
>
> | Order | Phase | Why |
> |-------|-------|-----|
> | 1 | **16.1** -- LLM Engine | `llm_client.py`, `model_router.py`, `prompt_registry.py` — every agent imports these |
> | 2 | **16.2** -- Filing-Agent LLM Upgrade | Existing `inbox_processor.py`, additive change |
> | 3 | **12** -- Scatter-Agent | First new LLM-native agent; depends on 16.1 |
> | 4 | **13** -- Intelligence-Agent | Depends on 16.1; extends with DNA + dedup + relationships |
> | 5 | **14** -- ReFileMe-Agent | Depends on 16.1 + routing history from Phase 13 DNA |
> | 6 | **15** -- Learning-Agent | Depends on 16.1; wires into all prior agents |
> | 7 | **16.3-16.5** -- Enrichment, Observability, Experiments | Depends on all agents being wired |
> | 8 | **16.6** -- Tests for Phase 16 modules | After all modules exist |
> | any | **11** -- Dry-Run Pipeline | No LLM dependency, standalone infrastructure |

---

### Phase 11: Dry-Run → Ready Pipeline

> When a dry-run passes with no errors, the associated requirement transitions
> to "ready for sprint" automatically. This closes the gap between validation
> and execution — no manual triage step between a green dry-run and sprint
> planning.

- [x] Add `dry_run_status` field to PRD task tracking
  - Possible values: `untested`, `dry_run_pass`, `dry_run_fail`, `ready`
  - Stored in `.organizer/agent/prd_task_status.json` (task_id → status map)
- [x] Create `organizer/dry_run_validator.py` module
  - `DryRunResult` dataclass: task_id, passed (bool), errors (list), timestamp
  - `validate_dry_run(task_id, test_output) -> DryRunResult`: parse test/build output, determine pass/fail
  - `mark_ready(task_id)`: set status to `ready` when dry-run passes
- [x] Wire dry-run validation into agent cycle
  - After `--agent-once` completes: if cycle ran in dry-run mode and all actions succeeded, mark associated PRD tasks as `dry_run_pass`
  - Auto-transition `dry_run_pass` → `ready` (no human gate needed for green runs)
- [x] Add `--dry-run` flag to agent cycle
  - Agent proposes actions but does not execute; validates proposals against filesystem and taxonomy
  - Reports: would-move count, confidence distribution, any conflicts
- [x] Add `GET /api/agents/ready-tasks` dashboard endpoint
  - Returns tasks with status `ready` — these are the next sprint candidates
  - Sorted by priority (phase order, then task order within phase)
- [ ] Add ready-tasks panel to Agents dashboard page
  - Shows tasks that passed dry-run and are ready to execute
  - One-click "Execute" button to run the task for real
- [ ] Add tests
  - `test_dry_run_validator.py`: pass/fail detection, status transitions, ready marking

### Phase 12: Scatter-Agent (LLM-Native)

> Files that exist outside their correct bin violate the taxonomy. The
> Scatter-Agent detects violations using **T1 Fast** for binary placement
> validation and **T2 Smart** for path-preservation reasoning. Locked bins
> cannot be renamed or merged by the agent. Every scatter proposal includes an
> LLM-generated explanation. If Ollama is unavailable, falls back to category
> mapper + filename signals.

- [ ] Lock top-level bins in taxonomy
  - `ROOT_TAXONOMY.json`: add `locked: true` to root categories (VA, Finances Bin, Work Bin, etc.)
  - Locked bins cannot be renamed, moved, or merged by the agent
  - New subcategories can still be created under locked bins
- [ ] Create `organizer/scatter_detector.py` module (LLM-native)
  - `ScatterViolation` dataclass: file_path, current_bin, expected_bin, confidence, reason, model_used
  - `detect_scatter(base_path, taxonomy, llm_client) -> list[ScatterViolation]`
  - For each file, call **T1 Fast** with prompt:
    `"File '{filename}' is in '{current_path}'. Based on its name and content preview, does it belong in '{current_bin}' or should it be in '{expected_bin}'? Reply JSON {belongs_here: bool, correct_bin, confidence, reason}"`
  - Escalation: if T1 confidence < 0.75, re-evaluate with **T2 Smart** using full content
  - Graceful degradation: if LLM unavailable, fall back to category mapper + filename signals
- [ ] LLM-powered path preservation
  - When proposing a scatter fix, ask **T2 Smart**:
    `"What subfolder structure should '{filename}' have inside '{target_bin}'? Preserve year/agency hierarchy. Reply JSON {suggested_subpath, reason}"`
  - Never flatten: `2011/IRS/1040.pdf` → `Finances Bin/Taxes/Federal/2011/1040.pdf`
- [ ] Resync canonical registry with taxonomy
  - Cross-check `canonical_registry.json` entries against `ROOT_TAXONOMY.json`
  - Remove orphaned entries; add missing entries
- [ ] Add scatter report to agent cycle
  - After inbox step, run scatter detection; add violations as `ProposedAction` with `action_type="scatter_fix"`
  - Always queue for review (never auto-execute); each proposal includes `reason` and `model_used`
- [ ] Add `GET /api/scatter-report` dashboard endpoint
  - Returns violations grouped by root bin: file, current location, proposed location, confidence, LLM reason
- [ ] Add scatter report page to dashboard
  - Table with LLM reasoning visible per row; approve/reject per item; bulk approve > 0.95
- [ ] Add tests
  - `test_scatter_detector.py`: LLM path (mock LLM), keyword fallback when LLM down, locked bin protection, path preservation
  - `test_continuous_agent.py`: scatter proposals appear in queue with `reason` and `model_used` fields

### Phase 13: Intelligence-Agent (LLM-Native)

> Content-aware classification, duplicate detection, and relationship linking.
> **T1 Fast** handles high-volume tag extraction. **T2 Smart** handles fuzzy
> dedup reasoning and cross-file relationship detection. **T3 Cloud** escalates
> for large clusters (> 50 files). Exact hash dedup is deterministic — no LLM
> needed. Falls back to regex + ROUTING_RULES keywords if LLM unavailable.

- [ ] Create `organizer/file_dna.py` module
  - `FileDNA` dataclass: file_path, sha256_hash, content_summary (first 500 chars), auto_tags, origin, first_seen_at, routed_to, duplicate_of, model_used
  - `DNARegistry` class: load/save from `.organizer/agent/file_dna.json`
  - `compute_file_hash(filepath) -> str`: SHA-256 in 8KB chunks
  - `extract_tags(filename, content_text, llm_client) -> list[str]`: call **T1 Fast** with prompt:
    `"Extract structured tags from file '{filename}', content: '{first_500_chars}'. Reply JSON {document_type, year, organizations, people, topics, suggested_tags}"`
  - Graceful degradation: if LLM unavailable, fall back to regex year extraction + ROUTING_RULES keyword matching
- [ ] Wire DNA registration into agent cycle
  - After each successful inbox move or consolidation, register file's DNA
  - During full scan, register newly discovered files with `origin="scan"`
- [ ] Create `organizer/dedup_engine.py` module
  - `DuplicateGroup` dataclass: sha256_hash, canonical_path, duplicate_paths, wasted_bytes
  - `find_exact_duplicates(dna_registry) -> list[DuplicateGroup]`: group by hash (deterministic — no LLM needed)
  - `find_fuzzy_duplicates(dna_registry, llm_client, threshold=0.85) -> list[DuplicateGroup]`: for candidate pairs with similar filenames, call **T2 Smart**:
    `"Are '{file_a}' (preview: '{content_a}') and '{file_b}' (preview: '{content_b}') duplicates, versions, or unrelated? Reply JSON {relationship: exact_duplicate|version_of|related|unrelated, confidence, reason}"`
  - Dedup never deletes — moves duplicates to `Archive/Duplicates/{hash_prefix}/`
- [ ] Add dedup step to agent cycle
  - After scatter detection, run dedup; add proposals as `ProposedAction` with `action_type="dedup_archive"`
  - Always queue for review (never auto-execute dedup)
- [ ] Create `organizer/relationship_linker.py` module
  - `FileRelationship` dataclass: source_path, related_path, relationship_type, reason, model_used
  - `detect_relationships(dna_registry, llm_client) -> list[FileRelationship]`: for files in same bin, ask **T2 Smart** to identify companions, versions, references
  - Escalation: clusters > 50 files escalate to **T3 Cloud**
  - Example: `nexus_letter.pdf` + `dbq_ptsd.pdf` → companions (both VA evidence)
- [ ] Add `GET /api/file-dna` dashboard endpoint
  - Search by keyword, hash, or tag; returns provenance, related files, duplicate status
- [ ] Add `GET /api/file-dna/duplicates` dashboard endpoint
  - Returns duplicate groups: hash, file count, wasted bytes, paths
- [ ] Add file intelligence page to dashboard
  - DNA search, duplicate report with storage savings estimate, relationship view
- [ ] Add tests
  - `test_file_dna.py`: hash computation, T1 tag extraction (mock LLM), keyword fallback when LLM down
  - `test_dedup_engine.py`: exact dedup (hash), T2 fuzzy dedup (mock LLM), archive path generation
  - `test_relationship_linker.py`: companion detection (mock T2), T3 escalation trigger for large clusters

### Phase 14: ReFileMe-Agent (LLM-Native)

> After filing, the user may accidentally move a file. **T1 Fast** determines
> if drift was intentional or accidental. **T2 Smart** suggests a new
> destination when the original location no longer exists. Hash matching
> prevents false positives. Falls back to path-type heuristics
> (taxonomy path = intentional, Desktop/Downloads = accidental) if LLM
> unavailable.

- [ ] Create `organizer/refile_agent.py` module
  - `DriftRecord` dataclass: file_path, original_filed_path, current_path, filed_by, filed_at, detected_at, sha256_hash, drift_assessment, reason, model_used
  - `detect_drift(routing_history, filesystem, llm_client) -> list[DriftRecord]`: for each executed routing record, check if file still exists at filed path; search by filename + hash if not; for found drifted files, call **T1 Fast**:
    `"File '{filename}' was filed at '{original_path}' on {filed_date}. It is now at '{current_path}'. Was this move intentional (user reorganized) or accidental (drag-drop)? Reply JSON {likely_intentional: bool, confidence, reason}"`
  - Escalation: T1 confidence < 0.75 → **T2 Smart** with file content for deeper analysis
  - Graceful degradation: if LLM unavailable, classify by path type (valid taxonomy path = likely_intentional, Desktop/Downloads/root = likely_accidental)
- [ ] LLM-powered refile destination suggestion
  - When original location no longer exists, ask **T2 Smart**:
    `"File '{filename}' was originally at '{original_path}' but that folder is gone. Based on the current taxonomy and file content, where should it go now? Reply JSON {suggested_path, confidence, reason}"`
- [ ] Add drift detection step to agent cycle
  - Runs last in cycle; only checks files filed in the last N days (default 90)
  - `ProposedAction` with `action_type="refile_drift"`, always queued for review
  - Each proposal includes `reason` and `model_used`
- [ ] Distinguish intentional from accidental drift for queue priority
  - `likely_accidental` = high priority (red in dashboard); `likely_intentional` = low priority (yellow)
  - If file moved to In-Box: skip (Filing-Agent handles it on next cycle)
- [ ] Update routing history on refile
  - On approval: update `RoutingRecord` to reflect new filing; preserve original with status `refiled`
- [ ] Add `GET /api/refile/drift-report` dashboard endpoint
  - Returns drifted files with LLM assessment, reason, model_used; filterable by priority and root bin
- [ ] Add drift report panel to Agents dashboard page
  - Color-coded: red for likely accidental, yellow for likely intentional; LLM reasoning visible
  - Approve (refile) / Dismiss (mark intentional) per item; bulk approve for likely-accidental
- [ ] Add tests
  - `test_refile_agent.py`: drift detection with hash matching, T1 assessment (mock LLM), T2 escalation, keyword fallback, routing history update on refile
  - `test_continuous_agent.py`: refile proposals appear in queue with `reason` and `model_used` fields

### Phase 15: Learning-Agent (LLM-Native)

> Absorbs the existing folder structure as-is. **T2 Smart** detects the
> domain (personal, medical, legal, automotive, car dealership) from folder
> structure context — no hardcoded keywords needed. **T2 Smart** generates
> routing rules from observation and narrates the organizational strategy in
> plain English. Dust off the shelves, align the books — don't reshuffle the
> boxes. Learned rules take priority over built-in taxonomy. Falls back to
> folder-name keyword matching if LLM unavailable.

- [ ] Create `organizer/structure_analyzer.py` module
  - Walk filesystem tree up to configurable depth (default: 4 levels)
  - At each level, record: folder name, depth, file count, file types present, naming patterns
  - Output `learned_structure.json`: snapshot with metadata per node and `strategy_description` field
  - Respect `.organizer` ignore patterns; skip system folders (`.Trash`, `node_modules`, etc.)
- [ ] LLM-powered domain detection (replaces rule-based domain_detector)
  - Primary model: **T2 Smart**
  - Prompt: `"Given this folder structure (top 3 levels with file counts and sample filenames): {structure_json}. What domain is this? Options: personal, medical, legal, automotive, creative, engineering, generic_business. Reply JSON {domain, confidence, evidence: [list of signals that matched]}"`
  - `DomainContext` dataclass: detected_domain, confidence, evidence, model_used
  - Graceful degradation: if LLM unavailable, keyword-match folder names against domain signal lists
- [ ] LLM-powered rule generation (replaces rule-based rule_generator)
  - Primary model: **T2 Smart**
  - For each folder, prompt: `"Folder '{folder_name}' contains these files: {filename_list}. What routing rule describes what belongs here? Reply JSON {pattern, destination, confidence, reasoning}"`
  - Output `learned_routing_rules.json`
- [ ] LLM-powered structure narration
  - After analysis, **T2 Smart** generates plain-English strategy description:
    `"Summarize this organizational strategy in 2-3 sentences for a non-technical user: {structure_json}"`
  - Stored in `learned_structure.json` as `strategy_description`; displayed in dashboard
- [ ] Create `organizer/learned_rules.py` module
  - `LearnedRuleStore` class: load/save from `.organizer/agent/learned_routing_rules.json`
  - `match(filename, content_signals) -> tuple[destination, confidence]`
  - Merge priority: learned rules → user overrides → built-in taxonomy → hardcoded `ROUTING_RULES`
- [ ] Wire learned rules into routing pipeline
  - `inbox_processor.py`: check `LearnedRuleStore.match()` before `ROUTING_RULES`
  - `scatter_detector.py` (Phase 12): measure violations against learned structure first
  - `refile_agent.py` (Phase 14): learned rules as source of truth for "correct" placement
  - Consolidation planner: respect learned hierarchy; never merge folders the snapshot says are separate
- [ ] Add onboarding CLI commands
  - `python3 -m organizer --learn-structure [path]`: trigger full scan, output summary (folder count, rule count, detected domain)
  - `python3 -m organizer --learn-confirm`: activate learned rules after user reviews them
  - `python3 -m organizer --learn-status`: current learned rules status (active/inactive, rule count, last scan date)
- [ ] Add learned rules page to dashboard
  - Collapsible folder tree of learned structure with `strategy_description` shown prominently
  - Domain detection result with confidence and evidence list
  - Browse generated rules: pattern, destination, confidence; toggle individual rules on/off
  - "Re-scan" button to refresh the structure snapshot
- [ ] Add tests
  - `test_structure_analyzer.py`: tree walking, metadata extraction, ignore patterns, depth limiting
  - `test_learning_agent.py`: T2 domain detection (mock LLM), T2 rule generation (mock LLM), structure narration, learned rule merge priority (learned > override > built-in > hardcoded)

### Phase 16: Multi-LLM Agentic Core

> The pivot from automation to true agentic AI. Every agent gains a brain.
> Instead of one model doing everything, a multi-LLM architecture routes
> each task to the right model: fast 8B for high-volume decisions, smart
> 14B for complex reasoning, and optional cloud 480B/671B for the hardest
> problems. The system degrades gracefully -- if the smart model is busy,
> the fast model handles it; if Ollama is down, keyword rules still work.
> No API costs for local models, no data leaves the machine. Cloud models
> are opt-in and can be disabled entirely.
>
> **Available Models (benchmarked):**
> | Tier | Model | Size | Speed | Use |
> |------|-------|------|-------|-----|
> | T1 Fast | `llama3.1:8b-instruct-q8_0` | 8.5GB | ~3.7s | Classification, yes/no, tagging |
> | T1 Fast | `qwen2.5-coder:latest` (7.6B) | 4.7GB | ~3s | Lightweight alt for T1 |
> | T2 Smart | `qwen2.5-coder:14b` | 9.0GB | ~10s | Complex reasoning, analysis |
> | T3 Cloud | `qwen3-coder:480b-cloud` | remote | ~15-30s | Deep analysis, hard cases |
> | T3 Cloud | `deepseek-v3.1:671b-cloud` | remote | ~15-30s | Fallback cloud option |

#### 16.1 -- LLM Engine (`organizer/llm_client.py`)
- [x] Create `LLMClient` class wrapping Ollama REST API (`localhost:11434/api/generate`)
  - `generate(prompt, model, temperature, max_tokens, timeout_s) -> LLMResponse`
  - `LLMResponse` dataclass: text, model_used, duration_ms, tokens_eval, success
  - Connection pooling via `requests.Session`; reuse across calls in same cycle
- [x] Create `ModelRouter` class for multi-LLM task routing
  - `ModelTier` enum: FAST, SMART, CLOUD
  - `TaskProfile` dataclass: task_type (classify, validate, analyze, enrich, generate), complexity (low, medium, high), content_length
  - `select_model(task_profile) -> str`: picks the right model name based on task + availability
  - Default routing table configurable in `agent_config.json` under `llm_models`:
    ```json
    {
      "llm_models": {
        "fast": "llama3.1:8b-instruct-q8_0",
        "smart": "qwen2.5-coder:14b",
        "cloud": null,
        "cloud_enabled": false,
        "escalation_threshold": 0.75
      }
    }
    ```
  - Availability check: before routing to a model, verify it is loaded (`/api/tags`); if not, fall to next tier
- [x] Implement confidence-based escalation
  - If T1 (fast) returns confidence < `escalation_threshold` (default 0.75), auto-escalate to T2 (smart)
  - If T2 returns confidence < threshold AND `cloud_enabled` is true, escalate to T3
  - Each escalation logs: original model, original confidence, escalated model, new confidence
  - Max escalation chain: T1 → T2 → T3 → keyword fallback (never loops)
- [x] Implement graceful degradation chain
  - If preferred model unavailable: T2 → T1 → keyword rules
  - If Ollama is down entirely: all agents fall back to keyword/rule-based logic seamlessly
  - Health state cached for 60s to avoid hammering Ollama on every call
- [x] Create prompt management system
  - Prompts stored in `.organizer/prompts/` directory as editable `.txt` files
  - `PromptRegistry` class: loads prompts by name, supports variable substitution (`{filename}`, `{bins}`, `{content}`)
  - Prompt versioning: each prompt file has a header comment with version and last-modified date
  - Default prompts created on first run if directory is missing

> **Note:** Sections 16.2–16.6 have been merged directly into Phases 12–15.
> Those phases are now LLM-native from day one — no separate "upgrade" step needed.
> Phase 16 covers only the shared infrastructure, enrichment service, observability,
> and experiment framework that all agents depend on.

#### 16.2 -- Filing-Agent LLM Integration (Phase 10 upgrade)
- [ ] Replace keyword matching in `InboxProcessor._classify()` with LLM-first classification
  - Primary model: **T1 Fast** (high volume, needs speed -- ~3.7s per file)
  - Prompt: given filename + first 500 chars of content + available bins/subcategories, return JSON `{bin, subcategory, confidence, reason}`
  - Escalation: if T1 confidence < 0.75, re-classify with **T2 Smart** using full content
  - Fallback: if LLM unavailable, existing keyword `ROUTING_RULES` still work as-is
- [ ] A/B comparison logging during rollout
  - For each file: run LLM classification AND keyword matching; log both results
  - `ClassificationComparison` dataclass: filename, llm_result, keyword_result, agreed (bool), winner (used for routing)
  - Comparison log stored at `.organizer/agent/logs/llm_comparison_{cycle_id}.json`
  - Dashboard can show agreement rate to build trust before disabling keyword fallback

#### 16.3 -- Metadata Enrichment Service
- [ ] Create `organizer/llm_enrichment.py` module
  - `enrich_file(filename, content_text) -> FileEnrichment`: extract structured metadata via LLM
  - `FileEnrichment` dataclass: document_type, date_references, people, organizations, key_topics, summary (1-2 sentences), suggested_tags
  - Primary model: **T2 Smart** (structured extraction needs accuracy)
  - Batch mode: process multiple files in sequence with progress reporting and rate limiting
  - Cache enrichments in `.organizer/agent/enrichment_cache.json` keyed by file hash; skip files already enriched
- [ ] Wire enrichment into agent cycle
  - After successful inbox filing: enrich the filed file (async, non-blocking to the filing flow)
  - After DNA registration (Phase 13): enrich if not already cached
  - Enrichment data stored alongside File DNA record
- [ ] Power dashboard search with enrichment data
  - Natural language search queries matched against enrichment metadata
  - "Find my Verizon bill from March 2024" matches against `organizations: ["Verizon"]`, `date_references: ["March 2024"]`
  - No vector database needed -- structured metadata + text search is sufficient for this scale

#### 16.4 -- Observability and Dashboard
- [ ] Add LLM health check endpoint
  - `GET /api/llm/status`: Ollama running?, loaded models, per-model avg response time, total classifications today
  - `GET /api/llm/models`: list available models with size, tier assignment, availability
  - Show LLM status on Agents page: model name, tier, avg response time, classification count
  - Alert when Ollama is down (system falls back to keyword matching automatically)
- [ ] Add explainability to all routing decisions
  - Every routing record now includes `reason` (natural language from LLM) and `model_used`
  - Dashboard inbox history shows: filename, destination, confidence, model tier, AND the LLM's explanation
  - Scatter report shows LLM reasoning for each violation
  - Drift report shows LLM's intentional-vs-accidental analysis
- [ ] Add model performance dashboard
  - Accuracy comparison: LLM vs keyword agreement rate over time
  - Latency percentiles per model tier (p50, p95, p99)
  - Escalation rate: how often T1 needs to escalate to T2
  - Cost tracking: if cloud models are enabled, track usage and estimated cost
- [ ] Add prompt management UI (stretch)
  - View and edit prompt templates from the dashboard
  - Test a prompt against a sample file and see the response
  - Prompt version history

#### 16.5 -- Multi-LLM Experiment Framework
- [ ] Create `organizer/llm_experiment.py` module
  - `Experiment` dataclass: name, models_to_compare (list of model names), test_files (list of paths), expected_results (optional ground truth)
  - `run_experiment(experiment) -> ExperimentResult`: run all models against all test files, collect results
  - `ExperimentResult`: per-file per-model results, agreement matrix, latency comparison, accuracy vs ground truth
- [ ] Add CLI command for experiments
  - `python3 -m organizer --experiment classify --models llama3.1:8b,qwen2.5:14b --files /path/to/test/files/`
  - Output: side-by-side comparison table, agreement %, latency stats
  - Save results to `.organizer/experiments/{experiment_name}_{timestamp}.json`
- [ ] Use experiments to tune model routing
  - Run experiment on a representative sample of files from each bin
  - Measure: which model tier is "good enough" for each task type?
  - Results inform the `escalation_threshold` and default routing table

#### 16.6 -- Tests
- [ ] `test_llm_client.py`: LLMClient generation, timeout handling, connection errors
- [ ] `test_model_router.py`: tier selection, escalation logic, availability fallback, degradation chain
- [ ] `test_prompt_registry.py`: prompt loading, variable substitution, missing prompt handling
- [ ] `test_llm_enrichment.py`: metadata extraction, batch mode, cache hits/misses
- [ ] `test_llm_experiment.py`: experiment runner, result aggregation, comparison output
- [ ] `test_inbox_processor.py` (update): LLM classification path, escalation from T1 to T2, keyword fallback when Ollama down, A/B comparison logging
- [ ] `test_scatter_detector.py` (update): LLM validation path, path preservation reasoning
- [ ] `test_refile_agent.py` (update): LLM drift assessment, destination suggestion when original path gone
- [ ] `test_learning_agent.py` (update): LLM domain detection, LLM rule generation, strategy narration

---

## Success Criteria
- ✅ Shows file type counts (categories) with visual charts
- ✅ Natural language search works: "Show me a file that is a verizon bill from 2024?"
- ✅ Search results show file path, category, summary, entities
- ✅ Can browse all documents with filtering and sorting
- ✅ Clickable paths open files in Finder (macOS)
- ✅ Detects orphaned files (exist on disk, not in database)
- ✅ Detects missing files (in database, path doesn't exist)
- ✅ Can analyze orphaned files and add to database
- ✅ Can suggest location for orphaned files (AI-powered)
- ✅ Can restore orphaned files to suggested/original location
- ✅ Can restore missing files to original location (from `document_locations` table)
- ✅ Can remove or update paths for missing files
- ✅ Detects empty folders after consolidation
- ✅ Assesses if original folder location was correct
- ✅ Can restore files to correct original folders
- ✅ Can remove empty duplicate/incorrect folders
- ✅ Example: ".plist" file in root → suggests Library/Preferences/ based on file type
- ✅ Example: Empty "Resume" folder → checks if files were correctly moved, offers restore if folder was right location
- ✅ Uses existing Supabase database (no new analysis needed)
- ✅ Fast and responsive UI

## Example Queries to Support
- "Show me a file that is a verizon bill from 2024?"
- "Find all tax documents from 2023"
- "Show me VA claims documents"
- "Find invoices from Amazon"
- "Show me documents from 2025"
- "Find all bank statements"
- "Show me contracts"

## Example Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  Organizer Dashboard                                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  📊 Statistics                                          │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐         │
│  │ Tax Docs  │  │ VA Claims │  │ Invoices  │         │
│  │    45     │  │    23     │  │    67     │         │
│  └───────────┘  └───────────┘  └───────────┘         │
│                                                         │
│  🔍 Search                                              │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Show me a file that is a verizon bill from 2024? │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  📄 Results                                             │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Verizon_Bill_2024_03.pdf                          │ │
│  │ 📁 /iCloud/Finances Bin/Bills/Verizon/            │ │
│  │ Category: utility_bill | Date: 2024-03-15         │ │
│  │ Entities: Verizon, $89.99                         │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  📋 All Documents                                       │
│  [Filters: Category ▼ | Date Range ▼ | Context Bin ▼] │
│  ┌───────────────────────────────────────────────────┐ │
│  │ Name              │ Path            │ Category    │ │
│  │ Verizon_Bill...   │ /iCloud/...     │ utility_bill│ │
│  │ Tax_2024.pdf      │ /iCloud/...     │ tax_doc     │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  🔍 Orphaned Files                                      │
│  ┌───────────────────────────────────────────────────┐ │
│  │ ⚠️  3 orphaned files (not in database)           │ │
│  │ 📄 random_file.pdf  (/iCloud/root/)  [Analyze]   │ │
│  │ 📄 document.pdf     (/iCloud/root/)  [Analyze]   │ │
│  └───────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────┐ │
│  │ ❌ 5 missing files (in DB, path doesn't exist)   │ │
│  │ 📄 moved_file.pdf                                │ │
│  │    Missing: /old/path/file.pdf                   │ │
│  │    Original: /Documents/File.pdf  [Restore]      │ │
│  └───────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 🔍 Orphaned File Analysis                        │ │
│  │ 📄 com.apple.DocumentsApp.plist                  │ │
│  │    Current: /iCloud/Library/Preferences/...      │ │
│  │    Suggested: /iCloud/Library/Preferences/       │ │
│  │    Reason: .plist file type → Preferences folder │ │
│  │    [Move to Suggested] [Keep Here]               │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
│  📂 Empty Folders                                      │
│  ┌───────────────────────────────────────────────────┐ │
│  │ 📁 /iCloud/Resume/ (0 files, had 12 files)       │ │
│  │    Files moved to: /iCloud/Employment/Resumes/   │ │
│  │    Assessment: ✅ Original folder was CORRECT     │ │
│  │    [Restore Files] [Remove Folder] [Keep Folder] │ │
│  ├───────────────────────────────────────────────────┤ │
│  │ 📁 /iCloud/Resumes/ (0 files, had 8 files)       │ │
│  │    Files moved to: /iCloud/Employment/Resumes/   │ │
│  │    Assessment: ❌ Duplicate folder name          │ │
│  │    [Remove Folder] [Keep for Reference]          │ │
│  └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```
