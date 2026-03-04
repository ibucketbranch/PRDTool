"""Tests for the file_operations module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from organizer.consolidation_planner import (
    ConsolidationPlan,
    FolderGroup,
    FolderInfo,
)
from organizer.file_operations import (
    ExecutionResult,
    FileMoveResult,
    FolderMoveResult,
    GroupMoveResult,
    MoveStatus,
    _get_unique_path,
    _paths_are_same,
    _resolve_target_path,
    execute_consolidation_plan,
    execute_folder_group,
    move_file_atomic,
    move_folder_contents,
    verify_files_at_target,
)


class TestMoveStatus:
    """Tests for MoveStatus enum."""

    def test_success_value(self):
        """Test SUCCESS enum value."""
        assert MoveStatus.SUCCESS.value == "success"

    def test_failed_value(self):
        """Test FAILED enum value."""
        assert MoveStatus.FAILED.value == "failed"

    def test_skipped_value(self):
        """Test SKIPPED enum value."""
        assert MoveStatus.SKIPPED.value == "skipped"


class TestFileMoveResult:
    """Tests for FileMoveResult dataclass."""

    def test_creation(self):
        """Test creating a FileMoveResult."""
        result = FileMoveResult(
            source_path="/source/file.txt",
            target_path="/target/file.txt",
            status=MoveStatus.SUCCESS,
        )
        assert result.source_path == "/source/file.txt"
        assert result.target_path == "/target/file.txt"
        assert result.status == MoveStatus.SUCCESS
        assert result.error == ""

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = FileMoveResult(
            source_path="/source/file.txt",
            target_path="/target/file.txt",
            status=MoveStatus.FAILED,
            error="Some error",
        )
        d = result.to_dict()
        assert d["source_path"] == "/source/file.txt"
        assert d["target_path"] == "/target/file.txt"
        assert d["status"] == "failed"
        assert d["error"] == "Some error"


class TestFolderMoveResult:
    """Tests for FolderMoveResult dataclass."""

    def test_creation(self):
        """Test creating a FolderMoveResult."""
        result = FolderMoveResult(
            source_folder="/source",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
        )
        assert result.source_folder == "/source"
        assert result.target_folder == "/target"
        assert result.status == MoveStatus.SUCCESS
        assert result.files_moved == 0
        assert result.files_failed == 0
        assert result.file_results == []

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = FolderMoveResult(
            source_folder="/source",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
            files_moved=5,
            files_failed=1,
        )
        d = result.to_dict()
        assert d["source_folder"] == "/source"
        assert d["target_folder"] == "/target"
        assert d["status"] == "success"
        assert d["files_moved"] == 5
        assert d["files_failed"] == 1


class TestGroupMoveResult:
    """Tests for GroupMoveResult dataclass."""

    def test_creation(self):
        """Test creating a GroupMoveResult."""
        result = GroupMoveResult(
            group_name="Test-related",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
        )
        assert result.group_name == "Test-related"
        assert result.target_folder == "/target"
        assert result.status == MoveStatus.SUCCESS

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = GroupMoveResult(
            group_name="Test-related",
            target_folder="/target",
            status=MoveStatus.SUCCESS,
            folders_processed=3,
            total_files_moved=10,
        )
        d = result.to_dict()
        assert d["group_name"] == "Test-related"
        assert d["folders_processed"] == 3
        assert d["total_files_moved"] == 10


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_creation(self):
        """Test creating an ExecutionResult."""
        result = ExecutionResult(status=MoveStatus.SUCCESS)
        assert result.status == MoveStatus.SUCCESS
        assert result.groups_completed == 0
        assert result.stopped_early is False

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = ExecutionResult(
            status=MoveStatus.FAILED,
            groups_completed=2,
            groups_failed=1,
            stopped_early=True,
            error="Stopped on error",
        )
        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["groups_completed"] == 2
        assert d["groups_failed"] == 1
        assert d["stopped_early"] is True


class TestMoveFileAtomic:
    """Tests for move_file_atomic function."""

    def test_move_file_success(self):
        """Test successfully moving a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            target = os.path.join(tmpdir, "target.txt")

            # Create source file
            Path(source).write_text("test content")

            result = move_file_atomic(source, target)

            assert result.status == MoveStatus.SUCCESS
            assert not Path(source).exists()
            assert Path(target).exists()
            assert Path(target).read_text() == "test content"

    def test_move_file_source_not_exists(self):
        """Test moving a non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "nonexistent.txt")
            target = os.path.join(tmpdir, "target.txt")

            result = move_file_atomic(source, target)

            assert result.status == MoveStatus.FAILED
            assert "does not exist" in result.error

    def test_move_file_source_is_directory(self):
        """Test moving a directory instead of file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source_dir")
            target = os.path.join(tmpdir, "target.txt")

            os.makedirs(source)

            result = move_file_atomic(source, target)

            assert result.status == MoveStatus.FAILED
            assert "not a file" in result.error

    def test_move_file_creates_target_directory(self):
        """Test that target directory is created if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            target = os.path.join(tmpdir, "nested", "dir", "target.txt")

            Path(source).write_text("test")

            result = move_file_atomic(source, target)

            assert result.status == MoveStatus.SUCCESS
            assert Path(target).exists()

    def test_move_file_name_collision(self):
        """Test moving a file when target already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            target = os.path.join(tmpdir, "target.txt")

            Path(source).write_text("source content")
            Path(target).write_text("existing content")

            result = move_file_atomic(source, target)

            assert result.status == MoveStatus.SUCCESS
            # Original target should still exist
            assert Path(target).exists()
            assert Path(target).read_text() == "existing content"
            # New file should have suffix
            assert "_1" in result.target_path
            assert Path(result.target_path).read_text() == "source content"


class TestGetUniquePath:
    """Tests for _get_unique_path function."""

    def test_path_doesnt_exist(self):
        """Test with non-existent path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "newfile.txt"
            result = _get_unique_path(path)
            assert result == path

    def test_path_exists_gets_suffix(self):
        """Test with existing path gets numeric suffix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "file.txt"
            path.touch()

            result = _get_unique_path(path)

            assert result != path
            assert result.name == "file_1.txt"

    def test_multiple_collisions(self):
        """Test with multiple existing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "file.txt"
            path.touch()
            (Path(tmpdir) / "file_1.txt").touch()
            (Path(tmpdir) / "file_2.txt").touch()

            result = _get_unique_path(path)

            assert result.name == "file_3.txt"


class TestMoveFolderContents:
    """Tests for move_folder_contents function."""

    def test_move_all_files_success(self):
        """Test successfully moving all files from a folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source")
            target = os.path.join(tmpdir, "target")

            os.makedirs(source)
            Path(os.path.join(source, "file1.txt")).write_text("content1")
            Path(os.path.join(source, "file2.txt")).write_text("content2")

            result = move_folder_contents(source, target)

            assert result.status == MoveStatus.SUCCESS
            assert result.files_moved == 2
            assert result.files_failed == 0
            assert Path(os.path.join(target, "file1.txt")).exists()
            assert Path(os.path.join(target, "file2.txt")).exists()

    def test_move_source_not_exists(self):
        """Test moving from non-existent folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "nonexistent")
            target = os.path.join(tmpdir, "target")

            result = move_folder_contents(source, target)

            assert result.status == MoveStatus.FAILED
            assert "does not exist" in result.error

    def test_move_source_is_file(self):
        """Test moving from a file instead of folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source.txt")
            target = os.path.join(tmpdir, "target")

            Path(source).write_text("content")

            result = move_folder_contents(source, target)

            assert result.status == MoveStatus.FAILED
            assert "not a directory" in result.error

    def test_move_creates_target_directory(self):
        """Test that target directory is created if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source")
            target = os.path.join(tmpdir, "nested", "target")

            os.makedirs(source)
            Path(os.path.join(source, "file.txt")).write_text("content")

            result = move_folder_contents(source, target)

            assert result.status == MoveStatus.SUCCESS
            assert Path(target).exists()
            assert Path(os.path.join(target, "file.txt")).exists()

    def test_move_empty_folder(self):
        """Test moving from empty folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source")
            target = os.path.join(tmpdir, "target")

            os.makedirs(source)

            result = move_folder_contents(source, target)

            assert result.status == MoveStatus.SUCCESS
            assert result.files_moved == 0
            assert result.files_failed == 0

    def test_move_with_progress_callback(self):
        """Test that progress callback is called."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "source")
            target = os.path.join(tmpdir, "target")

            os.makedirs(source)
            Path(os.path.join(source, "file1.txt")).write_text("content1")
            Path(os.path.join(source, "file2.txt")).write_text("content2")

            callback = MagicMock()

            result = move_folder_contents(source, target, progress_callback=callback)

            assert result.status == MoveStatus.SUCCESS
            assert callback.call_count == 2


class TestExecuteFolderGroup:
    """Tests for execute_folder_group function."""

    def test_consolidate_group_success(self):
        """Test successfully consolidating a folder group."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source folders
            source1 = os.path.join(tmpdir, "Resume")
            source2 = os.path.join(tmpdir, "Resumes")
            target = os.path.join(tmpdir, "Employment", "Resumes")

            os.makedirs(source1)
            os.makedirs(source2)
            Path(os.path.join(source1, "resume1.pdf")).write_text("content1")
            Path(os.path.join(source2, "resume2.pdf")).write_text("content2")

            folder1 = FolderInfo(path=source1, name="Resume", file_count=1)
            folder2 = FolderInfo(path=source2, name="Resumes", file_count=1)

            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.folders = [folder1, folder2]

            result = execute_folder_group(group, tmpdir)

            assert result.status == MoveStatus.SUCCESS
            assert result.total_files_moved == 2
            assert result.folders_processed == 2
            assert Path(os.path.join(target, "resume1.pdf")).exists()
            assert Path(os.path.join(target, "resume2.pdf")).exists()

    def test_consolidate_skips_target_folder(self):
        """Test that target folder is skipped if it's in source list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source folder that is also the target
            source1 = os.path.join(tmpdir, "Resumes")
            source2 = os.path.join(tmpdir, "Resume_Old")

            os.makedirs(source1)
            os.makedirs(source2)
            Path(os.path.join(source1, "existing.pdf")).write_text("content1")
            Path(os.path.join(source2, "old.pdf")).write_text("content2")

            folder1 = FolderInfo(path=source1, name="Resumes", file_count=1)
            folder2 = FolderInfo(path=source2, name="Resume_Old", file_count=1)

            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=source1,  # Target is same as folder1
            )
            group.folders = [folder1, folder2]

            result = execute_folder_group(group, tmpdir)

            # Should skip folder1 (target) and only move from folder2
            assert result.total_files_moved == 1
            assert result.folders_processed == 2

    def test_consolidate_with_relative_target(self):
        """Test consolidation with relative target path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "Source")
            os.makedirs(source)
            Path(os.path.join(source, "file.txt")).write_text("content")

            folder = FolderInfo(path=source, name="Source", file_count=1)

            group = FolderGroup(
                group_name="Test-related",
                category_key=None,
                target_folder="Organized/Target",  # Relative path
            )
            group.folders = [folder]

            result = execute_folder_group(group, tmpdir)

            assert result.status == MoveStatus.SUCCESS
            expected_target = os.path.join(tmpdir, "Organized", "Target")
            assert Path(os.path.join(expected_target, "file.txt")).exists()


class TestResolveTargetPath:
    """Tests for _resolve_target_path function."""

    def test_relative_path(self):
        """Test resolving relative path."""
        result = _resolve_target_path("subdir/target", "/base")
        assert result == "/base/subdir/target"

    def test_absolute_path(self):
        """Test resolving absolute path."""
        result = _resolve_target_path("/absolute/path", "/base")
        assert result == "/absolute/path"


class TestPathsAreSame:
    """Tests for _paths_are_same function."""

    def test_same_paths(self):
        """Test identical paths."""
        assert _paths_are_same("/path/to/dir", "/path/to/dir") is True

    def test_different_paths(self):
        """Test different paths."""
        assert _paths_are_same("/path/to/dir1", "/path/to/dir2") is False

    def test_same_with_trailing_slash(self):
        """Test paths that differ only in trailing slash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _paths_are_same(tmpdir, tmpdir + "/") is True


class TestExecuteConsolidationPlan:
    """Tests for execute_consolidation_plan function."""

    def test_execute_empty_plan(self):
        """Test executing an empty plan."""
        plan = ConsolidationPlan(base_path="/tmp", threshold=0.8)

        result = execute_consolidation_plan(plan)

        assert result.status == MoveStatus.SUCCESS
        assert result.groups_completed == 0
        assert result.total_files_moved == 0

    def test_execute_plan_success(self):
        """Test successfully executing a plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source folders
            source1 = os.path.join(tmpdir, "Folder1")
            source2 = os.path.join(tmpdir, "Folder2")
            os.makedirs(source1)
            os.makedirs(source2)
            Path(os.path.join(source1, "file1.txt")).write_text("content1")
            Path(os.path.join(source2, "file2.txt")).write_text("content2")

            # Create plan
            folder1 = FolderInfo(path=source1, name="Folder1", file_count=1)
            folder2 = FolderInfo(path=source2, name="Folder2", file_count=1)

            group = FolderGroup(
                group_name="Test-related",
                category_key=None,
                target_folder="Target",
            )
            group.folders = [folder1, folder2]

            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8, groups=[group])

            result = execute_consolidation_plan(plan)

            assert result.status == MoveStatus.SUCCESS
            assert result.groups_completed == 1
            assert result.total_files_moved == 2

    def test_execute_plan_with_progress_callback(self):
        """Test executing a plan with progress callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = os.path.join(tmpdir, "Source")
            os.makedirs(source)
            Path(os.path.join(source, "file.txt")).write_text("content")

            folder = FolderInfo(path=source, name="Source", file_count=1)
            group = FolderGroup(
                group_name="Test-related",
                category_key=None,
                target_folder="Target",
            )
            group.folders = [folder]

            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8, groups=[group])

            callback = MagicMock()
            result = execute_consolidation_plan(plan, progress_callback=callback)

            assert result.status == MoveStatus.SUCCESS
            assert callback.called

    def test_execute_plan_stops_on_error(self):
        """Test that execution stops on first error when stop_on_error=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First group - valid
            source1 = os.path.join(tmpdir, "Source1")
            os.makedirs(source1)
            Path(os.path.join(source1, "file1.txt")).write_text("content1")

            # Second group - invalid source
            source2 = os.path.join(tmpdir, "Nonexistent")

            folder1 = FolderInfo(path=source1, name="Source1", file_count=1)
            folder2 = FolderInfo(path=source2, name="Nonexistent", file_count=1)

            group1 = FolderGroup(
                group_name="Group1",
                category_key=None,
                target_folder="Target1",
            )
            group1.folders = [folder1]

            group2 = FolderGroup(
                group_name="Group2",
                category_key=None,
                target_folder="Target2",
            )
            group2.folders = [folder2]

            plan = ConsolidationPlan(
                base_path=tmpdir, threshold=0.8, groups=[group2, group1]
            )

            result = execute_consolidation_plan(plan, stop_on_error=True)

            assert result.status == MoveStatus.FAILED
            assert result.stopped_early is True
            assert result.groups_failed == 1
            # Second group should not have been processed
            assert len(result.group_results) == 1

    def test_execute_plan_continues_on_error(self):
        """Test that execution continues on error when stop_on_error=False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First group - invalid source
            source1 = os.path.join(tmpdir, "Nonexistent")

            # Second group - valid
            source2 = os.path.join(tmpdir, "Source2")
            os.makedirs(source2)
            Path(os.path.join(source2, "file2.txt")).write_text("content2")

            folder1 = FolderInfo(path=source1, name="Nonexistent", file_count=1)
            folder2 = FolderInfo(path=source2, name="Source2", file_count=1)

            group1 = FolderGroup(
                group_name="Group1",
                category_key=None,
                target_folder="Target1",
            )
            group1.folders = [folder1]

            group2 = FolderGroup(
                group_name="Group2",
                category_key=None,
                target_folder="Target2",
            )
            group2.folders = [folder2]

            plan = ConsolidationPlan(
                base_path=tmpdir, threshold=0.8, groups=[group1, group2]
            )

            result = execute_consolidation_plan(plan, stop_on_error=False)

            assert result.status == MoveStatus.FAILED
            assert result.stopped_early is False
            assert result.groups_completed == 1
            assert result.groups_failed == 1
            # Both groups should have been processed
            assert len(result.group_results) == 2


class TestVerifyFilesAtTarget:
    """Tests for verify_files_at_target function."""

    def test_verify_success(self):
        """Test verification succeeds with correct count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target")
            os.makedirs(target)
            Path(os.path.join(target, "file1.txt")).touch()
            Path(os.path.join(target, "file2.txt")).touch()

            success, count = verify_files_at_target(target, 2)

            assert success is True
            assert count == 2

    def test_verify_more_files_than_expected(self):
        """Test verification succeeds with more files than expected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target")
            os.makedirs(target)
            Path(os.path.join(target, "file1.txt")).touch()
            Path(os.path.join(target, "file2.txt")).touch()
            Path(os.path.join(target, "file3.txt")).touch()

            success, count = verify_files_at_target(target, 2)

            assert success is True
            assert count == 3

    def test_verify_fewer_files_than_expected(self):
        """Test verification fails with fewer files than expected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target")
            os.makedirs(target)
            Path(os.path.join(target, "file1.txt")).touch()

            success, count = verify_files_at_target(target, 2)

            assert success is False
            assert count == 1

    def test_verify_nonexistent_folder(self):
        """Test verification fails for non-existent folder."""
        success, count = verify_files_at_target("/nonexistent/path", 1)

        assert success is False
        assert count == 0

    def test_verify_empty_folder(self):
        """Test verification with empty folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target")
            os.makedirs(target)

            success, count = verify_files_at_target(target, 0)

            assert success is True
            assert count == 0


class TestIntegration:
    """Integration tests for file operations."""

    def test_full_consolidation_workflow(self):
        """Test complete consolidation workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure matching PRD example
            resume_path = os.path.join(tmpdir, "Resume")
            resumes_path = os.path.join(tmpdir, "Resumes")
            resume_docs_path = os.path.join(tmpdir, "Resume_Docs")

            os.makedirs(resume_path)
            os.makedirs(resumes_path)
            os.makedirs(resume_docs_path)

            # Add files
            Path(os.path.join(resume_path, "my_resume.pdf")).write_text("resume1")
            Path(os.path.join(resume_path, "cover_letter.pdf")).write_text("cover1")
            Path(os.path.join(resumes_path, "old_resume.pdf")).write_text("resume2")
            Path(os.path.join(resume_docs_path, "resume_2023.pdf")).write_text(
                "resume3"
            )

            # Create plan
            folder1 = FolderInfo(path=resume_path, name="Resume", file_count=2)
            folder2 = FolderInfo(path=resumes_path, name="Resumes", file_count=1)
            folder3 = FolderInfo(
                path=resume_docs_path, name="Resume_Docs", file_count=1
            )

            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.folders = [folder1, folder2, folder3]

            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                groups=[group],
            )

            # Execute
            result = execute_consolidation_plan(plan)

            # Verify
            assert result.status == MoveStatus.SUCCESS
            assert result.total_files_moved == 4
            assert result.groups_completed == 1

            target_path = os.path.join(tmpdir, "Employment", "Resumes")
            assert Path(target_path).exists()

            success, count = verify_files_at_target(target_path, 4)
            assert success is True
            assert count == 4
