#!/usr/bin/env python3
"""
Universal Conversation Parser
Handles multiple formats: PDF, TXT, JSON, CSV, images, WhatsApp, iMessage, etc.
"""

import sys
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Try importing optional dependencies
try:
    from PyPDF2 import PdfReader
    HAS_PDF = True
except:
    HAS_PDF = False

try:
    from pdf2image import convert_from_path
    import pytesseract
    HAS_OCR = True
except:
    HAS_OCR = False

try:
    import csv
    HAS_CSV = True
except:
    HAS_CSV = True  # csv is standard library

try:
    from PIL import Image
    HAS_PIL = True
except:
    HAS_PIL = False


class UniversalParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_ext = Path(file_path).suffix.lower()
        self.participants = {}
        self.messages = []
    
    def detect_format(self) -> str:
        """Detect conversation format."""
        if self.file_ext == '.pdf':
            return 'pdf'
        elif self.file_ext in ['.txt', '.text']:
            # Check if it's WhatsApp, iMessage, or plain text
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                sample = f.read(1000)
                if 'WhatsApp Chat with' in sample or re.search(r'\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}', sample):
                    return 'whatsapp'
                elif 'iMessage' in sample or re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', sample):
                    return 'imessage'
                else:
                    return 'text'
        elif self.file_ext == '.json':
            return 'json'
        elif self.file_ext == '.csv':
            return 'csv'
        elif self.file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            return 'image'
        elif self.file_ext == '.html':
            return 'html'
        else:
            return 'unknown'
    
    def parse(self) -> Dict:
        """Parse the file based on detected format."""
        format_type = self.detect_format()
        print(f"Detected format: {format_type}")
        
        if format_type == 'pdf':
            return self.parse_pdf()
        elif format_type == 'whatsapp':
            return self.parse_whatsapp()
        elif format_type == 'imessage':
            return self.parse_imessage()
        elif format_type == 'text':
            return self.parse_text()
        elif format_type == 'json':
            return self.parse_json()
        elif format_type == 'csv':
            return self.parse_csv()
        elif format_type == 'image':
            return self.parse_image()
        elif format_type == 'html':
            return self.parse_html()
        else:
            print(f"Unknown format: {self.file_ext}")
            return self.parse_text()  # Fallback
    
    def parse_whatsapp(self) -> Dict:
        """Parse WhatsApp chat export."""
        print("Parsing WhatsApp export...")
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        # WhatsApp format: 12/31/23, 11:59 PM - John Doe: Message text
        pattern = r'(\d{1,2}/\d{1,2}/\d{2,4}),?\s+(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–]\s*([^:]+?):\s*(.+?)(?=\d{1,2}/\d{1,2}/\d{2,4}|$)'
        
        matches = re.finditer(pattern, text, re.DOTALL)
        
        participants_set = set()
        for match in matches:
            date_str = match.group(1)
            time_str = match.group(2)
            sender = match.group(3).strip()
            message = match.group(4).strip()
            
            participants_set.add(sender)
            
            # Parse datetime
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%y %I:%M %p")
            except:
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %I:%M %p")
                except:
                    dt = None
            
            self.messages.append({
                'sender': sender,
                'text': message,
                'date': dt,
                'raw_date': f"{date_str} {time_str}"
            })
        
        # Assign participant IDs
        participants_list = sorted(list(participants_set))
        for i, name in enumerate(participants_list[:2]):
            self.participants[f"Person_{chr(65+i)}"] = name
        
        # Update messages with participant IDs
        for msg in self.messages:
            for pid, name in self.participants.items():
                if msg['sender'] == name:
                    msg['participant_id'] = pid
                    msg['participant_name'] = name
                    break
        
        return self._format_result()
    
    def parse_text(self) -> Dict:
        """Parse plain text file."""
        print("Parsing plain text...")
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Try to detect pattern
        for line in lines[:50]:
            # Look for common patterns
            if re.match(r'\d{4}-\d{2}-\d{2}', line):
                return self.parse_imessage()
        
        # Fallback: treat each non-empty line as a message
        self.participants = {"Person_A": "Person A", "Person_B": "Person B"}
        
        current_speaker = "Person_A"
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            self.messages.append({
                'sender': current_speaker,
                'participant_id': current_speaker,
                'participant_name': self.participants[current_speaker],
                'text': line,
                'date': None,
                'raw_date': None
            })
            
            # Alternate speakers
            current_speaker = "Person_B" if current_speaker == "Person_A" else "Person_A"
        
        return self._format_result()
    
    def parse_imessage(self) -> Dict:
        """Parse iMessage export (iPhone backup format)."""
        print("Parsing iMessage export...")
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        
        # Use the iPhone backup parser logic
        from parse_iphone_backup import parse_iphone_backup_messages
        result = parse_iphone_backup_messages(text)
        return result
    
    def parse_json(self) -> Dict:
        """Parse JSON conversation export."""
        print("Parsing JSON export...")
        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Try to detect structure
        if isinstance(data, list):
            # Array of messages
            for msg in data:
                if isinstance(msg, dict):
                    self.messages.append({
                        'sender': msg.get('sender', msg.get('from', msg.get('user', 'Unknown'))),
                        'text': msg.get('text', msg.get('message', msg.get('content', ''))),
                        'date': msg.get('timestamp', msg.get('date', msg.get('time'))),
                        'raw_date': str(msg.get('timestamp', msg.get('date', '')))
                    })
        elif isinstance(data, dict):
            # Check for Facebook Messenger format
            if 'messages' in data:
                for msg in data['messages']:
                    self.messages.append({
                        'sender': msg.get('sender_name', 'Unknown'),
                        'text': msg.get('content', ''),
                        'date': datetime.fromtimestamp(msg.get('timestamp_ms', 0) / 1000) if 'timestamp_ms' in msg else None,
                        'raw_date': str(msg.get('timestamp_ms', ''))
                    })
            # Check if it's already in our format
            elif 'participants' in data and 'messages' in data:
                return data
        
        # Extract participants
        senders = set(msg['sender'] for msg in self.messages)
        for i, sender in enumerate(sorted(senders)[:2]):
            self.participants[f"Person_{chr(65+i)}"] = sender
        
        # Update messages
        for msg in self.messages:
            for pid, name in self.participants.items():
                if msg['sender'] == name:
                    msg['participant_id'] = pid
                    msg['participant_name'] = name
                    break
        
        return self._format_result()
    
    def parse_csv(self) -> Dict:
        """Parse CSV conversation export."""
        print("Parsing CSV export...")
        with open(self.file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Try to find relevant columns
        for row in rows:
            sender = row.get('sender', row.get('from', row.get('user', row.get('name', 'Unknown'))))
            text = row.get('message', row.get('text', row.get('content', '')))
            date_str = row.get('date', row.get('timestamp', row.get('time', '')))
            
            self.messages.append({
                'sender': sender,
                'text': text,
                'date': None,  # TODO: parse date
                'raw_date': date_str
            })
        
        # Extract participants
        senders = set(msg['sender'] for msg in self.messages)
        for i, sender in enumerate(sorted(senders)[:2]):
            self.participants[f"Person_{chr(65+i)}"] = sender
        
        # Update messages
        for msg in self.messages:
            for pid, name in self.participants.items():
                if msg['sender'] == name:
                    msg['participant_id'] = pid
                    msg['participant_name'] = name
                    break
        
        return self._format_result()
    
    def parse_pdf(self) -> Dict:
        """Parse PDF - redirect to specialized parser."""
        print("PDF detected - please use parse_pdf_ocr.py for PDF files")
        print("Command: python parse_pdf_ocr.py <pdf_path>")
        sys.exit(1)
    
    def parse_image(self) -> Dict:
        """Parse image with OCR."""
        if not HAS_OCR or not HAS_PIL:
            print("Image parsing requires: pip install pdf2image pytesseract pillow")
            sys.exit(1)
        
        print("Extracting text from image with OCR...")
        image = Image.open(self.file_path)
        text = pytesseract.image_to_string(image)
        
        # Save OCR text and parse
        temp_file = 'temp_ocr_text.txt'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Parse the text
        self.file_path = temp_file
        result = self.parse_text()
        
        # Clean up
        os.remove(temp_file)
        return result
    
    def parse_html(self) -> Dict:
        """Parse HTML conversation export."""
        print("Parsing HTML export...")
        with open(self.file_path, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '\n', html)
        
        # Save as text and parse
        temp_file = 'temp_html_text.txt'
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        self.file_path = temp_file
        result = self.parse_text()
        
        os.remove(temp_file)
        return result
    
    def _format_result(self) -> Dict:
        """Format final result."""
        dates = [m['date'] for m in self.messages if m.get('date')]
        
        return {
            'participants': self.participants,
            'messages': self.messages,
            'total_messages': len(self.messages),
            'date_range': {
                'start': min(dates).isoformat() if dates else None,
                'end': max(dates).isoformat() if dates else None
            }
        }


def main():
    if len(sys.argv) < 2:
        print("Universal Conversation Parser")
        print("=" * 60)
        print("\nUsage: python universal_parser.py <file_path> [output.json]")
        print("\nSupported formats:")
        print("  • PDF (uses OCR)")
        print("  • WhatsApp (.txt export)")
        print("  • iMessage/iPhone backup (.txt)")
        print("  • JSON (various messaging apps)")
        print("  • CSV")
        print("  • Plain text")
        print("  • Images (screenshots with OCR)")
        print("  • HTML exports")
        print("\nExamples:")
        print("  python universal_parser.py conversation.txt")
        print("  python universal_parser.py whatsapp_export.txt")
        print("  python universal_parser.py messenger_export.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "conversation_data.json"
    
    if not os.path.exists(input_file):
        print(f"Error: File not found: {input_file}")
        sys.exit(1)
    
    print(f"Parsing: {input_file}")
    print(f"File size: {os.path.getsize(input_file) / 1024:.1f} KB\n")
    
    parser = UniversalParser(input_file)
    result = parser.parse()
    
    # Save result
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\n✓ Parsing complete!")
    print(f"Participants: {list(result['participants'].values())}")
    print(f"Total messages: {result['total_messages']}")
    print(f"Date range: {result['date_range']}")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
