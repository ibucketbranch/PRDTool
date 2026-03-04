#!/usr/bin/env python3
"""
Plan canonical folder + filename targets for every document.
This script updates the documents table with proposed destinations and
generates a CSV report for human review.
"""

import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from supabase import create_client  # type: ignore

DEFAULT_SUPABASE_URL = os.getenv("SUPABASE_URL", "http://127.0.0.1:54421")
DEFAULT_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

CATEGORY_FOLDER_MAP = {
    "tax_document": "Financial/Taxes/{Year}",
    "invoice": "Financial/Invoices/{Year}",
    "receipt": "Financial/Receipts/{Year}",
    "bank_statement": "Financial/Statements/{Year}",
    "utility_bill": "Financial/Utilities/{Year}",
    "medical_record": "Personal/Medical",
    "insurance_policy": "Financial/Insurance",
    "vehicle_registration": "Vehicles/{Vehicle}/Registration",
    "vehicle_insurance": "Vehicles/{Vehicle}/Insurance",
    "vehicle_maintenance": "Vehicles/{Vehicle}/Maintenance",
    "employment": "Professional/Employment",
    "education": "Personal/Education",
    "contract": "Legal/Contracts",
    "property_document": "Legal/Property",
    "correspondence": "Correspondence",
    "conversation": "Conversations",
}

BIN_KEYWORDS = {
    "personal bin": "Personal Bin",
    "family bin": "Family Bin",
    "work bin": "Work Bin",
    "finances bin": "Finances Bin",
    "legal bin": "Legal Bin",
    "projects bin": "Projects Bin",
    "projcts bin": "Projects Bin",
    "netv": "NetV",
    "leopard": "LEOPard",
    "usaa visa": "USAA Visa",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan canonical document destinations.")
    parser.add_argument(
        "--supabase-url",
        default=DEFAULT_SUPABASE_URL,
        help="Supabase API URL (default: %(default)s)",
    )
    parser.add_argument(
        "--supabase-key",
        default=DEFAULT_SUPABASE_KEY,
        help="Supabase service role key (default: env SUPABASE_SERVICE_ROLE_KEY)",
    )
    parser.add_argument(
        "--output",
        default="canonical_path_plan.csv",
        help="CSV file for the planning report (default: %(default)s)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=250,
        help="Batch size for Supabase fetches (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of documents processed (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate report without updating Supabase.",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    value = value.replace("&", " and ")
    value = re.sub(r"[^\w\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_").lower() or "document"


def sanitize_segment(value: str) -> str:
    value = re.sub(r"[\\/]+", "_", value)
    value = re.sub(r"[\s]+", " ", value).strip()
    return value or "General"


def detect_bin(doc: Dict[str, Any]) -> Tuple[str, str]:
    """
    Determine the best context bin for a document.
    
    Uses content analysis and document type to determine best fit,
    not just current location. Resumes always go to Work Bin.
    """
    ai_category = (doc.get("ai_category") or "").lower()
    file_name = (doc.get("file_name") or "").lower()
    extracted_text = (doc.get("extracted_text") or "")[:500].lower()  # First 500 chars for context
    
    # SPECIAL RULE: Resumes always go to Work Bin (work-related documents)
    is_resume = (
        ai_category == "employment" and 
        ("resume" in file_name or "resume" in extracted_text or 
         any(keyword in file_name for keyword in ["resume", "cv"]))
    )
    if is_resume:
        return "Work Bin", "resume_rule"
    
    # Use context_bin if available (from AI analysis)
    if doc.get("context_bin"):
        return str(doc["context_bin"]), "context_bin"

    # Check current path as context (but not final decision)
    path = doc.get("current_path") or ""
    path_lower = path.lower()
    for needle, label in BIN_KEYWORDS.items():
        if needle in path_lower:
            # Use path as context, but content analysis should override
            return label, f"path:{needle}"

    hierarchy = doc.get("folder_hierarchy") or []
    if isinstance(hierarchy, list):
        for part in hierarchy:
            if not isinstance(part, str):
                continue
            normalized = part.lower()
            if normalized in BIN_KEYWORDS:
                return BIN_KEYWORDS[normalized], "hierarchy"

    return "General Bin", "default"


def parse_entities(raw: Any) -> Dict[str, List[str]]:
    if isinstance(raw, dict):
        return raw  # type: ignore[return-value]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed  # type: ignore[return-value]
        except json.JSONDecodeError:
            pass
    return {}


def extract_year(doc: Dict[str, Any], entities: Dict[str, Any]) -> Tuple[str, str]:
    # Entities first
    dates = entities.get("dates") or []
    for candidate in dates:
        year = _extract_year_from_string(candidate)
        if year:
            return year, "entity"

    # File name fallback
    year = _extract_year_from_string(doc.get("file_name", ""))
    if year:
        return year, "filename"

    # Path fallback
    year = _extract_year_from_string(doc.get("current_path", ""))
    if year:
        return year, "path"

    return "Unknown", "default"


def _extract_year_from_string(value: str) -> Optional[str]:
    matches = re.findall(r"(?:19|20)\d{2}", value or "")
    return matches[0] if matches else None


def category_folder(ai_category: Optional[str], template_year: str, entities: Dict[str, Any], file_name: Optional[str] = None, extracted_text: Optional[str] = None) -> Tuple[str, str]:
    category = (ai_category or "uncategorized").lower()
    
    # Check if it's a resume by filename OR content
    file_lower = (file_name or "").lower()
    is_resume_by_filename = "resume" in file_lower
    is_resume_by_content = False
    
    if extracted_text:
        text_lower = extracted_text.lower()
        resume_indicators = [
            "work experience", "employment history", "professional experience",
            "education", "skills", "summary", "objective", "contact",
            "years of experience", "responsibilities", "achievements"
        ]
        matches = sum(1 for keyword in resume_indicators if keyword in text_lower)
        is_resume_by_content = matches >= 3  # At least 3 resume indicators
    
    is_resume = is_resume_by_filename or is_resume_by_content
    
    # Special handling for resumes - route to Employment/Resumes/
    if is_resume and category == "employment":
        # Extract person name from entities or filename
        person_name = None
        people = entities.get("people") if isinstance(entities, dict) else []
        if people and len(people) > 0:
            person_name = sanitize_segment(str(people[0]))
        elif file_name:
            # Try to extract from filename (e.g., "MichaelValderramaResume.pdf")
            name_match = re.search(r"([A-Z][a-z]+[A-Z][a-z]+)", file_name)
            if name_match:
                full_name = name_match.group(1)
                person_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", full_name)
                person_name = sanitize_segment(person_name)
        
        if person_name and person_name.lower() not in ["resume", "document", "other"]:
            template = f"Employment/Resumes/{person_name}"
        else:
            template = "Employment/Resumes/Other"
        return template, "resume"
    
    # Use standard category mapping for non-resumes
    template = CATEGORY_FOLDER_MAP.get(category, "Uncategorized/{Year}")

    vehicle = None
    vehicles = entities.get("vehicles") or [] if isinstance(entities, dict) else []
    if vehicles:
        vehicle = sanitize_segment(str(vehicles[0]))

    result = (
        template.replace("{Year}", template_year)
        .replace("{year}", template_year)
        .replace("{Vehicle}", vehicle or "General")
    )
    return result, category or "uncategorized"


def build_canonical_filename(doc: Dict[str, Any], category_slug: str, year: str) -> str:
    original = doc.get("file_name") or "document.pdf"
    stem = Path(original).stem
    ext = Path(original).suffix or ".pdf"

    stem_slug = slugify(stem)[:60]
    category_slug = slugify(category_slug)
    pieces = [year if year != "Unknown" else "undated", category_slug, stem_slug]
    name = "_".join(filter(None, pieces))
    return f"{name}{ext.lower()}"


def plan_for_document(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Plan canonical path for a document.
    PRIORITY: Use AI-suggested folder structure if available (intelligently learned from examples).
    Fallback to rule-based structure if AI didn't suggest one.
    """
    if not doc.get("current_path"):
        return None

    entities = parse_entities(doc.get("entities"))
    year, year_source = extract_year(doc, entities)
    
    # FIRST: Check if AI already suggested an intelligent folder structure
    # AI learns from examples like "Work Bin/Employment/Resumes/Michael Valderrama"
    ai_suggested_structure = doc.get("suggested_folder_structure", "")
    
    if ai_suggested_structure and ai_suggested_structure.strip():
        # AI has intelligently proposed a structure - use it!
        # Format: "Work Bin/Employment/Resumes/Michael Valderrama"
        # We need to convert this to: "Documents/Work Bin/Employment/Resumes/Michael Valderrama"
        canonical_folder = f"Documents/{ai_suggested_structure.strip()}"
        
        # Extract bin name from AI structure for reporting
        parts = ai_suggested_structure.strip().split('/')
        bin_name = parts[0] if parts else "General Bin"
        bin_source = "ai_suggested"  # AI learned from examples and proposed intelligently
        
        # Build filename from original (keep original name, AI suggests folder structure)
        original_name = doc.get("file_name") or "document.pdf"
        original_path_obj = Path(original_name)
        canonical_filename = original_path_obj.name  # Keep original filename, AI suggested folder structure
        
        category_used_for_notes = doc.get("ai_category", "unknown")
        notes = (
            f"AI-suggested structure (learned from examples: {ai_suggested_structure}); "
            f"category={category_used_for_notes}; "
            f"year={year} ({year_source})"
        )
    else:
        # Fallback: Use rule-based structure (if AI didn't suggest one)
        bin_name, bin_source = detect_bin(doc)
        folder_suffix, category_used = category_folder(
            doc.get("ai_category"), 
            year, 
            entities,
            doc.get("file_name"),
            doc.get("extracted_text")
        )
        
        # OVERRIDE: If this is a resume (employment category), 
        # force it to Work Bin regardless of current location
        ai_category = (doc.get("ai_category") or "").lower()
        file_name = (doc.get("file_name") or "").lower()
        current_path = (doc.get("current_path") or "").lower()
        
        is_resume = (
            ai_category == "employment" and 
            ("resume" in file_name or "resume" in current_path)
        )
        if is_resume:
            bin_name = "Work Bin"
            bin_source = "resume_rule_override"

        canonical_folder = f"Documents/{bin_name}/{folder_suffix}"
        canonical_filename = build_canonical_filename(doc, category_used, year)
        category_used_for_notes = category_used

        notes = (
            f"bin={bin_name} ({bin_source}); "
            f"category={category_used_for_notes}; "
            f"year={year} ({year_source})"
        )

    rename_status = doc.get("rename_status") or "unplanned"
    if rename_status not in {"applied", "locked"}:
        rename_status = "planned"

    return {
        "canonical_folder": canonical_folder,
        "canonical_filename": canonical_filename,
        "rename_status": rename_status,
        "rename_notes": notes,
        "last_reviewed_at": datetime.utcnow().isoformat(),
        "report_row": {
            "id": doc["id"],
            "file_name": doc.get("file_name"),
            "current_path": doc.get("current_path"),
            "canonical_folder": canonical_folder,
            "canonical_filename": canonical_filename,
            "rename_status": rename_status,
            "bin_source": bin_source,
            "year_source": year_source,
            "category": category_used_for_notes,
            "notes": notes,
        },
    }


def update_document(supabase: Any, doc_id: str, payload: Dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        return
    data = {k: v for k, v in payload.items() if k != "report_row"}
    supabase.table("documents").update(data).eq("id", doc_id).execute()


def fetch_documents(
    supabase: Any,
    start: int,
    end: int,
) -> List[Dict[str, Any]]:
    response = (
        supabase.table("documents")
        .select(
            "id,file_name,current_path,ai_category,entities,folder_hierarchy,"
            "context_bin,rename_status,canonical_folder,canonical_filename,extracted_text,"
            "suggested_folder_structure"
        )
        .order("created_at", desc=False)
        .range(start, end)
        .execute()
    )
    return response.data or []  # type: ignore[return-value]


def main() -> None:
    args = parse_args()
    if not args.supabase_key:
        raise SystemExit("SUPABASE_SERVICE_ROLE_KEY is required.")

    supabase = create_client(args.supabase_url, args.supabase_key)
    csv_rows: List[Dict[str, Any]] = []

    processed = 0
    start = 0
    while True:
        if args.limit is not None and processed >= args.limit:
            break
        end = start + args.page_size - 1
        if args.limit is not None:
            remaining = args.limit - processed
            if remaining < args.page_size:
                end = start + remaining - 1
        docs = fetch_documents(supabase, start, end)
        if not docs:
            break

        for doc in docs:
            plan = plan_for_document(doc)
            if not plan:
                continue
            csv_rows.append(plan["report_row"])
            update_document(supabase, doc["id"], plan, args.dry_run)
            processed += 1

        if len(docs) < args.page_size:
            break
        start += args.page_size

    fieldnames = [
        "id",
        "file_name",
        "current_path",
        "canonical_folder",
        "canonical_filename",
        "rename_status",
        "bin_source",
        "year_source",
        "category",
        "notes",
    ]
    with open(args.output, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    mode = "DRY-RUN" if args.dry_run else "UPDATED"
    print(f"{mode}: planned {len(csv_rows)} documents; report saved to {args.output}")


if __name__ == "__main__":
    main()
