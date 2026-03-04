#!/usr/bin/env python3
"""
Batch duplicate consolidation via macOS aliases.

- Generates (and caches) a duplicate plan from the PDF discovery cache.
- Each run processes up to --batch-size duplicate files by:
    1. Choosing a master copy per hash
    2. Replacing selected duplicates with symbolic links to the master
    3. Deleting the duplicate bytes once the alias is in place (with safety backup)

Usage examples:
    Dry run, preview next 100 replacements
        python3 batch_alias_duplicates.py

    Execute 100 replacements
        python3 batch_alias_duplicates.py --execute

    Refresh duplicate plan from scratch
        python3 batch_alias_duplicates.py --refresh-plan

    Process 25 duplicates at a time
        python3 batch_alias_duplicates.py --execute --batch-size 25
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PDF_CACHE = Path.home() / ".document_system" / "pdf_cache.json"
PLAN_FILE = Path.home() / ".document_system" / "alias_duplicate_plan.json"
STATE_FILE = Path.home() / ".document_system" / "alias_duplicate_state.json"
LOG_FILE = Path.home() / ".document_system" / "alias_duplicate_log.jsonl"


def read_json(path: Path, default):
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def append_log(entry: Dict) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def hash_file(path: Path) -> Optional[str]:
    try:
        sha256 = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError):
        return None


def score_path(path: Path) -> float:
    """Higher score means better master candidate."""
    path_lower = str(path).lower()
    score = 0.0

    # Avoid obvious backup/archive folders
    if "backup" in path_lower:
        score -= 100
    if "-old" in path_lower or "_old" in path_lower:
        score -= 60
    if "archive" in path_lower:
        score -= 40
    if "copy" in path_lower:
        score -= 20

    if "work bin" in path_lower or "personal bin" in path_lower or "family bin" in path_lower:
        score += 40
    if "projects bin" in path_lower or "finances bin" in path_lower:
        score += 20

    # Shorter path gets slight bonus (closer to root)
    score -= len(path.parts) * 2

    try:
        score += path.stat().st_mtime / 1_000_000  # prefer more recent edits
    except OSError:
        pass

    return score


def is_backup_path(path: Path) -> bool:
    lower = str(path).lower()
    keywords = ["backup", "archive", "temp", "-old", "_old", "-copy", "_copy", "duplicates"]
    return any(k in lower for k in keywords)


def choose_master(paths: List[Path]) -> Path:
    return max(paths, key=score_path)


def load_pdf_cache() -> List[Dict]:
    cache = read_json(PDF_CACHE, default=None)
    if not cache:
        raise SystemExit(f"PDF cache not found. Please run: python3 discover_pdfs.py <root>")
    return cache.get("pdfs", [])


def build_plan(min_copies: int = 2) -> Dict:
    pdf_entries = load_pdf_cache()
    existing = [entry for entry in pdf_entries if Path(entry["path"]).exists()]

    by_size: Dict[int, List[Path]] = defaultdict(list)
    for entry in existing:
        by_size[entry["size"]].append(Path(entry["path"]))

    plan = []
    for size, paths in by_size.items():
        if len(paths) < min_copies:
            continue

        hash_groups: Dict[str, List[Path]] = defaultdict(list)
        for path in paths:
            file_hash = hash_file(path)
            if file_hash:
                hash_groups[file_hash].append(path)

        for file_hash, group_paths in hash_groups.items():
            if len(group_paths) < min_copies:
                continue

            master = choose_master(group_paths)
            duplicates = [p for p in group_paths if p != master]

            # Sort duplicates so that backups/archives are processed first
            duplicates.sort(key=lambda p: (not is_backup_path(p), score_path(p)))

            plan.append(
                {
                    "hash": file_hash,
                    "size": size,
                    "master": str(master),
                    "duplicates": [str(p) for p in duplicates],
                    "total_copies": len(group_paths),
                }
            )

    plan.sort(key=lambda item: (item["total_copies"], item["size"]), reverse=True)
    payload = {
        "created": datetime.now().isoformat(),
        "min_copies": min_copies,
        "plan": plan,
    }
    write_json(PLAN_FILE, payload)
    return payload


def iter_actions(plan: Dict) -> Iterable[Dict]:
    for entry in plan.get("plan", []):
        master = entry["master"]
        for dup in entry["duplicates"]:
            yield {
                "hash": entry["hash"],
                "master": master,
                "target": dup,
                "size": entry["size"],
                "total_copies": entry["total_copies"],
            }


def prepare_actions(batch_size: int, dry_run: bool) -> Tuple[List[Dict], Dict]:
    plan = read_json(PLAN_FILE, default=None)
    if not plan:
        plan = build_plan()

    state = read_json(STATE_FILE, default={"aliased": [], "skipped": []})
    processed = set(state.get("aliased", []))
    skipped = set(state.get("skipped", []))

    actions: List[Dict] = []
    for action in iter_actions(plan):
        target = action["target"]
        if target in processed or target in skipped:
            continue

        target_path = Path(target)
        master_path = Path(action["master"])

        if not master_path.exists() or not target_path.exists():
            skipped.add(target)
            continue

        if os.path.islink(target_path):
            processed.add(target)
            continue

        actions.append(action)
        if len(actions) >= batch_size:
            break

    state["aliased"] = list(processed)
    state["skipped"] = list(skipped)
    return actions, state


def create_alias(master: Path, target: Path, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "dry-run"

    if not master.exists():
        return False, "master missing"
    if not target.exists():
        return False, "target missing"
    if os.path.islink(target):
        return False, "target already symlink"

    temp_backup = target.with_suffix(target.suffix + ".dupbackup")
    try:
        target.rename(temp_backup)
    except OSError as exc:
        return False, f"rename failed: {exc}"

    try:
        os.symlink(master, target)
    except OSError as exc:
        temp_backup.rename(target)
        return False, f"symlink failed: {exc}"

    try:
        temp_backup.unlink()
    except OSError:
        # fall back to trash-like location if delete fails
        try:
            trash_dir = Path.home() / ".Trash"
            trash_dir.mkdir(exist_ok=True)
            shutil.move(str(temp_backup), trash_dir / temp_backup.name)
        except OSError:
            pass

    return True, "alias created"


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch alias duplicate PDFs.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of duplicate files to convert per run (default: 100)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply changes (default: dry-run preview only).",
    )
    parser.add_argument(
        "--refresh-plan",
        action="store_true",
        help="Rebuild duplicate plan from the PDF cache before processing.",
    )
    parser.add_argument(
        "--min-copies",
        type=int,
        default=2,
        help="Minimum copies required to include a hash when refreshing the plan.",
    )
    args = parser.parse_args()

    dry_run = not args.execute

    if args.refresh_plan:
        print("🔄 Refreshing duplicate plan...")
        build_plan(min_copies=args.min_copies)

    actions, state = prepare_actions(batch_size=args.batch_size, dry_run=dry_run)
    if not actions:
        print("🎉 No duplicate files remain (plan exhausted).")
        return

    successes = 0
    failures = 0
    new_processed: List[str] = []
    new_skipped: List[str] = []

    print(f"{'DRY-RUN' if dry_run else 'EXECUTING'} batch of {len(actions)} duplicates...\n")

    for action in actions:
        master = Path(action["master"])
        target = Path(action["target"])
        ok, message = create_alias(master, target, dry_run=dry_run)

        append_log(
            {
                "timestamp": datetime.now().isoformat(),
                "dry_run": dry_run,
                "success": ok,
                "message": message,
                "master": str(master),
                "target": str(target),
                "hash": action["hash"],
            }
        )

        if ok:
            successes += 1
            if not dry_run:
                new_processed.append(str(target))
            print(f"✅ {target.name} → alias to master ({message})")
        else:
            failures += 1
            new_skipped.append(str(target))
            print(f"❌ {target}: {message}")

    state.setdefault("aliased", [])
    state.setdefault("skipped", [])
    state["aliased"].extend(new_processed)
    state["skipped"].extend(new_skipped)
    state["aliased"] = sorted(set(state["aliased"]))
    state["skipped"] = sorted(set(state["skipped"]))
    write_json(STATE_FILE, state)

    print("\n" + "=" * 80)
    print(f"Mode     : {'DRY-RUN (no changes written)' if dry_run else 'LIVE execution'}")
    print(f"Success  : {successes}")
    print(f"Failures : {failures}")
    print(f"Plan file: {PLAN_FILE}")
    print(f"State file: {STATE_FILE}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
