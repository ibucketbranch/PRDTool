#!/usr/bin/env python3
"""
Folder Analyzer
Analyzes folder structure, identifies organization issues, and suggests improvements.
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime

try:
    from groq import Groq
except ImportError:
    print("Groq not installed. Install with: pip install groq")
    sys.exit(1)

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase not installed. Install with: pip install supabase")
    sys.exit(1)


class FolderAnalyzer:
    def __init__(self, supabase_url: str = "http://127.0.0.1:54321",
                 supabase_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
                 groq_api_key: Optional[str] = None):
        """Initialize folder analyzer."""
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.groq_client = Groq(api_key=groq_api_key or os.getenv('GROQ_API_KEY'))
    
    def analyze_all_folders(self) -> Dict:
        """Analyze all folders containing documents in the database."""
        
        print(f"\n{'='*80}")
        print(f"📊 FOLDER STRUCTURE ANALYSIS")
        print(f"{'='*80}\n")
        
        # Get all documents grouped by folder
        print("📁 Loading documents from database...")
        try:
            result = self.supabase.table('documents')\
                .select('id, current_path, folder_hierarchy, ai_category, ai_subcategories, confidence_score, file_name')\
                .execute()
            
            documents = result.data
            print(f"   ✓ Found {len(documents)} documents")
        except Exception as e:
            print(f"❌ Error loading documents: {e}")
            return {}
        
        # Group by folder
        folders = defaultdict(list)
        for doc in documents:
            folder_path = str(Path(doc['current_path']).parent)
            folders[folder_path].append(doc)
        
        print(f"   ✓ Analyzing {len(folders)} folders\n")
        
        # Analyze each folder
        folder_analyses = {}
        for folder_path, folder_docs in folders.items():
            analysis = self.analyze_folder(folder_path, folder_docs)
            folder_analyses[folder_path] = analysis
            
            # Save to database
            self._save_folder_analysis(folder_path, analysis)
        
        # Generate overall recommendations
        overall_analysis = self._generate_overall_recommendations(folder_analyses)
        
        # Display summary
        self._display_analysis_summary(folder_analyses, overall_analysis)
        
        return {
            'folder_analyses': folder_analyses,
            'overall_recommendations': overall_analysis
        }
    
    def analyze_folder(self, folder_path: str, documents: List[Dict]) -> Dict:
        """Analyze a single folder's organization."""
        
        folder_name = Path(folder_path).name
        print(f"🔍 Analyzing: {folder_name}")
        
        # Count documents
        doc_count = len(documents)
        
        # Analyze categories
        categories = [doc['ai_category'] for doc in documents if doc.get('ai_category')]
        category_counts = Counter(categories)
        primary_categories = [cat for cat, _ in category_counts.most_common(3)]
        
        # Calculate category diversity (0 = uniform, 1 = very diverse)
        if len(categories) > 0:
            unique_ratio = len(set(categories)) / len(categories)
            category_diversity = min(1.0, unique_ratio * 1.5)  # Scale so >66% unique = high diversity
        else:
            category_diversity = 0.0
        
        # Calculate organization score
        organization_score = self._calculate_organization_score(
            doc_count, category_counts, category_diversity, folder_path
        )
        
        is_well_organized = organization_score >= 70
        
        # Find misplaced documents
        misplaced_docs = self._find_misplaced_documents(documents, primary_categories[0] if primary_categories else None)
        
        # Generate suggestions
        suggestions = self._generate_folder_suggestions(
            folder_path, documents, primary_categories, category_diversity, 
            organization_score, misplaced_docs
        )
        
        analysis = {
            'folder_path': folder_path,
            'folder_name': folder_name,
            'document_count': doc_count,
            'primary_categories': primary_categories,
            'category_distribution': dict(category_counts),
            'category_diversity': round(category_diversity, 2),
            'organization_score': organization_score,
            'is_well_organized': is_well_organized,
            'misplaced_documents': misplaced_docs,
            'suggestions': suggestions
        }
        
        # Print quick summary
        status = "✅" if is_well_organized else "⚠️"
        print(f"   {status} Score: {organization_score}/100 | {doc_count} docs | Categories: {', '.join(primary_categories[:2])}")
        
        return analysis
    
    def _calculate_organization_score(self, doc_count: int, category_counts: Counter,
                                      category_diversity: float, folder_path: str) -> int:
        """Calculate organization score (0-100)."""
        
        score = 50  # Base score
        
        # Penalize very high diversity (too many different document types in one folder)
        if category_diversity > 0.7:
            score -= 20
        elif category_diversity > 0.5:
            score -= 10
        else:
            score += 10  # Reward focused folders
        
        # Reward if folder has a clear primary category (>50% of docs in one category)
        if category_counts:
            max_category_ratio = max(category_counts.values()) / sum(category_counts.values())
            if max_category_ratio > 0.7:
                score += 20
            elif max_category_ratio > 0.5:
                score += 10
        
        # Check if folder name matches content
        folder_name_lower = Path(folder_path).name.lower()
        if category_counts:
            top_category = category_counts.most_common(1)[0][0]
            category_keywords = top_category.lower().replace('_', ' ').split()
            if any(keyword in folder_name_lower for keyword in category_keywords):
                score += 15
        
        # Penalize folders in temporary locations
        temp_locations = ['downloads', 'desktop', 'temp', 'tmp', 'untitled']
        if any(temp in folder_path.lower() for temp in temp_locations):
            score -= 25
        
        # Reward proper document hierarchies
        proper_roots = ['documents', 'files', 'personal', 'work', 'financial']
        if any(root in folder_path.lower() for root in proper_roots):
            score += 10
        
        # Penalize very large folders (should be subdivided)
        if doc_count > 50:
            score -= 15
        elif doc_count > 30:
            score -= 10
        
        # Reward moderate-sized folders
        if 5 <= doc_count <= 20:
            score += 10
        
        return max(0, min(100, score))
    
    def _find_misplaced_documents(self, documents: List[Dict], primary_category: Optional[str]) -> List[Dict]:
        """Find documents that don't match the folder's primary category."""
        
        if not primary_category:
            return []
        
        misplaced = []
        for doc in documents:
            # Document is misplaced if:
            # 1. Its category doesn't match primary category
            # 2. It has low path confidence
            # 3. It has a suggested path different from current
            
            is_misplaced = False
            reason = []
            
            if doc.get('ai_category') != primary_category:
                is_misplaced = True
                reason.append(f"Category mismatch (is {doc.get('ai_category')}, folder is {primary_category})")
            
            if doc.get('path_confidence', 1.0) < 0.5:
                is_misplaced = True
                reason.append(f"Low path confidence ({doc.get('path_confidence', 0):.0%})")
            
            if doc.get('suggested_path') and doc.get('suggested_path') not in doc.get('current_path', ''):
                is_misplaced = True
                reason.append(f"Should be in: {doc.get('suggested_path')}")
            
            if is_misplaced:
                misplaced.append({
                    'document_id': doc['id'],
                    'file_name': doc['file_name'],
                    'category': doc.get('ai_category'),
                    'reasons': reason,
                    'suggested_path': doc.get('suggested_path')
                })
        
        return misplaced
    
    def _generate_folder_suggestions(self, folder_path: str, documents: List[Dict],
                                     primary_categories: List[str], category_diversity: float,
                                     organization_score: int, misplaced_docs: List[Dict]) -> List[Dict]:
        """Generate improvement suggestions for a folder."""
        
        suggestions = []
        
        # Suggest rename if folder name doesn't match content
        if primary_categories:
            folder_name = Path(folder_path).name.lower()
            top_category = primary_categories[0].lower()
            
            if top_category.replace('_', '') not in folder_name.replace('_', '').replace('-', ''):
                suggestions.append({
                    'type': 'rename_folder',
                    'priority': 6,
                    'current': folder_path,
                    'suggested': str(Path(folder_path).parent / top_category.replace('_', '_').title()),
                    'reason': f"Folder name doesn't reflect content ({top_category})"
                })
        
        # Suggest subdivision if folder is too large or too diverse
        if len(documents) > 30 or category_diversity > 0.7:
            # Group by category for subdivision
            category_groups = defaultdict(list)
            for doc in documents:
                category_groups[doc.get('ai_category', 'other')].append(doc)
            
            if len(category_groups) > 1:
                subfolder_plan = {}
                for cat, cat_docs in category_groups.items():
                    if len(cat_docs) >= 3:  # Only create subfolder if 3+ docs
                        subfolder_plan[cat] = len(cat_docs)
                
                if subfolder_plan:
                    suggestions.append({
                        'type': 'subdivide_folder',
                        'priority': 7,
                        'current': folder_path,
                        'suggested_structure': subfolder_plan,
                        'reason': f"Large/diverse folder ({len(documents)} docs, {len(category_groups)} categories)"
                    })
        
        # Suggest moving misplaced documents
        if misplaced_docs:
            for misplaced in misplaced_docs[:5]:  # Top 5
                suggestions.append({
                    'type': 'move_document',
                    'priority': 8,
                    'document_id': misplaced['document_id'],
                    'file_name': misplaced['file_name'],
                    'current': folder_path,
                    'suggested': misplaced.get('suggested_path'),
                    'reason': ', '.join(misplaced['reasons'])
                })
        
        # Suggest moving folder if in temp location
        temp_locations = ['downloads', 'desktop', 'temp', 'tmp']
        if any(temp in folder_path.lower() for temp in temp_locations):
            if primary_categories:
                # Get category suggestion
                try:
                    cat_result = self.supabase.table('categories')\
                        .select('suggested_folder_path')\
                        .eq('category_name', primary_categories[0])\
                        .execute()
                    
                    if cat_result.data:
                        suggested_root = cat_result.data[0]['suggested_folder_path']
                        suggestions.append({
                            'type': 'move_folder',
                            'priority': 9,
                            'current': folder_path,
                            'suggested': suggested_root,
                            'reason': 'Folder in temporary location'
                        })
                except:
                    pass
        
        # Sort by priority
        suggestions.sort(key=lambda x: x['priority'], reverse=True)
        
        return suggestions
    
    def _generate_overall_recommendations(self, folder_analyses: Dict) -> Dict:
        """Generate overall recommendations for the entire folder structure."""
        
        print("\n🤖 Generating AI recommendations...")
        
        # Collect statistics
        total_folders = len(folder_analyses)
        total_docs = sum(analysis['document_count'] for analysis in folder_analyses.values())
        avg_score = sum(analysis['organization_score'] for analysis in folder_analyses.values()) / total_folders if total_folders > 0 else 0
        poorly_organized = sum(1 for analysis in folder_analyses.values() if analysis['organization_score'] < 60)
        
        # Collect all suggestions
        all_suggestions = []
        for folder_path, analysis in folder_analyses.items():
            for suggestion in analysis['suggestions']:
                suggestion['folder_path'] = folder_path
                all_suggestions.append(suggestion)
        
        # Sort by priority
        all_suggestions.sort(key=lambda x: x['priority'], reverse=True)
        
        # Use Groq to generate restructuring plan
        restructuring_plan = self._generate_ai_restructuring_plan(folder_analyses, all_suggestions)
        
        return {
            'statistics': {
                'total_folders': total_folders,
                'total_documents': total_docs,
                'average_organization_score': round(avg_score, 1),
                'poorly_organized_folders': poorly_organized,
                'total_suggestions': len(all_suggestions)
            },
            'top_suggestions': all_suggestions[:20],
            'restructuring_plan': restructuring_plan
        }
    
    def _generate_ai_restructuring_plan(self, folder_analyses: Dict, suggestions: List[Dict]) -> str:
        """Use Groq to generate an overall restructuring plan."""
        
        # Prepare summary for AI
        summary = {
            'folder_count': len(folder_analyses),
            'poorly_organized': [path for path, analysis in folder_analyses.items() 
                                if analysis['organization_score'] < 60],
            'top_categories': self._get_overall_category_distribution(folder_analyses),
            'top_suggestions': suggestions[:10]
        }
        
        prompt = f"""You are a document organization expert. Analyze this folder structure and provide recommendations.

Current State:
- {summary['folder_count']} folders analyzed
- {len(summary['poorly_organized'])} poorly organized folders
- Top categories: {', '.join(summary['top_categories'][:5])}

Top Issues:
{json.dumps(summary['top_suggestions'], indent=2, default=str)}

Provide a concise action plan (3-5 key recommendations) to improve the overall organization.
Focus on high-impact changes that will significantly improve findability and structure.
"""
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Warning: AI restructuring plan generation failed: {e}")
            return "AI analysis unavailable. Review individual folder suggestions above."
    
    def _get_overall_category_distribution(self, folder_analyses: Dict) -> List[str]:
        """Get overall category distribution across all folders."""
        all_categories = []
        for analysis in folder_analyses.values():
            all_categories.extend(analysis['category_distribution'].keys())
        
        category_counts = Counter(all_categories)
        return [cat for cat, _ in category_counts.most_common()]
    
    def _save_folder_analysis(self, folder_path: str, analysis: Dict):
        """Save folder analysis to database."""
        try:
            # Check if analysis exists
            existing = self.supabase.table('folder_analysis')\
                .select('id')\
                .eq('folder_path', folder_path)\
                .execute()
            
            data = {
                'folder_path': folder_path,
                'parent_folder': str(Path(folder_path).parent),
                'depth': len(Path(folder_path).parts),
                'document_count': analysis['document_count'],
                'primary_categories': analysis['primary_categories'],
                'category_diversity': analysis['category_diversity'],
                'is_well_organized': analysis['is_well_organized'],
                'organization_score': analysis['organization_score'],
                'suggested_restructure': analysis['suggestions'],
                'misplaced_document_count': len(analysis['misplaced_documents']),
                'analyzed_at': datetime.now().isoformat()
            }
            
            if existing.data:
                # Update existing
                self.supabase.table('folder_analysis')\
                    .update(data)\
                    .eq('id', existing.data[0]['id'])\
                    .execute()
            else:
                # Insert new
                self.supabase.table('folder_analysis').insert(data).execute()
                
        except Exception as e:
            print(f"Warning: Could not save folder analysis: {e}")
    
    def _display_analysis_summary(self, folder_analyses: Dict, overall_analysis: Dict):
        """Display analysis summary."""
        
        print(f"\n{'='*80}")
        print(f"📊 ANALYSIS SUMMARY")
        print(f"{'='*80}\n")
        
        stats = overall_analysis['statistics']
        print(f"📁 Total Folders: {stats['total_folders']}")
        print(f"📄 Total Documents: {stats['total_documents']}")
        print(f"⭐ Average Organization Score: {stats['average_organization_score']}/100")
        print(f"⚠️  Poorly Organized Folders: {stats['poorly_organized_folders']}")
        print(f"💡 Total Suggestions: {stats['total_suggestions']}")
        
        print(f"\n{'='*80}")
        print(f"🎯 TOP RECOMMENDATIONS")
        print(f"{'='*80}\n")
        
        for i, suggestion in enumerate(overall_analysis['top_suggestions'][:10], 1):
            print(f"[{i}] {suggestion['type'].upper().replace('_', ' ')}")
            print(f"    Priority: {suggestion['priority']}/10")
            print(f"    Reason: {suggestion['reason']}")
            if suggestion['type'] == 'move_document':
                print(f"    File: {suggestion['file_name']}")
            print(f"    Current: {suggestion.get('current', 'N/A')}")
            print(f"    Suggested: {suggestion.get('suggested', 'N/A')}")
            print()
        
        print(f"\n{'='*80}")
        print(f"🤖 AI RESTRUCTURING PLAN")
        print(f"{'='*80}\n")
        print(overall_analysis['restructuring_plan'])
        print(f"\n{'='*80}\n")
    
    def apply_suggestions(self, auto_apply: bool = False, suggestions_to_apply: List[int] = None):
        """Apply organization suggestions."""
        
        print("\n⚠️  APPLY SUGGESTIONS")
        print("This feature would move/rename files and folders.")
        print("Currently in read-only mode for safety.")
        print("\nTo implement file operations, uncomment the code in apply_suggestions() method.")
        
        # TODO: Implement actual file operations with user confirmation
        # This is intentionally left as a stub for safety
        pass


def main():
    analyzer = FolderAnalyzer()
    result = analyzer.analyze_all_folders()
    
    # Save full report
    report_file = f"folder_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"📝 Full report saved to: {report_file}")


if __name__ == "__main__":
    main()
