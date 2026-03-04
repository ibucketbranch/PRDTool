#!/usr/bin/env python3
"""
Gemini-powered conversation analysis - Primary AI for this project
Uses Google's Gemini API for deep psychological analysis
"""

import json
import sys
import os
from datetime import datetime

try:
    import google.generativeai as genai
except ImportError:
    print("Install: pip install google-generativeai")
    sys.exit(1)


class GeminiAnalyzer:
    def __init__(self, data, api_key=None):
        self.data = data
        self.participants = data.get('participants', {})
        self.messages = data.get('messages', [])
        
        # Initialize Gemini
        api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set. Set it with: export GEMINI_API_KEY='your-key'")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def ask_gemini(self, prompt, max_tokens=2000):
        """Send prompt to Gemini and get response."""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'max_output_tokens': max_tokens,
                }
            )
            return response.text
        except Exception as e:
            print(f"Gemini error: {e}")
            return f"Error: {e}"
    
    def analyze_participant(self, pid):
        """Analyze individual participant using Gemini."""
        msgs = [m for m in self.messages if m.get('participant_id') == pid]
        name = self.participants.get(pid, pid)
        if not msgs:
            return {}
        
        print(f"🤖 Gemini analyzing {name} ({len(msgs)} messages)...")
        
        # Sample messages
        sample = msgs[::max(1, len(msgs)//50)][:50]
        text = "\n".join([f"{m.get('raw_date','?')}: {m['text'][:150]}" for m in sample])
        
        prompt = f"""As an experienced relationship therapist, analyze {name}'s communication patterns from these {len(msgs)} messages:

{text}

Provide a detailed analysis in JSON format:
{{
  "communication_style": "brief description of their communication style",
  "emotional_patterns": ["list", "of", "emotional", "patterns"],
  "strengths": ["communication", "strengths"],
  "concerns": ["potential", "concerns"],
  "key_insights": ["important", "psychological", "insights"]
}}"""
        
        result = self.ask_gemini(prompt, 1500)
        
        try:
            # Extract JSON from response (Gemini sometimes adds markdown)
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0]
            elif '```' in result:
                result = result.split('```')[1].split('```')[0]
            
            analysis = json.loads(result.strip())
            analysis['message_count'] = len(msgs)
            return analysis
        except:
            return {
                "analysis": result,
                "message_count": len(msgs),
                "communication_style": "See full analysis",
                "key_insights": [result[:500]]
            }
    
    def analyze_relationship(self):
        """Analyze relationship dynamics using Gemini."""
        print("🤖 Gemini analyzing relationship dynamics...")
        
        p1, p2 = list(self.participants.values())
        sample = self.messages[::max(1, len(self.messages)//100)][:100]
        conv = "\n".join([
            f"{self.participants.get(m['participant_id'],'?')}: {m['text'][:120]}"
            for m in sample
        ])
        
        dates = [m['date'] for m in self.messages if m.get('date')]
        duration = f"{min(dates).year}-{max(dates).year}" if dates else "?"
        
        prompt = f"""As an experienced marriage and relationship therapist, analyze this conversation between {p1} and {p2}.

Total messages: {len(self.messages)}
Time period: {duration}

Sample conversation:
{conv}

Provide a comprehensive clinical assessment in JSON format:
{{
  "communication_dynamics": "description of how they interact",
  "conflict_resolution": "how they handle disagreements",
  "emotional_connection": "assessment of emotional intimacy",
  "red_flags": ["concerning", "patterns"],
  "positive_indicators": ["healthy", "patterns"],
  "survival_assessment": {{
    "probability": 0-100,
    "verdict": "survived/ended/uncertain",
    "reasoning": "clinical reasoning for the assessment based on Gottman's research and relationship psychology"
  }}
}}

Focus on patterns related to Gottman's Four Horsemen (criticism, contempt, defensiveness, stonewalling) and positive indicators like repair attempts, fondness, and admiration."""
        
        result = self.ask_gemini(prompt, 2000)
        
        try:
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0]
            elif '```' in result:
                result = result.split('```')[1].split('```')[0]
            
            data = json.loads(result.strip())
            survival = data.get('survival_assessment', {})
            prob = survival.get('probability', 50)
            if isinstance(prob, str):
                prob = float(prob.rstrip('%'))
            prob = prob / 100 if prob > 1 else prob
            
            return {
                **data,
                'survival_assessment': {
                    'survival_probability': prob,
                    'assessment': survival.get('verdict', 'uncertain'),
                    'assessment_text': survival.get('reasoning', ''),
                    'full_analysis': result
                }
            }
        except Exception as e:
            print(f"Parse error: {e}")
            return {
                "full_analysis": result,
                "survival_assessment": {
                    "survival_probability": 0.5,
                    "assessment": "uncertain",
                    "assessment_text": result
                }
            }
    
    def identify_themes(self):
        """Identify themes using Gemini."""
        print("🤖 Gemini identifying conversation themes...")
        
        sample_size = min(200, len(self.messages))
        step = max(1, len(self.messages) // sample_size)
        sample = self.messages[::step][:100]
        
        text = "\n".join([m['text'][:100] for m in sample])
        
        prompt = f"""Analyze these {len(self.messages)} messages and identify the 10 most significant recurring themes or topics.

Sample messages:
{text}

Provide as JSON array:
[
  {{"theme": "Theme Name", "description": "brief description", "significance": "high/medium/low"}},
  ...
]"""
        
        result = self.ask_gemini(prompt, 1000)
        
        try:
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0]
            elif '```' in result:
                result = result.split('```')[1].split('```')[0]
            
            themes = json.loads(result.strip())
            return themes if isinstance(themes, list) else []
        except:
            return [{'theme': 'See full analysis', 'description': result[:200]}]
    
    def analyze(self):
        """Run complete Gemini-powered analysis."""
        print(f"\n{'='*60}")
        print("🤖 GEMINI AI CONVERSATION ANALYSIS")
        print(f"{'='*60}\n")
        print(f"Total messages: {len(self.messages)}")
        print(f"Participants: {list(self.participants.values())}\n")
        
        analysis = {
            'participants': {},
            'relationship': {},
            'themes': []
        }
        
        # Analyze each participant
        for pid, name in self.participants.items():
            analysis['participants'][pid] = self.analyze_participant(pid)
        
        # Analyze relationship
        analysis['relationship'] = self.analyze_relationship()
        
        # Identify themes
        analysis['themes'] = self.identify_themes()
        
        print("\n✓ Analysis complete!")
        return analysis


def main():
    if len(sys.argv) < 2:
        print("Usage: python gemini_analyze.py <conversation.json> [output.json] [gemini_api_key]")
        print("\nExample:")
        print("  python gemini_analyze.py conversation_data.json analysis_results.json")
        print("\nSet GEMINI_API_KEY environment variable or pass as argument")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "analysis_results.json"
    gemini_key = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"Loading: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    analyzer = GeminiAnalyzer(data, api_key=gemini_key)
    result = analyzer.analyze()
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)
    
    survival = result['relationship']['survival_assessment']
    print(f"\n{'='*60}")
    print(f"🔍 RELATIONSHIP SURVIVAL ASSESSMENT")
    print(f"{'='*60}")
    print(f"Verdict: {survival['assessment'].upper()}")
    print(f"Probability: {survival['survival_probability']*100:.0f}%")
    print(f"\n{survival['assessment_text'][:500]}...")
    print(f"{'='*60}\n")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
