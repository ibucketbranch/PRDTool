"""Tests for organizer.learned_overrides module."""

from pathlib import Path

import pytest

from organizer.learned_overrides import (
    LearnedOverride,
    OverrideRegistry,
)


def test_add_and_find_match(tmp_path: Path) -> None:
    """Add override and find match by filename."""
    overrides_path = tmp_path / "learned_overrides.json"
    registry = OverrideRegistry(overrides_path)

    registry.add(
        LearnedOverride(
            pattern="neuropsych",
            correct_bin="VA/08_Evidence_Documents",
        )
    )

    match = registry.find_match("neuropsych_eval_2024.pdf")
    assert match is not None
    assert match.pattern == "neuropsych"
    assert match.correct_bin == "VA/08_Evidence_Documents"
    assert match.hit_count == 1


def test_find_match_case_insensitive(tmp_path: Path) -> None:
    """find_match is case-insensitive."""
    overrides_path = tmp_path / "learned_overrides.json"
    registry = OverrideRegistry(overrides_path)

    registry.add(LearnedOverride(pattern="tax", correct_bin="Finances Bin/Taxes"))

    assert registry.find_match("TAX_2024.pdf") is not None
    assert registry.find_match("Tax_Return.pdf") is not None


def test_override_takes_priority(tmp_path: Path) -> None:
    """Override replaces existing with same pattern."""
    overrides_path = tmp_path / "learned_overrides.json"
    registry = OverrideRegistry(overrides_path)

    registry.add(LearnedOverride(pattern="tax", correct_bin="BinA"))
    registry.add(LearnedOverride(pattern="tax", correct_bin="BinB"))

    all_overrides = registry.get_all()
    assert len(all_overrides) == 1
    assert all_overrides[0].correct_bin == "BinB"


def test_remove(tmp_path: Path) -> None:
    """remove deletes override by pattern."""
    overrides_path = tmp_path / "learned_overrides.json"
    registry = OverrideRegistry(overrides_path)

    registry.add(LearnedOverride(pattern="test", correct_bin="TestBin"))
    assert registry.find_match("test_file.pdf") is not None

    removed = registry.remove("test")
    assert removed is True
    assert registry.find_match("test_file.pdf") is None


def test_remove_nonexistent(tmp_path: Path) -> None:
    """remove returns False when pattern not found."""
    overrides_path = tmp_path / "learned_overrides.json"
    registry = OverrideRegistry(overrides_path)

    removed = registry.remove("nonexistent")
    assert removed is False
