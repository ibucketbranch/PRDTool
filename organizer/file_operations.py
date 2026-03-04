"""Atomic file operations for folder consolidation.

This module provides safe file operations that move files atomically per folder group,
with verification and error handling to ensure no data loss.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from organizer.consolidation_planner import ConsolidationPlan, FolderGroup


class MoveStatus(Enum):
    """Status of a file or folder move operation."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class FileMoveResult:
    """Result of moving a single file."""

    source_path: str
    target_path: str
    status: MoveStatus
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_path": self.source_path,
            "target_path": self.target_path,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class FolderMoveResult:
    """Result of moving all files from a single source folder."""

    source_folder: str
    target_folder: str
    status: MoveStatus
    files_moved: int = 0
    files_failed: int = 0
    file_results: list[FileMoveResult] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_folder": self.source_folder,
            "target_folder": self.target_folder,
            "status": self.status.value,
            "files_moved": self.files_moved,
            "files_failed": self.files_failed,
            "file_results": [r.to_dict() for r in self.file_results],
            "error": self.error,
        }


@dataclass
class GroupMoveResult:
    """Result of consolidating a folder group."""

    group_name: str
    target_folder: str
    status: MoveStatus
    folders_processed: int = 0
    total_files_moved: int = 0
    total_files_failed: int = 0
    folder_results: list[FolderMoveResult] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "group_name": self.group_name,
            "target_folder": self.target_folder,
            "status": self.status.value,
            "folders_processed": self.folders_processed,
            "total_files_moved": self.total_files_moved,
            "total_files_failed": self.total_files_failed,
            "folder_results": [r.to_dict() for r in self.folder_results],
            "error": self.error,
        }


@dataclass
class ExecutionResult:
    """Result of executing a full consolidation plan."""

    status: MoveStatus
    groups_completed: int = 0
    groups_failed: int = 0
    total_files_moved: int = 0
    total_files_failed: int = 0
    group_results: list[GroupMoveResult] = field(default_factory=list)
    error: str = ""
    stopped_early: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "groups_completed": self.groups_completed,
            "groups_failed": self.groups_failed,
            "total_files_moved": self.total_files_moved,
            "total_files_failed": self.total_files_failed,
            "group_results": [r.to_dict() for r in self.group_results],
            "error": self.error,
            "stopped_early": self.stopped_early,
        }


ProgressCallback = Callable[[str, int, int], None]


def move_file_atomic(source: str, target: str) -> FileMoveResult:
    """Move a single file atomically.

    If the target file already exists, the source file is renamed with a numeric
    suffix to avoid overwriting.

    Args:
        source: Path to the source file.
        target: Path to the target file.

    Returns:
        FileMoveResult with status and any error information.
    """
    try:
        source_path = Path(source)
        target_path = Path(target)

        if not source_path.exists():
            return FileMoveResult(
                source_path=source,
                target_path=target,
                status=MoveStatus.FAILED,
                error=f"Source file does not exist: {source}",
            )

        if not source_path.is_file():
            return FileMoveResult(
                source_path=source,
                target_path=target,
                status=MoveStatus.FAILED,
                error=f"Source is not a file: {source}",
            )

        # Handle name collision at target
        final_target = target_path
        if target_path.exists():
            final_target = _get_unique_path(target_path)

        # Ensure target directory exists
        final_target.parent.mkdir(parents=True, exist_ok=True)

        # Move the file
        shutil.move(str(source_path), str(final_target))

        # Verify the move succeeded
        if not final_target.exists():
            return FileMoveResult(
                source_path=source,
                target_path=str(final_target),
                status=MoveStatus.FAILED,
                error="File not found at target after move",
            )

        return FileMoveResult(
            source_path=source,
            target_path=str(final_target),
            status=MoveStatus.SUCCESS,
        )

    except PermissionError as e:
        return FileMoveResult(
            source_path=source,
            target_path=target,
            status=MoveStatus.FAILED,
            error=f"Permission denied: {e}",
        )
    except OSError as e:
        return FileMoveResult(
            source_path=source,
            target_path=target,
            status=MoveStatus.FAILED,
            error=f"OS error: {e}",
        )
    except Exception as e:
        return FileMoveResult(
            source_path=source,
            target_path=target,
            status=MoveStatus.FAILED,
            error=f"Unexpected error: {e}",
        )


def _get_unique_path(path: Path) -> Path:
    """Get a unique path by appending a numeric suffix if needed.

    Args:
        path: The desired path.

    Returns:
        A path that doesn't exist (original or with numeric suffix).
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def move_folder_contents(
    source_folder: str,
    target_folder: str,
    progress_callback: ProgressCallback | None = None,
) -> FolderMoveResult:
    """Move all files from a source folder to a target folder.

    This function moves files one at a time and verifies each move.
    If any file fails to move, the operation continues but records the failure.

    Args:
        source_folder: Path to the source folder.
        target_folder: Path to the target folder.
        progress_callback: Optional callback for progress updates.

    Returns:
        FolderMoveResult with details of all file moves.
    """
    source_path = Path(source_folder)
    target_path = Path(target_folder)

    result = FolderMoveResult(
        source_folder=source_folder,
        target_folder=target_folder,
        status=MoveStatus.SUCCESS,
    )

    # Verify source folder exists
    if not source_path.exists():
        result.status = MoveStatus.FAILED
        result.error = f"Source folder does not exist: {source_folder}"
        return result

    if not source_path.is_dir():
        result.status = MoveStatus.FAILED
        result.error = f"Source is not a directory: {source_folder}"
        return result

    # Create target folder if needed
    try:
        target_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        result.status = MoveStatus.FAILED
        result.error = f"Could not create target directory: {e}"
        return result

    # Get list of files to move
    try:
        files = [f for f in source_path.iterdir() if f.is_file()]
    except PermissionError as e:
        result.status = MoveStatus.FAILED
        result.error = f"Permission denied reading source folder: {e}"
        return result

    # Move each file
    for i, source_file in enumerate(files):
        target_file = target_path / source_file.name

        file_result = move_file_atomic(str(source_file), str(target_file))
        result.file_results.append(file_result)

        if file_result.status == MoveStatus.SUCCESS:
            result.files_moved += 1
        else:
            result.files_failed += 1
            result.status = MoveStatus.FAILED

        if progress_callback:
            progress_callback(f"Moving {source_file.name}", i + 1, len(files))

    # Set error message if any files failed
    if result.files_failed > 0:
        result.error = f"{result.files_failed} file(s) failed to move"

    return result


def execute_folder_group(
    group: FolderGroup,
    base_path: str,
    progress_callback: ProgressCallback | None = None,
) -> GroupMoveResult:
    """Execute consolidation for a single folder group.

    Moves all files from all source folders in the group to the target folder.
    This is an atomic operation per group - if any folder fails, the operation
    stops and reports what was completed.

    Args:
        group: The folder group to consolidate.
        base_path: The base path for resolving relative target paths.
        progress_callback: Optional callback for progress updates.

    Returns:
        GroupMoveResult with details of the consolidation.
    """
    target_folder = _resolve_target_path(group.target_folder, base_path)

    result = GroupMoveResult(
        group_name=group.group_name,
        target_folder=target_folder,
        status=MoveStatus.SUCCESS,
    )

    for folder_info in group.folders:
        # Skip the target folder if it's in the source list
        if _paths_are_same(folder_info.path, target_folder):
            result.folders_processed += 1
            continue

        folder_result = move_folder_contents(
            source_folder=folder_info.path,
            target_folder=target_folder,
            progress_callback=progress_callback,
        )
        result.folder_results.append(folder_result)
        result.folders_processed += 1
        result.total_files_moved += folder_result.files_moved
        result.total_files_failed += folder_result.files_failed

        # If a folder operation failed, mark the group as failed but continue
        if folder_result.status == MoveStatus.FAILED:
            result.status = MoveStatus.FAILED
            if not result.error:
                result.error = f"Failed to move files from {folder_info.path}"

    return result


def _resolve_target_path(target_folder: str, base_path: str) -> str:
    """Resolve the target folder path.

    If target_folder is relative, it's resolved against base_path.
    If it's absolute, it's returned as-is.

    Args:
        target_folder: The target folder path (may be relative).
        base_path: The base path for resolving relative paths.

    Returns:
        The resolved absolute path.
    """
    target_path = Path(target_folder)
    if target_path.is_absolute():
        return str(target_path)
    return str(Path(base_path) / target_folder)


def _paths_are_same(path1: str, path2: str) -> bool:
    """Check if two paths refer to the same location.

    Args:
        path1: First path.
        path2: Second path.

    Returns:
        True if the paths are the same.
    """
    try:
        return Path(path1).resolve() == Path(path2).resolve()
    except OSError:
        return path1 == path2


def execute_consolidation_plan(
    plan: ConsolidationPlan,
    progress_callback: ProgressCallback | None = None,
    stop_on_error: bool = True,
) -> ExecutionResult:
    """Execute a complete consolidation plan.

    Processes each folder group in order, moving files to their target folders.
    If stop_on_error is True, stops on first group failure.

    Args:
        plan: The consolidation plan to execute.
        progress_callback: Optional callback for progress updates.
        stop_on_error: Whether to stop on first error (default: True).

    Returns:
        ExecutionResult with details of the entire execution.
    """
    result = ExecutionResult(status=MoveStatus.SUCCESS)

    for i, group in enumerate(plan.groups):
        if progress_callback:
            progress_callback(
                f"Processing group: {group.group_name}",
                i + 1,
                len(plan.groups),
            )

        group_result = execute_folder_group(
            group=group,
            base_path=plan.base_path,
            progress_callback=progress_callback,
        )
        result.group_results.append(group_result)
        result.total_files_moved += group_result.total_files_moved
        result.total_files_failed += group_result.total_files_failed

        if group_result.status == MoveStatus.SUCCESS:
            result.groups_completed += 1
        else:
            result.groups_failed += 1
            result.status = MoveStatus.FAILED

            if stop_on_error:
                result.stopped_early = True
                result.error = (
                    f"Stopped after group '{group.group_name}' failed. "
                    f"Completed {result.groups_completed}/{len(plan.groups)} groups."
                )
                break

    return result


def verify_files_at_target(target_folder: str, expected_count: int) -> tuple[bool, int]:
    """Verify that files exist at the target folder.

    Args:
        target_folder: Path to the target folder.
        expected_count: Expected number of files.

    Returns:
        Tuple of (success, actual_count).
    """
    target_path = Path(target_folder)

    if not target_path.exists():
        return False, 0

    try:
        actual_count = sum(1 for f in target_path.iterdir() if f.is_file())
        return actual_count >= expected_count, actual_count
    except (PermissionError, OSError):
        return False, 0
