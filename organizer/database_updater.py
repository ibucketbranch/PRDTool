"""Database integration for file consolidation operations.

This module provides database update functionality when files are moved during
consolidation. It updates document_locations and documents tables to reflect
new file paths.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from organizer.file_operations import ExecutionResult, FileMoveResult, MoveStatus


class DatabaseConnection(Protocol):
    """Protocol for database connections to allow for different backends."""

    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...


@dataclass
class DocumentUpdate:
    """Record of a document update in the database."""

    file_path: str
    old_path: str
    new_path: str
    canonical_folder: str
    status: str
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "old_path": self.old_path,
            "new_path": self.new_path,
            "canonical_folder": self.canonical_folder,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class DatabaseUpdateResult:
    """Result of updating database after file moves."""

    documents_updated: int = 0
    locations_added: int = 0
    locations_marked_previous: int = 0
    errors: list[str] = None
    document_updates: list[DocumentUpdate] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.document_updates is None:
            self.document_updates = []

    @property
    def success(self) -> bool:
        """Check if the update was successful (no errors)."""
        return len(self.errors) == 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "documents_updated": self.documents_updated,
            "locations_added": self.locations_added,
            "locations_marked_previous": self.locations_marked_previous,
            "errors": self.errors,
            "success": self.success,
            "document_updates": [u.to_dict() for u in self.document_updates],
        }


def get_database_connection(db_path: str | Path) -> sqlite3.Connection:
    """Get a connection to the SQLite database.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLite connection object.

    Raises:
        FileNotFoundError: If the database file doesn't exist.
        sqlite3.Error: If connection fails.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    return sqlite3.connect(str(db_path))


def update_document_location(
    conn: DatabaseConnection,
    old_path: str,
    new_path: str,
    canonical_folder: str,
) -> DocumentUpdate:
    """Update database records for a single file move.

    This function:
    1. Finds the document by its current path
    2. Marks the old location as 'previous' in document_locations
    3. Adds new location entry in document_locations
    4. Updates current_path in documents table
    5. Sets canonical_folder and rename_status='done'

    Args:
        conn: Database connection.
        old_path: Original file path.
        new_path: New file path after move.
        canonical_folder: The canonical folder the file was moved to.

    Returns:
        DocumentUpdate with status of the operation.
    """
    update = DocumentUpdate(
        file_path=Path(new_path).name,
        old_path=old_path,
        new_path=new_path,
        canonical_folder=canonical_folder,
        status="success",
    )

    try:
        cursor = conn.execute(
            "SELECT id FROM documents WHERE current_path = ?",
            (old_path,),
        )
        row = cursor.fetchone()

        if row is None:
            # Document not found in database - this is not an error,
            # the file may not be tracked
            update.status = "not_found"
            return update

        document_id = row[0]
        timestamp = datetime.now().isoformat()

        # Mark old location as previous
        conn.execute(
            """
            UPDATE document_locations
            SET location_type = 'previous'
            WHERE document_id = ? AND location_type = 'current'
            """,
            (document_id,),
        )

        # Add new location entry
        conn.execute(
            """
            INSERT INTO document_locations (document_id, path, location_type, created_at)
            VALUES (?, ?, 'current', ?)
            """,
            (document_id, new_path, timestamp),
        )

        # Update documents table
        conn.execute(
            """
            UPDATE documents
            SET current_path = ?,
                canonical_folder = ?,
                rename_status = 'done',
                updated_at = ?
            WHERE id = ?
            """,
            (new_path, canonical_folder, timestamp, document_id),
        )

        return update

    except sqlite3.Error as e:
        update.status = "error"
        update.error = str(e)
        return update


def update_database_for_file_move(
    conn: DatabaseConnection,
    file_result: FileMoveResult,
    canonical_folder: str,
) -> DocumentUpdate | None:
    """Update database for a single file move result.

    Args:
        conn: Database connection.
        file_result: Result of the file move operation.
        canonical_folder: The canonical folder the file was moved to.

    Returns:
        DocumentUpdate if the file was successfully moved, None otherwise.
    """
    if file_result.status != MoveStatus.SUCCESS:
        return None

    return update_document_location(
        conn=conn,
        old_path=file_result.source_path,
        new_path=file_result.target_path,
        canonical_folder=canonical_folder,
    )


def update_database_for_execution(
    conn: DatabaseConnection,
    result: ExecutionResult,
) -> DatabaseUpdateResult:
    """Update database for all file moves in an execution result.

    This processes all successful file moves from the execution result
    and updates the database accordingly.

    Args:
        conn: Database connection.
        result: The execution result containing all file moves.

    Returns:
        DatabaseUpdateResult with summary of all updates.
    """
    db_result = DatabaseUpdateResult()

    for group_result in result.group_results:
        canonical_folder = group_result.target_folder

        for folder_result in group_result.folder_results:
            for file_result in folder_result.file_results:
                update = update_database_for_file_move(
                    conn=conn,
                    file_result=file_result,
                    canonical_folder=canonical_folder,
                )

                if update is None:
                    continue

                db_result.document_updates.append(update)

                if update.status == "success":
                    db_result.documents_updated += 1
                    db_result.locations_added += 1
                    db_result.locations_marked_previous += 1
                elif update.status == "error":
                    db_result.errors.append(
                        f"Failed to update {update.file_path}: {update.error}"
                    )
                # "not_found" status is not an error - file just wasn't tracked

    return db_result


def update_database_from_execution_result(
    db_path: str | Path,
    result: ExecutionResult,
) -> DatabaseUpdateResult:
    """Update database from an execution result using a database file path.

    This is a convenience function that handles connection management.

    Args:
        db_path: Path to the SQLite database file.
        result: The execution result containing all file moves.

    Returns:
        DatabaseUpdateResult with summary of all updates.

    Raises:
        FileNotFoundError: If the database file doesn't exist.
    """
    conn = get_database_connection(db_path)
    try:
        db_result = update_database_for_execution(conn, result)
        conn.commit()
        return db_result
    finally:
        conn.close()


def check_database_schema(conn: DatabaseConnection) -> tuple[bool, list[str]]:
    """Check if the database has the required schema.

    Args:
        conn: Database connection.

    Returns:
        Tuple of (schema_valid, missing_items).
    """
    required_tables = ["documents", "document_locations"]
    required_columns = {
        "documents": ["id", "current_path", "canonical_folder", "rename_status"],
        "document_locations": ["document_id", "path", "location_type"],
    }

    missing = []

    # Check tables exist
    for table in required_tables:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if cursor.fetchone() is None:
            missing.append(f"table:{table}")

    # Check columns exist
    for table, columns in required_columns.items():
        try:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            existing_columns = {row[1] for row in cursor.fetchall()}
            for column in columns:
                if column not in existing_columns:
                    missing.append(f"column:{table}.{column}")
        except sqlite3.Error:
            pass  # Table doesn't exist, already captured above

    return len(missing) == 0, missing
