#!/usr/bin/env python3
"""
File Processing Tracker
Logs all file processing attempts to Supabase database
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase not installed. Install with: pip install supabase")
    sys.exit(1)


class FileTracker:
    def __init__(self, supabase_url="http://127.0.0.1:54421", 
                 supabase_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"):
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def start_processing(self, file_path: str) -> str:
        """Log start of file processing."""
        file_path = str(file_path)
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        file_ext = Path(file_path).suffix.lower().lstrip('.')
        
        record = {
            'file_path': file_path,
            'file_name': file_name,
            'file_size_bytes': file_size,
            'file_type': file_ext,
            'status': 'processing',
            'started_at': datetime.now().isoformat()
        }
        
        result = self.supabase.table('file_processing_status').insert(record).execute()
        return result.data[0]['id']
    
    def update_status(self, record_id: str, status: str, **kwargs):
        """Update processing status."""
        update_data = {
            'status': status,
            'updated_at': datetime.now().isoformat()
        }
        
        # Add optional fields
        if 'error_message' in kwargs:
            update_data['error_message'] = kwargs['error_message']
        if 'notes' in kwargs:
            update_data['notes'] = kwargs['notes']
        if 'tags' in kwargs:
            update_data['tags'] = kwargs['tags']
        if 'messages_extracted' in kwargs:
            update_data['messages_extracted'] = kwargs['messages_extracted']
        if 'participants_found' in kwargs:
            update_data['participants_found'] = kwargs['participants_found']
        if 'pages_processed' in kwargs:
            update_data['pages_processed'] = kwargs['pages_processed']
        
        self.supabase.table('file_processing_status').update(update_data).eq('id', record_id).execute()
    
    def complete_processing(self, record_id: str, conversation_data: dict = None, duration_seconds: int = None):
        """Mark file processing as complete."""
        update_data = {
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        if duration_seconds:
            update_data['processing_duration_seconds'] = duration_seconds
        
        if conversation_data:
            update_data['messages_extracted'] = conversation_data.get('total_messages', 0)
            update_data['participants_found'] = len(conversation_data.get('participants', {}))
            
            date_range = conversation_data.get('date_range', {})
            if date_range.get('start'):
                update_data['date_range_start'] = date_range['start']
            if date_range.get('end'):
                update_data['date_range_end'] = date_range['end']
        
        self.supabase.table('file_processing_status').update(update_data).eq('id', record_id).execute()
    
    def mark_corrupted(self, record_id: str, error_msg: str, notes: str = None):
        """Mark file as corrupted."""
        self.update_status(
            record_id,
            'corrupted',
            error_message=error_msg,
            notes=notes,
            tags=['corrupted', 'needs_review'],
            completed_at=datetime.now().isoformat()
        )
    
    def mark_empty(self, record_id: str, notes: str = None):
        """Mark file as empty."""
        self.update_status(
            record_id,
            'empty',
            notes=notes or 'No content extracted',
            tags=['empty', 'needs_review'],
            completed_at=datetime.now().isoformat()
        )
    
    def mark_failed(self, record_id: str, error_msg: str, notes: str = None):
        """Mark file processing as failed."""
        self.update_status(
            record_id,
            'failed',
            error_message=error_msg,
            notes=notes,
            tags=['failed', 'needs_retry'],
            completed_at=datetime.now().isoformat()
        )
    
    def get_files_for_review(self):
        """Get all files needing review."""
        result = self.supabase.from_('files_needing_review').select('*').execute()
        return result.data
    
    def get_processing_summary(self):
        """Get processing status summary."""
        result = self.supabase.from_('processing_summary').select('*').execute()
        return result.data
    
    def increment_retry(self, record_id: str):
        """Increment retry count for a file."""
        # Get current retry count
        current = self.supabase.table('file_processing_status').select('retry_count').eq('id', record_id).execute()
        retry_count = (current.data[0].get('retry_count', 0) or 0) + 1
        
        self.supabase.table('file_processing_status').update({
            'retry_count': retry_count,
            'last_retry_at': datetime.now().isoformat(),
            'status': 'processing'
        }).eq('id', record_id).execute()


def main():
    """CLI for file tracker."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python file_tracker.py summary              - Show processing summary")
        print("  python file_tracker.py review               - List files needing review")
        print("  python file_tracker.py mark-corrupted <id>  - Mark file as corrupted")
        print("  python file_tracker.py mark-empty <id>      - Mark file as empty")
        sys.exit(1)
    
    tracker = FileTracker()
    command = sys.argv[1]
    
    if command == 'summary':
        summary = tracker.get_processing_summary()
        print("\n📊 PROCESSING SUMMARY")
        print("=" * 70)
        for row in summary:
            print(f"\nStatus: {row['status'].upper()}")
            print(f"  Files: {row['file_count']}")
            print(f"  Total Size: {row['total_size_bytes'] / (1024*1024):.1f} MB")
            print(f"  Total Messages: {row['total_messages'] or 0}")
            print(f"  Avg Duration: {row['avg_duration_seconds'] or 0:.1f}s")
            print(f"  Last Processed: {row['last_processed'] or 'N/A'}")
    
    elif command == 'review':
        files = tracker.get_files_for_review()
        print(f"\n⚠️  FILES NEEDING REVIEW ({len(files)})")
        print("=" * 70)
        for f in files:
            print(f"\n📄 {f['file_name']}")
            print(f"   Status: {f['status'].upper()}")
            print(f"   Path: {f['file_path']}")
            if f['error_message']:
                print(f"   Error: {f['error_message']}")
            if f['notes']:
                print(f"   Notes: {f['notes']}")
            print(f"   Priority: {f['priority']} | Retries: {f['retry_count']}")
            print(f"   ID: {f['id']}")
    
    elif command == 'mark-corrupted' and len(sys.argv) > 2:
        record_id = sys.argv[2]
        error_msg = sys.argv[3] if len(sys.argv) > 3 else "Manually marked as corrupted"
        tracker.mark_corrupted(record_id, error_msg)
        print(f"✓ Marked {record_id} as corrupted")
    
    elif command == 'mark-empty' and len(sys.argv) > 2:
        record_id = sys.argv[2]
        notes = sys.argv[3] if len(sys.argv) > 3 else None
        tracker.mark_empty(record_id, notes)
        print(f"✓ Marked {record_id} as empty")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
