#!/usr/bin/env python3
"""
Track file processing status in database
Logs corrupted, empty, or error files for review
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase-py not installed. Install with: pip install supabase")
    sys.exit(1)


class FileStatusTracker:
    def __init__(self, supabase_url: str = "http://127.0.0.1:54421", 
                 supabase_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"):
        """Initialize Supabase client."""
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def log_file_status(self, file_path: str, status: str, **kwargs):
        """
        Log file processing status to database.
        
        Args:
            file_path: Full path to the file
            status: 'success', 'corrupted', 'empty', 'error', 'pending'
            **kwargs: Additional fields (error_message, pages_processed, etc.)
        """
        file_stat = os.stat(file_path) if os.path.exists(file_path) else None
        
        data = {
            'file_path': file_path,
            'file_name': Path(file_path).name,
            'file_size_bytes': file_stat.st_size if file_stat else None,
            'file_type': Path(file_path).suffix.lower().lstrip('.'),
            'processing_status': status,
            'error_message': kwargs.get('error_message'),
            'error_details': kwargs.get('error_details'),
            'pages_processed': kwargs.get('pages_processed'),
            'total_pages': kwargs.get('total_pages'),
            'messages_extracted': kwargs.get('messages_extracted'),
            'processing_started_at': kwargs.get('processing_started_at'),
            'processing_completed_at': kwargs.get('processing_completed_at'),
            'notes': kwargs.get('notes')
        }
        
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        try:
            result = self.supabase.table('file_processing_status').insert(data).execute()
            print(f"✓ Logged status: {status} - {Path(file_path).name}")
            return result.data[0]['id'] if result.data else None
        except Exception as e:
            print(f"Warning: Could not log to database: {e}")
            # Still continue processing even if logging fails
            return None
    
    def update_file_status(self, file_path: str, **kwargs):
        """Update existing file status record."""
        try:
            # Find existing record
            existing = self.supabase.table('file_processing_status')\
                .select('*')\
                .eq('file_path', file_path)\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            
            if existing.data:
                record_id = existing.data[0]['id']
                update_data = {k: v for k, v in kwargs.items() if v is not None}
                self.supabase.table('file_processing_status')\
                    .update(update_data)\
                    .eq('id', record_id)\
                    .execute()
                print(f"✓ Updated status for {Path(file_path).name}")
            else:
                print(f"No existing record found for {Path(file_path).name}")
        except Exception as e:
            print(f"Warning: Could not update database: {e}")
    
    def get_problematic_files(self):
        """Get list of corrupted/empty/error files."""
        try:
            result = self.supabase.table('problematic_files').select('*').execute()
            return result.data
        except Exception as e:
            print(f"Error fetching problematic files: {e}")
            return []
    
    def get_processing_stats(self):
        """Get processing statistics."""
        try:
            result = self.supabase.table('processing_stats').select('*').execute()
            return result.data
        except Exception as e:
            print(f"Error fetching stats: {e}")
            return []
    
    def mark_corrupted(self, file_path: str, reason: str):
        """Mark a file as corrupted."""
        return self.log_file_status(
            file_path,
            'corrupted',
            error_message=reason,
            processing_completed_at=datetime.now().isoformat()
        )
    
    def mark_empty(self, file_path: str, reason: str = "No extractable content"):
        """Mark a file as empty."""
        return self.log_file_status(
            file_path,
            'empty',
            error_message=reason,
            messages_extracted=0,
            processing_completed_at=datetime.now().isoformat()
        )
    
    def mark_error(self, file_path: str, error: str, details: dict = None):
        """Mark a file as error."""
        return self.log_file_status(
            file_path,
            'error',
            error_message=str(error),
            error_details=details,
            processing_completed_at=datetime.now().isoformat()
        )
    
    def mark_success(self, file_path: str, messages_count: int, pages: int = None):
        """Mark a file as successfully processed."""
        return self.log_file_status(
            file_path,
            'success',
            messages_extracted=messages_count,
            pages_processed=pages,
            processing_completed_at=datetime.now().isoformat()
        )


def main():
    """CLI for file status tracking."""
    if len(sys.argv) < 3:
        print("Usage: python track_file_status.py <file_path> <status> [message]")
        print("\nStatus options:")
        print("  corrupted - File is corrupted/unreadable")
        print("  empty - File has no content")
        print("  error - Processing error occurred")
        print("  success - Successfully processed")
        print("\nExamples:")
        print("  python track_file_status.py file.pdf corrupted 'Invalid PDF structure'")
        print("  python track_file_status.py file.txt empty")
        print("  python track_file_status.py file.pdf success")
        sys.exit(1)
    
    file_path = sys.argv[1]
    status = sys.argv[2]
    message = sys.argv[3] if len(sys.argv) > 3 else None
    
    tracker = FileStatusTracker()
    
    if status == 'corrupted':
        tracker.mark_corrupted(file_path, message or "File corrupted")
    elif status == 'empty':
        tracker.mark_empty(file_path, message or "No content")
    elif status == 'error':
        tracker.mark_error(file_path, message or "Processing error")
    elif status == 'success':
        tracker.mark_success(file_path, messages_count=0)  # Update with actual count
    else:
        tracker.log_file_status(file_path, status, error_message=message)
    
    # Show problematic files
    print("\n" + "="*60)
    print("PROBLEMATIC FILES:")
    print("="*60)
    problematic = tracker.get_problematic_files()
    for file in problematic[:10]:
        print(f"\n📄 {file['file_name']}")
        print(f"   Status: {file['processing_status']}")
        print(f"   Error: {file['error_message']}")
        print(f"   Size: {file.get('file_size_mb', 0):.2f} MB")


if __name__ == "__main__":
    main()
