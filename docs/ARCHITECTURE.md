# FileRoomba Architecture

> Technical architecture for the FileRoomba document intelligence platform.
> Covers current state (Phase 1) and target state (Phases 2-3).

## System Overview

### Current State (Phase 1 Baseline)

```
macOS launchd (hourly)
       |
       v
ContinuousOrganizerAgent
       |
       +-- ConsolidationPlanner (folder similarity scan)
       +-- InboxProcessor (rule-based file routing)
       +-- EmptyFolderEvaluator (empty folder policy)
       |
       v
iCloud Drive filesystem
  /In-Box/           <-- drop zone
  /VA/                <-- canonical bins
  /Finances Bin/
  /Work Bin/
  /Family Bin/
  /Legal Bin/
  /Personal Bin/
  /Archive/
  /Needs-Review/

Dashboard (Next.js on localhost:3000)
       |
       +-- 7 pages (agents, inbox, browse, statistics, search, empty-folders, health)
       +-- 18 API routes
       +-- Supabase client (document metadata queries)
```

### Phase 1 Target State

```
macOS launchd (hourly)
       |
       v
ContinuousOrganizerAgent
       |
       +-- ConsolidationPlanner
       +-- InboxProcessor
       |     +-- RoutingHistory (tracks every move)
       |     +-- LearnedOverrides (corrections improve routing)
       +-- FileDNA Registry (content fingerprint + metadata)
       +-- DedupEngine (exact + fuzzy duplicate detection)
       +-- EmptyFolderEvaluator
       |
       v
iCloud Drive filesystem (unchanged)

MCP Server (stdio, for Claude Desktop / Cursor)
       |
       +-- classify_file
       +-- scan_inbox
       +-- search_files
       +-- get_file_dna
       +-- find_duplicates
       +-- get_life_context
       +-- record_correction

Dashboard (Next.js on localhost:3000)
       |
       +-- Existing pages
       +-- /health (file health score, storage savings)
       +-- /inbox (enhanced: history, overrides, corrections)
       +-- /api/file-dna (DNA search, duplicates, stats)
       +-- /api/health-report (aggregated health metrics)
       +-- /api/dedup (duplicate groups, quarantine action)
       +-- /api/inbox-process/history (routing log)
       +-- /api/inbox-process/overrides (learned corrections)
       +-- /api/inbox-process/correct (submit correction)
```

### Phase 2 Target State (SaaS)

```
Docker Compose
  +-- agent (Python, multi-connector)
  |     +-- connectors/local.py
  |     +-- connectors/google_drive.py
  |     +-- connectors/dropbox.py
  |     +-- connectors/onedrive.py
  +-- dashboard (Next.js)
  |     +-- onboarding wizard
  |     +-- multi-tenant auth
  +-- n8n (workflow orchestration, optional)
  +-- caddy (reverse proxy, HTTPS)
  +-- supabase (hosted or self-hosted)
        +-- tenants, users
        +-- file_dna, routing_history
        +-- learned_overrides
```

### Phase 3 Target State (Conduit)

```
Phase 2 stack
  +-- Conduit API
  |     +-- POST /conduit/request (platform requests docs)
  |     +-- POST /conduit/approve (user approves)
  |     +-- GET  /conduit/history (audit trail)
  +-- Package Assembler
  |     +-- mortgage template
  |     +-- tax_filing template
  |     +-- va_claim template
  +-- Partner SDKs (Python, JavaScript)
  +-- Pricing Engine (context-gated intelligence)
```

---

## Module Map

### Python Engine (`organizer/`)

| Module | Responsibility | Dependencies |
|--------|---------------|-------------|
| `continuous_agent.py` | Orchestrates hourly cycles | All modules below |
| `inbox_processor.py` | Rule-based file classification + routing | `routing_history`, `learned_overrides` |
| `routing_history.py` | Persistent log of every file routing | None (new, Phase 1) |
| `learned_overrides.py` | User corrections that override default rules | None (new, Phase 1) |
| `file_dna.py` | Content fingerprint, metadata, provenance | None (new, Phase 1) |
| `dedup_engine.py` | Exact + fuzzy duplicate detection | `file_dna`, `fuzzy_matcher` (new, Phase 1) |
| `mcp_server.py` | MCP tool server for AI assistants | `inbox_processor`, `file_dna` (new, Phase 1) |
| `consolidation_planner.py` | Folder similarity detection + merge plans | `fuzzy_matcher`, `content_analyzer` |
| `fuzzy_matcher.py` | Name normalization + similarity scoring | None |
| `canonical_registry.py` | Persistent folder-to-path mappings | None |
| `category_mapper.py` | File-to-category classification | `canonical_registry` |
| `content_analyzer.py` | Document processing, folder analysis | `database_updater` |
| `smart_rules.py` | Domain-specific rules (VA, code projects) | None |
| `file_operations.py` | Atomic file moves, never-delete safety | None |
| `execution_logger.py` | Rollback-capable operation logging | None |
| `database_updater.py` | Supabase integration | `supabase` |
| `post_verification.py` | File accessibility verification | None |
| `cli.py` | Command-line interface | All modules |
| `launchd_agent.py` | macOS service management | None |

### Dashboard (`dashboard/`)

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/agents` | GET, POST | Agent status and controls |
| `/api/agents/audit` | GET | System-wide agent audit |
| `/api/inbox-process` | POST | Trigger inbox processing |
| `/api/inbox-process/history` | GET | Routing history log (new, Phase 1) |
| `/api/inbox-process/overrides` | GET, DELETE | Learned overrides management (new, Phase 1) |
| `/api/inbox-process/correct` | POST | Submit a routing correction (new, Phase 1) |
| `/api/file-dna` | GET | Search DNA records (new, Phase 1) |
| `/api/file-dna/duplicates` | GET | Duplicate file groups (new, Phase 1) |
| `/api/file-dna/stats` | GET | DNA coverage statistics (new, Phase 1) |
| `/api/dedup` | GET | Dedup report and quarantine (new, Phase 1) |
| `/api/health-report` | GET | Aggregated file health metrics (new, Phase 1) |
| `/api/statistics` | GET | File type and category statistics |
| `/api/documents` | GET | Document browser with filters |
| `/api/search` | GET | Natural language document search |
| `/api/empty-folders` | GET | Empty folder detection |
| `/api/empty-folders/assess` | POST | Folder correctness assessment |
| `/api/empty-folders/remove` | POST | Remove empty folders |
| `/api/orphaned` | GET | Orphaned file detection |
| `/api/orphaned/analyze` | POST | Analyze orphaned files |
| `/api/orphaned/move` | POST | Move orphaned files |
| `/api/missing` | GET | Missing file detection |
| `/api/missing/restore` | POST | Restore missing files |
| `/api/canonical-registry` | GET | Registry viewer |
| `/api/execution-logs` | GET | Execution log viewer |
| `/api/open-in-finder` | POST | Open path in macOS Finder |
| `/api/health` | GET | Dashboard health check |

---

## Data Models

### File DNA Record

```json
{
  "file_path": "/iCloud/VA/nexus_letter_smith.pdf",
  "filename": "nexus_letter_smith.pdf",
  "extension": ".pdf",
  "size_bytes": 245832,
  "sha256_hash": "a1b2c3d4e5f6...",
  "content_summary": "Nexus letter from Dr. Smith establishing service connection for PTSD...",
  "auto_tags": ["va", "nexus", "ptsd", "service connection", "2026", "dr smith"],
  "origin": "inbox",
  "first_seen_at": "2026-02-22T16:06:00",
  "last_seen_at": "2026-02-22T16:06:00",
  "routed_to": "VA",
  "related_files": [
    "/iCloud/VA/08_Evidence_Documents/dbq_ptsd.pdf",
    "/iCloud/VA/buddy_statement_jones.pdf"
  ],
  "duplicate_of": null
}
```

### Routing History Record

```json
{
  "filename": "VA214138_TDIU_NeuropsychEvidence_Valderrama.docx",
  "source_path": "/iCloud/In-Box/VA214138_TDIU_NeuropsychEvidence_Valderrama.docx",
  "destination_bin": "VA",
  "destination_path": "/iCloud/VA/VA214138_TDIU_NeuropsychEvidence_Valderrama.docx",
  "confidence": 0.90,
  "matched_keywords": ["tdiu"],
  "routed_at": "2026-02-23T06:45:12",
  "status": "executed"
}
```

### Learned Override Record

```json
{
  "pattern": "neuropsych",
  "correct_bin": "VA/08_Evidence_Documents",
  "source": "user_correction",
  "created_at": "2026-02-23T07:00:00",
  "hit_count": 0
}
```

### Duplicate Group

```json
{
  "sha256_hash": "a1b2c3d4e5f6...",
  "canonical_path": "/iCloud/VA/nexus_letter.pdf",
  "duplicates": [
    "/iCloud/Downloads/nexus_letter.pdf",
    "/iCloud/Documents/nexus_letter (1).pdf"
  ],
  "total_wasted_bytes": 491664,
  "first_seen_at": "2026-02-20T10:00:00"
}
```

### Health Report

```json
{
  "total_files_tracked": 4847,
  "duplicates_found": 1203,
  "wasted_storage_bytes": 50331648000,
  "wasted_storage_gb": 47.2,
  "storage_saved_dollars_per_month": 3.42,
  "files_routed_this_month": 89,
  "corrections_this_month": 3,
  "health_score": 87,
  "inbox_pending": 0,
  "last_cycle_at": "2026-02-23T06:45:12",
  "agent_status": "running"
}
```

---

## MCP Server Specification

### Server Identity

- **Name**: `fileroomba`
- **Transport**: stdio
- **Config location**: `.organizer/agent_config.json`

### Tools

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `classify_file` | `{ filepath, content_hint? }` | `{ destination_bin, confidence, matched_keywords }` | Classify a single file |
| `scan_inbox` | none | `{ total_files, routed, unmatched, files[] }` | Scan In-Box for routing proposals |
| `search_files` | `{ query }` | `{ results: [{ filename, path, tags, confidence }] }` | Search DNA registry by keyword |
| `get_file_dna` | `{ filepath }` | Full DNA record | Get provenance for a file |
| `find_duplicates` | `{ filepath? }` | `{ groups: [{ hash, files[], wasted_bytes }] }` | Find duplicate files |
| `get_life_context` | `{ domain }` | `{ file_count, recent[], key_entities[] }` | Structured summary of a life domain |
| `record_correction` | `{ filename, wrong_bin, correct_bin }` | `{ override_created }` | Record a routing correction |

### Claude Desktop Configuration

To connect Claude Desktop to the FileRoomba MCP server, add to
`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fileroomba": {
      "command": "python3",
      "args": ["-m", "organizer", "--mcp-server"],
      "cwd": "/Users/michaelvalderrama/Websites/PRDTool"
    }
  }
}
```

---

## Configuration Files

### Agent Config (`.organizer/agent_config.json`)

Current fields plus Phase 1 additions:

```json
{
  "base_path": "/Users/.../com~apple~CloudDocs",
  "interval_seconds": 3600,
  "auto_execute": true,
  "min_auto_confidence": 0.95,
  "inbox_enabled": true,
  "inbox_folder_name": "In-Box",
  "inbox_min_confidence": 0.85,
  "dedup_enabled": true,
  "dna_tracking_enabled": true,
  "learning_enabled": true,
  "canonical_registry_file": ".../.organizer/canonical_registry.json",
  "root_taxonomy_file": ".../.organizer/ROOT_TAXONOMY.json",
  "routing_history_file": ".organizer/agent/routing_history.json",
  "learned_overrides_file": ".organizer/agent/learned_overrides.json",
  "file_dna_file": ".organizer/agent/file_dna.json"
}
```

### Taxonomy (`ROOT_TAXONOMY.json`)

Defines the canonical root categories and routing rules. Already exists with
8 roots: Family Bin, Finances Bin, Legal Bin, Personal Bin, Work Bin, VA,
Archive, Needs-Review.

### Canonical Registry (`canonical_registry.json`)

Maps 129 known folder names to their canonical Bin paths. Used by the inbox
processor as supplemental routing rules and by the consolidation planner for
folder merging.

---

## Security Model

### What is stored centrally (Supabase, Phase 2+)

- User accounts and auth tokens
- Tenant configuration (vertical, branding)
- File DNA metadata (paths, hashes, tags -- NOT file contents)
- Routing history
- Learned overrides
- Health scores and analytics

### What is NEVER stored centrally

- Actual file contents (PDFs, documents, images)
- File binary data
- User passwords for external services
- Bank credentials or financial data
- Medical records or PHI
- Raw extracted text beyond 500-char summaries

### Phase 1 (local only)

All data stored in JSON files under `.organizer/agent/`. Nothing leaves the
machine. Zero network calls except optional Supabase queries for document
metadata (existing feature).

### Phase 2+ (SaaS)

Files remain in user's cloud storage (Google Drive, Dropbox, etc). The agent
reads files via OAuth-scoped API access. Metadata syncs to Supabase. If the
Supabase database is compromised, the attacker gets filenames, tags, and hashes
-- not the actual documents.

### Conduit (Phase 3)

Documents flow directly from user's storage to the requesting platform via a
time-limited, signed URL. The conduit server facilitates the handshake but
never holds the file. The URL expires after delivery. Complete audit trail
maintained in routing history.

---

## Deployment Topology

### Phase 1: Local Only

```
User's Mac
  +-- launchd service (com.prdtool.organizer.agent)
  |     runs: python3 -m organizer --agent-forever
  +-- Dashboard (npm run dev on localhost:3000)
  +-- MCP Server (python3 -m organizer --mcp-server, stdio)
  +-- .organizer/agent/ (JSON state files)
  +-- iCloud Drive (the organized filesystem)
```

### Phase 2: Docker Appliance

```
Docker Host (user's server or cloud VM)
  +-- docker-compose.yml
  |
  +-- agent container (Python)
  |     connects to: Google Drive API, Dropbox API, OneDrive API
  |
  +-- dashboard container (Next.js)
  |     serves: https://files.example.com
  |
  +-- n8n container (optional)
  |     runs: workflow templates
  |
  +-- caddy container (reverse proxy)
  |     terminates: HTTPS
  |
  +-- Supabase (hosted at supabase.co or self-hosted)
        stores: metadata only
```

### Phase 3: Platform API

```
Phase 2 stack
  +-- Conduit API (additional endpoints on dashboard)
  +-- Webhook receiver (platform callbacks)
  +-- SDK clients (Python, JavaScript)
        used by: Rocket, TurboTax, etc.
```

---

## Test Strategy

### Unit Tests (`tests/`)

| Test File | Module Under Test | Key Scenarios |
|-----------|------------------|---------------|
| `test_routing_history.py` | `routing_history.py` | Record, query, FIFO eviction, correction detection |
| `test_learned_overrides.py` | `learned_overrides.py` | Add override, match filename, priority over defaults |
| `test_file_dna.py` | `file_dna.py` | Hash computation, tag extraction, duplicate detection |
| `test_dedup_engine.py` | `dedup_engine.py` | Exact dedup, fuzzy dedup, quarantine |
| `test_mcp_server.py` | `mcp_server.py` | All tool responses |
| `test_inbox_processor.py` | `inbox_processor.py` | Existing + override integration |

### Dashboard Tests (`dashboard/__tests__/`)

| Test File | Endpoint | Key Scenarios |
|-----------|----------|---------------|
| `health-report-api.test.ts` | `/api/health-report` | Score calculation, dollar estimates |
| `inbox-history-api.test.ts` | `/api/inbox-process/history` | Pagination, filtering |
| `inbox-overrides-api.test.ts` | `/api/inbox-process/overrides` | CRUD operations |
| `file-dna-api.test.ts` | `/api/file-dna` | Search, duplicates, stats |
| `dedup-api.test.ts` | `/api/dedup` | Report, quarantine action |

### Integration Tests

- Full agent cycle with inbox processing, DNA tracking, and dedup
- MCP server responds correctly to Claude Desktop requests
- Dashboard builds and all API routes return valid responses
