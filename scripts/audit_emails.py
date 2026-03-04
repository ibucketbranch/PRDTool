import os
import re
import json
from collections import defaultdict

def get_email_domain(header_str):
    if not header_str: return None
    # Try to find email in <> or just the string
    email_match = re.search(r'<([^>]+)>', header_str)
    email = email_match.group(1) if email_match else header_str
    domain_match = re.search(r'@([\w\.-]+)', email)
    return domain_match.group(1).lower() if domain_match else None

def analyze_emails():
    gdrive_root = "/Users/michaelvalderrama/Library/CloudStorage/GoogleDrive-mikevalderrama@gmail.com/My Drive"
    print(f"🔍 Deep analysis of 8,782 .emlx files...")
    
    # Domains clearly associated with CMedia or similar work
    work_domains = {'cmedia.com.tw', 'c-media.com.tw', 'cmedia.com', 'c-media.com'}
    work_keywords = ['cmedia', 'c-media', 'taiwan', 'tw', 'big5', 'vic hsieh', 'ronald']
    
    report = {
        "work": [],
        "personal": [],
        "junk_log": [],
        "unclassified": []
    }
    
    total = 0
    
    for root, dirs, files in os.walk(gdrive_root):
        for file in files:
            if file.endswith('.emlx'):
                total += 1
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        # Read first few lines for headers
                        header_block = ""
                        for _ in range(50):
                            line = f.readline()
                            if not line: break
                            header_block += line
                        
                        from_match = re.search(r'^From: (.*)', header_block, re.MULTILINE | re.IGNORECASE)
                        subj_match = re.search(r'^Subject: (.*)', header_block, re.MULTILINE | re.IGNORECASE)
                        date_match = re.search(r'^Date: (.*)', header_block, re.MULTILINE | re.IGNORECASE)
                        
                        from_val = from_match.group(1).strip() if from_match else ""
                        subj_val = subj_match.group(1).strip() if subj_match else ""
                        date_val = date_match.group(1).strip() if date_match else ""
                        
                        domain = get_email_domain(from_val)
                        
                        is_work = False
                        if domain in work_domains:
                            is_work = True
                        elif any(kw in header_block.lower() for kw in work_keywords):
                            is_work = True
                        elif "Synchronization Log" in subj_val:
                            report["junk_log"].append({"path": path, "name": file, "subject": subj_val})
                            continue

                        email_info = {
                            "name": file,
                            "path": path,
                            "from": from_val,
                            "subject": subj_val,
                            "date": date_val,
                            "domain": domain
                        }

                        if is_work:
                            report["work"].append(email_info)
                        else:
                            # Heuristic for personal
                            if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'me.com', 'icloud.com', 'msn.com']:
                                report["personal"].append(email_info)
                            else:
                                report["unclassified"].append(email_info)
                except:
                    continue
                
                if total % 1000 == 0:
                    print(f"  Processed {total} emails...")

    # Final Summary
    print("\n" + "="*80)
    print("📊 EMAIL CATEGORIZATION REPORT")
    print("="*80)
    print(f"Total .emlx Files Found:   {total}")
    print(f"Likely Work (CMedia):      {len(report['work'])}")
    print(f"Junk (System Logs):        {len(report['junk_log'])}")
    print(f"Likely Personal:           {len(report['personal'])}")
    print(f"Unclassified/Other:        {len(report['unclassified'])}")
    print("="*80)

    # Samples of Personal
    if report["personal"]:
        print("\nTop 10 Personal Email Samples:")
        for e in report["personal"][:10]:
            print(f" - {e['from'][:30]:<30} | {e['subject'][:40]}")

    # Samples of Unclassified
    if report["unclassified"]:
        print("\nTop 10 Unclassified Email Samples (Potential Personal?):")
        for e in report["unclassified"][:10]:
            print(f" - {e['from'][:30]:<30} | {e['subject'][:40]}")

    # Save details
    with open('/tmp/email_audit_details.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nFull audit saved to: /tmp/email_audit_details.json")

if __name__ == "__main__":
    analyze_emails()
