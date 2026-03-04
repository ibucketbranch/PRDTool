#!/usr/bin/env python3
"""
Search Engine
Natural language search for documents with entity extraction and semantic matching.
"""

import sys
import os
import json
import re
from typing import Dict, List, Optional, Tuple
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


class SearchEngine:
    def __init__(self, supabase_url: str = "http://127.0.0.1:54321",
                 supabase_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
                 groq_api_key: Optional[str] = None):
        """Initialize search engine with Supabase and Groq."""
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.groq_client = Groq(api_key=groq_api_key or os.getenv('GROQ_API_KEY'))
    
    def extract_search_entities(self, query: str) -> Dict:
        """Extract entities from natural language search query using Groq."""
        
        prompt = f"""Extract search entities from this query. Return ONLY valid JSON.

Query: "{query}"

Extract these entities:
- document_type: type of document (registration, insurance, receipt, invoice, contract, etc.)
- vehicle: vehicle make/model if mentioned
- year: year if mentioned
- organization: company/organization name
- person: person name
- amount: money amount
- date_range: date or date range
- category: document category
- keywords: other important search terms

Return this exact JSON structure:
{{
  "document_type": "registration",
  "vehicle": "Tesla Model 3",
  "year": "2024",
  "organization": null,
  "person": null,
  "amount": null,
  "date_range": null,
  "category": "vehicle_registration",
  "keywords": ["auto", "car"],
  "search_intent": "brief description of what user is looking for"
}}

Use null for fields not mentioned in the query.
"""
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            entities = json.loads(response.choices[0].message.content)
            return entities
            
        except Exception as e:
            print(f"Warning: Entity extraction failed: {e}")
            # Fallback to basic extraction
            return self._basic_entity_extraction(query)
    
    def _basic_entity_extraction(self, query: str) -> Dict:
        """Basic entity extraction using pattern matching."""
        entities = {
            'document_type': None,
            'vehicle': None,
            'year': None,
            'organization': None,
            'person': None,
            'amount': None,
            'date_range': None,
            'category': None,
            'keywords': [],
            'search_intent': query
        }
        
        # Extract year
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            entities['year'] = year_match.group(1)
        
        # Extract vehicle brands
        vehicle_brands = ['Tesla', 'BMW', 'Mercedes', 'Ford', 'Toyota', 'Honda', 'Chevrolet']
        for brand in vehicle_brands:
            if brand.lower() in query.lower():
                entities['vehicle'] = brand
                break
        
        # Extract document types
        doc_types = {
            'registration': ['registration', 'reg', 'dmv'],
            'insurance': ['insurance', 'policy', 'coverage'],
            'receipt': ['receipt', 'bill'],
            'invoice': ['invoice'],
            'contract': ['contract', 'agreement']
        }
        
        for doc_type, keywords in doc_types.items():
            if any(kw in query.lower() for kw in keywords):
                entities['document_type'] = doc_type
                entities['category'] = f'vehicle_{doc_type}' if 'vehicle' in entities else doc_type
                break
        
        # Extract keywords (words longer than 3 chars, excluding common words)
        common_words = {'find', 'show', 'search', 'look', 'about', 'document', 'file', 'with', 'from', 'for', 'the', 'and'}
        words = re.findall(r'\b\w{4,}\b', query.lower())
        entities['keywords'] = [w for w in words if w not in common_words]
        
        return entities
    
    def search(self, query: str, limit: int = 10, context_bin: Optional[str] = None) -> List[Dict]:
        """
        Main search method.
        
        Args:
            query: Natural language search query
            limit: Maximum results to return
            context_bin: Filter by specific context bin (e.g., 'Personal Bin', 'Work Bin')
        
        Example queries:
        - "find me a document about my auto registration for my 2024 tesla"
        - "show me tax documents from 2023"
        - "insurance policy for my car"
        - "find vehicle docs in Personal Bin"
        """
        
        print(f"\n{'='*80}")
        print(f"🔍 SEARCH QUERY: {query}")
        if context_bin:
            print(f"📂 Context Bin Filter: {context_bin}")
        print(f"{'='*80}\n")
        
        # Extract entities from query
        print("📊 Extracting search entities...")
        entities = self.extract_search_entities(query)
        
        # Check if query mentions a bin
        if not context_bin:
            for bin_name in ['Personal Bin', 'Work Bin', 'Family Bin', 'Finances Bin', 'Legal Bin', 'Projects Bin']:
                if bin_name.lower() in query.lower():
                    context_bin = bin_name
                    entities['context_bin'] = bin_name
                    break
        
        print(f"   Entity Analysis:")
        for key, value in entities.items():
            if value:
                print(f"   • {key}: {value}")
        
        # Build SQL query
        print("\n🔎 Searching database...")
        results = self._build_and_execute_query(query, entities, limit, context_bin)
        
        # Log search query
        self._log_search_query(query, entities, results, context_bin)
        
        # Format results
        print(f"\n📄 Found {len(results)} results\n")
        
        return results
    
    def _build_and_execute_query(self, query: str, entities: Dict, limit: int, context_bin: Optional[str] = None) -> List[Dict]:
        """Build and execute search query based on entities."""
        
        try:
            # Start with base query
            query_builder = self.supabase.table('documents').select('*')
            
            # Filter by context bin if specified
            if context_bin:
                query_builder = query_builder.eq('context_bin', context_bin)
            elif entities.get('context_bin'):
                query_builder = query_builder.eq('context_bin', entities['context_bin'])
            
            # Filter by document mode (if conversation vs document)
            # For now, search both
            
            # Filter by category
            if entities.get('category'):
                query_builder = query_builder.eq('ai_category', entities['category'])
            elif entities.get('document_type'):
                # Search in category name
                query_builder = query_builder.ilike('ai_category', f'%{entities["document_type"]}%')
            
            # Filter by year (in entities or key_dates)
            if entities.get('year'):
                query_builder = query_builder.contains('entities', {'dates': [entities['year']]})
            
            # Filter by vehicle
            if entities.get('vehicle'):
                query_builder = query_builder.contains('entities', {'vehicles': [entities['vehicle']]})
            
            # Full text search using PostgreSQL text search
            # Combine all search terms
            search_terms = []
            if entities.get('keywords'):
                search_terms.extend(entities['keywords'])
            if entities.get('document_type'):
                search_terms.append(entities['document_type'])
            if entities.get('vehicle'):
                search_terms.append(entities['vehicle'])
            
            if search_terms:
                # Use ilike for partial matching on multiple fields
                for term in search_terms:
                    query_builder = query_builder.or_(
                        f'file_name.ilike.%{term}%,'
                        f'ai_summary.ilike.%{term}%,'
                        f'extracted_text.ilike.%{term}%,'
                        f'ai_category.ilike.%{term}%'
                    )
            
            # Order by relevance (importance score, confidence, recent)
            query_builder = query_builder.order('importance_score', desc=True)\
                                        .order('confidence_score', desc=True)\
                                        .order('created_at', desc=True)
            
            # Limit results
            query_builder = query_builder.limit(limit)
            
            # Execute query
            result = query_builder.execute()
            
            # Score and rank results
            scored_results = self._score_results(result.data, entities, query)
            
            return scored_results
            
        except Exception as e:
            print(f"❌ Search error: {e}")
            # Fallback to simple text search
            return self._fallback_search(query, limit)
    
    def _score_results(self, results: List[Dict], entities: Dict, query: str) -> List[Dict]:
        """Score and rank search results based on relevance."""
        
        scored = []
        query_lower = query.lower()
        
        for doc in results:
            score = 0.0
            reasons = []
            
            # Base score from document importance
            score += doc.get('importance_score', 5) * 0.1
            
            # Confidence score
            score += doc.get('confidence_score', 0.5) * 0.2
            
            # Exact matches in filename
            file_name = doc.get('file_name', '').lower()
            if entities.get('vehicle') and entities['vehicle'].lower() in file_name:
                score += 1.0
                reasons.append(f"Vehicle '{entities['vehicle']}' in filename")
            
            if entities.get('year') and entities['year'] in file_name:
                score += 0.8
                reasons.append(f"Year '{entities['year']}' in filename")
            
            if entities.get('document_type') and entities['document_type'].lower() in file_name:
                score += 1.0
                reasons.append(f"Document type '{entities['document_type']}' in filename")
            
            # Category match
            if entities.get('category') and entities['category'] == doc.get('ai_category'):
                score += 1.5
                reasons.append(f"Category match: {entities['category']}")
            
            # Entity matches
            doc_entities = doc.get('entities', {})
            if entities.get('vehicle') and entities['vehicle'] in str(doc_entities.get('vehicles', [])):
                score += 1.2
                reasons.append(f"Vehicle in entities")
            
            if entities.get('year') and entities['year'] in str(doc_entities.get('dates', [])):
                score += 0.8
                reasons.append(f"Year in entities")
            
            # Keywords in summary
            summary = doc.get('ai_summary', '').lower()
            keyword_matches = sum(1 for kw in entities.get('keywords', []) if kw in summary)
            if keyword_matches > 0:
                score += keyword_matches * 0.3
                reasons.append(f"{keyword_matches} keyword(s) in summary")
            
            # Text preview matches
            text_preview = doc.get('text_preview', '').lower()
            if any(kw in text_preview for kw in entities.get('keywords', [])):
                score += 0.5
                reasons.append("Keywords in text preview")
            
            # Store score and reasons
            doc['search_score'] = round(score, 2)
            doc['match_reasons'] = reasons
            scored.append(doc)
        
        # Sort by score
        scored.sort(key=lambda x: x['search_score'], reverse=True)
        
        return scored
    
    def _fallback_search(self, query: str, limit: int) -> List[Dict]:
        """Simple fallback search if main search fails."""
        try:
            result = self.supabase.table('documents')\
                .select('*')\
                .or_(f'file_name.ilike.%{query}%,ai_summary.ilike.%{query}%')\
                .limit(limit)\
                .execute()
            
            return result.data
        except Exception as e:
            print(f"❌ Fallback search failed: {e}")
            return []
    
    def _log_search_query(self, query: str, entities: Dict, results: List[Dict], context_bin: Optional[str] = None):
        """Log search query for analysis and learning."""
        try:
            log_data = {
                'query_text': query,
                'query_type': 'natural_language',
                'extracted_entities': {**entities, 'context_bin': context_bin} if context_bin else entities,
                'results_count': len(results),
                'top_result_id': results[0]['id'] if results else None
            }
            
            self.supabase.table('search_queries').insert(log_data).execute()
        except Exception as e:
            print(f"Warning: Could not log search query: {e}")
    
    def display_results(self, results: List[Dict]):
        """Display search results in a readable format."""
        
        if not results:
            print("❌ No results found")
            return
        
        print(f"\n{'='*80}")
        print(f"📋 SEARCH RESULTS ({len(results)} documents)")
        print(f"{'='*80}\n")
        
        for i, doc in enumerate(results, 1):
            print(f"[{i}] {doc.get('file_name', 'Unknown')}")
            
            # Show context bin if available
            if doc.get('context_bin'):
                print(f"    📂 Bin: {doc.get('context_bin')}")
            
            print(f"    📁 Path: {doc.get('current_path', 'N/A')}")
            print(f"    🏷️  Category: {doc.get('ai_category', 'N/A')}")
            print(f"    ⭐ Score: {doc.get('search_score', 0):.2f}")
            
            if doc.get('match_reasons'):
                print(f"    ✓ Matches: {', '.join(doc['match_reasons'][:3])}")
            
            summary = doc.get('ai_summary', 'No summary available')
            print(f"    📝 Summary: {summary[:150]}...")
            
            # Show key entities if available
            entities = doc.get('entities', {})
            if entities.get('vehicles'):
                print(f"    🚗 Vehicles: {', '.join(entities['vehicles'][:3])}")
            if entities.get('dates'):
                print(f"    📅 Dates: {', '.join(entities['dates'][:3])}")
            
            print()
        
        print(f"{'='*80}\n")
    
    def search_by_category(self, category: str, limit: int = 20) -> List[Dict]:
        """Search documents by category."""
        try:
            result = self.supabase.table('documents')\
                .select('*')\
                .eq('ai_category', category)\
                .order('importance_score', desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data
        except Exception as e:
            print(f"❌ Category search failed: {e}")
            return []
    
    def search_by_tags(self, tags: List[str], limit: int = 20) -> List[Dict]:
        """Search documents by tags."""
        try:
            result = self.supabase.table('documents')\
                .select('*')\
                .contains('tags', tags)\
                .order('importance_score', desc=True)\
                .limit(limit)\
                .execute()
            
            return result.data
        except Exception as e:
            print(f"❌ Tag search failed: {e}")
            return []
    
    def get_document_by_id(self, document_id: str) -> Optional[Dict]:
        """Retrieve a specific document by ID."""
        try:
            result = self.supabase.table('documents')\
                .select('*')\
                .eq('id', document_id)\
                .execute()
            
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"❌ Error retrieving document: {e}")
            return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python search_engine.py \"your search query\"")
        print("\nExamples:")
        print('  python search_engine.py "find my 2024 tesla registration"')
        print('  python search_engine.py "show me tax documents from 2023"')
        print('  python search_engine.py "insurance policy for my car"')
        sys.exit(1)
    
    query = ' '.join(sys.argv[1:])
    
    engine = SearchEngine()
    results = engine.search(query)
    engine.display_results(results)
    
    # Offer to open a result
    if results and sys.stdin.isatty():
        try:
            choice = input("\nEnter result number to view full details (or press Enter to skip): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(results):
                    doc = results[idx]
                    print(f"\n{'='*80}")
                    print(f"FULL DOCUMENT DETAILS")
                    print(f"{'='*80}\n")
                    print(json.dumps(doc, indent=2, default=str))
        except KeyboardInterrupt:
            print("\n")


if __name__ == "__main__":
    main()
