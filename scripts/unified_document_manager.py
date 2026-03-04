#!/usr/bin/env python3
"""
Unified Document Manager
Main entry point for the dual-mode document management system.
Handles both conversation PDFs and general document organization.
"""

import sys
import os
import argparse
from pathlib import Path
from typing import List, Optional

# Import our modules
try:
    from document_processor import DocumentProcessor
    from search_engine import SearchEngine
    from folder_analyzer import FolderAnalyzer
    from parse_pdf import ConversationParser
    from groq_analyze import GroqAnalyzer
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all required files are in the same directory:")
    print("  - document_processor.py")
    print("  - search_engine.py")
    print("  - folder_analyzer.py")
    print("  - parse_pdf.py")
    print("  - groq_analyze.py")
    sys.exit(1)


class UnifiedDocumentManager:
    """Main interface for the document management system."""
    
    def __init__(self):
        self.doc_processor = DocumentProcessor()
        self.search_engine = SearchEngine()
        self.folder_analyzer = FolderAnalyzer()
    
    def process_file(self, file_path: str, force_mode: Optional[str] = None) -> dict:
        """
        Process a single PDF file.
        
        Args:
            file_path: Path to PDF file
            force_mode: 'conversation' or 'document' to force a specific mode,
                       None for auto-detection
        """
        
        print(f"\n{'='*80}")
        print(f"📄 PROCESSING FILE")
        print(f"{'='*80}")
        print(f"File: {file_path}")
        print(f"Mode: {force_mode or 'AUTO-DETECT'}")
        print(f"{'='*80}\n")
        
        if not os.path.exists(file_path):
            return {'error': f"File not found: {file_path}"}
        
        # Process with document processor (handles both modes)
        result = self.doc_processor.process_document(file_path)
        
        # If it's a conversation PDF, do deep conversation analysis
        if result.get('document_mode') == 'conversation' or force_mode == 'conversation':
            print("\n🗨️  Detected CONVERSATION mode - Running deep conversation analysis...")
            conv_result = self._process_conversation(file_path)
            result['conversation_analysis'] = conv_result
        
        return result
    
    def process_directory(self, directory: str, recursive: bool = True, 
                         force_mode: Optional[str] = None) -> dict:
        """
        Process all PDF files in a directory.
        
        Args:
            directory: Path to directory
            recursive: Process subdirectories
            force_mode: Force all files to a specific mode
        """
        
        print(f"\n{'='*80}")
        print(f"📁 BATCH PROCESSING DIRECTORY")
        print(f"{'='*80}")
        print(f"Directory: {directory}")
        print(f"Recursive: {recursive}")
        print(f"{'='*80}\n")
        
        if not os.path.isdir(directory):
            return {'error': f"Directory not found: {directory}"}
        
        # Find all PDF files
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(Path(directory).glob(pattern))
        
        print(f"Found {len(pdf_files)} PDF files\n")
        
        results = {
            'total': len(pdf_files),
            'processed': 0,
            'failed': 0,
            'skipped': 0,
            'files': []
        }
        
        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
            
            try:
                result = self.process_file(str(pdf_path), force_mode)
                
                if result.get('status') == 'success':
                    results['processed'] += 1
                elif result.get('status') == 'skipped':
                    results['skipped'] += 1
                else:
                    results['failed'] += 1
                
                results['files'].append({
                    'file': str(pdf_path),
                    'result': result
                })
                
            except Exception as e:
                print(f"❌ Error: {e}")
                results['failed'] += 1
                results['files'].append({
                    'file': str(pdf_path),
                    'error': str(e)
                })
        
        print(f"\n{'='*80}")
        print(f"📊 BATCH PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"✅ Processed: {results['processed']}")
        print(f"⏭️  Skipped: {results['skipped']}")
        print(f"❌ Failed: {results['failed']}")
        print(f"{'='*80}\n")
        
        return results
    
    def _process_conversation(self, file_path: str) -> dict:
        """Process file as a conversation and run deep analysis."""
        try:
            # Parse conversation
            parser = ConversationParser(file_path)
            conv_data = parser.parse()
            
            # Run Groq analysis
            analyzer = GroqAnalyzer(conv_data)
            analysis = analyzer.analyze()
            
            return {
                'conversation_data': conv_data,
                'analysis': analysis
            }
        except Exception as e:
            print(f"Warning: Conversation analysis failed: {e}")
            return {'error': str(e)}
    
    def search(self, query: str, limit: int = 10) -> List[dict]:
        """
        Search documents with natural language.
        
        Args:
            query: Natural language search query
            limit: Maximum results to return
        """
        results = self.search_engine.search(query, limit)
        self.search_engine.display_results(results)
        return results
    
    def search_by_category(self, category: str, limit: int = 20) -> List[dict]:
        """Search documents by category."""
        return self.search_engine.search_by_category(category, limit)
    
    def analyze_folders(self) -> dict:
        """Analyze all folder organization and generate suggestions."""
        return self.folder_analyzer.analyze_all_folders()
    
    def get_statistics(self) -> dict:
        """Get system statistics."""
        try:
            from supabase import create_client
            supabase = create_client(
                "http://127.0.0.1:54321",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
            )
            
            # Get document counts
            docs_result = supabase.table('documents').select('id, document_mode, ai_category').execute()
            docs = docs_result.data
            
            # Calculate stats
            total_docs = len(docs)
            conversation_docs = sum(1 for d in docs if d.get('document_mode') == 'conversation')
            document_docs = sum(1 for d in docs if d.get('document_mode') == 'document')
            
            # Category distribution
            from collections import Counter
            categories = Counter(d.get('ai_category', 'unknown') for d in docs)
            
            # Get folder stats
            folders_result = supabase.table('folder_analysis').select('*').execute()
            folders = folders_result.data
            
            avg_org_score = sum(f.get('organization_score', 0) for f in folders) / len(folders) if folders else 0
            
            stats = {
                'total_documents': total_docs,
                'conversation_mode': conversation_docs,
                'document_mode': document_docs,
                'total_folders': len(folders),
                'average_organization_score': round(avg_org_score, 1),
                'top_categories': dict(categories.most_common(10)),
            }
            
            print(f"\n{'='*80}")
            print(f"📊 SYSTEM STATISTICS")
            print(f"{'='*80}")
            print(f"Total Documents: {stats['total_documents']}")
            print(f"  - Conversations: {stats['conversation_mode']}")
            print(f"  - Documents: {stats['document_mode']}")
            print(f"Total Folders: {stats['total_folders']}")
            print(f"Avg Organization Score: {stats['average_organization_score']}/100")
            print(f"\nTop Categories:")
            for cat, count in list(stats['top_categories'].items())[:5]:
                print(f"  - {cat}: {count}")
            print(f"{'='*80}\n")
            
            return stats
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}


def main():
    parser = argparse.ArgumentParser(
        description='Unified Document Management System - Handles conversations and documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single file
  python unified_document_manager.py process file.pdf
  
  # Process a directory
  python unified_document_manager.py process /path/to/pdfs --directory
  
  # Force conversation mode
  python unified_document_manager.py process conversation.pdf --mode conversation
  
  # Search documents
  python unified_document_manager.py search "find my 2024 tesla registration"
  
  # Search by category
  python unified_document_manager.py search --category vehicle_registration
  
  # Analyze folder organization
  python unified_document_manager.py analyze-folders
  
  # Show statistics
  python unified_document_manager.py stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process PDF file(s)')
    process_parser.add_argument('path', help='Path to PDF file or directory')
    process_parser.add_argument('--directory', '-d', action='store_true', 
                               help='Process entire directory')
    process_parser.add_argument('--recursive', '-r', action='store_true', default=True,
                               help='Process subdirectories (default: True)')
    process_parser.add_argument('--mode', choices=['conversation', 'document'],
                               help='Force processing mode')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search documents')
    search_parser.add_argument('query', nargs='*', help='Search query')
    search_parser.add_argument('--category', help='Search by category')
    search_parser.add_argument('--limit', type=int, default=10, help='Max results')
    
    # Analyze folders command
    analyze_parser = subparsers.add_parser('analyze-folders', 
                                          help='Analyze folder organization')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show system statistics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Initialize manager
    manager = UnifiedDocumentManager()
    
    # Execute command
    if args.command == 'process':
        if args.directory:
            result = manager.process_directory(args.path, args.recursive, args.mode)
        else:
            result = manager.process_file(args.path, args.mode)
    
    elif args.command == 'search':
        if args.category:
            results = manager.search_by_category(args.category, args.limit)
            manager.search_engine.display_results(results)
        else:
            query = ' '.join(args.query)
            if not query:
                print("Error: Please provide a search query")
                sys.exit(1)
            manager.search(query, args.limit)
    
    elif args.command == 'analyze-folders':
        manager.analyze_folders()
    
    elif args.command == 'stats':
        manager.get_statistics()


if __name__ == "__main__":
    main()
