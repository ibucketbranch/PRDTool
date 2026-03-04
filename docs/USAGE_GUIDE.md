# Unified Document Management System - Usage Guide

## Overview

This system provides intelligent document management with dual modes:
- **Conversation Mode**: Deep analysis of iMessage conversation PDFs
- **Document Mode**: General PDF organization with AI categorization

## Installation

```bash
# Run the setup script
./setup.sh

# OR manually:
source venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="your_key_here"
supabase start
```

## Command Reference

### 1. Process Documents

#### Single File
```bash
# Auto-detect mode (conversation vs document)
python unified_document_manager.py process document.pdf

# Force conversation mode
python unified_document_manager.py process imessage_export.pdf --mode conversation

# Force document mode  
python unified_document_manager.py process receipt.pdf --mode document
```

#### Directory (Batch Processing)
```bash
# Process all PDFs in a directory (recursive by default)
python unified_document_manager.py process ~/Documents/Personal --directory

# Non-recursive (current directory only)
python unified_document_manager.py process ~/Downloads --directory --recursive=false
```

### 2. Search Documents

#### Natural Language Search
```bash
# General search
python unified_document_manager.py search "find my registration"

# Specific search with entities
python unified_document_manager.py search "find my auto registration for my 2024 tesla"

# Search with date
python unified_document_manager.py search "tax documents from 2023"

# Search by organization
python unified_document_manager.py search "invoice from Apple"
```

#### Category Search
```bash
# Search by specific category
python unified_document_manager.py search --category vehicle_registration

# Available categories:
# - vehicle_registration
# - vehicle_insurance
# - vehicle_maintenance
# - tax_document
# - invoice
# - receipt
# - contract
# - medical_record
# - insurance_policy
# - bank_statement
# - utility_bill
# - property_document
# - education
# - employment
# - correspondence
```

#### Search Options
```bash
# Limit results
python unified_document_manager.py search "insurance" --limit 5

# Default limit is 10
```

### 3. Analyze Folder Organization

```bash
# Analyze all folders containing documents
python unified_document_manager.py analyze-folders
```

This will:
- Calculate organization score for each folder
- Identify misplaced documents
- Suggest better folder hierarchies
- Generate AI-powered restructuring plan
- Save analysis to database

### 4. View Statistics

```bash
python unified_document_manager.py stats
```

Shows:
- Total documents processed
- Conversation vs document mode counts
- Total folders analyzed
- Average organization score
- Top document categories

### 5. Help

```bash
# General help
python unified_document_manager.py --help

# Command-specific help
python unified_document_manager.py process --help
python unified_document_manager.py search --help
```

## Individual Module Usage

### Document Processor (Standalone)
```bash
python document_processor.py /path/to/document.pdf
```

Features:
- Extracts text and metadata from PDF
- Detects document mode (conversation vs document)
- Generates AI summary and categorization
- Extracts entities (dates, vehicles, amounts, etc.)
- Analyzes file location appropriateness
- Stores in database

### Search Engine (Standalone)
```bash
python search_engine.py "find my 2024 tesla registration"
```

Features:
- Natural language query processing
- Entity extraction from query
- Semantic matching
- Relevance scoring
- Interactive result selection

### Folder Analyzer (Standalone)
```bash
python folder_analyzer.py
```

Features:
- Analyzes all folders in database
- Calculates organization scores
- Identifies misplaced documents
- Generates restructuring suggestions
- AI-powered recommendations

## Examples

### Example 1: First-Time Setup
```bash
# 1. Setup
./setup.sh

# 2. Process your documents folder
python unified_document_manager.py process ~/Documents --directory

# 3. View stats
python unified_document_manager.py stats

# 4. Analyze organization
python unified_document_manager.py analyze-folders
```

### Example 2: Daily Usage
```bash
# Process new document
python unified_document_manager.py process ~/Downloads/new_invoice.pdf

# Search for it
python unified_document_manager.py search "invoice"
```

### Example 3: Conversation Analysis
```bash
# Export iMessage conversation to PDF (use macOS Notes or screenshot)
# Then process it
python unified_document_manager.py process conversation_export.pdf --mode conversation

# This will run deep conversation analysis:
# - Participant identification
# - Sentiment analysis  
# - Relationship dynamics
# - Survival probability assessment
```

### Example 4: Organization Audit
```bash
# 1. Process everything
python unified_document_manager.py process ~/Documents --directory

# 2. Analyze organization
python unified_document_manager.py analyze-folders

# 3. Review suggestions in output or database
# View in Supabase Studio: http://127.0.0.1:54423
# Table: reorganization_suggestions
```

### Example 5: Advanced Search
```bash
# Search with multiple entities
python unified_document_manager.py search "2024 tesla model 3 registration dmv"

# The system will extract:
# - Year: 2024
# - Vehicle: Tesla Model 3  
# - Document type: registration
# - Organization: DMV
#
# And rank results by relevance
```

## Database Access

### Supabase Studio
Access the web interface: http://127.0.0.1:54423

### Main Tables
- `documents` - All processed documents
- `document_locations` - File location tracking
- `categories` - Document categories
- `folder_analysis` - Organization analysis results
- `search_queries` - Search history
- `reorganization_suggestions` - AI suggestions

### Useful Queries

#### View all documents
```sql
SELECT file_name, ai_category, ai_summary, current_path 
FROM documents 
ORDER BY created_at DESC;
```

#### View poorly organized folders
```sql
SELECT folder_path, organization_score, document_count, primary_categories
FROM folder_analysis
WHERE organization_score < 60
ORDER BY organization_score ASC;
```

#### View search history
```sql
SELECT query_text, results_count, created_at
FROM search_queries
ORDER BY created_at DESC
LIMIT 20;
```

#### View top suggestions
```sql
SELECT suggestion_type, priority, current, suggested, reason
FROM reorganization_suggestions
WHERE status = 'pending'
ORDER BY priority DESC
LIMIT 10;
```

## Troubleshooting

### Supabase not running
```bash
supabase start
```

### Database not initialized
```bash
supabase db reset
```

### Groq API errors
```bash
# Check API key
echo $GROQ_API_KEY

# Set API key
export GROQ_API_KEY="your_key_here"

# Or add to ~/.zshrc or ~/.bashrc
echo 'export GROQ_API_KEY="your_key_here"' >> ~/.zshrc
source ~/.zshrc
```

### Dependencies missing
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Migration errors
```bash
# Reset database
supabase db reset

# Or manually apply migrations
supabase db push
```

## Configuration

### Default Settings
- **Supabase URL**: http://127.0.0.1:54321
- **Supabase Studio**: http://127.0.0.1:54423
- **Database Port**: 54422
- **API Port**: 54421
- **Groq Model**: llama-3.3-70b-versatile

### Customization
Edit the connection strings in each script to use different settings:
- `document_processor.py`
- `search_engine.py`
- `folder_analyzer.py`
- `unified_document_manager.py`

## Best Practices

### Document Organization
1. **Process regularly**: Add new documents as they arrive
2. **Review suggestions**: Check folder analysis recommendations monthly
3. **Use consistent naming**: Name files descriptively
4. **Leverage categories**: Let AI categorize, but review periodically

### Search
1. **Be specific**: Include years, brands, document types
2. **Use natural language**: "find my..." works well
3. **Try different queries**: Rephrase if results aren't good
4. **Review top matches**: System learns from your selections

### Conversation Analysis
1. **Clean exports**: Ensure iMessage exports are clean PDFs
2. **Review results**: AI analysis is insightful but not perfect
3. **Privacy**: Keep conversation data secure

## Performance Notes

- **Large batches**: Processing 100+ files can take time
- **Search speed**: Searches are fast (<1 second typically)
- **Folder analysis**: Analyzing 50+ folders takes ~30 seconds
- **AI calls**: Groq responses are typically <2 seconds

## Future Enhancements

- Vector embeddings for better semantic search
- OCR for scanned documents
- Web interface
- Automatic file watching
- Cloud storage integration
- Export/import functionality

## Support

For issues or questions:
1. Check this guide
2. Review error messages
3. Check Supabase logs: `supabase status`
4. Check database in Studio: http://127.0.0.1:54423
