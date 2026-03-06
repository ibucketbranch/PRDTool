#!/usr/bin/env python3
"""
Safely remove empty folders from iCloud Drive.
Respects PRDTool's keep policy (VA folders) and review keywords.
No Supabase required. Generates rollback script.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ICLOUD_BASE = Path(
    "/Users/michaelvalderrama/Library/Mobile Documents/com~apple~CloudDocs"
)

# Folders to NEVER remove (PRDTool keep policy)
KEEP_EXACT = [
    "VA/06_Benefits_and_Payments",
    "VA/07_Correspondence",
    "VA/08_Evidence_Documents",
    "VA/99_Imported",
]

# Folder names containing these → skip (needs review)
REVIEW_KEYWORDS = [
    "inbox", "to-file", "staging", "pipeline", "pending", "review",
]

# Don't descend into or count these
SKIP_DIRS = {
    ".Trash", ".DocumentRevisions-V100", ".Spotlight-V100", ".fseventsd",
    ".TemporaryItems", "__MACOSX", ".icloud", ".com.apple.icloud",
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    ".cache", ".local", ".config", ".organizer",
}


def is_effectively_empty(path: Path) -> bool:
    """True if folder has no visible (non-hidden) files or subdirs."""
    try:
        items = os.listdir(path)
        real = [i for i in items if not i.startswith(".")]
        return len(real) == 0
    except (PermissionError, OSError):
        return False


def has_protected_content(path: Path) -> bool:
    """True if folder contains .git or other protected dirs we can't remove."""
    try:
        items = os.listdir(path)
        protected = {".git", ".svn", ".hg"}
        return any(i in protected for i in items)
    except (PermissionError, OSError):
        return True


def should_keep(path: Path, base: Path) -> bool:
    """True if folder must be kept per policy."""
    try:
        rel = path.relative_to(base)
    except ValueError:
        return True
    rel_str = str(rel).replace("\\", "/")
    for keep in KEEP_EXACT:
        if rel_str == keep or rel_str.startswith(keep + "/"):
            return True
    return False


def should_review(path: Path) -> bool:
    """True if folder name suggests active workflow."""
    name = path.name.lower()
    return any(kw in name for kw in REVIEW_KEYWORDS)


def find_empty_folders(base: Path) -> list[Path]:
    """Find empty folders, excluding OS/system and policy-protected."""
    empty: list[Path] = []
    for root, dirs, files in os.walk(base, topdown=True):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        try:
            folder = Path(root)
            if not folder.is_dir():
                continue
            if not is_effectively_empty(folder):
                continue
            if folder == base:
                continue
            if has_protected_content(folder):
                continue
            if should_keep(folder, base):
                continue
            if should_review(folder):
                continue
            name = folder.name
            if name in SKIP_DIRS or name.startswith("."):
                continue
            empty.append(folder)
        except (PermissionError, OSError):
            pass
    return empty


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely remove empty iCloud folders")
    parser.add_argument("--execute", action="store_true", help="Actually remove folders")
    parser.add_argument("--base", type=Path, default=ICLOUD_BASE, help="Base path to scan")
    args = parser.parse_args()

    base = args.base.resolve()
    if not base.exists() or not base.is_dir():
        print(f"Error: Base path does not exist: {base}", file=sys.stderr)
        sys.exit(1)

    empty = find_empty_folders(base)
    # Deepest first so we can rmdir children before parents
    empty_sorted = sorted(empty, key=lambda p: (-len(p.parts), str(p)))

    print("=" * 70)
    print("SAFE EMPTY FOLDER REMOVAL")
    print("=" * 70)
    print(f"Base: {base}")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"Found: {len(empty_sorted)} empty folders (policy-protected excluded)")
    print()

    if not empty_sorted:
        print("No empty folders to remove.")
        return

    # Rollback script path
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rollback_path = base / ".organizer" / "agent" / f"empty_folder_rollback_{ts}.sh"

    if args.execute:
        removed = 0
        errors = 0
        rollback_lines = ["#!/bin/bash", "# Rollback: recreate removed empty folders", ""]
        for folder in empty_sorted:
            try:
                # Remove .DS_Store etc first
                for f in folder.iterdir():
                    if f.name.startswith("."):
                        f.unlink()
                folder.rmdir()
                print(f"  Removed: {folder.relative_to(base)}")
                rollback_lines.append(f"mkdir -p '{folder}'")
                removed += 1
            except OSError as e:
                print(f"  Error: {folder.relative_to(base)}: {e}", file=sys.stderr)
                errors += 1

        if rollback_lines:
            rollback_path.parent.mkdir(parents=True, exist_ok=True)
            rollback_path.write_text("\n".join(rollback_lines) + "\n", encoding="utf-8")
            rollback_path.chmod(0o755)
            print(f"\nRollback script: {rollback_path}")

        print(f"\nDone. Removed: {removed}, Errors: {errors}")
    else:
        print("Folders that would be removed (first 30):")
        for p in empty_sorted[:30]:
            print(f"  {p.relative_to(base)}")
        if len(empty_sorted) > 30:
            print(f"  ... and {len(empty_sorted) - 30} more")
        print(f"\nTo remove, run: python3 {sys.argv[0]} --execute")


if __name__ == "__main__":
    main()
