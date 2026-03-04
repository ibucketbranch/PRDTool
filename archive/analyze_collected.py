#!/usr/bin/env python3
"""Analyze the collected documents and show insights"""
import json
from collections import Counter
from supabase import create_client

# Connect to database
supabase = create_client(
    'http://127.0.0.1:54421',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0'
)

# Get all documents
docs = supabase.table('documents').select('*').execute()

print("\n" + "="*80)
print(f"📊 ANALYSIS OF {len(docs.data)} DOCUMENTS")
print("="*80 + "\n")

# Category breakdown
categories = [d['ai_category'] for d in docs.data if d.get('ai_category')]
category_counts = Counter(categories)
print("📂 CATEGORIES:")
for cat, count in category_counts.most_common():
    print(f"   {cat}: {count} files")

# Document modes
modes = [d['document_mode'] for d in docs.data if d.get('document_mode')]
mode_counts = Counter(modes)
print(f"\n📄 DOCUMENT MODES:")
for mode, count in mode_counts.items():
    print(f"   {mode}: {count} files")

# Organizations
orgs = []
for d in docs.data:
    if d.get('entities') and isinstance(d['entities'], dict):
        orgs.extend(d['entities'].get('organizations', []))
org_counts = Counter(orgs)
print(f"\n🏢 TOP ORGANIZATIONS ({len(org_counts)} unique):")
for org, count in org_counts.most_common(10):
    print(f"   {org}: {count} mentions")

# People
people = []
for d in docs.data:
    if d.get('entities') and isinstance(d['entities'], dict):
        people.extend(d['entities'].get('people', []))
people_counts = Counter(people)
print(f"\n👤 TOP PEOPLE ({len(people_counts)} unique):")
for person, count in people_counts.most_common(10):
    print(f"   {person}: {count} mentions")

# File size stats
sizes = [d['file_size_bytes'] for d in docs.data if d.get('file_size_bytes')]
total_size = sum(sizes)
avg_size = total_size / len(sizes) if sizes else 0
print(f"\n💾 FILE SIZES:")
print(f"   Total: {total_size / 1024 / 1024:.2f} MB")
print(f"   Average: {avg_size / 1024:.2f} KB")
print(f"   Largest: {max(sizes) / 1024:.2f} KB" if sizes else "   N/A")

# Page count stats
pages = [d['page_count'] for d in docs.data if d.get('page_count')]
total_pages = sum(pages)
print(f"\n📑 PAGES:")
print(f"   Total pages: {total_pages:,}")
print(f"   Average per doc: {total_pages / len(pages):.1f}" if pages else "   N/A")

# Confidence scores
confidences = [d['confidence_score'] for d in docs.data if d.get('confidence_score')]
avg_confidence = sum(confidences) / len(confidences) if confidences else 0
print(f"\n🎯 AI CONFIDENCE:")
print(f"   Average: {avg_confidence:.1%}")
high_conf = sum(1 for c in confidences if c >= 0.8)
print(f"   High confidence (≥80%): {high_conf}/{len(confidences)} ({high_conf/len(confidences)*100:.1f}%)" if confidences else "   N/A")

print("\n" + "="*80 + "\n")
