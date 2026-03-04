"""Tests for organizer.inbox_processor (rule-based classifier and router)."""

from pathlib import Path

import pytest

from organizer.inbox_processor import InboxProcessor


def test_date_signals_extracted_from_filename(tmp_path: Path) -> None:
    """Date signals should include years parsed from filename."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "Tax_2024.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert r.destination_bin == "Finances Bin/Taxes"
    assert "filename_years" in r.date_signals
    assert 2024 in r.date_signals["filename_years"]


def test_date_signals_include_mtime(tmp_path: Path) -> None:
    """Date signals should include mtime from file metadata."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "resume.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert "mtime_year" in r.date_signals
    assert "mtime_iso" in r.date_signals


def test_tax_with_year_gets_confidence_boost(tmp_path: Path) -> None:
    """Tax documents with year in filename get classified to Finances Bin/Taxes."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "Tax_Return_2023.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert r.destination_bin == "Finances Bin/Taxes"
    assert r.confidence >= 0.65


def test_category_mapper_fallback_for_suggestive_names(tmp_path: Path) -> None:
    """Files with names matching CategoryMapper get taxonomy-aligned destination."""
    inbox = tmp_path / "In-Box"
    inbox.mkdir(parents=True)
    (inbox / "Resume_JohnDoe.pdf").write_text("", encoding="utf-8")

    processor = InboxProcessor(base_path=str(tmp_path), inbox_name="In-Box")
    result = processor.scan()

    assert result.total_files == 1
    r = result.routings[0]
    assert r.destination_bin
    assert "Resume" in r.destination_bin or "Employment" in r.destination_bin or "category:" in str(r.matched_keywords)
