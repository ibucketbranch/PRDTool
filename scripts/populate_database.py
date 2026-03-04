#!/usr/bin/env python3
"""
Database Population Script
Populates Supabase database with parsed conversation data and analysis.
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List

try:
    from supabase import create_client, Client
except ImportError:
    print("supabase-py not installed. Install with: pip install supabase")
    sys.exit(1)


class DatabasePopulator:
    def __init__(self, supabase_url: str = "http://127.0.0.1:54321", 
                 supabase_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"):
        """
        Initialize Supabase client.
        Default values are for local Supabase instance.
        """
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def populate_participants(self, participants: Dict[str, str]) -> Dict[str, str]:
        """Create participant records and return mapping of participant_id to UUID."""
        participant_map = {}
        
        for identifier, name in participants.items():
            # Check if participant already exists
            existing = self.supabase.table('participants').select('*').eq('identifier', identifier).execute()
            
            if existing.data:
                participant_id = existing.data[0]['id']
            else:
                result = self.supabase.table('participants').insert({
                    'name': name,
                    'identifier': identifier
                }).execute()
                participant_id = result.data[0]['id']
            
            participant_map[identifier] = participant_id
        
        return participant_map
    
    def populate_messages(self, messages: List[Dict], participant_map: Dict[str, str]) -> List[str]:
        """Insert messages into database and return list of message UUIDs."""
        message_ids = []
        
        for idx, msg in enumerate(messages):
            participant_uuid = participant_map.get(msg.get('participant_id'))
            if not participant_uuid:
                continue
            
            message_data = {
                'participant_id': participant_uuid,
                'message_text': msg['text'],
                'message_date': msg.get('date'),
                'message_order': idx + 1,
                'source_page': msg.get('page', None)
            }
            
            result = self.supabase.table('messages').insert(message_data).execute()
            message_ids.append(result.data[0]['id'])
        
        return message_ids
    
    def populate_sentiment(self, messages: List[Dict], message_ids: List[str], 
                          sentiment_data: List[Dict]) -> None:
        """Populate message sentiment data."""
        for idx, (msg_id, sentiment) in enumerate(zip(message_ids, sentiment_data)):
            if idx < len(messages):
                self.supabase.table('message_sentiment').insert({
                    'message_id': msg_id,
                    'sentiment_score': sentiment.get('sentiment_score', 0),
                    'emotional_tone': sentiment.get('emotional_tone', []),
                    'intensity': sentiment.get('intensity', 0)
                }).execute()
    
    def populate_participant_analysis(self, analysis: Dict, participant_map: Dict[str, str]) -> None:
        """Populate participant analysis data."""
        for participant_id, analysis_data in analysis.items():
            participant_uuid = participant_map.get(participant_id)
            if not participant_uuid or not analysis_data:
                continue
            
            # Communication style analysis
            self.supabase.table('participant_analysis').insert({
                'participant_id': participant_uuid,
                'analysis_type': 'communication_style',
                'analysis_text': f"Communication style: {analysis_data.get('communication_style', 'unknown')}. "
                               f"Average message length: {analysis_data.get('avg_message_length', 0)} characters. "
                               f"Total messages: {analysis_data.get('message_count', 0)}.",
                'key_insights': analysis_data.get('key_insights', []),
                'concerns': analysis_data.get('concerns', []),
                'strengths': analysis_data.get('strengths', [])
            }).execute()
            
            # Emotional patterns
            if analysis_data.get('emotional_patterns'):
                self.supabase.table('participant_analysis').insert({
                    'participant_id': participant_uuid,
                    'analysis_type': 'emotional_patterns',
                    'analysis_text': f"Emotional patterns: {', '.join(analysis_data.get('emotional_patterns', {}).keys())}. "
                                   f"Average sentiment: {analysis_data.get('avg_sentiment', 0)}.",
                    'key_insights': [f"Sentiment score: {analysis_data.get('avg_sentiment', 0)}"]
                }).execute()
    
    def populate_relationship_analysis(self, relationship_analysis: Dict, 
                                       date_range: Dict) -> None:
        """Populate relationship analysis data."""
        survival = relationship_analysis.get('survival_assessment', {})
        
        self.supabase.table('relationship_analysis').insert({
            'analysis_type': 'comprehensive',
            'analysis_text': f"Comprehensive relationship analysis. "
                           f"Communication balance: Participant 1: {relationship_analysis.get('communication_balance', {}).get('participant_1_ratio', 0)}, "
                           f"Participant 2: {relationship_analysis.get('communication_balance', {}).get('participant_2_ratio', 0)}. "
                           f"Overall sentiment: {relationship_analysis.get('sentiment_dynamics', {}).get('overall_avg', 0)}. "
                           f"Conflict ratio: {relationship_analysis.get('conflict_indicators', {}).get('conflict_ratio', 0)}. "
                           f"Resolution ratio: {relationship_analysis.get('resolution_indicators', {}).get('resolution_ratio', 0)}.",
            'key_insights': relationship_analysis.get('key_insights', []),
            'red_flags': relationship_analysis.get('red_flags', []),
            'positive_indicators': relationship_analysis.get('positive_indicators', []),
            'survival_probability': survival.get('survival_probability', 0.5),
            'survival_assessment': survival.get('assessment', 'uncertain'),
            'time_period_start': date_range.get('start'),
            'time_period_end': date_range.get('end')
        }).execute()
    
    def populate_themes(self, themes: List[Dict]) -> Dict[str, str]:
        """Populate themes and return mapping of theme_name to UUID."""
        theme_map = {}
        
        for theme in themes:
            # Check if theme exists
            existing = self.supabase.table('themes').select('*').eq('theme_name', theme['theme_name']).execute()
            
            if existing.data:
                theme_id = existing.data[0]['id']
            else:
                result = self.supabase.table('themes').insert({
                    'theme_name': theme['theme_name'],
                    'description': theme.get('description', ''),
                    'frequency': theme.get('frequency', 0)
                }).execute()
                theme_id = result.data[0]['id']
            
            theme_map[theme['theme_name']] = theme_id
        
        return theme_map
    
    def populate_all(self, conversation_data: Dict, analysis_data: Dict) -> None:
        """Populate all database tables with conversation and analysis data."""
        print("Populating participants...")
        participant_map = self.populate_participants(conversation_data.get('participants', {}))
        print(f"Created {len(participant_map)} participants")
        
        print("Populating messages...")
        messages = conversation_data.get('messages', [])
        message_ids = self.populate_messages(messages, participant_map)
        print(f"Inserted {len(message_ids)} messages")
        
        print("Populating sentiment data...")
        # Generate sentiment for messages if not already in analysis
        from analyze_conversation import ConversationAnalyzer
        analyzer = ConversationAnalyzer(conversation_data)
        sentiment_data = [analyzer.analyze_sentiment(msg['text']) for msg in messages]
        self.populate_sentiment(messages, message_ids, sentiment_data)
        print("Sentiment data populated")
        
        print("Populating participant analysis...")
        participant_analysis = analysis_data.get('participants', {})
        self.populate_participant_analysis(participant_analysis, participant_map)
        print("Participant analysis populated")
        
        print("Populating relationship analysis...")
        relationship_analysis = analysis_data.get('relationship', {})
        date_range = conversation_data.get('date_range', {})
        self.populate_relationship_analysis(relationship_analysis, date_range)
        print("Relationship analysis populated")
        
        print("Populating themes...")
        themes = analysis_data.get('themes', [])
        theme_map = self.populate_themes(themes)
        print(f"Created {len(theme_map)} themes")
        
        print("\nDatabase population complete!")
        print(f"\nSummary:")
        print(f"  Participants: {len(participant_map)}")
        print(f"  Messages: {len(message_ids)}")
        print(f"  Themes: {len(theme_map)}")
        print(f"  Survival Assessment: {relationship_analysis.get('survival_assessment', {}).get('assessment', 'N/A')}")
        print(f"  Survival Probability: {relationship_analysis.get('survival_assessment', {}).get('survival_probability', 'N/A')}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python populate_database.py <conversation_json> <analysis_json>")
        print("\nExample:")
        print("  python populate_database.py conversation_data.json analysis_results.json")
        sys.exit(1)
    
    conversation_file = sys.argv[1]
    analysis_file = sys.argv[2]
    
    # Check if Supabase is running
    print("Connecting to Supabase...")
    try:
        populator = DatabasePopulator()
        # Test connection
        populator.supabase.table('participants').select('count').execute()
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        print("\nMake sure Supabase is running locally:")
        print("  supabase start")
        sys.exit(1)
    
    print(f"Loading conversation data from: {conversation_file}")
    with open(conversation_file, 'r', encoding='utf-8') as f:
        conversation_data = json.load(f)
    
    print(f"Loading analysis data from: {analysis_file}")
    with open(analysis_file, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)
    
    populator.populate_all(conversation_data, analysis_data)


if __name__ == "__main__":
    main()
