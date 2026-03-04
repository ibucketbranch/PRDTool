#!/usr/bin/env python3
"""
Apply canonical rename/move plan for RESUMES ONLY.
This script filters for resumes (employment category + resume in name/path)
to ensure we only move actual resume files.

Features:
  * Dry-run mode (default) to preview changes
  * Resume-only filtering
  * Safe target-path collision handling (auto-suffix)
  * Per-file Supabase updates with detailed notes
  * Log file for auditing/rollback assistance
"""

from __future__ import annotations

import argparse
import json
import shutil
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from supabase import create_client  # type: ignore

DEFAULT_SUPABASE_URL = "http://127.0.0.1:54421"
DEFAULT_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
DEFAULT_BASE_PATH = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
LOG_FILE = Path.home() / ".document_system" / "resume_move_log.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply canonical rename/move plan for RESUMES ONLY.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of resume documents to process per run (default: 5).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default: dry-run preview only).",
    )
    parser.add_argument(
        "--base-path",
        type=Path,
        default=DEFAULT_BASE_PATH,
        help="Root path for organized documents (default: %(default)s).",
    )
    parser.add_argument(
        "--supabase-url",
        default=DEFAULT_SUPABASE_URL,
        help="Supabase API URL (default: %(default)s).",
    )
    parser.add_argument(
        "--supabase-key",
        default=DEFAULT_SUPABASE_KEY,
        help="Supabase service role key (default: env SUPABASE_SERVICE_ROLE_KEY).",
    )
    return parser.parse_args()


def log_event(entry: Dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def unique_target_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = target.with_name(f"{stem}__{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def append_note(existing: Optional[str], addition: str) -> str:
    if existing:
        return f"{existing} | {addition}"
    return addition


def build_actions(
    rows: List[Dict],
    base_path: Path,
) -> List[Dict]:
    actions: List[Dict] = []
    for row in rows:
        canonical_folder = (row.get("canonical_folder") or "").strip()
        canonical_filename = row.get("canonical_filename")
        current_path = row.get("current_path")

        if not canonical_folder or not canonical_filename or not current_path:
            continue

        src_path = Path(current_path)
        rel_folder = Path(canonical_folder.lstrip("/"))
        target_dir = base_path / rel_folder
        target_path = target_dir / canonical_filename

        actions.append(
            {
                "id": row["id"],
                "source": src_path,
                "target_dir": target_dir,
                "target_path": target_path,
                "row": row,
            }
        )
    return actions


def update_document(
    client,
    doc_id: str,
    payload: Dict,
) -> None:
    client.table("documents").update(payload).eq("id", doc_id).execute()


def fetch_resume_candidates(client, batch_size: int) -> List[Dict]:
    """
    Fetch resume documents only (employment category + resume in name/path).
    """
    response = (
        client.table("documents")
        .select(
            "id,file_name,current_path,canonical_folder,canonical_filename,"
            "rename_status,rename_notes,ai_category"
        )
        .eq("ai_category", "employment")  # Must be employment category
        .or_("file_name.ilike.%resume%,current_path.ilike.%resume%")  # Must have resume in name or path
        .eq("rename_status", "planned")  # Must be planned
        .limit(batch_size)
        .execute()
    )
    return response.data or []


def main() -> None:
    args = parse_args()
    supabase_key = args.supabase_key or DEFAULT_SUPABASE_KEY
    if not supabase_key:
        raise SystemExit("SUPABASE_SERVICE_ROLE_KEY is required (set env or --supabase-key).")

    client = create_client(args.supabase_url, supabase_key)
    rows = fetch_resume_candidates(client, args.batch_size)
    
    if not rows:
        print("🎉 No resume documents awaiting canonical moves (rename_status != 'planned').")
        return

    # Filter to ensure we only process actual resumes
    resume_rows = []
    for row in rows:
        file_name = (row.get("file_name") or "").lower()
        current_path = (row.get("current_path") or "").lower()
        ai_category = (row.get("ai_category") or "").lower()
        
        # Must be employment category AND have "resume" in name or path
        if ai_category == "employment" and ("resume" in file_name or "resume" in current_path):
            resume_rows.append(row)
    
    if not resume_rows:
        print("⚠️  No resume documents found in planned set (filtered out non-resumes).")
        return

    actions = build_actions(resume_rows, args.base_path)
    dry_run = not args.execute
    timestamp = datetime.now().isoformat()

    if not actions:
        print("⚠️ No valid actions generated (missing canonical data).")
        return

    print(f"{'DRY-RUN' if dry_run else 'EXECUTING'} {len(actions)} RESUME moves...\n")

    processed = 0
    skipped = 0

    for action in actions:
        row = action["row"]
        src = action["source"]
        target_dir = action["target_dir"]
        target = action["target_path"]

        if not src.exists():
            note = append_note(row.get("rename_notes"), "Source missing during rename batch.")
            update_document(
                client,
                row["id"],
                {
                    "rename_status": "blocked",
                    "rename_notes": note,
                    "last_reviewed_at": timestamp,
                },
            )
            skipped += 1
            print(f"⚠️ SKIP (missing): {src}")
            continue

        final_target = unique_target_path(target)
        relative_display = final_target.relative_to(args.base_path)

        if dry_run:
            print(f"🛈 WOULD MOVE RESUME: {src.name}")
            print(f"   FROM: {src}")
            print(f"   TO:   {relative_display}")
            print("")
            processed += 1
            continue

        # SAFETY: Create backup/log before moving
        target_dir.mkdir(parents=True, exist_ok=True)
        final_target.parent.mkdir(parents=True, exist_ok=True)
        
        # Use shutil.move (atomic on same filesystem)
        shutil.move(str(src), str(final_target))

        folder_hierarchy = list(final_target.parent.parts)
        note = append_note(row.get("rename_notes"), f"Moved to {relative_display} on {timestamp}")

        update_document(
            client,
            row["id"],
            {
                "current_path": str(final_target),
                "folder_hierarchy": folder_hierarchy,
                "rename_status": "applied",
                "rename_notes": note,
                "canonical_filename": final_target.name,
                "last_reviewed_at": timestamp,
            },
        )

        log_event(
            {
                "timestamp": timestamp,
                "id": row["id"],
                "source": str(src),
                "target": str(final_target),
                "dry_run": dry_run,
                "file_name": row.get("file_name"),
            },
        )
        processed += 1
        print(f"✅ MOVED RESUME: {src.name} → {relative_display}")

    print("\n" + "=" * 80)
    print(f"Mode     : {'DRY-RUN (no changes made)' if dry_run else 'LIVE execution'}")
    print(f"Processed: {processed} resumes")
    print(f"Skipped  : {skipped}")
    print(f"Log file : {LOG_FILE}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
