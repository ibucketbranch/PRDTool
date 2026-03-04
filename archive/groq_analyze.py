#!/usr/bin/env python3
"""Groq-powered conversation analysis - isolated for this project"""
import json, sys, os
from datetime import datetime

try:
    from groq import Groq
except ImportError:
    print("Install: pip install groq")
    sys.exit(1)

class GroqAnalyzer:
    def __init__(self, data, api_key=None):
        self.data = data
        self.participants = data.get('participants', {})
        self.messages = data.get('messages', [])
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
    
    def ask_groq(self, prompt, max_tokens=2000):
        try:
            response = self.client.chat.completions.create(
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
            return f"Error: {e}"
    
    def analyze_participant(self, pid):
        msgs = [m for m in self.messages if m.get('participant_id') == pid]
        name = self.participants.get(pid, pid)
        if not msgs: return {}
        
        print(f"Analyzing {name} ({len(msgs)} messages)...")
        sample = msgs[::max(1, len(msgs)//50)][:50]
        text = "\n".join([f"{m.get('raw_date','?')}: {m['text'][:150]}" for m in sample])
        
        prompt = f"""Analyze {name}'s communication ({len(msgs)} messages):

{text}

Provide JSON: {{"style": "...", "emotions": [], "strengths": [], "concerns": [], "insights": []}}"""
        
        result = self.ask_groq(prompt, 1500)
        try:
            return json.loads(result)
        except:
            return {"analysis": result, "message_count": len(msgs)}
    
    def analyze_relationship(self):
        print("Analyzing relationship...")
        p1, p2 = list(self.participants.values())
        sample = self.messages[::max(1, len(self.messages)//100)][:100]
        conv = "\n".join([f"{self.participants.get(m['participant_id'],'?')}: {m['text'][:120]}" for m in sample])
        
        dates = [m['date'] for m in self.messages if m.get('date')]
        duration = f"{min(dates).year}-{max(dates).year}" if dates else "?"
        
        prompt = f"""Therapist analysis of {p1} & {p2} ({len(self.messages)} messages, {duration}):

{conv}

Provide JSON: {{
  "dynamics": "...",
  "conflicts": "...",
  "positives": [],
  "red_flags": [],
  "survival": {{
    "probability": 0-100,
    "verdict": "survived/ended/uncertain",
    "reasoning": "..."
  }}
}}"""
        
        result = self.ask_groq(prompt, 2000)
        try:
            data = json.loads(result)
            survival = data.get('survival', {})
            prob = survival.get('probability', 50) / 100
            return {
                **data,
                'survival_assessment': {
                    'survival_probability': prob,
                    'assessment': survival.get('verdict', 'uncertain'),
                    'assessment_text': survival.get('reasoning', ''),
                    'full_analysis': result
                }
            }
        except:
            return {"full_analysis": result, "survival_assessment": {"assessment": "uncertain", "assessment_text": result}}
    
    def analyze(self):
        print(f"\nAnalyzing {len(self.messages)} messages between {list(self.participants.values())}\n")
        analysis = {
            'participants': {pid: self.analyze_participant(pid) for pid in self.participants},
            'relationship': self.analyze_relationship()
        }
        print("\n✓ Complete!")
        return analysis

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python groq_analyze.py <conversation.json> [output.json]")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as f:
        data = json.load(f)
    
    analyzer = GroqAnalyzer(data)
    result = analyzer.analyze()
    
    out_file = sys.argv[2] if len(sys.argv) > 2 else "analysis_groq.json"
    with open(out_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    survival = result['relationship']['survival_assessment']
    print(f"\n{'='*60}")
    print(f"VERDICT: {survival['assessment'].upper()}")
    print(f"PROBABILITY: {survival['survival_probability']*100:.0f}%")
    print(f"\n{survival['assessment_text'][:500]}")
    print(f"{'='*60}\n")
    print(f"Saved to: {out_file}")
