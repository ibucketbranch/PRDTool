# ThePDFConversation

> Migration notice (2026-02-21): active requirements and policy source-of-truth
> now live in `PRDTool`. This `docs/` folder remains available for historical
> collateral, implementation notes, and domain-specific references.

A dual-mode intelligent document management system ("The PDF Conversation") that handles both **conversation analysis** (iMessage transcripts) and **general document organization** with AI-powered categorization, context bins, and natural language search.

## Features

### 🗨️ Conversation Mode
- Deep analysis of iMessage conversation PDFs
- Participant identification and sentiment analysis
- Relationship dynamics assessment
- Timeline and pattern detection
- Therapist-style insights using Groq AI

### 📄 Document Mode
- Intelligent PDF scanning and cataloging
- AI-powered categorization and summarization
- **Context Bin Organization** (Personal Bin, Work Bin, Family Bin, etc.)
- **Hierarchical Categories** (parent-child relationships)
- Entity extraction (dates, amounts, vehicles, people, organizations)
- Metadata extraction (title, author, keywords)
- Content-based duplicate detection (SHA256 hashing)

### 🔍 Natural Language Search
- Search using plain English: *"find my 2024 tesla registration in Personal Bin"*
- **Filter by context bin**: Search within specific organizational bins
- Entity extraction from queries
- Semantic matching and relevance scoring
- Search by category hierarchy or tags
- Query learning from user behavior

### 📁 Folder Organization Analysis
- Analyze folder structure and organization quality
- Identify misplaced documents
- Suggest better folder hierarchies
- Auto-categorization recommendations
- AI-powered restructuring plans
- **Import existing folder structures** from iCloud, Google Drive, etc.

## New: Context Bins & Hierarchical Categories

### Context Bins
Organize documents by **life domain** rather than document type:
- **Personal Bin** - Personal documents and records
- **Work Bin** - Professional documents
- **Family Bin** - Family member documents
- **Finances Bin** - Financial records
- **Legal Bin** - Legal documents
- **Projects Bin** - Project-related files
- *Custom bins supported*

### Hierarchical Categories
Categories now have parent-child relationships:

```
Financial
  ├─ Tax Documents
  ├─ Bank Statements
  ├─ Invoices
  └─ Receipts

Vehicles
  ├─ Registration
  ├─ Insurance
  └─ Maintenance

Medical
  ├─ Medical Records
  ├─ Insurance
  └─ Prescriptions
```

## Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up Supabase (local):**
```bash
# Install Supabase CLI if needed
npm install -g supabase

# Start local Supabase instance
supabase start

# Run migrations
supabase db reset
```

3. **Configure Groq API:**
```bash
export GROQ_API_KEY="your_groq_api_key_here"
```

## Quick Start

### Import Your Existing Folders

**Step 1: Dry run to preview what will be imported**
```bash
python folder_structure_importer.py ~/Library/Mobile\ Documents/com~apple~CloudDocs --dry-run
```

**Step 2: Import all PDFs from iCloud Drive**
```bash
python folder_structure_importer.py ~/Library/Mobile\ Documents/com~apple~CloudDocs
```

**Step 3: View statistics by bin**
```bash
python folder_structure_importer.py --stats
```

### Process a Single PDF
```bash
# Auto-detect mode
python unified_document_manager.py process document.pdf

# Force conversation mode
python unified_document_manager.py process conversation.pdf --mode conversation

# Force document mode
python unified_document_manager.py process invoice.pdf --mode document
```

### Process a Directory
```bash
# Process all PDFs in directory (recursive)
python unified_document_manager.py process /path/to/pdfs --directory

# Non-recursive
python unified_document_manager.py process /path/to/pdfs --directory --recursive=false
```

### Search Documents
```bash
# Natural language search
python unified_document_manager.py search "find my auto registration for my 2024 tesla"

# Search within a specific bin
python unified_document_manager.py search "find insurance documents in Personal Bin"

# Search by category
python unified_document_manager.py search --category vehicle_registration

# Limit results
python unified_document_manager.py search "tax documents 2023" --limit 5
```

### Analyze Folder Organization
```bash
python unified_document_manager.py analyze-folders
```

### View Statistics
```bash
python unified_document_manager.py stats
```

## Individual Module Usage

### Document Processor
```bash
python document_processor.py /path/to/document.pdf
```

### Search Engine
```bash
python search_engine.py "find my insurance policy"
```

### Folder Analyzer
```bash
python folder_analyzer.py
```

## Database Schema

The system uses Supabase (PostgreSQL) with the following main tables:

- **documents** - Main document metadata and content **(NEW: context_bin field)**
- **document_locations** - Track file locations (primary, backups, duplicates)
- **categories** - Document category taxonomy **(NEW: parent_category_id for hierarchy)**
- **document_categories** - Document-to-category mapping
- **context_bins** - **(NEW)** Available context bins configuration
- **folder_analysis** - Folder organization analysis results
- **search_queries** - Search history for learning
- **reorganization_suggestions** - AI-generated organization suggestions

For conversation mode:
- **participants** - Conversation participants
- **messages** - Individual messages
- **message_sentiment** - Sentiment analysis
- **relationship_analysis** - Relationship insights

### New Views
- **category_hierarchy** - Full category tree with paths
- **documents_with_context** - Documents with bin and category hierarchy
- **bin_statistics** - Statistics grouped by context bin

## Architecture

```
unified_document_manager.py (Main Entry Point)
├── document_processor.py (PDF Processing)
│   ├── Content extraction
│   ├── Mode detection (conversation vs document)
│   ├── **Context bin detection**
│   ├── Entity extraction
│   ├── AI categorization (Groq)
│   └── Database storage
│
├── search_engine.py (Natural Language Search)
│   ├── Query entity extraction
│   ├── **Context bin filtering**
│   ├── Semantic search
│   ├── Relevance scoring
│   └── Query logging
│
├── folder_analyzer.py (Organization Analysis)
│   ├── Folder structure analysis
│   ├── Organization scoring
│   ├── Misplaced document detection
│   └── AI restructuring recommendations
│
├── **folder_structure_importer.py** (Import Existing Folders)
│   ├── Scan iCloud/local folders
│   ├── Detect bins and categories
│   ├── Batch processing
│   └── Progress reporting
│
├── parse_pdf.py (Conversation Parser)
│   └── iMessage conversation extraction
│
└── groq_analyze.py (Conversation Analysis)
    └── Relationship dynamics analysis
```

## Configuration

Default configuration uses local Supabase:
- **URL:** `http://127.0.0.1:54321`
- **API Port:** `54421`
- **DB Port:** `54422`
- **Studio:** `http://127.0.0.1:54423`

## Examples

### Example 1: Import Your Existing iCloud Documents
```bash
# Preview what will be imported
python folder_structure_importer.py ~/Library/Mobile\ Documents/com~apple~CloudDocs --dry-run

# Import everything
python folder_structure_importer.py ~/Library/Mobile\ Documents/com~apple~CloudDocs

# Import just Personal Bin
python folder_structure_importer.py ~/Library/Mobile\ Documents/com~apple~CloudDocs/Personal\ Bin

# View statistics
python folder_structure_importer.py --stats
```

### Example 2: Process and Search
```bash
# Process a vehicle registration
python unified_document_manager.py process tesla_registration_2024.pdf

# Search for it
python unified_document_manager.py search "tesla registration"
```

### Example 2: Batch Process and Analyze
```bash
# Process all documents
python unified_document_manager.py process ~/Documents/Personal --directory

# Analyze organization
python unified_document_manager.py analyze-folders

# View stats
python unified_document_manager.py stats
```

### Example 3: Conversation Analysis
```bash
# Process an iMessage conversation export
python unified_document_manager.py process conversation_export.pdf --mode conversation
```

## API Integration

All modules can be used programmatically:

```python
from unified_document_manager import UnifiedDocumentManager

manager = UnifiedDocumentManager()

# Process file
result = manager.process_file('document.pdf')

# Search
results = manager.search("find my registration", limit=5)

# Analyze folders
analysis = manager.analyze_folders()

# Get stats
stats = manager.get_statistics()
```

## Roadmap

- [ ] Vector embeddings for semantic search (OpenAI/local models)
- [ ] OCR support for scanned PDFs
- [ ] Web interface
- [ ] Automatic file watching and processing
- [ ] Cloud storage integration (Google Drive, Dropbox)
- [ ] Advanced conversation analytics dashboard
- [ ] Multi-user support with access control
- [ ] Export/import functionality
- [ ] Mobile app

## Contributing

This is a personal project but suggestions and improvements are welcome!

## License

MIT License

## Support

For issues or questions, please create an issue in the repository.

---

**Built with:**
- Python 3.13+
- Supabase (PostgreSQL)
- Groq AI (Llama 3.3 70B)
- PyPDF2
