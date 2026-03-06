"""Tests for the Goldilocks light extractor."""

import os
import tempfile
from pathlib import Path

import pytest

from organizer.light_extractor import (
    FileSignals,
    collect_signals,
    MAX_PREVIEW_CHARS,
    SKIP_CONTENT_EXTENSIONS,
    TEXT_EXTENSIONS,
    _extract_plain,
)


@pytest.fixture
def tmp_text_file(tmp_path):
    f = tmp_path / "test_doc.txt"
    f.write_text("Hello world, this is a test document for content extraction.")
    return str(f)


@pytest.fixture
def tmp_large_file(tmp_path):
    f = tmp_path / "large.txt"
    f.write_text("A" * 2000)
    return str(f)


@pytest.fixture
def tmp_json_file(tmp_path):
    f = tmp_path / "config.json"
    f.write_text('{"key": "value", "nested": {"a": 1}}')
    return str(f)


def test_collect_signals_text_file(tmp_text_file):
    signals = collect_signals(tmp_text_file)
    assert isinstance(signals, FileSignals)
    assert signals.filename == "test_doc.txt"
    assert signals.extension == ".txt"
    assert signals.file_size > 0
    assert "Hello world" in signals.content_preview
    assert signals.extraction_method == "filename_only"  # fallthrough
    assert len(signals.content_preview) <= MAX_PREVIEW_CHARS


def test_collect_signals_json_file(tmp_json_file):
    signals = collect_signals(tmp_json_file)
    assert signals.filename == "config.json"
    assert signals.extension == ".json"
    assert '"key"' in signals.content_preview


def test_content_preview_truncated(tmp_large_file):
    signals = collect_signals(tmp_large_file)
    assert len(signals.content_preview) <= MAX_PREVIEW_CHARS


def test_skip_content_for_images(tmp_path):
    img = tmp_path / "photo.png"
    img.write_bytes(b"\x89PNG" + b"\x00" * 100)
    signals = collect_signals(str(img))
    assert signals.content_preview == ""
    assert signals.extraction_method == "filename_only"


def test_parent_folders(tmp_path):
    nested = tmp_path / "sub1" / "sub2"
    nested.mkdir(parents=True)
    f = nested / "deep.txt"
    f.write_text("deep content")
    signals = collect_signals(str(f))
    assert len(signals.parent_folders) > 0


def test_extract_plain_utf8(tmp_path):
    f = tmp_path / "unicode.txt"
    f.write_text("Ünïcödé text with ñ and ü", encoding="utf-8")
    result = _extract_plain(f)
    assert "Ünïcödé" in result


def test_skip_content_extensions_frozen():
    assert ".png" in SKIP_CONTENT_EXTENSIONS
    assert ".mp4" in SKIP_CONTENT_EXTENSIONS
    assert ".zip" in SKIP_CONTENT_EXTENSIONS
    assert ".icloud" in SKIP_CONTENT_EXTENSIONS


def test_text_extensions_frozen():
    assert ".txt" in TEXT_EXTENSIONS
    assert ".md" in TEXT_EXTENSIONS
    assert ".json" in TEXT_EXTENSIONS
    assert ".py" in TEXT_EXTENSIONS
