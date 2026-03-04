#!/usr/bin/env python3
"""
PDF Conversation Parser
Extracts text messages/conversations from a PDF and structures them for analysis.
"""

import sys
import re
from datetime import datetime
from typing import List, Dict, Optional
import json

try:
    import PyPDF2
    from PyPDF2 import PdfReader
except ImportError:
    print("PyPDF2 not installed. Install with: pip install PyPDF2")
    sys.exit(1)

try:
    from dateutil import parser as date_parser
except ImportError:
    print("python-dateutil not installed. Install with: pip install python-dateutil")
    sys.exit(1)


class ConversationParser:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.messages: List[Dict] = []
        self.participants: Dict[str, str] = {}  # Maps identifiers to names
        
    def extract_text_from_pdf(self) -> str:
        """Extract all text from the PDF."""
        text = ""
        try:
            reader = PdfReader(self.pdf_path)
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
        except Exception as e:
            print(f"Error reading PDF: {e}")
            sys.exit(1)
        return text
    
    def identify_participants(self, text: str) -> Dict[str, str]:
        """
        Try to identify the two participants in the conversation.
        Looks for common patterns like names, phone numbers, email addresses.
        """
        # Common patterns to identify participants
        patterns = [
            r'From:\s*([^\n]+)',
            r'To:\s*([^\n]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+):',  # Name: pattern
            r'(\+?[\d\s\-\(\)]{10,}):',  # Phone number pattern
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):',  # Email pattern
        ]
        
        participants = {}
        for pattern in patterns:
            matches = re.findall(pattern, text[:5000])  # Check first 5000 chars
            if matches:
                for match in matches[:2]:  # Take first 2 unique matches
                    if match not in participants.values():
                        identifier = f"Person_{len(participants) + 1}"
                        participants[identifier] = match.strip()
        
        # If we can't identify, use generic identifiers
        if len(participants) < 2:
            participants = {
                "Person_A": "Person A",
                "Person_B": "Person B"
            }
        
        return participants
    
    def parse_messages(self, text: str) -> List[Dict]:
        """
        Parse messages from the text.
        This is a flexible parser that tries multiple patterns.
        """
        messages = []
        
        # Split by common message separators
        # Try different patterns based on common text message formats
        
        # Pattern 1: Date/Time followed by sender and message
        pattern1 = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}[\s,]+(?:\d{1,2}:\d{2}(?:\s*[AP]M)?)?)\s*[-:]?\s*([^:\n]+?):\s*(.+?)(?=\d{1,2}[/-]\d{1,2}|$)'
        
        # Pattern 2: Sender name followed by message (no date)
        pattern2 = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|\+?[\d\s\-\(\)]{10,}|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):\s*(.+?)(?=(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|\+?[\d\s\-\(\)]{10,}|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):|$)'
        
        # Try pattern 1 first (with dates)
        matches = re.finditer(pattern1, text, re.MULTILINE | re.DOTALL)
        for match in matches:
            date_str = match.group(1).strip()
            sender = match.group(2).strip()
            message_text = match.group(3).strip()
            
            # Try to parse date
            message_date = None
            try:
                message_date = date_parser.parse(date_str, fuzzy=True)
            except:
                pass
            
            messages.append({
                'sender': sender,
                'text': message_text,
                'date': message_date,
                'raw_date': date_str
            })
        
        # If pattern 1 didn't work, try pattern 2
        if not messages:
            matches = re.finditer(pattern2, text, re.MULTILINE | re.DOTALL)
            for idx, match in enumerate(matches):
                sender = match.group(1).strip()
                message_text = match.group(2).strip()
                
                messages.append({
                    'sender': sender,
                    'text': message_text,
                    'date': None,
                    'raw_date': None
                })
        
        # If still no messages, try line-by-line parsing
        if not messages:
            lines = text.split('\n')
            current_sender = None
            current_message = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_sender and current_message:
                        messages.append({
                            'sender': current_sender,
                            'text': ' '.join(current_message),
                            'date': None,
                            'raw_date': None
                        })
                        current_message = []
                    continue
                
                # Check if line looks like a sender identifier
                if ':' in line and len(line.split(':')[0]) < 50:
                    if current_sender and current_message:
                        messages.append({
                            'sender': current_sender,
                            'text': ' '.join(current_message),
                            'date': None,
                            'raw_date': None
                        })
                    current_sender = line.split(':')[0].strip()
                    current_message = [line.split(':', 1)[1].strip()] if ':' in line else []
                else:
                    if current_sender:
                        current_message.append(line)
            
            # Add last message
            if current_sender and current_message:
                messages.append({
                    'sender': current_sender,
                    'text': ' '.join(current_message),
                    'date': None,
                    'raw_date': None
                })
        
        return messages
    
    def normalize_participants(self, messages: List[Dict]) -> List[Dict]:
        """Normalize participant names/identifiers."""
        # Find unique senders
        unique_senders = list(set([msg['sender'] for msg in messages]))
        
        # Map to Person A and Person B
        if len(unique_senders) >= 2:
            self.participants = {
                "Person_A": unique_senders[0],
                "Person_B": unique_senders[1]
            }
        elif len(unique_senders) == 1:
            self.participants = {
                "Person_A": unique_senders[0],
                "Person_B": "Unknown"
            }
        else:
            self.participants = {
                "Person_A": "Person A",
                "Person_B": "Person B"
            }
        
        # Normalize messages
        sender_map = {v: k for k, v in self.participants.items()}
        normalized = []
        for msg in messages:
            sender_id = sender_map.get(msg['sender'], "Person_A")
            normalized.append({
                **msg,
                'participant_id': sender_id,
                'participant_name': self.participants[sender_id]
            })
        
        return normalized
    
    def parse(self) -> Dict:
        """Main parsing function."""
        print(f"Extracting text from PDF: {self.pdf_path}")
        text = self.extract_text_from_pdf()
        
        print("Parsing messages...")
        messages = self.parse_messages(text)
        print(f"Found {len(messages)} messages")
        
        print("Normalizing participants...")
        normalized_messages = self.normalize_participants(messages)
        
        # Sort by date if available, otherwise by order
        try:
            normalized_messages.sort(key=lambda x: x['date'] if x['date'] else datetime.min)
        except:
            pass
        
        return {
            'participants': self.participants,
            'messages': normalized_messages,
            'total_messages': len(normalized_messages),
            'date_range': self._get_date_range(normalized_messages)
        }
    
    def _get_date_range(self, messages: List[Dict]) -> Dict:
        """Get the date range of the conversation."""
        dates = [msg['date'] for msg in messages if msg['date']]
        if dates:
            return {
                'start': min(dates).isoformat() if dates else None,
                'end': max(dates).isoformat() if dates else None
            }
        return {'start': None, 'end': None}


def main():
    if len(sys.argv) < 2:
        print("Usage: python parse_pdf.py <pdf_path> [output_json]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) > 2 else "conversation_data.json"
    
    parser = ConversationParser(pdf_path)
    result = parser.parse()
    
    # Save to JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\nParsing complete!")
    print(f"Participants: {list(result['participants'].values())}")
    print(f"Total messages: {result['total_messages']}")
    print(f"Date range: {result['date_range']}")
    print(f"Data saved to: {output_json}")


if __name__ == "__main__":
    main()
