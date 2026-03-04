# PRD: Content-Aware Folder Consolidation

## Problem Statement
The current organizer tool only matches folder **names** (fuzzy matching), which is too simplistic. It would incorrectly consolidate:
- "Desktop" (Microsoft files) + "Desktop 2" (macOS files) → **BAD** (different contexts)
- "Resume" (MY resumes) + "Resume" (OTHER people's resumes) → **BAD** (different content)
- "Tax 2002" + "Tax 2025" → **BAD** (different timeframes)
- Folders with similar names but completely different document types

## Solution: Intelligent Decision Engine
**The organizer's job: Take all existing information and make smart decisions about where folders should live.**

The system already has:
- ✅ File discovery and scanning (DocumentProcessor)
- ✅ Content extraction and AI analysis (stored in Supabase)
- ✅ Rich context: categories, entities, dates, paths, summaries

**The organizer's role:**
- Use all this existing information
- Apply intelligent rules (dates, categories, context, paths)
- **Make the decision**: Should these folders consolidate? Where should they go?
- **It's a DECISION ENGINE, not a file finder or analyzer**

## Integration Points

### 1. Document-First Approach (PRIMARY SOURCE OF TRUTH)
**The actual document files are the source of truth. The database is a helpful cache/index.**

- **Read actual files FIRST** - Scan folder structure, read file metadata, extract content
- **Use database as helpful cache/index:**
  - Query Supabase `documents` table to get existing AI analysis (if available)
  - Use `ai_category`, `ai_summary`, `entities`, `key_dates` as hints
  - **BUT**: Always verify against actual file content
  - **If database is stale or missing**: Re-analyze the actual document
- **Database fields to leverage (when available):**
  - `ai_category` - Primary category (e.g., "VA Claims", "Tax Document")
  - `ai_subcategories[]` - Additional categories
  - `ai_summary` - AI-generated summary of content
  - `entities` (JSONB) - Extracted entities: people, organizations, dates, amounts, vehicles
  - `key_dates[]` - Important dates found in document
  - `pdf_created_date`, `pdf_modified_date` - File metadata dates
  - `document_locations.original_path` - Original path history
- **Always verify**: If database says one thing but file content says another, trust the file
- **Re-analyze if needed**: If file is newer than database entry, or database is missing, analyze the actual document

### 2. Content Analysis Rules
- **Same AI category** → Can consolidate (e.g., both "VA Claims")
- **Same context bin** → Can consolidate (e.g., both "Personal Bin")
- **Same original path context** → Can consolidate (e.g., both from "Desktop")
- **Same temporal context** → Can consolidate (e.g., both from 2025)
- **Different content** → DON'T consolidate (e.g., "Resume" vs "Tax Documents")
- **Different dates/timeframes** → DON'T consolidate (e.g., ANY document from 2002 ≠ same type from 2025)
  - Tax documents: 2002 tax year ≠ 2025 tax year
  - VA Claims: 2002 claim ≠ 2025 claim
  - Resumes: 2002 resume ≠ 2025 resume
  - Contracts: 2002 contract ≠ 2025 contract
  - **Rule**: Documents from different timeframes (especially different years) are different contexts

### 3. Path Context Rules
- Check **original path** in database (`document_locations.original_path`)
- "Desktop" from Microsoft folder ≠ "Desktop" from macOS folder
- Preserve path context when consolidating

## Tasks

### Phase 1: Content Analyzer Module (Use Existing System)
- [ ] Create `organizer/content_analyzer.py`
- [ ] **Import and use existing `DocumentProcessor` class** (don't recreate file finding/analysis)
- [ ] Function: `analyze_folder_content(folder_path)` → **PRIMARY METHOD**
  - **Step 1**: Use `DocumentProcessor` to find files in folder (it already does this!)
  - **Step 2**: Query Supabase for existing analysis (all the rich context already collected)
  - **Step 3**: For files NOT in database: Use `DocumentProcessor.process_file()` (it already extracts content, runs AI)
  - **Step 4**: Extract from database/analysis:
    - `ai_category`, `ai_subcategories` - Already analyzed!
    - `entities` (JSONB) - Already extracted!
    - `key_dates[]` - Already found!
    - `pdf_created_date`, `pdf_modified_date` - Already stored!
    - `folder_hierarchy[]` - Already tracked!
    - `document_locations.original_path` - Already recorded!
  - **Step 5**: Return comprehensive analysis using existing data:
    - AI categories (from `ai_category` in database)
    - Context bins (from `folder_hierarchy` in database)
    - Original paths (from `document_locations` table)
    - Entity extraction (from `entities` JSONB in database)
    - **Temporal analysis**: Date ranges from `key_dates[]` and metadata dates
    - Year clusters (e.g., "2002-2003", "2024-2025")
- [ ] Function: `get_folder_metadata(folder_path)` → Query Supabase
  - Use Supabase client to query `documents` WHERE `current_path` LIKE folder_path
  - Join with `document_locations` for path history
  - Return all the rich context already collected by existing system
- [ ] Function: `should_consolidate_folders(folder1_path, folder2_path)` → Returns True/False with reasoning
  - Query database for all files in both folders (use existing analysis)
  - Compare AI categories from `ai_category` field
  - Compare date ranges from `key_dates[]` and metadata dates
  - Compare entities from `entities` JSONB
  - Compare original paths from `document_locations` table
  - **Use the expert system** - all the analysis is already done!

### Phase 2: Intelligent Decision Engine
- [ ] Update `consolidation_planner.py` to use `content_analyzer`
- [ ] **Decision logic: Use all existing information to make smart choices**
- [ ] For each potential consolidation, gather ALL context:
  1. Query database for all files in both folders
  2. Extract AI categories from `ai_category` field
  3. Extract date ranges from `key_dates[]` and metadata dates
  4. Extract entities from `entities` JSONB (people, organizations)
  5. Extract original paths from `document_locations` table
  6. Extract context bins from `folder_hierarchy` array
- [ ] **Apply decision rules:**
  1. ✅ Same AI category? (e.g., both "VA Claims")
  2. ✅ Same date range? (e.g., both 2024-2025, NOT 2002 vs 2025)
  3. ✅ Same context bin? (e.g., both "Personal Bin")
  4. ✅ Same entities? (e.g., same people, same organizations)
  5. ✅ Compatible original paths? (e.g., both from same source)
- [ ] **Make the decision**: Only consolidate if ALL rules pass
- [ ] **Decide where it should live**: Use category mappings + canonical registry
- [ ] Add clear reasoning to plan (why consolidate or not, where it goes)

### Phase 3: Integration with Existing Document Processor
- [ ] **Import `DocumentProcessor` class** - Don't recreate file finding/analysis!
- [ ] **Use existing Supabase connection** (from `document_processor.py`)
- [ ] **Query database for existing analysis** - All the info is already there:
  - `documents` table has: `ai_category`, `ai_summary`, `entities`, `key_dates`, etc.
  - `document_locations` table has: `original_path`, location history
  - All this was collected by the existing expert system!
- [ ] **For files NOT in database:**
  - Use `DocumentProcessor.process_file()` - it already does everything!
  - It finds files, extracts content, runs AI, stores in database
  - Don't recreate this - use the existing expert system
- [ ] **Leverage existing categorization** from `smart_consolidate_all_categories.py`
- [ ] **Use existing folder analysis** from `folder_analyzer.py` if available
- [ ] **The organizer is an expert USER of the existing system**, not a replacement

### Phase 4: Smart Rules Engine
- [ ] Implement rules from existing system:
  - MY vs OTHER people's documents (check names in files)
  - VA document patterns (exclude from general consolidation)
  - Code project indicators (skip entirely)
- [ ] Path context rules:
  - Microsoft Desktop ≠ macOS Desktop
  - Different source folders = different contexts
- [ ] Content similarity threshold (configurable)

### Phase 5: Enhanced CLI
- [ ] Add `--content-aware` flag (default: True)
- [ ] Add `--analyze-missing` flag (analyze folders not in Supabase)
- [ ] Add `--min-content-similarity` threshold (0.0-1.0)
- [ ] Show content analysis in plan output
- [ ] Show reasoning for each consolidation decision

### Phase 6: Safety & Verification
- [ ] Pre-execution: Show content analysis summary
- [ ] Warn if consolidating folders with different content types
- [ ] Require explicit confirmation for content-mismatch consolidations
- [ ] Log content analysis results to execution log

## Success Criteria
- ✅ **Makes smart decisions** using all existing information
- ✅ Consolidates "Resume" + "Resumes" + "Resume_Docs" (same content, same dates, same context)
- ✅ Does NOT consolidate "Desktop" (Microsoft) + "Desktop 2" (macOS) (different contexts)
- ✅ Does NOT consolidate "Resume" (MY) + "Resume" (OTHER) (different content/entities)
- ✅ Does NOT consolidate ANY documents from 2002 + same type from 2025 (different timeframes)
  - Tax 2002 ≠ Tax 2025
  - VA Claims 2002 ≠ VA Claims 2025
  - Resume 2002 ≠ Resume 2025
- ✅ **Uses existing Supabase analysis** (all the rich context already collected)
- ✅ **Makes intelligent decisions** based on:
  - AI categories from database
  - Date ranges from `key_dates[]` and metadata
  - Entities (people, organizations) from `entities` JSONB
  - Original paths from `document_locations`
  - Context bins from `folder_hierarchy`
- ✅ Shows clear reasoning for each decision (why consolidate or not)

## Example Output

```
Group 1: Resume-related (3 folders, 47 files)
  - /iCloud/Resume/           (12 files, AI: "Employment/Resumes", Context: "Personal Bin")
  - /iCloud/Resumes/          (8 files, AI: "Employment/Resumes", Context: "Personal Bin")
  - /iCloud/Resume_Docs/      (15 files, AI: "Employment/Resumes", Context: "Personal Bin")
  → ✅ CAN CONSOLIDATE: Same AI category, same context bin
  → Suggested canonical: Employment/Resumes/

Group 2: Desktop folders (2 folders, 156 files)
  - /iCloud/Desktop/           (89 files, AI: "Mixed", Context: "Microsoft Desktop")
  - /iCloud/Desktop 2/         (67 files, AI: "Mixed", Context: "macOS Desktop")
  → ❌ DO NOT CONSOLIDATE: Different path contexts (Microsoft vs macOS)
  → Keep separate: Desktop/ and Desktop 2/

Group 3: Tax Documents (2 folders, 34 files)
  - /iCloud/Tax 2002/           (18 files, AI: "Finances/Taxes", Dates: "2002-2003")
  - /iCloud/Tax 2025/           (16 files, AI: "Finances/Taxes", Dates: "2024-2025")
  → ❌ DO NOT CONSOLIDATE: Different timeframes (2002 vs 2025)
  → Keep separate: Tax 2002/ and Tax 2025/
```
