# PRD: PRDTool -- Document Intelligence Platform

> Full product vision with phased execution.
> Phase 1 is the active build phase. Phases 2-3 are future roadmap.
> See `docs/STORY.md` for the product narrative.
> See `docs/ARCHITECTURE.md` for technical architecture.

## Vision

PRDTool is a document intelligence platform that autonomously organizes files,
builds a knowledge graph of document relationships, and provides a consent-gated
conduit for platforms that need user documents. It runs locally (privacy-first),
works across any storage provider, never deletes files, and gets smarter from
corrections.

## What Already Exists

The following modules are built and operational:

| Module | Path | Status |
|--------|------|--------|
| Continuous agent | `organizer/continuous_agent.py` | Running hourly via launchd |
| Inbox processor | `organizer/inbox_processor.py` | 90+ keyword rules, PDF text extraction |
| Consolidation planner | `organizer/consolidation_planner.py` | Folder similarity + merge planning |
| Fuzzy matcher | `organizer/fuzzy_matcher.py` | Name normalization + similarity scoring |
| Canonical registry | `organizer/canonical_registry.py` | Persistent folder-to-path mappings |
| Category mapper | `organizer/category_mapper.py` | File-to-category classification |
| Content analyzer | `organizer/content_analyzer.py` | Document processing, folder analysis |
| Smart rules | `organizer/smart_rules.py` | Domain rules (VA, code projects) |
| File operations | `organizer/file_operations.py` | Atomic moves, never-delete safety |
| Execution logger | `organizer/execution_logger.py` | Rollback-capable operation logs |
| Database updater | `organizer/database_updater.py` | Supabase integration |
| Post verification | `organizer/post_verification.py` | File accessibility checks |
| CLI | `organizer/cli.py` | scan, plan, execute commands |
| Launchd agent | `organizer/launchd_agent.py` | macOS service management |
| Dashboard | `dashboard/` | 7 pages, 18 API routes, Next.js + Supabase |
| Taxonomy | `.organizer/ROOT_TAXONOMY.json` | 8 root categories with subcategories |
| Registry | `.organizer/canonical_registry.json` | 129 folder-to-path mappings |
| Agent config | `.organizer/agent_config.json` | Runtime config (hourly, auto-execute) |

---

## Phase 1: Foundation Polish (Active Build Phase)

> Goal: Make the existing system production-quality with learning capabilities,
> file DNA tracking, an MCP server for AI assistant integration, and a dedup engine.
> Everything runs locally, zero external costs.

### 1.1 Learning Loop

The agent must get smarter from user corrections. When a file is routed to the wrong
place and the user moves it back to In-Box or to the correct location, the agent should
detect this and update its routing rules permanently.

#### Tasks

- [ ] Create `organizer/routing_history.py` module
  - `RoutingRecord` dataclass: filename, source_path, destination_bin, confidence,
    matched_keywords, routed_at timestamp, status (executed/corrected/reverted)
  - `RoutingHistory` class: load/save from `.organizer/agent/routing_history.json`,
    record a routing, query history by filename or destination
  - History file capped at 10,000 entries (FIFO eviction)

- [ ] Create `organizer/learned_overrides.py` module
  - `LearnedOverride` dataclass: pattern (keyword or filename fragment), correct_bin,
    source (user_correction/manual), created_at, hit_count
  - `OverrideRegistry` class: load/save from `.organizer/agent/learned_overrides.json`,
    add override, match against filename, merge with routing rules
  - Overrides take priority over built-in `ROUTING_RULES` in `inbox_processor.py`

- [ ] Add correction detection to `organizer/inbox_processor.py`
  - Before routing a file, check `RoutingHistory` for previous routing of same filename
  - If file was previously routed and is back in In-Box: mark as correction, route to
    `Needs-Review` instead of same destination, log the conflict
  - If an override exists for this file pattern: use the override destination

- [ ] Wire `RoutingHistory` recording into `InboxProcessor.execute()`
  - After each successful move, write a `RoutingRecord` to history
  - After each error, record with status="error"

- [ ] Wire override priority into `InboxProcessor._classify()`
  - Check `OverrideRegistry` before `ROUTING_RULES` and `_extra_rules`
  - If override matches, use override destination with confidence 0.95

- [ ] Add `POST /api/inbox-process/correct` API endpoint in dashboard
  - Accepts: `{ filename, wrong_bin, correct_bin }`
  - Creates a `LearnedOverride` entry
  - Returns confirmation with the new override

- [ ] Add correction UI to dashboard inbox page (`dashboard/app/inbox/page.tsx`)
  - Show recent routing history (last 50 moves)
  - Each row shows: filename, destination, confidence, timestamp
  - "Correct" button opens modal: select correct destination from taxonomy
  - Submit calls `POST /api/inbox-process/correct`

- [ ] Write tests for routing history module
  - Test: record, query, FIFO eviction at cap
  - Test: correction detection (same file back in inbox)
  - Test: override priority over built-in rules
  - Test file: `tests/test_routing_history.py`

- [ ] Write tests for learned overrides module
  - Test: add override, match against filename, hit count increment
  - Test: override takes priority in `InboxProcessor._classify()`
  - Test file: `tests/test_learned_overrides.py`

### 1.2 File DNA

Every file processed by the agent gets a provenance record: content fingerprint,
extracted metadata, origin, relationships. This is the foundation for dedup,
relationship search, and the conduit.

#### Tasks

- [ ] Create `organizer/file_dna.py` module
  - `FileDNA` dataclass: file_path, filename, extension, size_bytes, sha256_hash,
    content_summary (first 500 chars extracted text), auto_tags (list of strings),
    origin (inbox/download/email/unknown), first_seen_at, last_seen_at,
    routed_to (current bin), related_files (list of file_paths),
    duplicate_of (canonical file_path or None)
  - `DNARegistry` class: load/save from `.organizer/agent/file_dna.json`,
    register a file (compute hash, extract text, generate tags),
    find duplicates by hash, find related by tags, search by keyword

- [ ] Add SHA-256 hashing utility
  - Function `compute_file_hash(filepath) -> str` in `file_dna.py`
  - Streams file in 8KB chunks to handle large files without memory issues

- [ ] Add auto-tagging from filename and content
  - Function `extract_tags(filename, content_text) -> list[str]` in `file_dna.py`
  - Extract: year mentions (4-digit numbers 1990-2030), names (from taxonomy
    family_members), document types (tax, receipt, statement, claim), organizations
    (from ROUTING_RULES keywords)

- [ ] Wire DNA registration into `InboxProcessor.execute()`
  - After each successful move, call `DNARegistry.register(filepath)`
  - Store DNA record with origin="inbox"

- [ ] Wire DNA registration into `ContinuousOrganizerAgent.run_cycle()`
  - During the consolidation scan, register newly discovered files
  - Store DNA record with origin="scan"

- [ ] Add `GET /api/file-dna` endpoint in dashboard
  - Query param: `?search=keyword` or `?hash=sha256`
  - Returns matching DNA records with file path, tags, duplicates

- [ ] Add `GET /api/file-dna/duplicates` endpoint in dashboard
  - Returns all files grouped by SHA-256 hash where count > 1
  - Each group shows: hash, file count, total wasted bytes, file paths

- [ ] Add `GET /api/file-dna/stats` endpoint in dashboard
  - Total files tracked, total duplicates found, total wasted storage,
    organization health score (0-100 based on: % files with DNA,
    % duplicates resolved, % files in correct bins)

- [ ] Write tests for file DNA module
  - Test: hash computation, tag extraction, duplicate detection
  - Test: register file, find by hash, find by keyword
  - Test file: `tests/test_file_dna.py`

### 1.3 MCP Server

Expose the classification engine, file DNA, and knowledge graph as MCP tools so any
AI assistant (Claude Desktop, Cursor, custom agents) can query your file intelligence.

#### Tasks

- [ ] Create `organizer/mcp_server.py` module
  - Use `mcp` Python SDK (add to `requirements.txt`)
  - Server name: "prdtool"
  - Transport: stdio (for Claude Desktop / Cursor integration)

- [ ] Implement MCP tool: `classify_file`
  - Input: `filepath: str`, `content_hint: str` (optional)
  - Loads `InboxProcessor`, calls `_classify()` on the file
  - Returns: `{ destination_bin, confidence, matched_keywords }`

- [ ] Implement MCP tool: `scan_inbox`
  - No input required (uses configured inbox path)
  - Calls `InboxProcessor.scan()`
  - Returns: `{ total_files, routed, unmatched, files: [...] }`

- [ ] Implement MCP tool: `search_files`
  - Input: `query: str`
  - Searches `DNARegistry` by keyword across tags, filename, content_summary
  - Returns: `{ results: [{ filename, path, tags, confidence }] }`

- [ ] Implement MCP tool: `get_file_dna`
  - Input: `filepath: str`
  - Returns full DNA record for the file

- [ ] Implement MCP tool: `find_duplicates`
  - Input: `filepath: str` (optional -- if omitted, returns all duplicate groups)
  - Returns: `{ groups: [{ hash, files: [...], wasted_bytes }] }`

- [ ] Implement MCP tool: `get_life_context`
  - Input: `domain: str` (work/finances/legal/health/family/va/education/personal)
  - Queries DNA registry for all files tagged with that domain
  - Returns: structured summary with file counts, recent activity, key entities

- [ ] Implement MCP tool: `record_correction`
  - Input: `{ filename, wrong_bin, correct_bin }`
  - Writes a `LearnedOverride` entry
  - Returns confirmation

- [ ] Add CLI flag `--mcp-server` to `organizer/cli.py`
  - Starts the MCP server on stdio
  - Loads config from `.organizer/agent_config.json`

- [ ] Create MCP config file for Claude Desktop integration
  - `docs/claude_desktop_config.json` with server path and args
  - Include setup instructions in `docs/ARCHITECTURE.md`

- [ ] Write tests for MCP server tools
  - Test: classify_file returns valid classification
  - Test: search_files finds by keyword
  - Test: find_duplicates groups correctly
  - Test file: `tests/test_mcp_server.py`

### 1.4 Deduplication Engine

Detect exact and near-duplicate files across the organized file system. Report
wasted storage and optionally consolidate to a single canonical copy.

#### Tasks

- [ ] Create `organizer/dedup_engine.py` module
  - `DuplicateGroup` dataclass: sha256_hash, canonical_path, duplicates (list of paths),
    total_wasted_bytes, first_seen_at
  - `DedupEngine` class: scan a directory tree, compute hashes, build groups,
    report wasted storage, optionally consolidate (keep canonical, quarantine dupes)

- [ ] Add filename-based near-duplicate detection
  - Function `find_near_duplicates(files) -> list[NearDupGroup]`
  - Detect: `report.pdf` vs `report (1).pdf` vs `report_copy.pdf`
  - Use `fuzzy_matcher.normalize_folder_name()` adapted for filenames
  - Confidence scoring: exact hash match = 1.0, fuzzy name match = 0.7-0.9

- [ ] Wire dedup scan into `ContinuousOrganizerAgent.run_cycle()`
  - Add `dedup_enabled: bool = True` config field to `ContinuousAgentConfig`
  - Run dedup scan after inbox processing, before writing state
  - Add dedup summary to cycle log: groups found, total wasted bytes

- [ ] Add `GET /api/dedup` endpoint in dashboard
  - Returns duplicate groups with canonical path, duplicates, wasted bytes
  - Supports `?action=report` (read-only) and `?action=quarantine` (move dupes)

- [ ] Add dedup section to dashboard home page or statistics page
  - Show: total duplicates, wasted storage (in GB and $/mo equivalent)
  - List top 10 duplicate groups by wasted space
  - "Quarantine Duplicates" button (moves to `Archive/Quarantined-Duplicates/`)

- [ ] Write tests for dedup engine
  - Test: hash-based exact duplicate detection
  - Test: filename-based near-duplicate detection
  - Test: quarantine moves dupes, keeps canonical
  - Test file: `tests/test_dedup_engine.py`

### 1.5 File Health Report

A dashboard view that gives users an at-a-glance understanding of their file system
health and the value the agent is providing.

#### Tasks

- [ ] Add `GET /api/health-report` endpoint in dashboard
  - Aggregate data from: DNA registry (total tracked, total dupes),
    routing history (files routed this month), dedup engine (wasted storage),
    inbox processor (pending files)
  - Return: `{ total_files_tracked, duplicates_found, wasted_storage_bytes,
    files_routed_this_month, corrections_this_month, health_score,
    storage_saved_dollars_per_month }`
  - Health score formula: 100 - (duplicate_pct * 30) - (untracked_pct * 40) -
    (inbox_pending_pct * 30)

- [ ] Create file health dashboard page (`dashboard/app/health/page.tsx`)
  - Hero metric: "File Health Score: 87/100" with color (green/yellow/red)
  - Cards: total files tracked, duplicates found, storage wasted,
    files organized this month, corrections applied
  - "Storage savings" card: "You have X GB of duplicates. That costs ~$Y/month
    in cloud storage."
  - Recent activity feed: last 20 routing actions with timestamps

- [ ] Add navigation link to health page in dashboard layout
  - Add to sidebar/header navigation alongside existing pages

- [ ] Write tests for health report endpoint
  - Test: score calculation with known inputs
  - Test: dollar estimation from bytes
  - Test file: `dashboard/__tests__/health-report-api.test.ts`

### 1.6 Dashboard Inbox Enhancements

The existing inbox page needs to show routing activity, not just trigger processing.

#### Tasks

- [ ] Enhance `dashboard/app/inbox/page.tsx`
  - Add "Recent Activity" tab showing last 50 routing actions from history
  - Add "Learned Overrides" tab showing all active overrides with hit counts
  - Add "Pending Files" tab showing current In-Box contents with proposed routing

- [ ] Add `GET /api/inbox-process/history` endpoint
  - Returns last N routing records from `routing_history.json`
  - Supports `?limit=50` query param

- [ ] Add `GET /api/inbox-process/overrides` endpoint
  - Returns all learned overrides from `learned_overrides.json`
  - Each entry shows: pattern, correct_bin, hit_count, created_at

- [ ] Add `DELETE /api/inbox-process/overrides` endpoint
  - Accepts: `{ pattern }` -- removes an override
  - For cases where user wants to undo a learned correction

### Phase 1 Success Criteria

- [ ] Agent learns from corrections: move a file back to In-Box, it does not repeat
  the same mistake
- [ ] Every file processed gets a DNA record with hash, tags, and provenance
- [ ] MCP server responds to `classify_file`, `search_files`, `find_duplicates`,
  `get_life_context` tools from Claude Desktop
- [ ] Duplicate files are detected and reported with wasted storage in GB and $/mo
- [ ] File health dashboard shows a score, recent activity, and storage savings
- [ ] All new modules have passing tests
- [ ] Dashboard builds cleanly (`npm run build` exit 0)
- [ ] Agent runs without errors (`python3 -m organizer --agent-once`)

---

## Phase 2: Multi-Platform SaaS (Future)

> Goal: Extend the agent from local-only to cloud-hosted, supporting Google Drive,
> Dropbox, and OneDrive via OAuth. Add an onboarding wizard that generates a taxonomy
> from business context. Package as a Docker appliance.

### 2.1 Storage Connectors

#### Tasks

- [ ] Create `organizer/connectors/base.py` -- abstract `StorageConnector` class
  - Interface: `list_files(path)`, `read_file(path)`, `move_file(src, dst)`,
    `get_metadata(path)`, `watch(callback)` (polling or webhook)
  - All connectors implement this interface

- [ ] Create `organizer/connectors/local.py` -- local filesystem connector
  - Wraps existing `Path` operations to match the connector interface
  - This is what the current agent uses, refactored into the new pattern

- [ ] Create `organizer/connectors/google_drive.py` -- Google Drive connector
  - OAuth 2.0 flow for user authorization
  - Google Drive API v3 for file operations
  - Webhook / polling for change detection

- [ ] Create `organizer/connectors/dropbox.py` -- Dropbox connector
  - OAuth 2.0 flow
  - Dropbox API v2 for file operations
  - Longpoll / webhook for change detection

- [ ] Create `organizer/connectors/onedrive.py` -- OneDrive connector
  - Microsoft Graph API OAuth flow
  - Graph API for file operations
  - Delta query for change detection

- [ ] Refactor `ContinuousOrganizerAgent` to use connector interface
  - Replace direct `Path` operations with connector calls
  - Connector selected based on config: `storage_type: local|gdrive|dropbox|onedrive`

### 2.2 Onboarding Wizard

#### Tasks

- [ ] Create `organizer/onboarding.py` -- taxonomy generator
  - Input: vertical (legal/medical/realestate/freelancer/family/custom),
    primary_axis (client/project/department/date),
    lifecycle (active/archive triggers),
    naming_conventions (optional patterns)
  - Output: generated `ROOT_TAXONOMY.json` and `canonical_registry.json`

- [ ] Create vertical template library (`templates/`)
  - `templates/legal.json` -- case-based taxonomy with pleadings, discovery, etc.
  - `templates/medical.json` -- patient-based taxonomy
  - `templates/realestate.json` -- property/transaction-based taxonomy
  - `templates/freelancer.json` -- client/project-based taxonomy
  - `templates/family.json` -- personal life taxonomy (what exists now)
  - `templates/general.json` -- generic business taxonomy

- [ ] Create onboarding wizard dashboard page (`dashboard/app/onboarding/page.tsx`)
  - Step 1: "What do you do?" -- vertical selection
  - Step 2: "How is your work structured?" -- primary axis
  - Step 3: "What matters most?" -- priorities
  - Step 4: "What does done look like?" -- lifecycle rules
  - Step 5: "Connect your storage" -- OAuth flow or local path
  - Result: taxonomy generated, agent configured, first scan triggered

- [ ] Add `POST /api/onboarding` endpoint
  - Accepts wizard answers
  - Generates taxonomy and registry from template + customization
  - Writes config files
  - Returns generated taxonomy for preview

### 2.3 Cloud Agent Packaging

#### Tasks

- [ ] Create `Dockerfile` for the Python agent
  - Based on `python:3.12-slim`
  - Installs dependencies, copies organizer package
  - Entrypoint: `python3 -m organizer --agent-forever`

- [ ] Create `docker-compose.yml` for full stack
  - Services: agent, dashboard (Next.js), n8n (optional), caddy (reverse proxy)
  - Supabase: use hosted Supabase (free tier) or self-hosted
  - Single `.env` file for all configuration

- [ ] Create `docker-compose.override.yml` for development
  - Volume mounts for live reload
  - Debug ports exposed

- [ ] Add n8n workflow templates (`n8n/workflows/`)
  - `inbox_watcher.json` -- watch for new files, trigger classification
  - `email_attachment.json` -- extract email attachments, route to inbox
  - `scheduled_scan.json` -- hourly full scan

- [ ] Create one-line install script (`install.sh`)
  - Pulls Docker image, prompts for config, starts services
  - Opens browser to onboarding wizard

### 2.4 Multi-Tenant Data Model

#### Tasks

- [ ] Design Supabase schema for multi-tenancy
  - `tenants` table: id, name, slug, vertical, branding (jsonb), created_at
  - `tenant_users` table: id, tenant_id, user_id, role, created_at
  - `file_dna` table: id, tenant_id, file_path, sha256, tags, metadata, created_at
  - `routing_history` table: id, tenant_id, filename, source, destination, created_at
  - `learned_overrides` table: id, tenant_id, pattern, correct_bin, hit_count
  - RLS policies: users can only see their own tenant's data

- [ ] Migrate local JSON storage to Supabase
  - `routing_history.json` -> `routing_history` table
  - `learned_overrides.json` -> `learned_overrides` table
  - `file_dna.json` -> `file_dna` table
  - Keep JSON as fallback for local-only mode

- [ ] Add tenant-aware API routes
  - All dashboard API routes scoped to authenticated user's tenant
  - Supabase auth for user sessions

### Phase 2 Success Criteria

- [ ] Agent organizes files on Google Drive via OAuth (not just local filesystem)
- [ ] New user can go from signup to first scan in under 3 minutes via onboarding wizard
- [ ] Full stack deploys with `docker compose up -d` from a single `.env` file
- [ ] Two separate tenants can use the system without seeing each other's data
- [ ] Vertical templates produce correct taxonomy for legal and medical use cases

---

## Phase 3: The Conduit (Future)

> Goal: Build the consent-gated document sharing pipeline. Platforms request documents,
> users approve, documents flow directly from user storage to the platform. No files
> stored centrally.

### 3.1 Consent-Gated Sharing API

#### Tasks

- [ ] Create `organizer/conduit/sharing.py` module
  - `ShareRequest` dataclass: requesting_platform, requested_documents (list of types),
    purpose, expires_at, status (pending/approved/denied/expired)
  - `ShareApproval` dataclass: request_id, approved_documents (list of file_paths),
    approved_at, approved_by
  - `ConduitManager` class: create share request, approve/deny, assemble package,
    deliver to platform, revoke access

- [ ] Create `organizer/conduit/document_package.py` module
  - `DocumentPackage` dataclass: purpose, documents (list of PackagedDocument),
    assembled_at, delivered_to, status
  - `PackagedDocument` dataclass: type, file_path, sha256_hash, extracted_data (dict)
  - `PackageAssembler` class: given a purpose (mortgage/tax/insurance/va_claim),
    query DNA registry for matching documents, assemble into package,
    verify completeness

- [ ] Define package templates (`conduit/templates/`)
  - `mortgage.json`: W-2 (2yr), tax returns (2yr), bank statements (3mo), pay stubs
  - `tax_filing.json`: W-2, 1099s, receipts by category, prior returns
  - `insurance_quote.json`: vehicle info, property details, current policies
  - `va_claim.json`: service records, medical evidence, buddy statements, nexus letters
  - `rental_application.json`: pay stubs, employment verification, credit authorization

- [ ] Add `POST /api/conduit/request` endpoint
  - Platform sends: purpose, requested document types
  - Creates a `ShareRequest`, sends notification to user
  - Returns request_id for polling

- [ ] Add `POST /api/conduit/approve` endpoint
  - User approves/denies a share request
  - If approved: assemble package, deliver to platform callback URL
  - Returns assembled package summary

- [ ] Add `GET /api/conduit/history` endpoint
  - Returns all share requests with status, documents shared, timestamps
  - User can see exactly what they shared with whom and when

- [ ] Create conduit management dashboard page (`dashboard/app/conduit/page.tsx`)
  - Pending requests: platform name, requested documents, approve/deny buttons
  - History: past shares with platform, documents, timestamp, revoke option
  - Permissions: which platforms have active access

### 3.2 Partner SDK

#### Tasks

- [ ] Create Python SDK (`sdk/python/prdtool/`)
  - `PRDToolClient` class: init with API key, request documents,
    poll for approval, download package
  - Package as `prdtool` on PyPI

- [ ] Create JavaScript SDK (`sdk/js/`)
  - `PRDToolClient` class: same interface as Python
  - Package as `@prdtool/sdk` on npm

- [ ] Write SDK documentation (`docs/SDK.md`)
  - Quick start for Python and JavaScript
  - Authentication flow
  - Request document packages
  - Handle approvals and denials
  - Webhook configuration for real-time notifications

### 3.3 Intelligence-Based Pricing Engine

#### Tasks

- [ ] Create `organizer/pricing.py` module
  - `PricingTier` enum: starter (1 context), focused (3), full_life (unlimited),
    family_team (unlimited + shared)
  - `ContextGate` class: given a user's tier and a file, determine if the file's
    domain context is unlocked
  - If context is locked: classify with basic rules (filename only, low confidence),
    do not extract content, do not build DNA, do not track relationships

- [ ] Wire context gating into `InboxProcessor._classify()`
  - Check user's tier before deep classification
  - Locked context: return classification with `status="locked"`,
    `upgrade_prompt="Unlock Finances context for full routing"`

- [ ] Add pricing/upgrade flow to dashboard
  - Settings page shows current tier and unlocked contexts
  - Locked contexts show count of unprocessed files waiting
  - "Upgrade" button with tier comparison

### Phase 3 Success Criteria

- [ ] Platform can request documents via API, user approves in dashboard, documents
  delivered to platform callback within seconds
- [ ] Document packages for mortgage and tax filing are complete and correct
- [ ] Python and JavaScript SDKs published and functional
- [ ] Context gating works: free-tier user only gets deep classification in 1 domain
- [ ] Share history shows complete audit trail of all document sharing

---

## Technical Dependencies

| Dependency | Phase | Purpose |
|-----------|-------|---------|
| `mcp` (Python SDK) | Phase 1 | MCP server for AI assistant integration |
| `pdftotext` (system) | Phase 1 | PDF text extraction (already available) |
| `google-api-python-client` | Phase 2 | Google Drive connector |
| `dropbox` | Phase 2 | Dropbox connector |
| `msgraph-sdk` | Phase 2 | OneDrive connector |
| `docker` | Phase 2 | Container packaging |
| `n8n` | Phase 2 | Workflow orchestration (optional) |

## Non-Negotiable Principles

1. **Never delete files.** Move, rename, quarantine -- never delete.
2. **Privacy first.** Files stay in user's storage. Central system stores only metadata.
3. **Corrections make it smarter.** Every user correction permanently improves routing.
4. **Explainable decisions.** Every routing shows matched keywords and confidence score.
5. **PRD is source of truth.** No orphan code -- every change maps to a task above.
