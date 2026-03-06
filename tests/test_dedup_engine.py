"""Tests for organizer.dedup_engine module."""

from pathlib import Path

import pytest

from organizer.dedup_engine import (
    DedupEngine,
    DuplicateGroup,
    NearDupGroup,
    find_near_duplicates,
)
from organizer.file_dna import compute_file_hash


def test_dedup_engine_exact_duplicates(tmp_path: Path) -> None:
    """Hash-based exact duplicate detection."""
    (tmp_path / "a.txt").write_text("same content")
    (tmp_path / "b.txt").write_text("same content")
    (tmp_path / "c.txt").write_text("different")

    engine = DedupEngine(tmp_path)
    groups = engine.scan(extensions={".txt"})

    assert len(groups) == 1
    assert groups[0].sha256_hash == compute_file_hash(tmp_path / "a.txt")
    assert len(groups[0].duplicates) == 1
    assert groups[0].total_wasted_bytes == len("same content")


def test_dedup_engine_no_duplicates(tmp_path: Path) -> None:
    """No groups when all files unique."""
    (tmp_path / "a.txt").write_text("content a")
    (tmp_path / "b.txt").write_text("content b")

    engine = DedupEngine(tmp_path)
    groups = engine.scan(extensions={".txt"})

    assert len(groups) == 0


def test_find_near_duplicates(tmp_path: Path) -> None:
    """Filename-based near-duplicate detection."""
    (tmp_path / "report.pdf").write_text("x")
    (tmp_path / "report (1).pdf").write_text("x")
    (tmp_path / "report_copy.pdf").write_text("x")

    files = list(tmp_path.glob("*.pdf"))
    groups = find_near_duplicates(files)

    assert len(groups) >= 1
    assert any(len(g.files) >= 2 for g in groups)


def test_report_wasted_storage(tmp_path: Path) -> None:
    """report_wasted_storage returns total wasted bytes."""
    content = "duplicate content here"
    (tmp_path / "d1.txt").write_text(content)
    (tmp_path / "d2.txt").write_text(content)

    engine = DedupEngine(tmp_path)
    engine.scan(extensions={".txt"})

    assert engine.report_wasted_storage() == len(content)
