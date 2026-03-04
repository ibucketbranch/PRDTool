# PRD: Organizer Dashboard

## Problem Statement
Users need a visual interface to:
- See what types of files they have and how many
- Search for documents using natural language queries (e.g., "Show me a file that is a verizon bill from 2024?")
- View file locations and contextual information from the database
- Understand their document organization at a glance

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
- [ ] Create `dashboard/` directory in TheConversation
- [ ] Set up Next.js app with TypeScript
- [ ] Configure Supabase client connection
- [ ] Create API routes for database queries
- [ ] Test database connection and query data

### Phase 2: Statistics Dashboard
- [ ] Create statistics API endpoint:
  - Category counts
  - Date distribution (by year)
  - Context bin counts
- [ ] Build statistics UI component:
  - Category breakdown with counts
  - Date distribution chart
  - Context bin overview
- [ ] Add filtering (by category, date range)
- [ ] Make charts interactive (click to filter)

### Phase 3: Natural Language Search
- [ ] Create search API endpoint:
  - Parse natural language queries
  - Extract keywords: category, date, entity, organization
  - Build Supabase query with filters
- [ ] Build search UI:
  - Search input with example queries
  - Results list with file info
  - Clickable paths to open files
- [ ] Display search results:
  - File name
  - Full path (clickable)
  - AI category and summary
  - Key entities (people, organizations, dates)
  - Date information

### Phase 4: Document Browser
- [ ] Create document list API endpoint:
  - Get all documents with pagination
  - Support filtering and sorting
- [ ] Build document browser UI:
  - Table/list view with columns
  - Filters sidebar (category, date, context bin)
  - Sort controls
  - Pagination
- [ ] Add "Open in Finder" functionality (macOS)

### Phase 5: Empty Folders Detection & Management
- [ ] Create empty folders API endpoint:
  - `GET /api/empty-folders` - Find empty folders after consolidation
  - `GET /api/empty-folders/{folder}/history` - Get files that were moved from folder
  - `POST /api/empty-folders/{folder}/assess` - Assess if original folder location was correct
  - `POST /api/empty-folders/{folder}/restore` - Restore files to original folder
  - `POST /api/empty-folders/{folder}/remove` - Remove empty folder
- [ ] Implement folder assessment logic:
  - Check folder name vs AI categories of moved files
  - Check if folder location matches `folder_hierarchy` patterns
  - Check if folder name is in canonical registry
  - Determine: "Correct location" vs "Incorrect/duplicate"
- [ ] Query execution logs and `document_locations`:
  - Find folders that had files moved (check `location_type='previous'`)
  - Track which files came from which folders
  - Show file movement history
- [ ] Build empty folders UI:
  - Tab/section for "Empty Folders"
  - List with: folder path, original file count, files moved, assessment
  - "Restore Files" button (if folder was correct)
  - "Remove Folder" button (if folder was duplicate/incorrect)
  - "Keep Folder" option
  - Bulk selection and operations
- [ ] Integrate with existing systems:
  - Use execution logs to track file movements
  - Query `document_locations` for file history
  - Use `canonical_registry` to check folder names
  - Use category mapping to assess folder correctness

### Phase 6: Orphaned Files Detection & Restoration
- [ ] Create orphaned files API endpoint:
  - `GET /api/orphaned` - Find files on disk not in database
  - `GET /api/missing` - Find files in database with missing paths
  - `POST /api/orphaned/analyze` - Analyze orphaned file (add to DB)
  - `POST /api/orphaned/suggest-location` - Suggest location for orphaned file
  - `POST /api/orphaned/restore` - Move orphaned file to suggested/original location
  - `POST /api/missing/get-original` - Get original path from `document_locations` table
  - `POST /api/missing/restore` - Restore missing file to original location
  - `POST /api/missing/remove` - Remove missing file from DB
  - `POST /api/missing/update-path` - Update path for moved file
- [ ] Implement location suggestion logic:
  - Check if file hash exists in database → use `document_locations` for original path
  - For unknown files: Analyze file type, name, content to suggest location
  - Use existing category mapping from `organizer/category_mapper.py`
  - Check `folder_hierarchy` patterns for similar files
  - AI-powered suggestion using file metadata (e.g., ".plist" → Library/Preferences/)
- [ ] Build orphaned files UI:
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
- [ ] Integrate with existing systems:
  - Use `verify_file_accessible()` from `organizer/post_verification.py`
  - Use `scan_folder_for_files()` to find orphaned files
  - Use `DocumentProcessor` to analyze orphaned files
  - Query `document_locations` table for location history
  - Use file hash matching to find original locations

### Phase 7: Polish & UX
- [ ] Add loading states and error handling
- [ ] Responsive design (mobile-friendly)
- [ ] Add example queries in search placeholder
- [ ] Add tooltips and help text
- [ ] Optimize queries for performance

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
