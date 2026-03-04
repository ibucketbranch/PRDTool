"""Tests for post_verification module."""

import tempfile
from pathlib import Path

import pytest

from organizer.file_operations import (
    ExecutionResult,
    FileMoveResult,
    FolderMoveResult,
    GroupMoveResult,
    MoveStatus,
)
from organizer.post_verification import (
    FileVerificationResult,
    VerificationResult,
    ExecutionSummaryReport,
    verify_file_accessible,
    verify_files_at_new_locations,
    check_no_files_lost,
    generate_execution_summary,
    save_summary_report,
    load_summary_report,
    format_verification_summary,
    format_summary_report,
)


class TestFileVerificationResult:
    """Tests for FileVerificationResult dataclass."""

    def test_create_file_verification_result(self):
        """Test creating a FileVerificationResult."""
        result = FileVerificationResult(
            file_path="/path/to/file.txt",
            exists=True,
            accessible=True,
        )
        assert result.file_path == "/path/to/file.txt"
        assert result.exists is True
        assert result.accessible is True
        assert result.error == ""

    def test_file_verification_result_with_error(self):
        """Test FileVerificationResult with an error."""
        result = FileVerificationResult(
            file_path="/path/to/file.txt",
            exists=False,
            accessible=False,
            error="File does not exist",
        )
        assert result.exists is False
        assert result.accessible is False
        assert result.error == "File does not exist"

    def test_file_verification_result_to_dict(self):
        """Test to_dict serialization."""
        result = FileVerificationResult(
            file_path="/path/to/file.txt",
            exists=True,
            accessible=True,
        )
        d = result.to_dict()
        assert d["file_path"] == "/path/to/file.txt"
        assert d["exists"] is True
        assert d["accessible"] is True
        assert d["error"] == ""


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_create_verification_result(self):
        """Test creating a VerificationResult."""
        result = VerificationResult(
            status="verified",
            total_files_expected=10,
            total_files_verified=10,
            files_at_target=10,
            files_missing=0,
            files_inaccessible=0,
        )
        assert result.status == "verified"
        assert result.total_files_expected == 10
        assert result.total_files_verified == 10
        assert result.success is True

    def test_verification_result_partial_status(self):
        """Test VerificationResult with partial status."""
        result = VerificationResult(
            status="partial",
            total_files_expected=10,
            total_files_verified=8,
            files_at_target=8,
            files_missing=2,
            files_inaccessible=0,
        )
        assert result.status == "partial"
        assert result.success is False

    def test_verification_result_failed_status(self):
        """Test VerificationResult with failed status."""
        result = VerificationResult(
            status="failed",
            total_files_expected=10,
            total_files_verified=0,
            files_at_target=0,
            files_missing=10,
            files_inaccessible=0,
        )
        assert result.status == "failed"
        assert result.success is False

    def test_verification_result_to_dict(self):
        """Test to_dict serialization."""
        detail = FileVerificationResult(
            file_path="/path/to/file.txt",
            exists=True,
            accessible=True,
        )
        result = VerificationResult(
            status="verified",
            total_files_expected=1,
            total_files_verified=1,
            files_at_target=1,
            files_missing=0,
            files_inaccessible=0,
            verification_details=[detail],
            errors=[],
        )
        d = result.to_dict()
        assert d["status"] == "verified"
        assert len(d["verification_details"]) == 1
        assert d["verification_details"][0]["file_path"] == "/path/to/file.txt"


class TestExecutionSummaryReport:
    """Tests for ExecutionSummaryReport dataclass."""

    def test_create_summary_report(self):
        """Test creating an ExecutionSummaryReport."""
        report = ExecutionSummaryReport(
            timestamp="2026-01-20 10:00:00",
            execution_status="success",
            total_groups=3,
            groups_completed=3,
            groups_failed=0,
            total_files_moved=50,
            total_files_failed=0,
        )
        assert report.timestamp == "2026-01-20 10:00:00"
        assert report.execution_status == "success"
        assert report.overall_success is True

    def test_summary_report_with_verification(self):
        """Test summary report with verification result."""
        verification = VerificationResult(
            status="verified",
            total_files_expected=50,
            total_files_verified=50,
            files_at_target=50,
            files_missing=0,
            files_inaccessible=0,
        )
        report = ExecutionSummaryReport(
            timestamp="2026-01-20 10:00:00",
            execution_status="success",
            total_groups=3,
            groups_completed=3,
            groups_failed=0,
            total_files_moved=50,
            total_files_failed=0,
            verification_result=verification,
        )
        assert report.overall_success is True

    def test_summary_report_failed_execution(self):
        """Test summary report with failed execution."""
        report = ExecutionSummaryReport(
            timestamp="2026-01-20 10:00:00",
            execution_status="failed",
            total_groups=3,
            groups_completed=2,
            groups_failed=1,
            total_files_moved=30,
            total_files_failed=5,
        )
        assert report.overall_success is False

    def test_summary_report_failed_verification(self):
        """Test summary report with failed verification."""
        verification = VerificationResult(
            status="partial",
            total_files_expected=50,
            total_files_verified=45,
            files_at_target=45,
            files_missing=5,
            files_inaccessible=0,
        )
        report = ExecutionSummaryReport(
            timestamp="2026-01-20 10:00:00",
            execution_status="success",
            total_groups=3,
            groups_completed=3,
            groups_failed=0,
            total_files_moved=50,
            total_files_failed=0,
            verification_result=verification,
        )
        assert report.overall_success is False

    def test_summary_report_to_dict(self):
        """Test to_dict serialization."""
        report = ExecutionSummaryReport(
            timestamp="2026-01-20 10:00:00",
            execution_status="success",
            total_groups=3,
            groups_completed=3,
            groups_failed=0,
            total_files_moved=50,
            total_files_failed=0,
            errors=["Some warning"],
        )
        d = report.to_dict()
        assert d["timestamp"] == "2026-01-20 10:00:00"
        assert d["execution_status"] == "success"
        assert d["total_groups"] == 3
        assert "Some warning" in d["errors"]


class TestVerifyFileAccessible:
    """Tests for verify_file_accessible function."""

    def test_verify_existing_file(self):
        """Test verifying an existing accessible file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_path = f.name

        try:
            result = verify_file_accessible(temp_path)
            assert result.exists is True
            assert result.accessible is True
            assert result.error == ""
        finally:
            Path(temp_path).unlink()

    def test_verify_nonexistent_file(self):
        """Test verifying a file that doesn't exist."""
        result = verify_file_accessible("/nonexistent/path/file.txt")
        assert result.exists is False
        assert result.accessible is False
        assert "does not exist" in result.error

    def test_verify_file_path_recorded(self):
        """Test that file path is recorded in result."""
        path = "/some/path/file.txt"
        result = verify_file_accessible(path)
        assert result.file_path == path


class TestVerifyFilesAtNewLocations:
    """Tests for verify_files_at_new_locations function."""

    def test_verify_all_files_successful(self):
        """Test verifying files when all are at their target locations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files at target locations
            file1 = Path(tmpdir) / "file1.txt"
            file2 = Path(tmpdir) / "file2.txt"
            file1.write_text("content1")
            file2.write_text("content2")

            # Create execution result with these files
            file_results = [
                FileMoveResult(
                    source_path="/original/file1.txt",
                    target_path=str(file1),
                    status=MoveStatus.SUCCESS,
                ),
                FileMoveResult(
                    source_path="/original/file2.txt",
                    target_path=str(file2),
                    status=MoveStatus.SUCCESS,
                ),
            ]
            folder_result = FolderMoveResult(
                source_folder="/original",
                target_folder=tmpdir,
                status=MoveStatus.SUCCESS,
                files_moved=2,
                file_results=file_results,
            )
            group_result = GroupMoveResult(
                group_name="Test Group",
                target_folder=tmpdir,
                status=MoveStatus.SUCCESS,
                total_files_moved=2,
                folder_results=[folder_result],
            )
            execution_result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                total_files_moved=2,
                group_results=[group_result],
            )

            result = verify_files_at_new_locations(execution_result)
            assert result.status == "verified"
            assert result.total_files_expected == 2
            assert result.total_files_verified == 2
            assert result.files_at_target == 2
            assert result.files_missing == 0
            assert result.success is True

    def test_verify_with_missing_files(self):
        """Test verification when some files are missing."""
        # Create execution result with files that don't exist at target
        file_results = [
            FileMoveResult(
                source_path="/original/file1.txt",
                target_path="/nonexistent/file1.txt",
                status=MoveStatus.SUCCESS,
            ),
        ]
        folder_result = FolderMoveResult(
            source_folder="/original",
            target_folder="/nonexistent",
            status=MoveStatus.SUCCESS,
            files_moved=1,
            file_results=file_results,
        )
        group_result = GroupMoveResult(
            group_name="Test Group",
            target_folder="/nonexistent",
            status=MoveStatus.SUCCESS,
            total_files_moved=1,
            folder_results=[folder_result],
        )
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=1,
            group_results=[group_result],
        )

        result = verify_files_at_new_locations(execution_result)
        assert result.status == "failed"
        assert result.files_missing == 1
        assert result.success is False

    def test_verify_empty_execution_result(self):
        """Test verification with no files moved."""
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=0,
            total_files_moved=0,
            group_results=[],
        )

        result = verify_files_at_new_locations(execution_result)
        assert result.status == "verified"
        assert result.total_files_expected == 0
        assert result.success is True

    def test_verify_skips_failed_moves(self):
        """Test that verification only checks successful moves."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file1.write_text("content1")

            file_results = [
                FileMoveResult(
                    source_path="/original/file1.txt",
                    target_path=str(file1),
                    status=MoveStatus.SUCCESS,
                ),
                FileMoveResult(
                    source_path="/original/file2.txt",
                    target_path="/nonexistent/file2.txt",
                    status=MoveStatus.FAILED,
                    error="Move failed",
                ),
            ]
            folder_result = FolderMoveResult(
                source_folder="/original",
                target_folder=tmpdir,
                status=MoveStatus.FAILED,
                files_moved=1,
                files_failed=1,
                file_results=file_results,
            )
            group_result = GroupMoveResult(
                group_name="Test Group",
                target_folder=tmpdir,
                status=MoveStatus.FAILED,
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

            result = verify_files_at_new_locations(execution_result)
            # Only the successful move is verified
            assert result.total_files_expected == 1
            assert result.files_at_target == 1
            assert result.success is True


class TestCheckNoFilesLost:
    """Tests for check_no_files_lost function."""

    def test_no_files_lost_all_at_target(self):
        """Test when all files are at their target locations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file1.write_text("content")

            file_results = [
                FileMoveResult(
                    source_path="/original/file1.txt",
                    target_path=str(file1),
                    status=MoveStatus.SUCCESS,
                ),
            ]
            folder_result = FolderMoveResult(
                source_folder="/original",
                target_folder=tmpdir,
                status=MoveStatus.SUCCESS,
                files_moved=1,
                file_results=file_results,
            )
            group_result = GroupMoveResult(
                group_name="Test Group",
                target_folder=tmpdir,
                status=MoveStatus.SUCCESS,
                total_files_moved=1,
                folder_results=[folder_result],
            )
            execution_result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                total_files_moved=1,
                group_results=[group_result],
            )

            no_files_lost, lost_files = check_no_files_lost(execution_result)
            assert no_files_lost is True
            assert len(lost_files) == 0

    def test_files_lost_not_at_target_or_source(self):
        """Test when files are missing from both source and target."""
        file_results = [
            FileMoveResult(
                source_path="/nonexistent/source/file1.txt",
                target_path="/nonexistent/target/file1.txt",
                status=MoveStatus.SUCCESS,
            ),
        ]
        folder_result = FolderMoveResult(
            source_folder="/nonexistent/source",
            target_folder="/nonexistent/target",
            status=MoveStatus.SUCCESS,
            files_moved=1,
            file_results=file_results,
        )
        group_result = GroupMoveResult(
            group_name="Test Group",
            target_folder="/nonexistent/target",
            status=MoveStatus.SUCCESS,
            total_files_moved=1,
            folder_results=[folder_result],
        )
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=1,
            group_results=[group_result],
        )

        no_files_lost, lost_files = check_no_files_lost(execution_result)
        assert no_files_lost is False
        assert len(lost_files) == 1
        assert "/nonexistent/target/file1.txt" in lost_files

    def test_empty_execution_no_files_lost(self):
        """Test that empty execution means no files lost."""
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=0,
            total_files_moved=0,
            group_results=[],
        )

        no_files_lost, lost_files = check_no_files_lost(execution_result)
        assert no_files_lost is True
        assert len(lost_files) == 0


class TestGenerateExecutionSummary:
    """Tests for generate_execution_summary function."""

    def test_generate_summary_success(self):
        """Test generating summary for successful execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = Path(tmpdir) / "file1.txt"
            file1.write_text("content")

            file_results = [
                FileMoveResult(
                    source_path="/original/file1.txt",
                    target_path=str(file1),
                    status=MoveStatus.SUCCESS,
                ),
            ]
            folder_result = FolderMoveResult(
                source_folder="/original",
                target_folder=tmpdir,
                status=MoveStatus.SUCCESS,
                files_moved=1,
                file_results=file_results,
            )
            group_result = GroupMoveResult(
                group_name="Test Group",
                target_folder=tmpdir,
                status=MoveStatus.SUCCESS,
                total_files_moved=1,
                folder_results=[folder_result],
            )
            execution_result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                total_files_moved=1,
                group_results=[group_result],
            )

            report = generate_execution_summary(execution_result, total_groups=1)
            assert report.execution_status == "success"
            assert report.groups_completed == 1
            assert report.total_files_moved == 1
            assert report.verification_result is not None
            assert report.verification_result.success is True
            assert report.overall_success is True

    def test_generate_summary_failed_execution(self):
        """Test generating summary for failed execution."""
        execution_result = ExecutionResult(
            status=MoveStatus.FAILED,
            groups_completed=0,
            groups_failed=1,
            total_files_moved=0,
            total_files_failed=5,
            group_results=[],
            error="Execution failed",
        )

        report = generate_execution_summary(execution_result, total_groups=1)
        assert report.execution_status == "failed"
        assert "Execution failed" in report.errors

    def test_generate_summary_without_verification(self):
        """Test generating summary without verification."""
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=5,
            group_results=[],
        )

        report = generate_execution_summary(
            execution_result, total_groups=1, include_verification=False
        )
        assert report.verification_result is None


class TestSaveAndLoadSummaryReport:
    """Tests for save_summary_report and load_summary_report functions."""

    def test_save_and_load_report(self):
        """Test saving and loading a summary report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = ExecutionSummaryReport(
                timestamp="2026-01-20 10:00:00",
                execution_status="success",
                total_groups=3,
                groups_completed=3,
                groups_failed=0,
                total_files_moved=50,
                total_files_failed=0,
            )

            output_path = Path(tmpdir) / "report.json"
            saved_path = save_summary_report(report, output_path=output_path)
            assert saved_path == output_path
            assert output_path.exists()

            loaded = load_summary_report(saved_path)
            assert loaded.timestamp == report.timestamp
            assert loaded.execution_status == report.execution_status
            assert loaded.total_groups == report.total_groups

    def test_save_report_with_verification(self):
        """Test saving and loading a report with verification results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verification = VerificationResult(
                status="verified",
                total_files_expected=50,
                total_files_verified=50,
                files_at_target=50,
                files_missing=0,
                files_inaccessible=0,
            )
            report = ExecutionSummaryReport(
                timestamp="2026-01-20 10:00:00",
                execution_status="success",
                total_groups=3,
                groups_completed=3,
                groups_failed=0,
                total_files_moved=50,
                total_files_failed=0,
                verification_result=verification,
            )

            output_path = Path(tmpdir) / "report.json"
            saved_path = save_summary_report(report, output_path=output_path)

            loaded = load_summary_report(saved_path)
            assert loaded.verification_result is not None
            assert loaded.verification_result.status == "verified"
            assert loaded.verification_result.success is True

    def test_save_report_default_location(self):
        """Test saving report to default location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = ExecutionSummaryReport(
                timestamp="2026-01-20 10:00:00",
                execution_status="success",
                total_groups=1,
                groups_completed=1,
                groups_failed=0,
                total_files_moved=5,
                total_files_failed=0,
            )

            saved_path = save_summary_report(report, base_path=tmpdir)
            assert saved_path.parent.name == ".organizer"
            assert "summary_report_" in saved_path.name
            assert saved_path.suffix == ".json"

    def test_load_nonexistent_report(self):
        """Test loading a report that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_summary_report("/nonexistent/path/report.json")


class TestFormatVerificationSummary:
    """Tests for format_verification_summary function."""

    def test_format_successful_verification(self):
        """Test formatting successful verification."""
        verification = VerificationResult(
            status="verified",
            total_files_expected=50,
            total_files_verified=50,
            files_at_target=50,
            files_missing=0,
            files_inaccessible=0,
        )

        output = format_verification_summary(verification)
        assert "VERIFICATION COMPLETE" in output
        assert "50 files verified" in output

    def test_format_partial_verification(self):
        """Test formatting partial verification with missing files."""
        verification = VerificationResult(
            status="partial",
            total_files_expected=50,
            total_files_verified=45,
            files_at_target=45,
            files_missing=5,
            files_inaccessible=0,
        )

        output = format_verification_summary(verification)
        assert "45/50 files verified" in output
        assert "5 files MISSING" in output


class TestFormatSummaryReport:
    """Tests for format_summary_report function."""

    def test_format_successful_report(self):
        """Test formatting a successful report."""
        verification = VerificationResult(
            status="verified",
            total_files_expected=50,
            total_files_verified=50,
            files_at_target=50,
            files_missing=0,
            files_inaccessible=0,
        )
        report = ExecutionSummaryReport(
            timestamp="2026-01-20 10:00:00",
            execution_status="success",
            total_groups=3,
            groups_completed=3,
            groups_failed=0,
            total_files_moved=50,
            total_files_failed=0,
            verification_result=verification,
        )

        output = format_summary_report(report)
        assert "FINAL SUMMARY" in output
        assert "3 folder groups consolidated" in output
        assert "50 files moved successfully" in output
        assert "0 files lost" in output

    def test_format_report_with_errors(self):
        """Test formatting a report with errors."""
        report = ExecutionSummaryReport(
            timestamp="2026-01-20 10:00:00",
            execution_status="failed",
            total_groups=3,
            groups_completed=2,
            groups_failed=1,
            total_files_moved=30,
            total_files_failed=5,
            errors=["Error 1", "Error 2"],
        )

        output = format_summary_report(report)
        assert "Errors (2):" in output
        assert "Error 1" in output
        assert "Error 2" in output


class TestIntegration:
    """Integration tests for the full verification workflow."""

    def test_full_verification_workflow(self):
        """Test the complete verification workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source and target directories
            source_dir = Path(tmpdir) / "source"
            target_dir = Path(tmpdir) / "target"
            source_dir.mkdir()
            target_dir.mkdir()

            # Create files at target (simulating successful move)
            (target_dir / "file1.txt").write_text("content1")
            (target_dir / "file2.txt").write_text("content2")

            # Create execution result
            file_results = [
                FileMoveResult(
                    source_path=str(source_dir / "file1.txt"),
                    target_path=str(target_dir / "file1.txt"),
                    status=MoveStatus.SUCCESS,
                ),
                FileMoveResult(
                    source_path=str(source_dir / "file2.txt"),
                    target_path=str(target_dir / "file2.txt"),
                    status=MoveStatus.SUCCESS,
                ),
            ]
            folder_result = FolderMoveResult(
                source_folder=str(source_dir),
                target_folder=str(target_dir),
                status=MoveStatus.SUCCESS,
                files_moved=2,
                file_results=file_results,
            )
            group_result = GroupMoveResult(
                group_name="Documents",
                target_folder=str(target_dir),
                status=MoveStatus.SUCCESS,
                total_files_moved=2,
                folder_results=[folder_result],
            )
            execution_result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                total_files_moved=2,
                group_results=[group_result],
            )

            # Generate summary
            report = generate_execution_summary(
                execution_result, total_groups=1, include_verification=True
            )

            # Verify results
            assert report.overall_success is True
            assert report.verification_result is not None
            assert report.verification_result.success is True
            assert report.verification_result.files_at_target == 2
            assert report.verification_result.files_missing == 0

            # Save and load report
            report_path = save_summary_report(report, base_path=tmpdir)
            loaded_report = load_summary_report(report_path)

            assert loaded_report.overall_success is True

    def test_verification_with_multiple_groups(self):
        """Test verification across multiple folder groups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple target directories with files
            targets = []
            all_file_results = []

            for i in range(3):
                target_dir = Path(tmpdir) / f"target_{i}"
                target_dir.mkdir()
                (target_dir / f"file_{i}.txt").write_text(f"content_{i}")
                targets.append(target_dir)

                all_file_results.append(
                    FileMoveResult(
                        source_path=f"/source_{i}/file_{i}.txt",
                        target_path=str(target_dir / f"file_{i}.txt"),
                        status=MoveStatus.SUCCESS,
                    )
                )

            # Create execution result with multiple groups
            group_results = []
            for i, (target_dir, file_result) in enumerate(
                zip(targets, all_file_results)
            ):
                folder_result = FolderMoveResult(
                    source_folder=f"/source_{i}",
                    target_folder=str(target_dir),
                    status=MoveStatus.SUCCESS,
                    files_moved=1,
                    file_results=[file_result],
                )
                group_results.append(
                    GroupMoveResult(
                        group_name=f"Group {i}",
                        target_folder=str(target_dir),
                        status=MoveStatus.SUCCESS,
                        total_files_moved=1,
                        folder_results=[folder_result],
                    )
                )

            execution_result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=3,
                total_files_moved=3,
                group_results=group_results,
            )

            # Verify
            verification = verify_files_at_new_locations(execution_result)
            assert verification.status == "verified"
            assert verification.total_files_expected == 3
            assert verification.files_at_target == 3

            # Check no files lost
            no_files_lost, lost_files = check_no_files_lost(execution_result)
            assert no_files_lost is True
