"""Tests for the Goldilocks database schema."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from organizer.schema import init_database


def test_init_creates_database(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_database(db_path)
    assert Path(db_path).exists()
    conn.close()


def test_init_creates_documents_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_database(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='documents'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_init_creates_document_locations_table(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_database(db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='document_locations'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_documents_has_expected_columns(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_database(db_path)
    cursor = conn.execute("PRAGMA table_info(documents)")
    columns = {row[1] for row in cursor.fetchall()}
    expected = {
        "id", "filename", "current_path", "file_hash", "file_size",
        "file_extension", "ai_category", "ai_subcategories", "ai_summary",
        "entities", "key_dates", "folder_hierarchy", "original_path",
        "canonical_folder", "rename_status", "content_preview",
        "classification_confidence", "classification_model",
        "indexed_at", "updated_at",
    }
    assert expected.issubset(columns)
    conn.close()


def test_init_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn1 = init_database(db_path)
    conn1.execute(
        "INSERT INTO documents (filename, current_path, indexed_at, updated_at) VALUES (?, ?, ?, ?)",
        ("test.pdf", "/test/test.pdf", "2025-01-01", "2025-01-01"),
    )
    conn1.commit()
    conn1.close()

    conn2 = init_database(db_path)
    count = conn2.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert count == 1
    conn2.close()


def test_indexes_exist(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = init_database(db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    index_names = {row[0] for row in cursor.fetchall()}
    assert "idx_documents_current_path" in index_names
    assert "idx_documents_file_hash" in index_names
    assert "idx_documents_ai_category" in index_names
    conn.close()
