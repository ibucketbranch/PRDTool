# Data Preservation - What Gets Preserved vs Updated

## ✅ PRESERVED (Never Overwritten)

These fields are **NEVER** changed when reprocessing:

1. **`id`** - Unique document ID (never changes)
2. **`file_hash`** - SHA256 hash (same file = same hash)
3. **`created_at`** - When document was first added to database (preserved)
4. **Original Path** - Stored in `document_locations` table with `location_type='original'`

## 📝 UPDATED (Improved/Refreshed)

These fields are **UPDATED** with better data when reprocessing:

### AI Analysis (Improved Categorization)
- `ai_category` - New intelligent category
- `ai_summary` - New summary
- `ai_subcategories` - New subcategories  
- `confidence_score` - New confidence level

### Content (Re-extracted)
- `extracted_text` - Re-extracted (may be better with new extraction)
- `text_preview` - Updated preview
- `entities` - Re-extracted entities (may find more)

### Location (Current State)
- `current_path` - **Updated to where file is NOW**
- `folder_hierarchy` - Updated to current folder structure
- `last_verified_at` - Updated to current time

### Metadata (Refreshed)
- `file_size_bytes` - Updated (in case file changed)
- `pdf_title`, `pdf_author`, `pdf_subject` - Updated from PDF metadata
- `page_count` - Updated

## 📍 Path History Tracking

**Original path is NEVER lost!**

When a file's path changes:
1. **Old path** is saved to `document_locations` table with `location_type='previous'`
2. **Current path** is updated in `current_path` field
3. **Original path** (first time we saw it) is in `document_locations` with `location_type='original'`

### Example:

```
First processed:
  current_path: "/Users/.../Downloads/resume.pdf"
  document_locations: {location_type: 'original', path: "/Users/.../Downloads/resume.pdf"}

File moved, reprocessed:
  current_path: "/Users/.../Documents/Resumes/resume.pdf"  ← Updated
  document_locations: 
    - {location_type: 'original', path: "/Users/.../Downloads/resume.pdf"}  ← Preserved
    - {location_type: 'previous', path: "/Users/.../Downloads/resume.pdf"}  ← Old path saved
```

## Query Original Path

To find the original path of any document:

```sql
SELECT 
  d.id,
  d.file_name,
  d.current_path AS current_location,
  dl.location_path AS original_path
FROM documents d
LEFT JOIN document_locations dl 
  ON d.id = dl.document_id 
  AND dl.location_type = 'original'
WHERE d.id = 'your-document-id';
```

## What This Means

✅ **Your original paths are safe** - stored in `document_locations` table  
✅ **Current location is tracked** - `current_path` shows where file is now  
✅ **History is preserved** - all previous locations are recorded  
✅ **No data loss** - original information is never deleted
