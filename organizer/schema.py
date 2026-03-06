"""Database schema for the content ingestion pipeline.

Creates and manages the SQLite database that stores document metadata,
classifications, and location history. Schema aligns with the columns
expected by content_analyzer.py's get_folder_metadata() query.
"""

import sqlite3
from pathlib import Path


def init_database(db_path: str) -> sqlite3.Connection:
    """Create the database and tables if they don't exist.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Open connection to the initialized database.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT NOT NULL,
            current_path    TEXT UNIQUE NOT NULL,
            file_hash       TEXT,
            file_size       INTEGER,
            file_extension  TEXT,
            ai_category     TEXT,
            ai_subcategories TEXT,
            ai_summary      TEXT,
            entities        TEXT,
            key_dates       TEXT,
            folder_hierarchy TEXT,
            original_path   TEXT,
            canonical_folder TEXT,
            rename_status   TEXT DEFAULT 'pending',
            content_preview TEXT,
            classification_confidence REAL,
            classification_model TEXT,
            pdf_created_date TEXT,
            pdf_modified_date TEXT,
            indexed_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS document_locations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id     INTEGER NOT NULL,
            path            TEXT NOT NULL,
            location_type   TEXT NOT NULL DEFAULT 'current',
            created_at      TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_documents_current_path
            ON documents(current_path);
        CREATE INDEX IF NOT EXISTS idx_documents_file_hash
            ON documents(file_hash);
        CREATE INDEX IF NOT EXISTS idx_documents_ai_category
            ON documents(ai_category);
        CREATE INDEX IF NOT EXISTS idx_documents_confidence
            ON documents(classification_confidence);
        CREATE INDEX IF NOT EXISTS idx_document_locations_document_id
            ON document_locations(document_id);
        CREATE INDEX IF NOT EXISTS idx_document_locations_path
            ON document_locations(path);
    """)

    conn.commit()
    return conn
