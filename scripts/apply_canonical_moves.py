#!/usr/bin/env python3
"""
Apply canonical rename/move plan in controlled batches.

For each document whose canonical folder/filename have been computed, move the
physical file into the organized hierarchy and update the database metadata.

Features:
  * Dry-run mode (default) to preview changes
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
LOG_FILE = Path.home() / ".document_system" / "canonical_move_log.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply canonical rename/move plan.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of documents to process per run (default: 25).",
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


def fetch_candidates(client, batch_size: int) -> List[Dict]:
    all_rows = []
    page_size = 1000
    start = 0
    
    while len(all_rows) < batch_size:
        # Fetch current page
        current_limit = min(page_size, batch_size - len(all_rows))
        response = (
            client.table("documents")
            .select(
                "id,file_name,current_path,canonical_folder,canonical_filename,"
                "rename_status,rename_notes"
            )
            .in_("rename_status", ["planned"])
            .range(start, start + current_limit - 1)
            .execute()
        )
        
        rows = response.data or []
        if not rows:
            break
            
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
            
        start += page_size
        
    return all_rows


def main() -> None:
    args = parse_args()
    supabase_key = args.supabase_key or DEFAULT_SUPABASE_KEY
    if not supabase_key:
        raise SystemExit("SUPABASE_SERVICE_ROLE_KEY is required (set env or --supabase-key).")

    client = create_client(args.supabase_url, supabase_key)
    rows = fetch_candidates(client, args.batch_size)
    if not rows:
        print("🎉 No documents awaiting canonical moves (rename_status != 'planned').")
        return

    actions = build_actions(rows, args.base_path)
    dry_run = not args.execute
    timestamp = datetime.now().isoformat()

    if not actions:
        print("⚠️ No valid actions generated (missing canonical data).")
        return

    print(f"{'DRY-RUN' if dry_run else 'EXECUTING'} {len(actions)} canonical moves...\n")

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
            print(f"🛈 WOULD MOVE: {src} → {relative_display}")
            processed += 1
            continue

        target_dir.mkdir(parents=True, exist_ok=True)
        final_target.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.move(str(src), str(final_target))
        except Exception as e:
            print(f"❌ ERROR moving {src}: {e}")
            note = append_note(row.get("rename_notes"), f"Move failed: {e}")
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
            continue

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
            },
        )
        processed += 1
        print(f"✅ MOVED: {src} → {relative_display}")

    print("\n" + "=" * 80)
    print(f"Mode     : {'DRY-RUN (no changes made)' if dry_run else 'LIVE execution'}")
    print(f"Processed: {processed}")
    print(f"Skipped  : {skipped}")
    print(f"Log file : {LOG_FILE}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
