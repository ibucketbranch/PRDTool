"""Tests for the database_updater module."""

import sqlite3
from pathlib import Path

import pytest

from organizer.database_updater import (
    DatabaseUpdateResult,
    DocumentUpdate,
    check_database_schema,
    get_database_connection,
    update_database_for_execution,
    update_database_for_file_move,
    update_database_from_execution_result,
    update_document_location,
)
from organizer.file_operations import (
    ExecutionResult,
    FileMoveResult,
    FolderMoveResult,
    GroupMoveResult,
    MoveStatus,
)


def create_test_database(db_path: Path) -> sqlite3.Connection:
    """Create a test database with the required schema."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            filename TEXT,
            current_path TEXT,
            canonical_folder TEXT,
            rename_status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE document_locations (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            path TEXT,
            location_type TEXT DEFAULT 'current',
            created_at TEXT,
            FOREIGN KEY (document_id) REFERENCES documents (id)
        )
    """)
    conn.commit()
    return conn


def insert_test_document(
    conn: sqlite3.Connection,
    doc_id: int,
    filename: str,
    current_path: str,
) -> None:
    """Insert a test document into the database."""
    conn.execute(
        """
        INSERT INTO documents (id, filename, current_path, rename_status, created_at)
        VALUES (?, ?, ?, 'pending', datetime('now'))
        """,
        (doc_id, filename, current_path),
    )
    conn.execute(
        """
        INSERT INTO document_locations (document_id, path, location_type, created_at)
        VALUES (?, ?, 'current', datetime('now'))
        """,
        (doc_id, current_path),
    )
    conn.commit()


class TestDocumentUpdate:
    """Tests for DocumentUpdate dataclass."""

    def test_create_document_update(self):
        """Test creating a DocumentUpdate."""
        update = DocumentUpdate(
            file_path="test.pdf",
            old_path="/old/test.pdf",
            new_path="/new/test.pdf",
            canonical_folder="/new",
            status="success",
        )
        assert update.file_path == "test.pdf"
        assert update.old_path == "/old/test.pdf"
        assert update.new_path == "/new/test.pdf"
        assert update.canonical_folder == "/new"
        assert update.status == "success"
        assert update.error == ""

    def test_document_update_with_error(self):
        """Test DocumentUpdate with error."""
        update = DocumentUpdate(
            file_path="test.pdf",
            old_path="/old/test.pdf",
            new_path="/new/test.pdf",
            canonical_folder="/new",
            status="error",
            error="Database error",
        )
        assert update.status == "error"
        assert update.error == "Database error"

    def test_document_update_to_dict(self):
        """Test to_dict serialization."""
        update = DocumentUpdate(
            file_path="test.pdf",
            old_path="/old/test.pdf",
            new_path="/new/test.pdf",
            canonical_folder="/new",
            status="success",
        )
        d = update.to_dict()
        assert d["file_path"] == "test.pdf"
        assert d["old_path"] == "/old/test.pdf"
        assert d["new_path"] == "/new/test.pdf"
        assert d["canonical_folder"] == "/new"
        assert d["status"] == "success"
        assert d["error"] == ""


class TestDatabaseUpdateResult:
    """Tests for DatabaseUpdateResult dataclass."""

    def test_create_empty_result(self):
        """Test creating an empty DatabaseUpdateResult."""
        result = DatabaseUpdateResult()
        assert result.documents_updated == 0
        assert result.locations_added == 0
        assert result.locations_marked_previous == 0
        assert result.errors == []
        assert result.document_updates == []
        assert result.success is True

    def test_result_with_updates(self):
        """Test DatabaseUpdateResult with updates."""
        result = DatabaseUpdateResult(
            documents_updated=5,
            locations_added=5,
            locations_marked_previous=5,
        )
        assert result.documents_updated == 5
        assert result.success is True

    def test_result_with_errors(self):
        """Test DatabaseUpdateResult with errors."""
        result = DatabaseUpdateResult(
            errors=["Error 1", "Error 2"],
        )
        assert result.success is False
        assert len(result.errors) == 2

    def test_result_to_dict(self):
        """Test to_dict serialization."""
        update = DocumentUpdate(
            file_path="test.pdf",
            old_path="/old/test.pdf",
            new_path="/new/test.pdf",
            canonical_folder="/new",
            status="success",
        )
        result = DatabaseUpdateResult(
            documents_updated=1,
            locations_added=1,
            locations_marked_previous=1,
            document_updates=[update],
        )
        d = result.to_dict()
        assert d["documents_updated"] == 1
        assert d["success"] is True
        assert len(d["document_updates"]) == 1


class TestGetDatabaseConnection:
    """Tests for get_database_connection function."""

    def test_connect_to_existing_database(self, tmp_path):
        """Test connecting to an existing database."""
        db_path = tmp_path / "test.db"
        # Create the database first
        conn = sqlite3.connect(str(db_path))
        conn.close()

        # Now connect to it
        conn = get_database_connection(db_path)
        assert conn is not None
        conn.close()

    def test_connect_to_nonexistent_database(self, tmp_path):
        """Test connecting to a nonexistent database raises error."""
        db_path = tmp_path / "nonexistent.db"
        with pytest.raises(FileNotFoundError):
            get_database_connection(db_path)


class TestUpdateDocumentLocation:
    """Tests for update_document_location function."""

    def test_update_existing_document(self, tmp_path):
        """Test updating an existing document."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)
        insert_test_document(conn, 1, "resume.pdf", "/old/Resume/resume.pdf")

        update = update_document_location(
            conn=conn,
            old_path="/old/Resume/resume.pdf",
            new_path="/new/Employment/Resumes/resume.pdf",
            canonical_folder="/new/Employment/Resumes",
        )
        conn.commit()

        assert update.status == "success"
        assert update.new_path == "/new/Employment/Resumes/resume.pdf"

        # Verify documents table was updated
        cursor = conn.execute(
            "SELECT current_path, canonical_folder, rename_status FROM documents WHERE id = 1"
        )
        row = cursor.fetchone()
        assert row[0] == "/new/Employment/Resumes/resume.pdf"
        assert row[1] == "/new/Employment/Resumes"
        assert row[2] == "done"

        # Verify old location marked as previous
        cursor = conn.execute(
            "SELECT location_type FROM document_locations WHERE path = ?",
            ("/old/Resume/resume.pdf",),
        )
        row = cursor.fetchone()
        assert row[0] == "previous"

        # Verify new location added as current
        cursor = conn.execute(
            "SELECT location_type FROM document_locations WHERE path = ?",
            ("/new/Employment/Resumes/resume.pdf",),
        )
        row = cursor.fetchone()
        assert row[0] == "current"

        conn.close()

    def test_update_nonexistent_document(self, tmp_path):
        """Test updating a document that doesn't exist in database."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        update = update_document_location(
            conn=conn,
            old_path="/nonexistent/file.pdf",
            new_path="/new/file.pdf",
            canonical_folder="/new",
        )

        assert update.status == "not_found"
        conn.close()

    def test_multiple_updates_same_document(self, tmp_path):
        """Test multiple updates to the same document."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)
        insert_test_document(conn, 1, "doc.pdf", "/v1/doc.pdf")

        # First update
        update1 = update_document_location(
            conn=conn,
            old_path="/v1/doc.pdf",
            new_path="/v2/doc.pdf",
            canonical_folder="/v2",
        )
        conn.commit()
        assert update1.status == "success"

        # Second update
        update2 = update_document_location(
            conn=conn,
            old_path="/v2/doc.pdf",
            new_path="/v3/doc.pdf",
            canonical_folder="/v3",
        )
        conn.commit()
        assert update2.status == "success"

        # Verify current path
        cursor = conn.execute("SELECT current_path FROM documents WHERE id = 1")
        assert cursor.fetchone()[0] == "/v3/doc.pdf"

        # Verify location history
        cursor = conn.execute(
            "SELECT COUNT(*) FROM document_locations WHERE document_id = 1"
        )
        assert cursor.fetchone()[0] == 3  # Original + 2 updates

        conn.close()


class TestUpdateDatabaseForFileMove:
    """Tests for update_database_for_file_move function."""

    def test_update_for_successful_move(self, tmp_path):
        """Test database update for a successful file move."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)
        insert_test_document(conn, 1, "test.pdf", "/old/test.pdf")

        file_result = FileMoveResult(
            source_path="/old/test.pdf",
            target_path="/new/test.pdf",
            status=MoveStatus.SUCCESS,
        )

        update = update_database_for_file_move(
            conn=conn,
            file_result=file_result,
            canonical_folder="/new",
        )
        conn.commit()

        assert update is not None
        assert update.status == "success"
        conn.close()

    def test_update_for_failed_move(self, tmp_path):
        """Test database update for a failed file move returns None."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        file_result = FileMoveResult(
            source_path="/old/test.pdf",
            target_path="/new/test.pdf",
            status=MoveStatus.FAILED,
            error="Move failed",
        )

        update = update_database_for_file_move(
            conn=conn,
            file_result=file_result,
            canonical_folder="/new",
        )

        assert update is None
        conn.close()

    def test_update_for_skipped_move(self, tmp_path):
        """Test database update for a skipped file move returns None."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        file_result = FileMoveResult(
            source_path="/old/test.pdf",
            target_path="/new/test.pdf",
            status=MoveStatus.SKIPPED,
        )

        update = update_database_for_file_move(
            conn=conn,
            file_result=file_result,
            canonical_folder="/new",
        )

        assert update is None
        conn.close()


class TestUpdateDatabaseForExecution:
    """Tests for update_database_for_execution function."""

    def test_update_for_empty_execution(self, tmp_path):
        """Test database update for an empty execution result."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        execution_result = ExecutionResult(status=MoveStatus.SUCCESS)

        db_result = update_database_for_execution(conn, execution_result)

        assert db_result.documents_updated == 0
        assert db_result.success is True
        conn.close()

    def test_update_for_execution_with_moves(self, tmp_path):
        """Test database update for execution with multiple file moves."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        # Insert test documents
        insert_test_document(conn, 1, "doc1.pdf", "/old/doc1.pdf")
        insert_test_document(conn, 2, "doc2.pdf", "/old/doc2.pdf")
        insert_test_document(conn, 3, "doc3.pdf", "/old/doc3.pdf")

        # Create execution result with multiple successful moves
        file_results = [
            FileMoveResult("/old/doc1.pdf", "/new/doc1.pdf", MoveStatus.SUCCESS),
            FileMoveResult("/old/doc2.pdf", "/new/doc2.pdf", MoveStatus.SUCCESS),
            FileMoveResult("/old/doc3.pdf", "/new/doc3.pdf", MoveStatus.SUCCESS),
        ]
        folder_result = FolderMoveResult(
            source_folder="/old",
            target_folder="/new",
            status=MoveStatus.SUCCESS,
            files_moved=3,
            file_results=file_results,
        )
        group_result = GroupMoveResult(
            group_name="Test Group",
            target_folder="/new",
            status=MoveStatus.SUCCESS,
            folders_processed=1,
            total_files_moved=3,
            folder_results=[folder_result],
        )
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=3,
            group_results=[group_result],
        )

        db_result = update_database_for_execution(conn, execution_result)
        conn.commit()

        assert db_result.documents_updated == 3
        assert db_result.locations_added == 3
        assert db_result.locations_marked_previous == 3
        assert db_result.success is True
        conn.close()

    def test_update_for_execution_with_mixed_results(self, tmp_path):
        """Test database update for execution with mixed success/failure."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        insert_test_document(conn, 1, "doc1.pdf", "/old/doc1.pdf")

        file_results = [
            FileMoveResult("/old/doc1.pdf", "/new/doc1.pdf", MoveStatus.SUCCESS),
            FileMoveResult(
                "/old/doc2.pdf", "/new/doc2.pdf", MoveStatus.FAILED, "Error"
            ),
        ]
        folder_result = FolderMoveResult(
            source_folder="/old",
            target_folder="/new",
            status=MoveStatus.FAILED,
            files_moved=1,
            files_failed=1,
            file_results=file_results,
        )
        group_result = GroupMoveResult(
            group_name="Test Group",
            target_folder="/new",
            status=MoveStatus.FAILED,
            folders_processed=1,
            total_files_moved=1,
            total_files_failed=1,
            folder_results=[folder_result],
        )
        execution_result = ExecutionResult(
            status=MoveStatus.FAILED,
            groups_completed=0,
            groups_failed=1,
            total_files_moved=1,
            total_files_failed=1,
            group_results=[group_result],
        )

        db_result = update_database_for_execution(conn, execution_result)
        conn.commit()

        # Only successful moves are updated
        assert db_result.documents_updated == 1
        assert db_result.success is True
        conn.close()

    def test_update_for_untracked_files(self, tmp_path):
        """Test database update for files not tracked in database."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        # Don't insert any documents - files aren't tracked

        file_results = [
            FileMoveResult(
                "/old/untracked.pdf", "/new/untracked.pdf", MoveStatus.SUCCESS
            ),
        ]
        folder_result = FolderMoveResult(
            source_folder="/old",
            target_folder="/new",
            status=MoveStatus.SUCCESS,
            files_moved=1,
            file_results=file_results,
        )
        group_result = GroupMoveResult(
            group_name="Test Group",
            target_folder="/new",
            status=MoveStatus.SUCCESS,
            folders_processed=1,
            total_files_moved=1,
            folder_results=[folder_result],
        )
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=1,
            group_results=[group_result],
        )

        db_result = update_database_for_execution(conn, execution_result)

        # Files not in database should not cause errors
        assert db_result.documents_updated == 0
        assert db_result.success is True
        assert len(db_result.document_updates) == 1
        assert db_result.document_updates[0].status == "not_found"
        conn.close()


class TestUpdateDatabaseFromExecutionResult:
    """Tests for update_database_from_execution_result function."""

    def test_update_from_execution_result(self, tmp_path):
        """Test convenience function for updating database."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)
        insert_test_document(conn, 1, "doc.pdf", "/old/doc.pdf")
        conn.close()

        file_results = [
            FileMoveResult("/old/doc.pdf", "/new/doc.pdf", MoveStatus.SUCCESS),
        ]
        folder_result = FolderMoveResult(
            source_folder="/old",
            target_folder="/new",
            status=MoveStatus.SUCCESS,
            files_moved=1,
            file_results=file_results,
        )
        group_result = GroupMoveResult(
            group_name="Test Group",
            target_folder="/new",
            status=MoveStatus.SUCCESS,
            folders_processed=1,
            total_files_moved=1,
            folder_results=[folder_result],
        )
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=1,
            group_results=[group_result],
        )

        db_result = update_database_from_execution_result(db_path, execution_result)

        assert db_result.documents_updated == 1
        assert db_result.success is True

    def test_update_from_execution_result_nonexistent_db(self, tmp_path):
        """Test convenience function with nonexistent database."""
        db_path = tmp_path / "nonexistent.db"
        execution_result = ExecutionResult(status=MoveStatus.SUCCESS)

        with pytest.raises(FileNotFoundError):
            update_database_from_execution_result(db_path, execution_result)


class TestCheckDatabaseSchema:
    """Tests for check_database_schema function."""

    def test_valid_schema(self, tmp_path):
        """Test checking a valid schema."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        valid, missing = check_database_schema(conn)

        assert valid is True
        assert missing == []
        conn.close()

    def test_missing_documents_table(self, tmp_path):
        """Test checking schema with missing documents table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        # Only create document_locations table
        conn.execute("""
            CREATE TABLE document_locations (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                path TEXT,
                location_type TEXT
            )
        """)

        valid, missing = check_database_schema(conn)

        assert valid is False
        assert "table:documents" in missing
        conn.close()

    def test_missing_document_locations_table(self, tmp_path):
        """Test checking schema with missing document_locations table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        # Only create documents table
        conn.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                current_path TEXT,
                canonical_folder TEXT,
                rename_status TEXT
            )
        """)

        valid, missing = check_database_schema(conn)

        assert valid is False
        assert "table:document_locations" in missing
        conn.close()

    def test_missing_column(self, tmp_path):
        """Test checking schema with missing column."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        # Create documents table without canonical_folder
        conn.execute("""
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                current_path TEXT,
                rename_status TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE document_locations (
                id INTEGER PRIMARY KEY,
                document_id INTEGER,
                path TEXT,
                location_type TEXT
            )
        """)

        valid, missing = check_database_schema(conn)

        assert valid is False
        assert "column:documents.canonical_folder" in missing
        conn.close()

    def test_empty_database(self, tmp_path):
        """Test checking empty database with no tables."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))

        valid, missing = check_database_schema(conn)

        assert valid is False
        assert "table:documents" in missing
        assert "table:document_locations" in missing
        conn.close()


class TestIntegration:
    """Integration tests for database updater."""

    def test_full_consolidation_database_flow(self, tmp_path):
        """Test complete flow: execution result -> database updates."""
        db_path = tmp_path / "test.db"
        conn = create_test_database(db_path)

        # Insert documents that simulate a resume folder consolidation
        insert_test_document(conn, 1, "resume_2023.pdf", "/docs/Resume/resume_2023.pdf")
        insert_test_document(conn, 2, "resume_v2.pdf", "/docs/Resumes/resume_v2.pdf")
        insert_test_document(conn, 3, "cv.pdf", "/docs/Resume_Docs/cv.pdf")
        conn.close()

        # Create execution result simulating folder consolidation
        file_results_1 = [
            FileMoveResult(
                "/docs/Resume/resume_2023.pdf",
                "/Employment/Resumes/resume_2023.pdf",
                MoveStatus.SUCCESS,
            ),
        ]
        file_results_2 = [
            FileMoveResult(
                "/docs/Resumes/resume_v2.pdf",
                "/Employment/Resumes/resume_v2.pdf",
                MoveStatus.SUCCESS,
            ),
        ]
        file_results_3 = [
            FileMoveResult(
                "/docs/Resume_Docs/cv.pdf",
                "/Employment/Resumes/cv.pdf",
                MoveStatus.SUCCESS,
            ),
        ]

        folder_results = [
            FolderMoveResult(
                "/docs/Resume",
                "/Employment/Resumes",
                MoveStatus.SUCCESS,
                files_moved=1,
                file_results=file_results_1,
            ),
            FolderMoveResult(
                "/docs/Resumes",
                "/Employment/Resumes",
                MoveStatus.SUCCESS,
                files_moved=1,
                file_results=file_results_2,
            ),
            FolderMoveResult(
                "/docs/Resume_Docs",
                "/Employment/Resumes",
                MoveStatus.SUCCESS,
                files_moved=1,
                file_results=file_results_3,
            ),
        ]

        group_result = GroupMoveResult(
            group_name="Resume-related",
            target_folder="/Employment/Resumes",
            status=MoveStatus.SUCCESS,
            folders_processed=3,
            total_files_moved=3,
            folder_results=folder_results,
        )

        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=3,
            group_results=[group_result],
        )

        # Update database
        db_result = update_database_from_execution_result(db_path, execution_result)

        assert db_result.documents_updated == 3
        assert db_result.locations_added == 3
        assert db_result.locations_marked_previous == 3
        assert db_result.success is True

        # Verify database state
        conn = sqlite3.connect(str(db_path))

        # All documents should have new paths
        cursor = conn.execute("SELECT current_path FROM documents ORDER BY id")
        paths = [row[0] for row in cursor.fetchall()]
        assert paths == [
            "/Employment/Resumes/resume_2023.pdf",
            "/Employment/Resumes/resume_v2.pdf",
            "/Employment/Resumes/cv.pdf",
        ]

        # All documents should have canonical_folder set
        cursor = conn.execute("SELECT canonical_folder FROM documents")
        folders = [row[0] for row in cursor.fetchall()]
        assert all(f == "/Employment/Resumes" for f in folders)

        # All documents should have rename_status='done'
        cursor = conn.execute("SELECT rename_status FROM documents")
        statuses = [row[0] for row in cursor.fetchall()]
        assert all(s == "done" for s in statuses)

        # Each document should have 2 location entries (original + new)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM document_locations WHERE document_id = 1"
        )
        assert cursor.fetchone()[0] == 2

        conn.close()
