"""Ingestion pipeline orchestrator for Goldilocks content indexing.

Scans the filesystem, collects file signals, classifies via LLM,
and stores results in the SQLite database. Supports incremental
ingestion, batching, and resume by file hash.
"""

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from organizer.light_extractor import (
    FileSignals,
    collect_signals,
    SKIP_CONTENT_EXTENSIONS,
)
from organizer.llm_classifier import Classification, classify_file
from organizer.schema import init_database

SUPPORTED_EXTENSIONS = frozenset({
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".txt", ".md", ".csv", ".log", ".rtf",
    ".json", ".xml", ".yaml", ".yml",
    ".html", ".htm",
    ".doc", ".key", ".numbers", ".pages",
    ".py", ".js", ".ts", ".sh", ".cfg", ".ini", ".conf",
    ".png", ".jpg", ".jpeg", ".gif", ".tiff", ".bmp", ".heic", ".webp",
    ".mp4", ".mov", ".m4v", ".avi", ".mkv",
    ".mp3", ".m4a", ".wav",
    ".zip", ".gz", ".tar", ".dmg",
})


@dataclass
class IngestionProgress:
    total: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    elapsed_seconds: float = 0.0

    @property
    def remaining(self) -> int:
        return self.total - self.processed - self.skipped - self.failed


class IngestionPipeline:
    def __init__(
        self,
        db_path: str,
        fast_model: str = "llama3.1:8b-instruct-q8_0",
        smart_model: str = "qwen2.5-coder:14b",
        escalation_threshold: float = 0.7,
        rate_limit_seconds: float = 0.5,
    ):
        self.db_path = db_path
        self.fast_model = fast_model
        self.smart_model = smart_model
        self.escalation_threshold = escalation_threshold
        self.rate_limit_seconds = rate_limit_seconds
        self.conn = init_database(db_path)

    def scan(
        self,
        base_path: str,
        max_depth: int = 3,
    ) -> list[str]:
        """Walk filesystem and find files not yet indexed.

        Returns list of file paths to ingest.
        """
        indexed_hashes = self._get_indexed_hashes()
        files_to_ingest: list[str] = []

        self._walk_directory(
            Path(base_path), max_depth, 0,
            files_to_ingest, indexed_hashes,
        )

        return files_to_ingest

    def ingest_file(self, file_path: str) -> bool:
        """Ingest a single file: collect signals, classify, store.

        Returns True if successfully ingested.
        """
        try:
            file_hash = _compute_hash(file_path)

            if self._is_indexed(file_hash):
                return False

            signals = collect_signals(file_path)
            classification = classify_file(
                signals,
                fast_model=self.fast_model,
                smart_model=self.smart_model,
                escalation_threshold=self.escalation_threshold,
                rate_limit_seconds=self.rate_limit_seconds,
            )
            self._store(signals, classification, file_hash)
            return True
        except Exception:
            return False

    def ingest_batch(
        self,
        file_paths: list[str],
        batch_size: int = 20,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionProgress:
        """Process a batch of files with progress tracking.

        Commits to DB every batch_size files.
        """
        progress = IngestionProgress(total=len(file_paths))
        start_time = time.time()

        for i, file_path in enumerate(file_paths):
            try:
                if self.ingest_file(file_path):
                    progress.processed += 1
                else:
                    progress.skipped += 1
            except Exception:
                progress.failed += 1

            if (i + 1) % batch_size == 0:
                self.conn.commit()
                progress.elapsed_seconds = time.time() - start_time
                if progress_callback:
                    progress_callback(progress)

        self.conn.commit()
        progress.elapsed_seconds = time.time() - start_time
        if progress_callback:
            progress_callback(progress)

        return progress

    def ingest_all(
        self,
        base_path: str,
        max_depth: int = 3,
        max_files: int | None = None,
        batch_size: int = 20,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionProgress:
        """Full scan + ingest."""
        files = self.scan(base_path, max_depth)
        if max_files:
            files = files[:max_files]
        return self.ingest_batch(files, batch_size, progress_callback)

    def get_stats(self) -> dict:
        """Return database statistics."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM documents")
        total = cursor.fetchone()[0]

        cursor = self.conn.execute(
            "SELECT ai_category, COUNT(*) FROM documents GROUP BY ai_category ORDER BY COUNT(*) DESC"
        )
        categories = {row[0] or "uncategorized": row[1] for row in cursor.fetchall()}

        cursor = self.conn.execute(
            "SELECT AVG(classification_confidence), MIN(classification_confidence), MAX(classification_confidence) FROM documents"
        )
        conf_row = cursor.fetchone()

        cursor = self.conn.execute(
            "SELECT classification_model, COUNT(*) FROM documents GROUP BY classification_model"
        )
        models = {row[0] or "unknown": row[1] for row in cursor.fetchall()}

        return {
            "total_documents": total,
            "categories": categories,
            "confidence": {
                "avg": round(conf_row[0] or 0, 3),
                "min": round(conf_row[1] or 0, 3),
                "max": round(conf_row[2] or 0, 3),
            },
            "models_used": models,
        }

    def close(self) -> None:
        self.conn.close()

    def _walk_directory(
        self,
        path: Path,
        max_depth: int,
        current_depth: int,
        results: list[str],
        indexed_hashes: set[str],
    ) -> None:
        if current_depth > max_depth:
            return

        try:
            entries = list(os.scandir(path))
        except (PermissionError, OSError):
            return

        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.name.endswith(".icloud"):
                continue

            if entry.is_file(follow_symlinks=False):
                ext = Path(entry.name).suffix.lower()
                if ext not in SUPPORTED_EXTENSIONS and ext not in SKIP_CONTENT_EXTENSIONS:
                    continue
                try:
                    file_hash = _compute_hash(entry.path)
                    if file_hash not in indexed_hashes:
                        results.append(entry.path)
                except OSError:
                    continue

            elif entry.is_dir(follow_symlinks=False):
                self._walk_directory(
                    Path(entry.path), max_depth, current_depth + 1,
                    results, indexed_hashes,
                )

    def _get_indexed_hashes(self) -> set[str]:
        cursor = self.conn.execute("SELECT file_hash FROM documents WHERE file_hash IS NOT NULL")
        return {row[0] for row in cursor.fetchall()}

    def _is_indexed(self, file_hash: str) -> bool:
        cursor = self.conn.execute(
            "SELECT 1 FROM documents WHERE file_hash = ?", (file_hash,)
        )
        return cursor.fetchone() is not None

    def _store(
        self,
        signals: FileSignals,
        classification: Classification,
        file_hash: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        folder_parts = signals.parent_folders

        self.conn.execute(
            """INSERT OR REPLACE INTO documents (
                filename, current_path, file_hash, file_size, file_extension,
                ai_category, ai_subcategories, ai_summary, entities, key_dates,
                folder_hierarchy, original_path, content_preview,
                classification_confidence, classification_model,
                indexed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signals.filename,
                signals.file_path,
                file_hash,
                signals.file_size,
                signals.extension,
                classification.category,
                json.dumps([classification.subcategory]) if classification.subcategory else "[]",
                classification.summary,
                json.dumps(classification.entities),
                json.dumps(classification.key_dates),
                json.dumps(folder_parts),
                signals.file_path,
                signals.content_preview,
                classification.confidence,
                classification.model_used,
                now,
                now,
            ),
        )

        doc_id = self.conn.execute(
            "SELECT id FROM documents WHERE file_hash = ?", (file_hash,)
        ).fetchone()

        if doc_id:
            self.conn.execute(
                """INSERT INTO document_locations (document_id, path, location_type, created_at)
                   VALUES (?, ?, 'current', ?)""",
                (doc_id[0], signals.file_path, now),
            )


def _compute_hash(file_path: str, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file (first 1MB for speed)."""
    h = hashlib.sha256()
    bytes_read = 0
    max_bytes = 1024 * 1024

    with open(file_path, "rb") as f:
        while bytes_read < max_bytes:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
            bytes_read += len(chunk)

    return h.hexdigest()
