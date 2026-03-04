#!/usr/bin/env python3
"""
Conversation Analysis Script
Performs therapist-style analysis on the conversation data.
"""

import json
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import Counter, defaultdict
import re

try:
    from textblob import TextBlob
except ImportError:
    print("TextBlob not installed. Install with: pip install textblob")
    print("Note: Sentiment analysis will be simplified without TextBlob")
    TextBlob = None


class ConversationAnalyzer:
    def __init__(self, conversation_data: Dict):
        self.data = conversation_data
        self.participants = conversation_data.get('participants', {})
        self.messages = conversation_data.get('messages', [])
        self.analysis = {
            'participants': {},
            'relationship': {},
            'themes': [],
            'timeline': [],
            'survival_assessment': {}
        }
    
    def analyze_sentiment(self, text: str) -> Dict:
        """Analyze sentiment of a message."""
        if TextBlob:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            subjectivity = blob.sentiment.subjectivity  # 0 to 1
        else:
            # Simple keyword-based sentiment
            positive_words = ['love', 'happy', 'great', 'wonderful', 'thanks', 'sorry', 'miss', 'care']
            negative_words = ['hate', 'angry', 'frustrated', 'upset', 'disappointed', 'hurt', 'wrong']
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            if positive_count + negative_count == 0:
                polarity = 0
            else:
                polarity = (positive_count - negative_count) / (positive_count + negative_count)
            subjectivity = 0.5
        
        # Determine emotional tone
        emotions = []
        text_lower = text.lower()
        
        emotion_keywords = {
            'anger': ['angry', 'mad', 'furious', 'rage', 'hate', 'frustrated'],
            'sadness': ['sad', 'depressed', 'hurt', 'crying', 'upset', 'disappointed'],
            'joy': ['happy', 'excited', 'love', 'great', 'wonderful', 'amazing'],
            'fear': ['scared', 'afraid', 'worried', 'anxious', 'nervous'],
            'guilt': ['sorry', 'guilty', 'regret', 'apologize'],
            'gratitude': ['thanks', 'thank you', 'appreciate', 'grateful']
        }
        
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                emotions.append(emotion)
        
        return {
            'sentiment_score': round(polarity, 3),
            'emotional_tone': emotions if emotions else ['neutral'],
            'intensity': abs(polarity)
        }
    
    def analyze_participant(self, participant_id: str) -> Dict:
        """Analyze individual participant's communication patterns."""
        participant_messages = [m for m in self.messages if m.get('participant_id') == participant_id]
        
        if not participant_messages:
            return {}
        
        # Communication style analysis
        avg_message_length = sum(len(m['text']) for m in participant_messages) / len(participant_messages)
        total_words = sum(len(m['text'].split()) for m in participant_messages)
        
        # Sentiment analysis
        sentiments = [self.analyze_sentiment(m['text']) for m in participant_messages]
        avg_sentiment = sum(s['sentiment_score'] for s in sentiments) / len(sentiments)
        
        # Emotional patterns
        all_emotions = []
        for s in sentiments:
            all_emotions.extend(s['emotional_tone'])
        emotion_frequency = Counter(all_emotions)
        
        # Communication frequency
        message_count = len(participant_messages)
        
        # Key phrases and topics
        common_words = self._extract_common_words([m['text'] for m in participant_messages])
        
        # Identify communication style
        communication_style = self._identify_communication_style(participant_messages, avg_sentiment)
        
        # Identify concerns and strengths
        concerns = self._identify_concerns(participant_messages, sentiments)
        strengths = self._identify_strengths(participant_messages, sentiments)
        
        return {
            'communication_style': communication_style,
            'avg_message_length': round(avg_message_length, 2),
            'total_words': total_words,
            'message_count': message_count,
            'avg_sentiment': round(avg_sentiment, 3),
            'emotional_patterns': dict(emotion_frequency),
            'common_words': common_words[:10],
            'concerns': concerns,
            'strengths': strengths,
            'key_insights': self._generate_insights(participant_messages, communication_style, avg_sentiment)
        }
    
    def _identify_communication_style(self, messages: List[Dict], avg_sentiment: float) -> str:
        """Identify the participant's communication style."""
        styles = []
        
        avg_length = sum(len(m['text']) for m in messages) / len(messages)
        if avg_length > 200:
            styles.append("verbose")
        elif avg_length < 50:
            styles.append("concise")
        
        # Check for question marks
        question_count = sum(1 for m in messages if '?' in m['text'])
        if question_count / len(messages) > 0.3:
            styles.append("inquisitive")
        
        # Check for exclamation marks
        exclamation_count = sum(1 for m in messages if '!' in m['text'])
        if exclamation_count / len(messages) > 0.2:
            styles.append("expressive")
        
        # Check sentiment
        if avg_sentiment > 0.2:
            styles.append("positive")
        elif avg_sentiment < -0.2:
            styles.append("negative")
        else:
            styles.append("neutral")
        
        return ", ".join(styles) if styles else "balanced"
    
    def _identify_concerns(self, messages: List[Dict], sentiments: List[Dict]) -> List[str]:
        """Identify potential concerns about the participant."""
        concerns = []
        
        # High negative sentiment
        negative_ratio = sum(1 for s in sentiments if s['sentiment_score'] < -0.3) / len(sentiments)
        if negative_ratio > 0.4:
            concerns.append("High frequency of negative communication")
        
        # Anger patterns
        anger_count = sum(1 for s in sentiments if 'anger' in s['emotional_tone'])
        if anger_count / len(sentiments) > 0.2:
            concerns.append("Frequent expressions of anger")
        
        # Defensive language
        defensive_words = ['always', 'never', 'you always', 'you never', 'why do you']
        defensive_count = sum(1 for m in messages 
                            if any(word in m['text'].lower() for word in defensive_words))
        if defensive_count > len(messages) * 0.1:
            concerns.append("Defensive communication patterns")
        
        # Avoidance
        if len(messages) < 10:  # Very few messages
            concerns.append("Limited engagement in conversation")
        
        return concerns
    
    def _identify_strengths(self, messages: List[Dict], sentiments: List[Dict]) -> List[str]:
        """Identify strengths in the participant's communication."""
        strengths = []
        
        # Positive sentiment
        positive_ratio = sum(1 for s in sentiments if s['sentiment_score'] > 0.3) / len(sentiments)
        if positive_ratio > 0.4:
            strengths.append("Generally positive communication")
        
        # Apology/accountability
        apology_words = ['sorry', 'apologize', 'my fault', 'i was wrong']
        apology_count = sum(1 for m in messages 
                          if any(word in m['text'].lower() for word in apology_words))
        if apology_count > 0:
            strengths.append("Shows accountability and willingness to apologize")
        
        # Gratitude
        gratitude_words = ['thank', 'thanks', 'appreciate', 'grateful']
        gratitude_count = sum(1 for m in messages 
                            if any(word in m['text'].lower() for word in gratitude_words))
        if gratitude_count > 0:
            strengths.append("Expresses gratitude")
        
        # Engagement
        if len(messages) > 50:
            strengths.append("High level of engagement in conversation")
        
        return strengths
    
    def _generate_insights(self, messages: List[Dict], style: str, sentiment: float) -> List[str]:
        """Generate key insights about the participant."""
        insights = []
        
        insights.append(f"Communication style: {style}")
        insights.append(f"Average sentiment: {'positive' if sentiment > 0.1 else 'negative' if sentiment < -0.1 else 'neutral'}")
        
        # Response patterns
        if len(messages) > 20:
            insights.append("Active participant in the conversation")
        
        return insights
    
    def _extract_common_words(self, texts: List[str], min_length: int = 4) -> List[str]:
        """Extract most common words (excluding common stop words)."""
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'on', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 
                     'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                     'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'}
        
        all_words = []
        for text in texts:
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            all_words.extend([w for w in words if len(w) >= min_length and w not in stop_words])
        
        word_freq = Counter(all_words)
        return [word for word, count in word_freq.most_common(20)]
    
    def analyze_relationship(self) -> Dict:
        """Analyze the relationship dynamics between both participants."""
        if len(self.participants) < 2:
            return {}
        
        participant_ids = list(self.participants.keys())
        p1_id, p2_id = participant_ids[0], participant_ids[1]
        
        p1_messages = [m for m in self.messages if m.get('participant_id') == p1_id]
        p2_messages = [m for m in self.messages if m.get('participant_id') == p2_id]
        
        # Communication balance
        message_ratio = len(p1_messages) / len(p2_messages) if p2_messages else 1
        
        # Sentiment trends
        p1_sentiments = [self.analyze_sentiment(m['text']) for m in p1_messages]
        p2_sentiments = [self.analyze_sentiment(m['text']) for m in p2_messages]
        
        p1_avg_sentiment = sum(s['sentiment_score'] for s in p1_sentiments) / len(p1_sentiments) if p1_sentiments else 0
        p2_avg_sentiment = sum(s['sentiment_score'] for s in p2_sentiments) / len(p2_sentiments) if p2_sentiments else 0
        
        # Conflict indicators
        conflict_keywords = ['fight', 'argument', 'disagree', 'wrong', 'problem', 'issue', 'upset', 'angry']
        conflict_messages = [m for m in self.messages 
                           if any(keyword in m['text'].lower() for keyword in conflict_keywords)]
        conflict_ratio = len(conflict_messages) / len(self.messages) if self.messages else 0
        
        # Resolution indicators
        resolution_keywords = ['sorry', 'apologize', 'forgive', 'understand', 'work', 'together', 'love']
        resolution_messages = [m for m in self.messages 
                             if any(keyword in m['text'].lower() for keyword in resolution_keywords)]
        resolution_ratio = len(resolution_messages) / len(self.messages) if self.messages else 0
        
        # Communication patterns
        communication_dynamics = self._analyze_communication_dynamics(p1_messages, p2_messages)
        
        # Survival assessment
        survival_assessment = self._assess_relationship_survival(
            p1_avg_sentiment, p2_avg_sentiment, conflict_ratio, resolution_ratio, 
            communication_dynamics
        )
        
        return {
            'communication_balance': {
                'participant_1_ratio': round(message_ratio / (1 + message_ratio), 2),
                'participant_2_ratio': round(1 / (1 + message_ratio), 2),
                'balanced': 0.4 < message_ratio < 0.6
            },
            'sentiment_dynamics': {
                'participant_1_avg': round(p1_avg_sentiment, 3),
                'participant_2_avg': round(p2_avg_sentiment, 3),
                'overall_avg': round((p1_avg_sentiment + p2_avg_sentiment) / 2, 3)
            },
            'conflict_indicators': {
                'conflict_ratio': round(conflict_ratio, 3),
                'conflict_message_count': len(conflict_messages),
                'high_conflict': conflict_ratio > 0.2
            },
            'resolution_indicators': {
                'resolution_ratio': round(resolution_ratio, 3),
                'resolution_message_count': len(resolution_messages),
                'good_resolution': resolution_ratio > 0.15
            },
            'communication_dynamics': communication_dynamics,
            'survival_assessment': survival_assessment,
            'key_insights': self._generate_relationship_insights(
                p1_avg_sentiment, p2_avg_sentiment, conflict_ratio, resolution_ratio
            ),
            'red_flags': self._identify_red_flags(conflict_ratio, p1_avg_sentiment, p2_avg_sentiment),
            'positive_indicators': self._identify_positive_indicators(resolution_ratio, p1_avg_sentiment, p2_avg_sentiment)
        }
    
    def _analyze_communication_dynamics(self, p1_messages: List[Dict], p2_messages: List[Dict]) -> Dict:
        """Analyze how the two participants communicate with each other."""
        dynamics = {
            'response_patterns': 'unknown',
            'engagement_level': 'unknown',
            'topic_consistency': 'unknown'
        }
        
        # Response patterns (simplified - would need timestamps for accurate analysis)
        if len(p1_messages) > 0 and len(p2_messages) > 0:
            dynamics['engagement_level'] = 'high' if len(self.messages) > 100 else 'moderate' if len(self.messages) > 50 else 'low'
        
        return dynamics
    
    def _assess_relationship_survival(self, p1_sentiment: float, p2_sentiment: float, 
                                     conflict_ratio: float, resolution_ratio: float,
                                     dynamics: Dict) -> Dict:
        """Assess whether the relationship likely survived."""
        # Scoring system
        score = 0.5  # Start neutral
        
        # Sentiment factors
        avg_sentiment = (p1_sentiment + p2_sentiment) / 2
        if avg_sentiment > 0.2:
            score += 0.2
        elif avg_sentiment < -0.2:
            score -= 0.2
        
        # Conflict factors
        if conflict_ratio > 0.3:
            score -= 0.3
        elif conflict_ratio < 0.1:
            score += 0.1
        
        # Resolution factors
        if resolution_ratio > 0.2:
            score += 0.2
        elif resolution_ratio < 0.05:
            score -= 0.1
        
        # Engagement
        if dynamics.get('engagement_level') == 'high':
            score += 0.1
        
        # Clamp score
        score = max(0, min(1, score))
        
        # Determine assessment
        if score > 0.6:
            assessment = "likely_survived"
            assessment_text = "The relationship shows positive indicators and likely survived."
        elif score < 0.4:
            assessment = "likely_ended"
            assessment_text = "The relationship shows concerning patterns and likely ended."
        else:
            assessment = "uncertain"
            assessment_text = "The relationship shows mixed signals; outcome is uncertain."
        
        return {
            'survival_probability': round(score, 3),
            'assessment': assessment,
            'assessment_text': assessment_text,
            'factors': {
                'sentiment': round(avg_sentiment, 3),
                'conflict_level': round(conflict_ratio, 3),
                'resolution_ability': round(resolution_ratio, 3)
            }
        }
    
    def _generate_relationship_insights(self, p1_sentiment: float, p2_sentiment: float,
                                       conflict_ratio: float, resolution_ratio: float) -> List[str]:
        """Generate key insights about the relationship."""
        insights = []
        
        sentiment_diff = abs(p1_sentiment - p2_sentiment)
        if sentiment_diff > 0.3:
            insights.append("Significant sentiment imbalance between participants")
        else:
            insights.append("Relatively balanced sentiment between participants")
        
        if conflict_ratio > 0.2:
            insights.append("High frequency of conflict-related communication")
        elif conflict_ratio < 0.1:
            insights.append("Low conflict frequency")
        
        if resolution_ratio > 0.15:
            insights.append("Good evidence of conflict resolution attempts")
        else:
            insights.append("Limited evidence of explicit resolution attempts")
        
        return insights
    
    def _identify_red_flags(self, conflict_ratio: float, p1_sentiment: float, p2_sentiment: float) -> List[str]:
        """Identify red flags in the relationship."""
        red_flags = []
        
        if conflict_ratio > 0.3:
            red_flags.append("Very high conflict frequency")
        
        if p1_sentiment < -0.3 or p2_sentiment < -0.3:
            red_flags.append("Persistently negative sentiment from one or both participants")
        
        if (p1_sentiment < -0.2 and p2_sentiment < -0.2):
            red_flags.append("Both participants showing negative sentiment")
        
        return red_flags
    
    def _identify_positive_indicators(self, resolution_ratio: float, p1_sentiment: float, p2_sentiment: float) -> List[str]:
        """Identify positive indicators in the relationship."""
        positive = []
        
        if resolution_ratio > 0.15:
            positive.append("Strong evidence of conflict resolution and repair attempts")
        
        if p1_sentiment > 0.2 and p2_sentiment > 0.2:
            positive.append("Both participants maintain positive sentiment")
        
        if abs(p1_sentiment - p2_sentiment) < 0.2:
            positive.append("Balanced emotional engagement from both participants")
        
        return positive
    
    def identify_themes(self) -> List[Dict]:
        """Identify recurring themes in the conversation."""
        all_text = ' '.join([m['text'] for m in self.messages])
        
        # Common relationship themes
        theme_keywords = {
            'Communication Issues': ['talk', 'discuss', 'communication', 'listen', 'understand'],
            'Conflict': ['fight', 'argument', 'disagree', 'upset', 'angry', 'mad'],
            'Apology/Forgiveness': ['sorry', 'apologize', 'forgive', 'forgiveness'],
            'Love/Affection': ['love', 'care', 'miss', 'hug', 'kiss'],
            'Family': ['family', 'kids', 'children', 'parent', 'mom', 'dad'],
            'Work/Career': ['work', 'job', 'career', 'boss', 'office'],
            'Money/Finances': ['money', 'pay', 'bill', 'cost', 'expensive', 'cheap'],
            'Time Together': ['together', 'date', 'time', 'spend', 'see'],
            'Health': ['health', 'sick', 'doctor', 'hospital', 'pain'],
            'Future Plans': ['future', 'plan', 'goal', 'dream', 'hope']
        }
        
        themes = []
        for theme_name, keywords in theme_keywords.items():
            count = sum(1 for keyword in keywords if keyword.lower() in all_text.lower())
            if count > 0:
                themes.append({
                    'theme_name': theme_name,
                    'frequency': count,
                    'description': f"Discussions related to {theme_name.lower()}"
                })
        
        return sorted(themes, key=lambda x: x['frequency'], reverse=True)
    
    def analyze(self) -> Dict:
        """Run complete analysis."""
        print("Analyzing participants...")
        for participant_id, participant_name in self.participants.items():
            self.analysis['participants'][participant_id] = self.analyze_participant(participant_id)
        
        print("Analyzing relationship dynamics...")
        self.analysis['relationship'] = self.analyze_relationship()
        
        print("Identifying themes...")
        self.analysis['themes'] = self.identify_themes()
        
        print("Analysis complete!")
        return self.analysis


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_conversation.py <conversation_json> [output_json]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "analysis_results.json"
    
    print(f"Loading conversation data from: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        conversation_data = json.load(f)
    
    analyzer = ConversationAnalyzer(conversation_data)
    analysis = analyzer.analyze()
    
    # Save results
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, default=str)
    
    print(f"\nAnalysis saved to: {output_file}")
    print(f"\nSurvival Assessment: {analysis['relationship'].get('survival_assessment', {}).get('assessment_text', 'N/A')}")
    print(f"Survival Probability: {analysis['relationship'].get('survival_assessment', {}).get('survival_probability', 'N/A')}")


if __name__ == "__main__":
    main()
