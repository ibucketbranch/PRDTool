"""Deduplication engine for exact and near-duplicate file detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from organizer.file_dna import compute_file_hash


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass
class DuplicateGroup:
    """A group of duplicate files (exact hash match)."""

    sha256_hash: str
    canonical_path: str
    duplicates: list[str] = field(default_factory=list)
    total_wasted_bytes: int = 0
    first_seen_at: str = ""

    def __post_init__(self) -> None:
        if not self.first_seen_at:
            self.first_seen_at = _now_iso()


@dataclass
class NearDupGroup:
    """A group of near-duplicate files (fuzzy filename match)."""

    base_name: str
    files: list[str] = field(default_factory=list)
    confidence: float = 0.0


def _normalize_filename_for_dedup(name: str) -> str:
    """Normalize filename for near-duplicate comparison."""
    from organizer.fuzzy_matcher import normalize_folder_name

    stem = Path(name).stem
    # Remove common copy patterns: (1), _copy, _copy2, copy of
    import re
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    stem = re.sub(r"_copy\d*$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"^copy of\s+", "", stem, flags=re.IGNORECASE)
    return normalize_folder_name(stem)


def find_near_duplicates(files: list[Path]) -> list[NearDupGroup]:
    """Find filename-based near-duplicates (report.pdf vs report (1).pdf)."""
    from difflib import SequenceMatcher

    if len(files) < 2:
        return []

    normalized: dict[str, list[Path]] = {}
    for f in files:
        if not f.is_file():
            continue
        norm = _normalize_filename_for_dedup(f.name)
        if norm:
            normalized.setdefault(norm, []).append(f)

    groups: list[NearDupGroup] = []
    for norm, paths in normalized.items():
        if len(paths) < 2:
            continue
        # Sort by name for consistent canonical
        paths_sorted = sorted(paths, key=lambda p: p.name)
        canonical = paths_sorted[0]
        dupes = [str(p) for p in paths_sorted[1:]]
        # Confidence: higher if names are very similar
        conf = 0.7
        if any("(1)" in p.name or "copy" in p.name.lower() for p in paths_sorted[1:]):
            conf = 0.9
        groups.append(
            NearDupGroup(
                base_name=canonical.name,
                files=[str(canonical)] + dupes,
                confidence=conf,
            )
        )
    return groups


class DedupEngine:
    """Scan directory tree for exact and near-duplicate files."""

    def __init__(self, scan_path: str | Path):
        self.scan_path = Path(scan_path)
        self._hash_to_paths: dict[str, list[str]] = {}
        self._groups: list[DuplicateGroup] = []

    def scan(
        self,
        extensions: set[str] | None = None,
        max_files: int = 10_000,
    ) -> list[DuplicateGroup]:
        """Scan directory, compute hashes, build duplicate groups."""
        if extensions is None:
            extensions = {".pdf", ".doc", ".docx", ".txt", ".xlsx", ".pptx"}

        all_files: list[Path] = []
        for ext in extensions:
            all_files.extend(self.scan_path.rglob(f"*{ext}"))

        all_files = [f for f in all_files if f.is_file()][:max_files]
        self._hash_to_paths.clear()
        self._groups.clear()

        for f in all_files:
            try:
                h = compute_file_hash(f)
                self._hash_to_paths.setdefault(h, []).append(str(f))
            except (OSError, FileNotFoundError):
                continue

        for h, paths in self._hash_to_paths.items():
            if len(paths) < 2:
                continue
            canonical = min(paths)
            dupes = [p for p in paths if p != canonical]
            total_bytes = 0
            try:
                for p in dupes:
                    total_bytes += Path(p).stat().st_size
            except OSError:
                pass
            self._groups.append(
                DuplicateGroup(
                    sha256_hash=h,
                    canonical_path=canonical,
                    duplicates=dupes,
                    total_wasted_bytes=total_bytes,
                )
            )

        return self._groups

    def get_groups(self) -> list[DuplicateGroup]:
        """Return duplicate groups from last scan."""
        return list(self._groups)

    def report_wasted_storage(self) -> int:
        """Total wasted bytes across all duplicate groups."""
        return sum(g.total_wasted_bytes for g in self._groups)
