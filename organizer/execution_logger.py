"""Execution logging for folder consolidation operations.

This module provides detailed logging of consolidation execution with rollback
instructions for recovery.

Phase 6 enhancement: Log content analysis results to execution log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from organizer.file_operations import (
    ExecutionResult,
    FileMoveResult,
    GroupMoveResult,
    MoveStatus,
)

if TYPE_CHECKING:
    from organizer.consolidation_planner import ConsolidationPlan, FolderGroup


@dataclass
class ContentAnalysisEntry:
    """Content analysis data for a folder group.

    Records the content analysis results that led to the consolidation decision.
    """

    group_name: str
    should_consolidate: bool
    decision_summary: str
    confidence: float
    ai_categories: list[str] = field(default_factory=list)
    date_ranges: dict[str, str] = field(default_factory=dict)
    reasoning: list[str] = field(default_factory=list)
    folder_summaries: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "group_name": self.group_name,
            "should_consolidate": self.should_consolidate,
            "decision_summary": self.decision_summary,
            "confidence": self.confidence,
            "ai_categories": self.ai_categories,
            "date_ranges": self.date_ranges,
            "reasoning": self.reasoning,
            "folder_summaries": self.folder_summaries,
        }

    @classmethod
    def from_folder_group(cls, group: FolderGroup) -> ContentAnalysisEntry:
        """Create content analysis entry from a FolderGroup.

        Args:
            group: The FolderGroup with content analysis data.

        Returns:
            ContentAnalysisEntry with all content analysis details.
        """
        # Convert folder_content_summaries to serializable dict
        folder_summaries = {}
        for path, summary in group.folder_content_summaries.items():
            folder_summaries[path] = summary.to_dict()

        return cls(
            group_name=group.group_name,
            should_consolidate=group.should_consolidate,
            decision_summary=group.decision_summary,
            confidence=group.confidence,
            ai_categories=list(group.ai_categories),
            date_ranges=dict(group.date_ranges),
            reasoning=list(group.consolidation_reasoning),
            folder_summaries=folder_summaries,
        )


@dataclass
class RollbackInstruction:
    """Instructions for undoing a single file move."""

    current_path: str
    original_path: str
    command: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "current_path": self.current_path,
            "original_path": self.original_path,
            "command": self.command,
        }

    @classmethod
    def from_file_move(
        cls, file_result: FileMoveResult
    ) -> "RollbackInstruction | None":
        """Create rollback instruction from a successful file move.

        Args:
            file_result: The file move result.

        Returns:
            RollbackInstruction if the move was successful, None otherwise.
        """
        if file_result.status != MoveStatus.SUCCESS:
            return None

        command = f'mv "{file_result.target_path}" "{file_result.source_path}"'
        return cls(
            current_path=file_result.target_path,
            original_path=file_result.source_path,
            command=command,
        )


@dataclass
class GroupLogEntry:
    """Log entry for a folder group consolidation."""

    group_name: str
    target_folder: str
    folders_processed: int
    files_moved: int
    files_failed: int
    status: str
    error: str = ""
    folder_entries: list[dict] = field(default_factory=list)
    rollback_instructions: list[RollbackInstruction] = field(default_factory=list)
    content_analysis: ContentAnalysisEntry | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "group_name": self.group_name,
            "target_folder": self.target_folder,
            "folders_processed": self.folders_processed,
            "files_moved": self.files_moved,
            "files_failed": self.files_failed,
            "status": self.status,
            "error": self.error,
            "folder_entries": self.folder_entries,
            "rollback_instructions": [r.to_dict() for r in self.rollback_instructions],
        }
        if self.content_analysis is not None:
            result["content_analysis"] = self.content_analysis.to_dict()
        return result

    @classmethod
    def from_group_result(cls, group_result: GroupMoveResult) -> "GroupLogEntry":
        """Create a log entry from a group move result.

        Args:
            group_result: The group move result.

        Returns:
            GroupLogEntry with all move details and rollback instructions.
        """
        rollback_instructions: list[RollbackInstruction] = []
        folder_entries: list[dict] = []

        for folder_result in group_result.folder_results:
            folder_entry = {
                "source_folder": folder_result.source_folder,
                "target_folder": folder_result.target_folder,
                "files_moved": folder_result.files_moved,
                "files_failed": folder_result.files_failed,
                "status": folder_result.status.value,
                "error": folder_result.error,
            }
            folder_entries.append(folder_entry)

            # Collect rollback instructions from successful file moves
            for file_result in folder_result.file_results:
                instruction = RollbackInstruction.from_file_move(file_result)
                if instruction:
                    rollback_instructions.append(instruction)

        return cls(
            group_name=group_result.group_name,
            target_folder=group_result.target_folder,
            folders_processed=group_result.folders_processed,
            files_moved=group_result.total_files_moved,
            files_failed=group_result.total_files_failed,
            status=group_result.status.value,
            error=group_result.error,
            folder_entries=folder_entries,
            rollback_instructions=rollback_instructions,
        )


@dataclass
class ExecutionLog:
    """Complete log of a consolidation plan execution."""

    timestamp: str
    plan_file: str
    base_path: str
    total_groups: int
    groups_completed: int
    groups_failed: int
    total_files_moved: int
    total_files_failed: int
    status: str
    stopped_early: bool = False
    error: str = ""
    group_entries: list[GroupLogEntry] = field(default_factory=list)
    content_aware: bool = False
    content_analysis_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Collect all rollback instructions
        all_rollback_instructions: list[dict] = []
        for entry in self.group_entries:
            all_rollback_instructions.extend(
                [r.to_dict() for r in entry.rollback_instructions]
            )

        result = {
            "execution_summary": {
                "timestamp": self.timestamp,
                "plan_file": self.plan_file,
                "base_path": self.base_path,
                "total_groups": self.total_groups,
                "groups_completed": self.groups_completed,
                "groups_failed": self.groups_failed,
                "total_files_moved": self.total_files_moved,
                "total_files_failed": self.total_files_failed,
                "status": self.status,
                "stopped_early": self.stopped_early,
                "error": self.error,
                "content_aware": self.content_aware,
            },
            "group_entries": [entry.to_dict() for entry in self.group_entries],
            "rollback": {
                "total_moves_to_undo": len(all_rollback_instructions),
                "instructions": all_rollback_instructions,
                "rollback_script": self._generate_rollback_script(
                    all_rollback_instructions
                ),
            },
        }

        # Add content analysis summary if content-aware mode was used
        if self.content_aware and self.content_analysis_summary:
            result["content_analysis"] = self.content_analysis_summary

        return result

    def _generate_rollback_script(self, instructions: list[dict]) -> str:
        """Generate a shell script to rollback all moves.

        Args:
            instructions: List of rollback instruction dictionaries.

        Returns:
            Shell script content as a string.
        """
        if not instructions:
            return "# No moves to rollback"

        lines = [
            "#!/bin/bash",
            "# Rollback script for consolidation execution",
            f"# Generated: {self.timestamp}",
            f"# Plan file: {self.plan_file}",
            "",
            "set -e  # Exit on first error",
            "",
        ]

        for i, instruction in enumerate(instructions, 1):
            lines.append(f"# Move {i}/{len(instructions)}")
            lines.append(instruction["command"])
            lines.append("")

        lines.append(f'echo "Rollback complete: {len(instructions)} files restored"')

        return "\n".join(lines)

    @classmethod
    def from_execution_result(
        cls,
        result: ExecutionResult,
        plan_file: str,
        base_path: str,
        total_groups: int,
        plan: ConsolidationPlan | None = None,
    ) -> "ExecutionLog":
        """Create an execution log from an execution result.

        Args:
            result: The execution result.
            plan_file: Path to the plan file that was executed.
            base_path: Base path used for the execution.
            total_groups: Total number of groups in the plan.
            plan: Optional ConsolidationPlan to extract content analysis from.

        Returns:
            ExecutionLog with all execution details.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build group entries with content analysis if available
        group_entries: list[GroupLogEntry] = []
        content_aware = plan is not None and plan.content_aware

        # Create a mapping of group names to FolderGroups for content analysis
        plan_groups_by_name: dict[str, FolderGroup] = {}
        if plan is not None:
            for group in plan.groups:
                plan_groups_by_name[group.group_name] = group

        for group_result in result.group_results:
            entry = GroupLogEntry.from_group_result(group_result)

            # Add content analysis if available
            if content_aware and group_result.group_name in plan_groups_by_name:
                folder_group = plan_groups_by_name[group_result.group_name]
                if folder_group.content_analysis_done:
                    entry.content_analysis = ContentAnalysisEntry.from_folder_group(
                        folder_group
                    )

            group_entries.append(entry)

        # Build content analysis summary
        content_analysis_summary: dict = {}
        if content_aware and plan is not None:
            content_analysis_summary = cls._build_content_analysis_summary(plan)

        return cls(
            timestamp=timestamp,
            plan_file=plan_file,
            base_path=base_path,
            total_groups=total_groups,
            groups_completed=result.groups_completed,
            groups_failed=result.groups_failed,
            total_files_moved=result.total_files_moved,
            total_files_failed=result.total_files_failed,
            status=result.status.value,
            stopped_early=result.stopped_early,
            error=result.error,
            group_entries=group_entries,
            content_aware=content_aware,
            content_analysis_summary=content_analysis_summary,
        )

    @classmethod
    def _build_content_analysis_summary(cls, plan: ConsolidationPlan) -> dict:
        """Build a summary of content analysis from a consolidation plan.

        Args:
            plan: The ConsolidationPlan with content analysis data.

        Returns:
            Dictionary with content analysis summary.
        """
        # Collect all AI categories and their counts
        all_categories: dict[str, int] = {}
        all_date_ranges: set[str] = set()
        groups_analyzed = 0
        groups_to_consolidate = 0
        groups_to_skip = 0

        for group in plan.groups:
            if group.content_analysis_done:
                groups_analyzed += 1

                if group.should_consolidate:
                    groups_to_consolidate += 1
                else:
                    groups_to_skip += 1

                for category in group.ai_categories:
                    all_categories[category] = all_categories.get(category, 0) + 1

                for date_range in group.date_ranges.values():
                    all_date_ranges.add(date_range)

        return {
            "content_aware_mode": True,
            "groups_analyzed": groups_analyzed,
            "groups_to_consolidate": groups_to_consolidate,
            "groups_to_skip": groups_to_skip,
            "ai_categories_found": all_categories,
            "date_ranges_found": sorted(all_date_ranges),
            "group_decisions": [
                {
                    "group_name": g.group_name,
                    "should_consolidate": g.should_consolidate,
                    "decision_summary": g.decision_summary,
                    "confidence": g.confidence,
                    "ai_categories": list(g.ai_categories),
                }
                for g in plan.groups
                if g.content_analysis_done
            ],
        }


def create_execution_log(
    result: ExecutionResult,
    plan_file: str,
    base_path: str,
    total_groups: int,
    log_dir: str | Path | None = None,
    plan: ConsolidationPlan | None = None,
) -> Path:
    """Create an execution log file from an execution result.

    Args:
        result: The execution result to log.
        plan_file: Path to the plan file that was executed.
        base_path: Base path used for the execution.
        total_groups: Total number of groups in the plan.
        log_dir: Directory to save the log. Defaults to .organizer/ in base_path.
        plan: Optional ConsolidationPlan to extract content analysis from.
            If provided and content-aware mode was used, the log will include
            detailed content analysis results for each group.

    Returns:
        Path to the created log file.
    """
    # Determine log directory
    if log_dir is None:
        log_dir = Path(base_path) / ".organizer"
    else:
        log_dir = Path(log_dir)

    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped log filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"execution_log_{timestamp}.json"
    log_path = log_dir / log_filename

    # Create log
    log = ExecutionLog.from_execution_result(
        result=result,
        plan_file=plan_file,
        base_path=base_path,
        total_groups=total_groups,
        plan=plan,
    )

    # Save log to file
    with open(log_path, "w") as f:
        json.dump(log.to_dict(), f, indent=2)

    return log_path


def load_execution_log(log_path: str | Path) -> dict:
    """Load an execution log from a file.

    Args:
        log_path: Path to the execution log file.

    Returns:
        The execution log as a dictionary.

    Raises:
        FileNotFoundError: If the log file doesn't exist.
        json.JSONDecodeError: If the log file is not valid JSON.
    """
    with open(log_path) as f:
        return json.load(f)


def get_rollback_script(log_path: str | Path) -> str:
    """Extract the rollback script from an execution log.

    Args:
        log_path: Path to the execution log file.

    Returns:
        The rollback script as a string.

    Raises:
        FileNotFoundError: If the log file doesn't exist.
        KeyError: If the log file doesn't contain rollback information.
    """
    log_data = load_execution_log(log_path)
    return log_data["rollback"]["rollback_script"]


def save_rollback_script(
    log_path: str | Path, output_path: str | Path | None = None
) -> Path:
    """Save the rollback script from an execution log to a file.

    Args:
        log_path: Path to the execution log file.
        output_path: Path to save the script. Defaults to same directory as log with .sh extension.

    Returns:
        Path to the saved script file.
    """
    log_path = Path(log_path)

    if output_path is None:
        output_path = log_path.with_suffix(".sh")
    else:
        output_path = Path(output_path)

    script = get_rollback_script(log_path)

    with open(output_path, "w") as f:
        f.write(script)

    # Make script executable
    output_path.chmod(output_path.stat().st_mode | 0o111)

    return output_path
