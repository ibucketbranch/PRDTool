"""Tests for the execution_logger module."""

import json
import os
import tempfile
from pathlib import Path

from organizer.execution_logger import (
    ContentAnalysisEntry,
    ExecutionLog,
    GroupLogEntry,
    RollbackInstruction,
    create_execution_log,
    get_rollback_script,
    load_execution_log,
    save_rollback_script,
)
from organizer.file_operations import (
    ExecutionResult,
    FileMoveResult,
    FolderMoveResult,
    GroupMoveResult,
    MoveStatus,
)
from organizer.consolidation_planner import (
    ConsolidationPlan,
    FolderGroup,
    FolderInfo,
    FolderContentSummary,
)


class TestRollbackInstruction:
    """Tests for RollbackInstruction dataclass."""

    def test_creation(self):
        """Test creating a RollbackInstruction."""
        instruction = RollbackInstruction(
            current_path="/target/file.txt",
            original_path="/source/file.txt",
            command='mv "/target/file.txt" "/source/file.txt"',
        )
        assert instruction.current_path == "/target/file.txt"
        assert instruction.original_path == "/source/file.txt"
        assert "mv" in instruction.command

    def test_to_dict(self):
        """Test converting to dictionary."""
        instruction = RollbackInstruction(
            current_path="/target/file.txt",
            original_path="/source/file.txt",
            command='mv "/target/file.txt" "/source/file.txt"',
        )
        d = instruction.to_dict()
        assert d["current_path"] == "/target/file.txt"
        assert d["original_path"] == "/source/file.txt"
        assert d["command"] == 'mv "/target/file.txt" "/source/file.txt"'

    def test_from_file_move_success(self):
        """Test creating from a successful file move."""
        file_result = FileMoveResult(
            source_path="/source/file.txt",
            target_path="/target/file.txt",
            status=MoveStatus.SUCCESS,
        )
        instruction = RollbackInstruction.from_file_move(file_result)
        assert instruction is not None
        assert instruction.current_path == "/target/file.txt"
        assert instruction.original_path == "/source/file.txt"
        assert 'mv "/target/file.txt" "/source/file.txt"' in instruction.command

    def test_from_file_move_failed(self):
        """Test creating from a failed file move returns None."""
        file_result = FileMoveResult(
            source_path="/source/file.txt",
            target_path="/target/file.txt",
            status=MoveStatus.FAILED,
            error="Some error",
        )
        instruction = RollbackInstruction.from_file_move(file_result)
        assert instruction is None

    def test_from_file_move_skipped(self):
        """Test creating from a skipped file move returns None."""
        file_result = FileMoveResult(
            source_path="/source/file.txt",
            target_path="/target/file.txt",
            status=MoveStatus.SKIPPED,
        )
        instruction = RollbackInstruction.from_file_move(file_result)
        assert instruction is None


class TestGroupLogEntry:
    """Tests for GroupLogEntry dataclass."""

    def test_creation(self):
        """Test creating a GroupLogEntry."""
        entry = GroupLogEntry(
            group_name="Resume-related",
            target_folder="/target/Resumes",
            folders_processed=3,
            files_moved=10,
            files_failed=0,
            status="success",
        )
        assert entry.group_name == "Resume-related"
        assert entry.target_folder == "/target/Resumes"
        assert entry.files_moved == 10
        assert entry.status == "success"

    def test_to_dict(self):
        """Test converting to dictionary."""
        entry = GroupLogEntry(
            group_name="Resume-related",
            target_folder="/target/Resumes",
            folders_processed=3,
            files_moved=10,
            files_failed=1,
            status="failed",
            error="One file failed",
        )
        d = entry.to_dict()
        assert d["group_name"] == "Resume-related"
        assert d["target_folder"] == "/target/Resumes"
        assert d["folders_processed"] == 3
        assert d["files_moved"] == 10
        assert d["files_failed"] == 1
        assert d["status"] == "failed"
        assert d["error"] == "One file failed"

    def test_from_group_result(self):
        """Test creating from a GroupMoveResult."""
        file_result = FileMoveResult(
            source_path="/source/file.txt",
            target_path="/target/file.txt",
            status=MoveStatus.SUCCESS,
        )
        folder_result = FolderMoveResult(
            source_folder="/source",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
            files_moved=1,
            files_failed=0,
            file_results=[file_result],
        )
        group_result = GroupMoveResult(
            group_name="Test-related",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
            folders_processed=1,
            total_files_moved=1,
            total_files_failed=0,
            folder_results=[folder_result],
        )

        entry = GroupLogEntry.from_group_result(group_result)

        assert entry.group_name == "Test-related"
        assert entry.target_folder == "/target"
        assert entry.files_moved == 1
        assert entry.status == "success"
        assert len(entry.folder_entries) == 1
        assert len(entry.rollback_instructions) == 1

    def test_from_group_result_with_failures(self):
        """Test creating from a GroupMoveResult with some failures."""
        success_file = FileMoveResult(
            source_path="/source/good.txt",
            target_path="/target/good.txt",
            status=MoveStatus.SUCCESS,
        )
        failed_file = FileMoveResult(
            source_path="/source/bad.txt",
            target_path="/target/bad.txt",
            status=MoveStatus.FAILED,
            error="Permission denied",
        )
        folder_result = FolderMoveResult(
            source_folder="/source",
            target_folder="/target",
            status=MoveStatus.FAILED,
            files_moved=1,
            files_failed=1,
            file_results=[success_file, failed_file],
            error="1 file failed",
        )
        group_result = GroupMoveResult(
            group_name="Test-related",
            target_folder="/target",
            status=MoveStatus.FAILED,
            folders_processed=1,
            total_files_moved=1,
            total_files_failed=1,
            folder_results=[folder_result],
            error="Folder move failed",
        )

        entry = GroupLogEntry.from_group_result(group_result)

        assert entry.status == "failed"
        assert entry.files_moved == 1
        assert entry.files_failed == 1
        # Only successful file should have rollback instruction
        assert len(entry.rollback_instructions) == 1


class TestExecutionLog:
    """Tests for ExecutionLog dataclass."""

    def test_creation(self):
        """Test creating an ExecutionLog."""
        log = ExecutionLog(
            timestamp="2026-01-20 14:30:00",
            plan_file="/path/to/plan.json",
            base_path="/base",
            total_groups=3,
            groups_completed=2,
            groups_failed=1,
            total_files_moved=50,
            total_files_failed=5,
            status="failed",
            stopped_early=True,
            error="Stopped on error",
        )
        assert log.timestamp == "2026-01-20 14:30:00"
        assert log.total_groups == 3
        assert log.groups_completed == 2
        assert log.status == "failed"

    def test_to_dict_structure(self):
        """Test to_dict returns correct structure."""
        log = ExecutionLog(
            timestamp="2026-01-20 14:30:00",
            plan_file="/path/to/plan.json",
            base_path="/base",
            total_groups=1,
            groups_completed=1,
            groups_failed=0,
            total_files_moved=5,
            total_files_failed=0,
            status="success",
        )
        d = log.to_dict()

        # Check structure
        assert "execution_summary" in d
        assert "group_entries" in d
        assert "rollback" in d

        # Check execution_summary
        summary = d["execution_summary"]
        assert summary["timestamp"] == "2026-01-20 14:30:00"
        assert summary["plan_file"] == "/path/to/plan.json"
        assert summary["total_files_moved"] == 5
        assert summary["status"] == "success"

        # Check rollback structure
        rollback = d["rollback"]
        assert "total_moves_to_undo" in rollback
        assert "instructions" in rollback
        assert "rollback_script" in rollback

    def test_to_dict_with_rollback_instructions(self):
        """Test to_dict includes rollback instructions from all groups."""
        instruction1 = RollbackInstruction(
            current_path="/target/file1.txt",
            original_path="/source1/file1.txt",
            command='mv "/target/file1.txt" "/source1/file1.txt"',
        )
        instruction2 = RollbackInstruction(
            current_path="/target/file2.txt",
            original_path="/source2/file2.txt",
            command='mv "/target/file2.txt" "/source2/file2.txt"',
        )
        entry1 = GroupLogEntry(
            group_name="Group1",
            target_folder="/target",
            folders_processed=1,
            files_moved=1,
            files_failed=0,
            status="success",
            rollback_instructions=[instruction1],
        )
        entry2 = GroupLogEntry(
            group_name="Group2",
            target_folder="/target",
            folders_processed=1,
            files_moved=1,
            files_failed=0,
            status="success",
            rollback_instructions=[instruction2],
        )
        log = ExecutionLog(
            timestamp="2026-01-20 14:30:00",
            plan_file="/path/to/plan.json",
            base_path="/base",
            total_groups=2,
            groups_completed=2,
            groups_failed=0,
            total_files_moved=2,
            total_files_failed=0,
            status="success",
            group_entries=[entry1, entry2],
        )

        d = log.to_dict()

        assert d["rollback"]["total_moves_to_undo"] == 2
        assert len(d["rollback"]["instructions"]) == 2

    def test_generate_rollback_script_empty(self):
        """Test rollback script generation with no moves."""
        log = ExecutionLog(
            timestamp="2026-01-20 14:30:00",
            plan_file="/path/to/plan.json",
            base_path="/base",
            total_groups=0,
            groups_completed=0,
            groups_failed=0,
            total_files_moved=0,
            total_files_failed=0,
            status="success",
        )
        d = log.to_dict()

        assert "No moves to rollback" in d["rollback"]["rollback_script"]

    def test_generate_rollback_script_with_moves(self):
        """Test rollback script generation with moves."""
        instruction = RollbackInstruction(
            current_path="/target/file.txt",
            original_path="/source/file.txt",
            command='mv "/target/file.txt" "/source/file.txt"',
        )
        entry = GroupLogEntry(
            group_name="Test",
            target_folder="/target",
            folders_processed=1,
            files_moved=1,
            files_failed=0,
            status="success",
            rollback_instructions=[instruction],
        )
        log = ExecutionLog(
            timestamp="2026-01-20 14:30:00",
            plan_file="/path/to/plan.json",
            base_path="/base",
            total_groups=1,
            groups_completed=1,
            groups_failed=0,
            total_files_moved=1,
            total_files_failed=0,
            status="success",
            group_entries=[entry],
        )
        d = log.to_dict()

        script = d["rollback"]["rollback_script"]
        assert "#!/bin/bash" in script
        assert 'mv "/target/file.txt" "/source/file.txt"' in script
        assert "set -e" in script

    def test_from_execution_result(self):
        """Test creating log from ExecutionResult."""
        file_result = FileMoveResult(
            source_path="/source/file.txt",
            target_path="/target/file.txt",
            status=MoveStatus.SUCCESS,
        )
        folder_result = FolderMoveResult(
            source_folder="/source",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
            files_moved=1,
            file_results=[file_result],
        )
        group_result = GroupMoveResult(
            group_name="Test-related",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
            folders_processed=1,
            total_files_moved=1,
            folder_results=[folder_result],
        )
        execution_result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            groups_failed=0,
            total_files_moved=1,
            total_files_failed=0,
            group_results=[group_result],
        )

        log = ExecutionLog.from_execution_result(
            result=execution_result,
            plan_file="/path/to/plan.json",
            base_path="/base",
            total_groups=1,
        )

        assert log.plan_file == "/path/to/plan.json"
        assert log.base_path == "/base"
        assert log.total_groups == 1
        assert log.groups_completed == 1
        assert log.status == "success"
        assert len(log.group_entries) == 1


class TestCreateExecutionLog:
    """Tests for create_execution_log function."""

    def test_creates_log_file(self):
        """Test that log file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
            )

            assert log_path.exists()
            assert log_path.suffix == ".json"

    def test_log_file_name_format(self):
        """Test log file follows naming convention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
            )

            # Check filename format: execution_log_YYYYMMDD_HHMMSS.json
            assert log_path.name.startswith("execution_log_")
            assert log_path.suffix == ".json"
            # Check timestamp format in filename
            timestamp_part = log_path.stem.replace("execution_log_", "")
            assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS

    def test_log_file_in_default_directory(self):
        """Test log is saved in .organizer directory by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
            )

            assert ".organizer" in str(log_path)
            assert log_path.parent.name == ".organizer"

    def test_log_file_in_custom_directory(self):
        """Test log is saved in custom directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = os.path.join(tmpdir, "custom_logs")
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
                log_dir=custom_dir,
            )

            assert log_path.parent == Path(custom_dir)
            assert log_path.exists()

    def test_creates_directory_if_needed(self):
        """Test log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = os.path.join(tmpdir, "nested", "log", "dir")
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
                log_dir=custom_dir,
            )

            assert log_path.exists()
            assert Path(custom_dir).exists()

    def test_log_file_is_valid_json(self):
        """Test log file contains valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
            )

            with open(log_path) as f:
                data = json.load(f)

            assert "execution_summary" in data
            assert "group_entries" in data
            assert "rollback" in data

    def test_log_contains_correct_data(self):
        """Test log file contains correct execution data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_result = FileMoveResult(
                source_path="/source/file.txt",
                target_path="/target/file.txt",
                status=MoveStatus.SUCCESS,
            )
            folder_result = FolderMoveResult(
                source_folder="/source",
                target_folder="/target",
                status=MoveStatus.SUCCESS,
                files_moved=1,
                file_results=[file_result],
            )
            group_result = GroupMoveResult(
                group_name="Test-related",
                target_folder="/target",
                status=MoveStatus.SUCCESS,
                folders_processed=1,
                total_files_moved=1,
                folder_results=[folder_result],
            )
            result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                total_files_moved=1,
                group_results=[group_result],
            )

            log_path = create_execution_log(
                result=result,
                plan_file="my_plan.json",
                base_path=tmpdir,
                total_groups=1,
            )

            with open(log_path) as f:
                data = json.load(f)

            summary = data["execution_summary"]
            assert summary["plan_file"] == "my_plan.json"
            assert summary["base_path"] == tmpdir
            assert summary["total_groups"] == 1
            assert summary["groups_completed"] == 1
            assert summary["total_files_moved"] == 1
            assert summary["status"] == "success"

    def test_multiple_logs_get_different_names(self):
        """Test multiple logs get unique filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            # Create first log
            log_path1 = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
            )

            # Slight delay to ensure different timestamp
            import time

            time.sleep(1.1)

            # Create second log
            log_path2 = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
            )

            assert log_path1 != log_path2
            assert log_path1.exists()
            assert log_path2.exists()


class TestLoadExecutionLog:
    """Tests for load_execution_log function."""

    def test_load_valid_log(self):
        """Test loading a valid execution log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_log.json"
            log_data = {
                "execution_summary": {
                    "timestamp": "2026-01-20 14:30:00",
                    "status": "success",
                },
                "group_entries": [],
                "rollback": {
                    "total_moves_to_undo": 0,
                    "instructions": [],
                    "rollback_script": "# No moves",
                },
            }
            with open(log_path, "w") as f:
                json.dump(log_data, f)

            loaded = load_execution_log(log_path)

            assert loaded["execution_summary"]["status"] == "success"

    def test_load_nonexistent_file(self):
        """Test loading a non-existent file raises error."""
        import pytest

        with pytest.raises(FileNotFoundError):
            load_execution_log("/nonexistent/path.json")

    def test_load_invalid_json(self):
        """Test loading invalid JSON raises error."""
        import pytest

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "invalid.json"
            log_path.write_text("not valid json {{{")

            with pytest.raises(json.JSONDecodeError):
                load_execution_log(log_path)


class TestGetRollbackScript:
    """Tests for get_rollback_script function."""

    def test_get_script_from_log(self):
        """Test extracting rollback script from log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_log.json"
            script_content = "#!/bin/bash\nmv /target /source"
            log_data = {
                "execution_summary": {},
                "group_entries": [],
                "rollback": {
                    "total_moves_to_undo": 1,
                    "instructions": [],
                    "rollback_script": script_content,
                },
            }
            with open(log_path, "w") as f:
                json.dump(log_data, f)

            script = get_rollback_script(log_path)

            assert script == script_content

    def test_get_script_missing_rollback_key(self):
        """Test error when rollback key is missing."""
        import pytest

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test_log.json"
            log_data = {"execution_summary": {}}
            with open(log_path, "w") as f:
                json.dump(log_data, f)

            with pytest.raises(KeyError):
                get_rollback_script(log_path)


class TestSaveRollbackScript:
    """Tests for save_rollback_script function."""

    def test_save_script_default_path(self):
        """Test saving script with default output path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "execution_log_20260120_143000.json"
            log_data = {
                "execution_summary": {},
                "group_entries": [],
                "rollback": {
                    "total_moves_to_undo": 1,
                    "instructions": [],
                    "rollback_script": "#!/bin/bash\necho test",
                },
            }
            with open(log_path, "w") as f:
                json.dump(log_data, f)

            script_path = save_rollback_script(log_path)

            assert script_path.exists()
            assert script_path.suffix == ".sh"
            assert script_path.stem == log_path.stem

    def test_save_script_custom_path(self):
        """Test saving script with custom output path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "log.json"
            output_path = Path(tmpdir) / "my_rollback.sh"
            log_data = {
                "execution_summary": {},
                "group_entries": [],
                "rollback": {
                    "total_moves_to_undo": 1,
                    "instructions": [],
                    "rollback_script": "#!/bin/bash\necho test",
                },
            }
            with open(log_path, "w") as f:
                json.dump(log_data, f)

            result_path = save_rollback_script(log_path, output_path)

            assert result_path == output_path
            assert result_path.exists()

    def test_save_script_is_executable(self):
        """Test saved script has executable permission."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "log.json"
            log_data = {
                "execution_summary": {},
                "group_entries": [],
                "rollback": {
                    "total_moves_to_undo": 0,
                    "instructions": [],
                    "rollback_script": "#!/bin/bash\necho test",
                },
            }
            with open(log_path, "w") as f:
                json.dump(log_data, f)

            script_path = save_rollback_script(log_path)

            # Check executable bit
            assert os.access(script_path, os.X_OK)

    def test_save_script_content(self):
        """Test saved script has correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "log.json"
            expected_script = "#!/bin/bash\nmv /a /b\nmv /c /d"
            log_data = {
                "execution_summary": {},
                "group_entries": [],
                "rollback": {
                    "total_moves_to_undo": 2,
                    "instructions": [],
                    "rollback_script": expected_script,
                },
            }
            with open(log_path, "w") as f:
                json.dump(log_data, f)

            script_path = save_rollback_script(log_path)

            assert script_path.read_text() == expected_script


class TestIntegration:
    """Integration tests for execution logging."""

    def test_full_logging_workflow(self):
        """Test complete logging workflow from execution result to rollback script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate a real execution result
            file1 = FileMoveResult(
                source_path="/Resume/resume.pdf",
                target_path="/Employment/Resumes/resume.pdf",
                status=MoveStatus.SUCCESS,
            )
            file2 = FileMoveResult(
                source_path="/Resume/cover.pdf",
                target_path="/Employment/Resumes/cover.pdf",
                status=MoveStatus.SUCCESS,
            )
            folder1 = FolderMoveResult(
                source_folder="/Resume",
                target_folder="/Employment/Resumes",
                status=MoveStatus.SUCCESS,
                files_moved=2,
                file_results=[file1, file2],
            )
            group1 = GroupMoveResult(
                group_name="Resume-related",
                target_folder="/Employment/Resumes",
                status=MoveStatus.SUCCESS,
                folders_processed=1,
                total_files_moved=2,
                folder_results=[folder1],
            )
            result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                total_files_moved=2,
                group_results=[group1],
            )

            # Create log
            log_path = create_execution_log(
                result=result,
                plan_file="consolidation_plan.json",
                base_path=tmpdir,
                total_groups=1,
            )

            # Load and verify log
            log_data = load_execution_log(log_path)

            assert log_data["execution_summary"]["total_files_moved"] == 2
            assert log_data["execution_summary"]["status"] == "success"
            assert log_data["rollback"]["total_moves_to_undo"] == 2

            # Extract and save rollback script
            script_path = save_rollback_script(log_path)

            assert script_path.exists()
            script_content = script_path.read_text()
            assert "#!/bin/bash" in script_content
            assert "/Resume/resume.pdf" in script_content
            assert "/Resume/cover.pdf" in script_content

    def test_logging_with_partial_failure(self):
        """Test logging when some files fail to move."""
        with tempfile.TemporaryDirectory() as tmpdir:
            success_file = FileMoveResult(
                source_path="/source/good.pdf",
                target_path="/target/good.pdf",
                status=MoveStatus.SUCCESS,
            )
            failed_file = FileMoveResult(
                source_path="/source/bad.pdf",
                target_path="/target/bad.pdf",
                status=MoveStatus.FAILED,
                error="Permission denied",
            )
            folder_result = FolderMoveResult(
                source_folder="/source",
                target_folder="/target",
                status=MoveStatus.FAILED,
                files_moved=1,
                files_failed=1,
                file_results=[success_file, failed_file],
                error="1 file failed",
            )
            group_result = GroupMoveResult(
                group_name="Test-related",
                target_folder="/target",
                status=MoveStatus.FAILED,
                folders_processed=1,
                total_files_moved=1,
                total_files_failed=1,
                folder_results=[folder_result],
                error="Folder move had failures",
            )
            result = ExecutionResult(
                status=MoveStatus.FAILED,
                groups_completed=0,
                groups_failed=1,
                total_files_moved=1,
                total_files_failed=1,
                group_results=[group_result],
            )

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=1,
            )

            log_data = load_execution_log(log_path)

            # Verify failure is logged
            assert log_data["execution_summary"]["status"] == "failed"
            assert log_data["execution_summary"]["total_files_failed"] == 1

            # Verify only successful move has rollback instruction
            assert log_data["rollback"]["total_moves_to_undo"] == 1
            assert len(log_data["rollback"]["instructions"]) == 1
            assert (
                "/source/good.pdf"
                in log_data["rollback"]["instructions"][0]["original_path"]
            )


class TestContentAnalysisEntry:
    """Tests for ContentAnalysisEntry dataclass."""

    def test_creation(self):
        """Test creating a ContentAnalysisEntry."""
        entry = ContentAnalysisEntry(
            group_name="Resume-related",
            should_consolidate=True,
            decision_summary="Same AI category, same context bin",
            confidence=0.85,
            ai_categories=["Employment/Resumes"],
            date_ranges={"/path/Resume": "2024-2025"},
            reasoning=["Rule 1: Same AI category", "Rule 2: Same date range"],
        )
        assert entry.group_name == "Resume-related"
        assert entry.should_consolidate is True
        assert entry.confidence == 0.85
        assert "Employment/Resumes" in entry.ai_categories

    def test_to_dict(self):
        """Test converting to dictionary."""
        entry = ContentAnalysisEntry(
            group_name="Tax-related",
            should_consolidate=False,
            decision_summary="Different timeframes",
            confidence=0.3,
            ai_categories=["Finances/Taxes"],
            date_ranges={"/path/Tax2022": "2022", "/path/Tax2025": "2025"},
            reasoning=["Different timeframes detected"],
        )
        d = entry.to_dict()

        assert d["group_name"] == "Tax-related"
        assert d["should_consolidate"] is False
        assert d["decision_summary"] == "Different timeframes"
        assert d["confidence"] == 0.3
        assert "Finances/Taxes" in d["ai_categories"]
        assert "/path/Tax2022" in d["date_ranges"]

    def test_from_folder_group(self):
        """Test creating from a FolderGroup."""
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            decision_summary="Same AI category",
            confidence=0.9,
            ai_categories={"Employment/Resumes"},
            date_ranges={"/Resume": "2024-2025"},
            content_analysis_done=True,
            consolidation_reasoning=["Rule 1: Same AI category"],
            folder_content_summaries={
                "/Resume": FolderContentSummary(
                    folder_path="/Resume",
                    ai_categories={"Employment/Resumes"},
                    context_bins={"Personal"},
                    year_clusters=["2024-2025"],
                    document_count=5,
                )
            },
        )

        entry = ContentAnalysisEntry.from_folder_group(group)

        assert entry.group_name == "Resume-related"
        assert entry.should_consolidate is True
        assert entry.decision_summary == "Same AI category"
        assert entry.confidence == 0.9
        assert "Employment/Resumes" in entry.ai_categories
        assert "/Resume" in entry.folder_summaries

    def test_from_folder_group_no_consolidate(self):
        """Test creating from a FolderGroup that should not consolidate."""
        group = FolderGroup(
            group_name="Desktop-related",
            category_key=None,
            target_folder="Desktop",
            should_consolidate=False,
            decision_summary="Different path contexts",
            confidence=0.2,
            ai_categories={"Mixed"},
            content_analysis_done=True,
            consolidation_reasoning=["Rule 5: Incompatible paths"],
        )

        entry = ContentAnalysisEntry.from_folder_group(group)

        assert entry.should_consolidate is False
        assert entry.decision_summary == "Different path contexts"


class TestGroupLogEntryWithContentAnalysis:
    """Tests for GroupLogEntry with content analysis."""

    def test_to_dict_without_content_analysis(self):
        """Test to_dict when no content analysis present."""
        entry = GroupLogEntry(
            group_name="Test-related",
            target_folder="/target",
            folders_processed=1,
            files_moved=5,
            files_failed=0,
            status="success",
        )
        d = entry.to_dict()

        assert "content_analysis" not in d
        assert d["group_name"] == "Test-related"

    def test_to_dict_with_content_analysis(self):
        """Test to_dict includes content analysis when present."""
        content = ContentAnalysisEntry(
            group_name="Resume-related",
            should_consolidate=True,
            decision_summary="Same category",
            confidence=0.85,
            ai_categories=["Employment/Resumes"],
        )
        entry = GroupLogEntry(
            group_name="Resume-related",
            target_folder="/target/Resumes",
            folders_processed=2,
            files_moved=10,
            files_failed=0,
            status="success",
            content_analysis=content,
        )
        d = entry.to_dict()

        assert "content_analysis" in d
        assert d["content_analysis"]["group_name"] == "Resume-related"
        assert d["content_analysis"]["should_consolidate"] is True
        assert d["content_analysis"]["confidence"] == 0.85


class TestExecutionLogWithContentAnalysis:
    """Tests for ExecutionLog with content analysis."""

    def test_to_dict_includes_content_aware_flag(self):
        """Test that to_dict includes content_aware flag."""
        log = ExecutionLog(
            timestamp="2026-01-21 10:00:00",
            plan_file="/plan.json",
            base_path="/base",
            total_groups=1,
            groups_completed=1,
            groups_failed=0,
            total_files_moved=5,
            total_files_failed=0,
            status="success",
            content_aware=True,
        )
        d = log.to_dict()

        assert d["execution_summary"]["content_aware"] is True

    def test_to_dict_includes_content_analysis_summary(self):
        """Test that to_dict includes content_analysis when present."""
        log = ExecutionLog(
            timestamp="2026-01-21 10:00:00",
            plan_file="/plan.json",
            base_path="/base",
            total_groups=2,
            groups_completed=2,
            groups_failed=0,
            total_files_moved=10,
            total_files_failed=0,
            status="success",
            content_aware=True,
            content_analysis_summary={
                "content_aware_mode": True,
                "groups_analyzed": 2,
                "groups_to_consolidate": 1,
                "groups_to_skip": 1,
            },
        )
        d = log.to_dict()

        assert "content_analysis" in d
        assert d["content_analysis"]["content_aware_mode"] is True
        assert d["content_analysis"]["groups_analyzed"] == 2

    def test_to_dict_no_content_analysis_when_not_content_aware(self):
        """Test that content_analysis is not included when not content-aware."""
        log = ExecutionLog(
            timestamp="2026-01-21 10:00:00",
            plan_file="/plan.json",
            base_path="/base",
            total_groups=1,
            groups_completed=1,
            groups_failed=0,
            total_files_moved=5,
            total_files_failed=0,
            status="success",
            content_aware=False,
        )
        d = log.to_dict()

        assert d["execution_summary"]["content_aware"] is False
        assert "content_analysis" not in d

    def test_from_execution_result_with_plan(self):
        """Test creating log from ExecutionResult with a plan."""
        # Create a content-aware plan
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            decision_summary="Same AI category",
            confidence=0.9,
            ai_categories={"Employment/Resumes"},
            date_ranges={"/Resume": "2024-2025"},
            content_analysis_done=True,
            consolidation_reasoning=["Rule 1: Same AI category"],
        )
        group.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=5))

        plan = ConsolidationPlan(
            base_path="/base",
            threshold=0.8,
            groups=[group],
            content_aware=True,
        )

        # Create execution result
        file_result = FileMoveResult(
            source_path="/Resume/file.pdf",
            target_path="/Employment/Resumes/file.pdf",
            status=MoveStatus.SUCCESS,
        )
        folder_result = FolderMoveResult(
            source_folder="/Resume",
            target_folder="/Employment/Resumes",
            status=MoveStatus.SUCCESS,
            files_moved=1,
            file_results=[file_result],
        )
        group_result = GroupMoveResult(
            group_name="Resume-related",
            target_folder="/Employment/Resumes",
            status=MoveStatus.SUCCESS,
            folders_processed=1,
            total_files_moved=1,
            folder_results=[folder_result],
        )
        result = ExecutionResult(
            status=MoveStatus.SUCCESS,
            groups_completed=1,
            total_files_moved=1,
            group_results=[group_result],
        )

        log = ExecutionLog.from_execution_result(
            result=result,
            plan_file="plan.json",
            base_path="/base",
            total_groups=1,
            plan=plan,
        )

        assert log.content_aware is True
        assert len(log.group_entries) == 1
        assert log.group_entries[0].content_analysis is not None
        assert log.group_entries[0].content_analysis.should_consolidate is True
        assert log.content_analysis_summary["groups_analyzed"] == 1

    def test_from_execution_result_without_plan(self):
        """Test creating log from ExecutionResult without a plan (backward compat)."""
        result = ExecutionResult(status=MoveStatus.SUCCESS)

        log = ExecutionLog.from_execution_result(
            result=result,
            plan_file="plan.json",
            base_path="/base",
            total_groups=0,
        )

        assert log.content_aware is False
        assert log.content_analysis_summary == {}


class TestCreateExecutionLogWithContentAnalysis:
    """Tests for create_execution_log with content analysis."""

    def test_create_log_with_content_aware_plan(self):
        """Test creating log file with content-aware plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a content-aware plan
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                decision_summary="Same AI category, same context",
                confidence=0.9,
                ai_categories={"Employment/Resumes"},
                content_analysis_done=True,
            )
            group.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=5))

            plan = ConsolidationPlan(
                base_path=tmpdir,
                groups=[group],
                content_aware=True,
            )

            result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
            )

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=1,
                plan=plan,
            )

            # Load and verify
            with open(log_path) as f:
                data = json.load(f)

            assert data["execution_summary"]["content_aware"] is True
            assert "content_analysis" in data
            assert data["content_analysis"]["content_aware_mode"] is True
            assert data["content_analysis"]["groups_analyzed"] == 1

    def test_create_log_includes_group_content_analysis(self):
        """Test that log file includes content analysis per group."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create groups with different decisions
            group1 = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                should_consolidate=True,
                decision_summary="Same category",
                confidence=0.9,
                ai_categories={"Employment/Resumes"},
                content_analysis_done=True,
            )
            group1.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=3))

            group2 = FolderGroup(
                group_name="Tax-related",
                category_key="finances",
                should_consolidate=False,
                decision_summary="Different timeframes",
                confidence=0.3,
                ai_categories={"Finances/Taxes"},
                content_analysis_done=True,
            )
            group2.add_folder(FolderInfo(path="/Tax", name="Tax", file_count=2))

            plan = ConsolidationPlan(
                base_path=tmpdir,
                groups=[group1, group2],
                content_aware=True,
            )

            # Create matching execution results
            group1_result = GroupMoveResult(
                group_name="Resume-related",
                target_folder="/Employment/Resumes",
                status=MoveStatus.SUCCESS,
                folders_processed=1,
                total_files_moved=3,
            )
            group2_result = GroupMoveResult(
                group_name="Tax-related",
                target_folder="/Finances/Taxes",
                status=MoveStatus.SKIPPED,
                folders_processed=0,
            )

            result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                group_results=[group1_result, group2_result],
            )

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=2,
                plan=plan,
            )

            with open(log_path) as f:
                data = json.load(f)

            # Check content analysis summary
            assert data["content_analysis"]["groups_to_consolidate"] == 1
            assert data["content_analysis"]["groups_to_skip"] == 1

            # Check group-level content analysis
            assert len(data["group_entries"]) == 2
            assert data["group_entries"][0]["content_analysis"]["should_consolidate"]
            assert not data["group_entries"][1]["content_analysis"]["should_consolidate"]

    def test_create_log_without_plan_backward_compatible(self):
        """Test creating log without plan works (backward compatibility)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=0,
            )

            with open(log_path) as f:
                data = json.load(f)

            assert data["execution_summary"]["content_aware"] is False
            assert "content_analysis" not in data


class TestContentAnalysisIntegration:
    """Integration tests for content analysis logging."""

    def test_full_content_aware_logging_workflow(self):
        """Test complete workflow with content analysis."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a realistic content-aware plan
            folder1 = FolderInfo(path="/Resume", name="Resume", file_count=5)
            folder2 = FolderInfo(path="/Resumes", name="Resumes", file_count=3)

            summary1 = FolderContentSummary(
                folder_path="/Resume",
                ai_categories={"Employment/Resumes"},
                context_bins={"Personal"},
                year_clusters=["2024-2025"],
                document_count=5,
            )
            summary2 = FolderContentSummary(
                folder_path="/Resumes",
                ai_categories={"Employment/Resumes"},
                context_bins={"Personal"},
                year_clusters=["2024-2025"],
                document_count=3,
            )

            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                decision_summary="Same AI category, same context bin",
                confidence=0.95,
                ai_categories={"Employment/Resumes"},
                date_ranges={"/Resume": "2024-2025", "/Resumes": "2024-2025"},
                content_analysis_done=True,
                consolidation_reasoning=[
                    "Rule 1: ✅ Same AI category",
                    "Rule 2: ✅ Same date range",
                    "Rule 3: ✅ Same context bin",
                ],
                folder_content_summaries={
                    "/Resume": summary1,
                    "/Resumes": summary2,
                },
            )
            group.folders = [folder1, folder2]

            plan = ConsolidationPlan(
                base_path=tmpdir,
                groups=[group],
                content_aware=True,
            )

            # Create execution results
            file1 = FileMoveResult(
                source_path="/Resume/resume.pdf",
                target_path="/Employment/Resumes/resume.pdf",
                status=MoveStatus.SUCCESS,
            )
            folder_result = FolderMoveResult(
                source_folder="/Resume",
                target_folder="/Employment/Resumes",
                status=MoveStatus.SUCCESS,
                files_moved=5,
                file_results=[file1],
            )
            group_result = GroupMoveResult(
                group_name="Resume-related",
                target_folder="/Employment/Resumes",
                status=MoveStatus.SUCCESS,
                folders_processed=2,
                total_files_moved=8,
                folder_results=[folder_result],
            )
            result = ExecutionResult(
                status=MoveStatus.SUCCESS,
                groups_completed=1,
                total_files_moved=8,
                group_results=[group_result],
            )

            # Create log
            log_path = create_execution_log(
                result=result,
                plan_file="consolidation_plan.json",
                base_path=tmpdir,
                total_groups=1,
                plan=plan,
            )

            # Load and verify comprehensive content
            data = load_execution_log(log_path)

            # Verify execution summary
            assert data["execution_summary"]["content_aware"] is True
            assert data["execution_summary"]["total_files_moved"] == 8

            # Verify content analysis summary
            ca = data["content_analysis"]
            assert ca["content_aware_mode"] is True
            assert ca["groups_analyzed"] == 1
            assert ca["groups_to_consolidate"] == 1
            assert ca["groups_to_skip"] == 0
            assert "Employment/Resumes" in ca["ai_categories_found"]
            assert "2024-2025" in ca["date_ranges_found"]

            # Verify group decisions
            assert len(ca["group_decisions"]) == 1
            decision = ca["group_decisions"][0]
            assert decision["group_name"] == "Resume-related"
            assert decision["should_consolidate"] is True
            assert decision["confidence"] == 0.95

            # Verify group-level content analysis
            group_entry = data["group_entries"][0]
            assert "content_analysis" in group_entry
            group_ca = group_entry["content_analysis"]
            assert group_ca["should_consolidate"] is True
            assert group_ca["decision_summary"] == "Same AI category, same context bin"
            assert "/Resume" in group_ca["folder_summaries"]
            assert "/Resumes" in group_ca["folder_summaries"]

    def test_mixed_consolidation_decisions_logged(self):
        """Test logging when some groups consolidate and some don't."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Group 1: Should consolidate
            group1 = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                should_consolidate=True,
                decision_summary="Same category",
                confidence=0.9,
                ai_categories={"Employment/Resumes"},
                content_analysis_done=True,
            )
            group1.add_folder(FolderInfo(path="/Resume", name="Resume", file_count=3))

            # Group 2: Should NOT consolidate (different timeframes)
            group2 = FolderGroup(
                group_name="Tax-related",
                category_key="finances",
                should_consolidate=False,
                decision_summary="Different timeframes (Tax2022 vs Tax2025)",
                confidence=0.2,
                ai_categories={"Finances/Taxes"},
                date_ranges={"/Tax2022": "2022", "/Tax2025": "2025"},
                content_analysis_done=True,
            )
            group2.add_folder(FolderInfo(path="/Tax2022", name="Tax2022", file_count=5))
            group2.add_folder(FolderInfo(path="/Tax2025", name="Tax2025", file_count=4))

            plan = ConsolidationPlan(
                base_path=tmpdir,
                groups=[group1, group2],
                content_aware=True,
            )

            result = ExecutionResult(status=MoveStatus.SUCCESS)

            log_path = create_execution_log(
                result=result,
                plan_file="plan.json",
                base_path=tmpdir,
                total_groups=2,
                plan=plan,
            )

            data = load_execution_log(log_path)

            # Verify summary accurately reflects mixed decisions
            ca = data["content_analysis"]
            assert ca["groups_analyzed"] == 2
            assert ca["groups_to_consolidate"] == 1
            assert ca["groups_to_skip"] == 1

            # Verify both categories are tracked
            assert "Employment/Resumes" in ca["ai_categories_found"]
            assert "Finances/Taxes" in ca["ai_categories_found"]

            # Verify date ranges are tracked
            assert "2022" in ca["date_ranges_found"]
            assert "2025" in ca["date_ranges_found"]
