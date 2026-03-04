import os
import json
import sys
from pathlib import Path

# Add the project root to sys.path so we can import document_processor
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from document_processor import DocumentProcessor

def main():
    analysis_file = '/tmp/gdrive_deep_analysis.json'
    if not os.path.exists(analysis_file):
        print("Error: Analysis file not found. Run deep comparison first.")
        return

    with open(analysis_file, 'r') as f:
        data = json.load(f)

    new_files = data.get('truly_new', [])
    if not new_files:
        print("No new files found to process.")
        return

    print(f"--- Ingesting {len(new_files)} new Google Drive files ---")
    
    processor = DocumentProcessor()
    
    processed_count = 0
    error_count = 0
    total = len(new_files)

    for i, path in enumerate(new_files, 1):
        print(f"\n[{i}/{total}] Processing: {os.path.basename(path)}")
        try:
            # process_document handles text extraction, AI analysis, and DB saving
            # We set skip_if_exists=False because we already know these are new (or we want to re-analyze)
            result = processor.process_document(path, skip_if_exists=False)
            
            if result.get('status') == 'success':
                print(f"✅ SUCCESS: {result.get('category')}")
                processed_count += 1
            else:
                print(f"⚠️  WARNING: Status is {result.get('status')}")
                error_count += 1
        except Exception as e:
            print(f"❌ ERROR processing {path}: {e}")
            error_count += 1

    print("\n" + "="*80)
    print("INGESTION SUMMARY")
    print("="*80)
    print(f"Total files:     {total}")
    print(f"Successfully processed: {processed_count}")
    print(f"Errors/Skipped:         {error_count}")
    print("="*80)
    print("\nNext step: Run path planning and move scripts.")

if __name__ == "__main__":
    main()
