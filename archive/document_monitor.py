#!/usr/bin/env python3
"""
Document Monitor
Monitors specified directories for new PDF files and processes them automatically.
Sends macOS notifications for new files found.
"""

import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set
import subprocess
import socket

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase not installed. Install with: pip install supabase")
    sys.exit(1)

try:
    from document_processor import DocumentProcessor
except ImportError:
    print("Error: document_processor.py not found")
    sys.exit(1)


class DocumentMonitor:
    """Monitor directories for new PDF files and auto-process them."""
    
    def __init__(self, watched_paths: List[str], check_interval: int = 300):
        """
        Initialize document monitor.
        
        Args:
            watched_paths: List of directory paths to monitor
            check_interval: Seconds between checks (default: 300 = 5 minutes)
        """
        self.watched_paths = [Path(p) for p in watched_paths]
        self.check_interval = check_interval
        self.processor = DocumentProcessor()
        self.supabase: Client = create_client(
            "http://127.0.0.1:54321",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
        )
        self.state_file = Path.home() / '.document_monitor_state.json'
        self.known_files: Set[str] = self._load_state()
        self.log_file = Path.home() / '.document_monitor.log'
    
    def _load_state(self) -> Set[str]:
        """Load previously seen files from state file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('known_files', []))
            except:
                return set()
        return set()
    
    def _save_state(self):
        """Save known files to state file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'known_files': list(self.known_files),
                    'last_check': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            self._log(f"Error saving state: {e}")
    
    def _log(self, message: str):
        """Log message to file."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_message)
        except:
            pass  # Silent fail for logging
    
    def check_internet_connection(self) -> bool:
        """Check if connected to internet."""
        try:
            # Try to connect to Google DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            pass
        
        # Try alternative check
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=3)
            return True
        except OSError:
            return False
    
    def check_supabase_connection(self) -> bool:
        """Check if Supabase is running."""
        try:
            self.supabase.table('documents').select('id').limit(1).execute()
            return True
        except:
            return False
    
    def send_notification(self, title: str, message: str, sound: bool = True):
        """Send macOS notification."""
        try:
            script = f'''
                display notification "{message}" with title "{title}"
            '''
            if sound:
                script = f'''
                    display notification "{message}" with title "{title}" sound name "Glass"
                '''
            subprocess.run(['osascript', '-e', script], check=False, capture_output=True)
        except Exception as e:
            self._log(f"Error sending notification: {e}")
    
    def scan_for_new_files(self) -> List[Path]:
        """Scan watched directories for new PDF files."""
        new_files = []
        
        for watch_path in self.watched_paths:
            if not watch_path.exists():
                self._log(f"Warning: Watch path does not exist: {watch_path}")
                continue
            
            # Find all PDFs
            try:
                pdf_files = list(watch_path.glob('**/*.pdf'))
                
                for pdf_path in pdf_files:
                    # Skip hidden files and system files
                    if any(part.startswith('.') for part in pdf_path.parts):
                        continue
                    
                    pdf_str = str(pdf_path)
                    if pdf_str not in self.known_files:
                        new_files.append(pdf_path)
                        self.known_files.add(pdf_str)
                
            except Exception as e:
                self._log(f"Error scanning {watch_path}: {e}")
        
        return new_files
    
    def process_new_files(self, new_files: List[Path]) -> Dict:
        """Process newly discovered PDF files."""
        results = {
            'total': len(new_files),
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'files': []
        }
        
        for pdf_path in new_files:
            try:
                self._log(f"Processing: {pdf_path.name}")
                result = self.processor.process_document(str(pdf_path), skip_if_exists=True)
                
                if result.get('status') == 'success':
                    results['processed'] += 1
                    results['files'].append({
                        'name': pdf_path.name,
                        'path': str(pdf_path),
                        'status': 'success',
                        'category': result.get('category'),
                        'bin': result.get('context_bin')
                    })
                elif result.get('status') == 'skipped':
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                    results['files'].append({
                        'name': pdf_path.name,
                        'path': str(pdf_path),
                        'status': 'failed',
                        'error': result.get('reason')
                    })
                
            except Exception as e:
                self._log(f"Error processing {pdf_path.name}: {e}")
                results['failed'] += 1
                results['files'].append({
                    'name': pdf_path.name,
                    'path': str(pdf_path),
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def generate_report(self, results: Dict) -> str:
        """Generate a readable report of processing results."""
        report = f"""
📊 NEW PDF FILES REPORT
{'='*50}

Total New Files: {results['total']}
✅ Processed: {results['processed']}
⏭️  Skipped: {results['skipped']}
❌ Failed: {results['failed']}

Files by Bin:
"""
        # Group by bin
        bins = {}
        for file in results['files']:
            if file.get('status') == 'success':
                bin_name = file.get('bin', 'Unknown')
                if bin_name not in bins:
                    bins[bin_name] = []
                bins[bin_name].append(file)
        
        for bin_name, files in bins.items():
            report += f"\n📂 {bin_name}: {len(files)} documents\n"
            for file in files[:3]:  # Show first 3
                report += f"   • {file['name']} ({file.get('category', 'unknown')})\n"
            if len(files) > 3:
                report += f"   ... and {len(files) - 3} more\n"
        
        return report
    
    def run_check(self):
        """Run a single check for new files."""
        self._log("=== Starting check ===")
        
        # Check internet connection
        if not self.check_internet_connection():
            self._log("No internet connection, skipping check")
            return
        
        # Check Supabase connection
        if not self.check_supabase_connection():
            self._log("Supabase not running, skipping check")
            self.send_notification(
                "Document Monitor",
                "⚠️ Database not running. Start Supabase with: supabase start",
                sound=False
            )
            return
        
        # Scan for new files
        new_files = self.scan_for_new_files()
        
        if not new_files:
            self._log("No new files found")
            self.send_notification(
                "Document Monitor",
                "✅ No new PDF files",
                sound=False
            )
            self._save_state()
            return
        
        # Process new files
        self._log(f"Found {len(new_files)} new files")
        self.send_notification(
            "Document Monitor",
            f"📄 Found {len(new_files)} new PDF files. Processing...",
            sound=True
        )
        
        results = self.process_new_files(new_files)
        
        # Generate report
        report = self.generate_report(results)
        self._log(report)
        
        # Save report to file
        report_file = Path.home() / 'Documents' / f"pdf_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            report_file.parent.mkdir(exist_ok=True)
            with open(report_file, 'w') as f:
                f.write(report)
            self._log(f"Report saved to: {report_file}")
        except Exception as e:
            self._log(f"Error saving report: {e}")
        
        # Send notification
        if results['processed'] > 0:
            self.send_notification(
                "Document Monitor",
                f"✅ Processed {results['processed']} new documents. Report saved to Documents folder.",
                sound=True
            )
        else:
            self.send_notification(
                "Document Monitor",
                f"⚠️ Found {results['total']} files but {results['failed']} failed. Check report.",
                sound=True
            )
        
        # Save state
        self._save_state()
        self._log("=== Check complete ===\n")
    
    def run_once(self):
        """Run a single check and exit."""
        self._log("Running one-time check")
        self.run_check()
    
    def run_daemon(self):
        """Run continuously, checking at intervals."""
        self._log(f"Starting daemon mode (checking every {self.check_interval} seconds)")
        print(f"Document Monitor running...")
        print(f"Watching: {[str(p) for p in self.watched_paths]}")
        print(f"Check interval: {self.check_interval} seconds")
        print(f"Log file: {self.log_file}")
        print(f"Press Ctrl+C to stop")
        
        try:
            while True:
                self.run_check()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self._log("Daemon stopped by user")
            print("\nMonitor stopped.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Monitor directories for new PDF files and auto-process them',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run once (good for testing or LaunchAgent)
  python document_monitor.py --once
  
  # Run as daemon (continuous monitoring)
  python document_monitor.py --daemon
  
  # Monitor specific paths
  python document_monitor.py --once --paths ~/Downloads ~/Documents/Scans
  
  # Custom check interval (in seconds)
  python document_monitor.py --daemon --interval 600
  
Default Paths (if not specified):
  - ~/Library/Mobile Documents/com~apple~CloudDocs (iCloud Drive)
  - ~/Downloads
  - ~/Documents
        """
    )
    
    parser.add_argument('--once', action='store_true', 
                       help='Run once and exit (for LaunchAgent)')
    parser.add_argument('--daemon', action='store_true',
                       help='Run continuously as daemon')
    parser.add_argument('--paths', nargs='+',
                       help='Directories to monitor (space-separated)')
    parser.add_argument('--interval', type=int, default=300,
                       help='Check interval in seconds (default: 300)')
    parser.add_argument('--test', action='store_true',
                       help='Test notifications only')
    
    args = parser.parse_args()
    
    # Default watched paths
    default_paths = [
        str(Path.home() / 'Library' / 'Mobile Documents' / 'com~apple~CloudDocs'),
        str(Path.home() / 'Downloads'),
        str(Path.home() / 'Documents')
    ]
    
    watched_paths = args.paths if args.paths else default_paths
    
    # Test mode
    if args.test:
        monitor = DocumentMonitor(watched_paths, args.interval)
        monitor.send_notification(
            "Document Monitor Test",
            "✅ Notifications are working!",
            sound=True
        )
        print("Test notification sent!")
        sys.exit(0)
    
    # Create monitor
    monitor = DocumentMonitor(watched_paths, args.interval)
    
    # Run mode
    if args.once:
        monitor.run_once()
    elif args.daemon:
        monitor.run_daemon()
    else:
        print("Please specify --once or --daemon mode")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
