#!/usr/bin/env python3
"""
Universal AI Analyzer with Fallback
PRIMARY: Google Gemini
FALLBACK: Groq
"""

import json
import sys
import os
from datetime import datetime

# Try Gemini first
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# Groq as backup
try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False


class UniversalAIAnalyzer:
    def __init__(self, data, gemini_key=None, groq_key=None):
        self.data = data
        self.participants = data.get('participants', {})
        self.messages = data.get('messages', [])
        self.ai_used = None
        
        # Try Gemini FIRST (primary)
        gemini_key = gemini_key or os.getenv('GEMINI_API_KEY')
        if HAS_GEMINI and gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.model = genai.GenerativeModel('gemini-1.5-pro')
                self.ai_used = 'gemini'
                print("✅ Using Gemini (PRIMARY)")
                return
            except Exception as e:
                print(f"⚠️  Gemini setup failed: {e}")
        
        # Fall back to Groq only if Gemini unavailable
        groq_key = groq_key or os.getenv('GROQ_API_KEY')
        if HAS_GROQ and groq_key:
            try:
                self.groq_client = Groq(api_key=groq_key)
                self.ai_used = 'groq'
                print("⚠️  Using Groq (FALLBACK - Gemini not available)")
                return
            except Exception as e:
                print(f"⚠️  Groq setup failed: {e}")
        
        raise ValueError("❌ No AI available! Set GEMINI_API_KEY (primary) or GROQ_API_KEY (backup)")
    
    def ask_ai(self, prompt, max_tokens=2000):
        """Send prompt to AI (Gemini first, Groq as fallback)."""
        if self.ai_used == 'gemini':
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config={'temperature': 0.7, 'max_output_tokens': max_tokens}
                )
                return response.text
            except Exception as e:
                print(f"Gemini error: {e}")
                return f"Error: {e}"
        
        elif self.ai_used == 'groq':
            try:
                response = self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are an experienced relationship therapist."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Groq error: {e}")
                return f"Error: {e}"
    
    def analyze_participant(self, pid):
        """Analyze participant."""
        msgs = [m for m in self.messages if m.get('participant_id') == pid]
        name = self.participants.get(pid, pid)
        if not msgs:
            return {}
        
        print(f"🤖 Analyzing {name} ({len(msgs)} messages)...")
        sample = msgs[::max(1, len(msgs)//50)][:50]
        text = "\n".join([f"{m.get('raw_date','?')}: {m['text'][:150]}" for m in sample])
        
        prompt = f"""As a relationship therapist, analyze {name}'s communication from {len(msgs)} messages:

{text}

Provide JSON:
{{
  "communication_style": "description",
  "emotional_patterns": ["patterns"],
  "strengths": ["strengths"],
  "concerns": ["concerns"],
  "key_insights": ["insights"]
}}"""
        
        result = self.ask_ai(prompt, 1500)
        
        try:
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0]
            elif '```' in result:
                result = result.split('```')[1].split('```')[0]
            analysis = json.loads(result.strip())
            analysis['message_count'] = len(msgs)
            analysis['ai_used'] = self.ai_used
            return analysis
        except:
            return {"analysis": result, "message_count": len(msgs), "ai_used": self.ai_used}
    
    def analyze_relationship(self):
        """Analyze relationship."""
        print("🤖 Analyzing relationship dynamics...")
        p1, p2 = list(self.participants.values())
        sample = self.messages[::max(1, len(self.messages)//100)][:100]
        conv = "\n".join([f"{self.participants.get(m['participant_id'],'?')}: {m['text'][:120]}" for m in sample])
        
        dates = [m['date'] for m in self.messages if m.get('date')]
        duration = f"{min(dates).year}-{max(dates).year}" if dates else "?"
        
        prompt = f"""Therapist analysis: {p1} & {p2}, {len(self.messages)} messages ({duration})

{conv}

Provide JSON:
{{
  "communication_dynamics": "...",
  "conflict_resolution": "...",
  "emotional_connection": "...",
  "red_flags": ["..."],
  "positive_indicators": ["..."],
  "survival_assessment": {{
    "probability": 0-100,
    "verdict": "survived/ended/uncertain",
    "reasoning": "clinical reasoning"
  }}
}}"""
        
        result = self.ask_ai(prompt, 2000)
        
        try:
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0]
            data = json.loads(result.strip())
            survival = data.get('survival_assessment', {})
            prob = survival.get('probability', 50)
            if isinstance(prob, str):
                prob = float(prob.rstrip('%'))
            prob = prob / 100 if prob > 1 else prob
            
            return {
                **data,
                'ai_used': self.ai_used,
                'survival_assessment': {
                    'survival_probability': prob,
                    'assessment': survival.get('verdict', 'uncertain'),
                    'assessment_text': survival.get('reasoning', ''),
                    'full_analysis': result,
                    'ai_used': self.ai_used
                }
            }
        except:
            return {"full_analysis": result, "ai_used": self.ai_used}
    
    def analyze(self):
        """Run analysis."""
        print(f"\n{'='*60}")
        print(f"🤖 AI ANALYSIS ({self.ai_used.upper()})")
        print(f"{'='*60}\n")
        
        analysis = {
            'ai_used': self.ai_used,
            'participants': {pid: self.analyze_participant(pid) for pid in self.participants},
            'relationship': self.analyze_relationship()
        }
        
        print("\n✓ Complete!")
        return analysis


def main():
    if len(sys.argv) < 2:
        print("Usage: python ai_analyze.py <conversation.json> [output.json]")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        data = json.load(f)
    
    analyzer = UniversalAIAnalyzer(data)
    result = analyzer.analyze()
    
    out = sys.argv[2] if len(sys.argv) > 2 else "analysis_results.json"
    with open(out, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    survival = result['relationship']['survival_assessment']
    print(f"\n{'='*60}")
    print(f"VERDICT: {survival['assessment'].upper()}")
    print(f"PROBABILITY: {survival['survival_probability']*100:.0f}%")
    print(f"AI: {result['ai_used'].upper()}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
