"""PRD task status tracking for dry-run validation pipeline.

Tracks the lifecycle of PRD tasks from untested → dry_run_pass/fail → ready.
This module enables the Dry-Run → Ready Pipeline (Phase 11) where tasks
that pass dry-run validation are automatically marked as ready for sprint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class DryRunStatus(Enum):
    """Status values for PRD task dry-run validation."""

    UNTESTED = "untested"
    DRY_RUN_PASS = "dry_run_pass"
    DRY_RUN_FAIL = "dry_run_fail"
    READY = "ready"


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass
class TaskStatus:
    """Status record for a single PRD task."""

    task_id: str
    status: DryRunStatus = DryRunStatus.UNTESTED
    last_dry_run_at: str | None = None
    last_errors: list[str] = field(default_factory=list)
    marked_ready_at: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "last_dry_run_at": self.last_dry_run_at,
            "last_errors": self.last_errors,
            "marked_ready_at": self.marked_ready_at,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskStatus":
        """Create TaskStatus from dictionary."""
        return cls(
            task_id=data["task_id"],
            status=DryRunStatus(data.get("status", "untested")),
            last_dry_run_at=data.get("last_dry_run_at"),
            last_errors=data.get("last_errors", []),
            marked_ready_at=data.get("marked_ready_at"),
            history=data.get("history", []),
        )


class PRDTaskStatusTracker:
    """Tracks dry-run status for PRD tasks.

    This tracker persists task status to a JSON file and provides methods
    for updating task status through the dry-run validation lifecycle.

    Lifecycle:
        untested -> dry_run_pass -> ready  (happy path)
        untested -> dry_run_fail           (needs fixing)
        dry_run_fail -> dry_run_pass       (after fix)
        dry_run_pass -> ready              (automatic transition)
    """

    DEFAULT_FILE = ".organizer/agent/prd_task_status.json"

    def __init__(self, status_file: str | Path | None = None):
        """Initialize tracker with optional custom status file path.

        Args:
            status_file: Path to the JSON status file.
                         Defaults to .organizer/agent/prd_task_status.json
        """
        self.status_file = Path(status_file or self.DEFAULT_FILE)
        self._tasks: dict[str, TaskStatus] = {}
        self._load()

    def _load(self) -> None:
        """Load task statuses from disk."""
        if not self.status_file.exists():
            self._tasks = {}
            return

        try:
            data = json.loads(self.status_file.read_text(encoding="utf-8"))
            self._tasks = {
                task_id: TaskStatus.from_dict(task_data)
                for task_id, task_data in data.get("tasks", {}).items()
            }
        except (json.JSONDecodeError, KeyError, ValueError):
            self._tasks = {}

    def _save(self) -> None:
        """Persist task statuses to disk."""
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _now_iso(),
            "tasks": {
                task_id: task.to_dict() for task_id, task in self._tasks.items()
            },
        }
        self.status_file.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def get_status(self, task_id: str) -> DryRunStatus:
        """Get the current status for a task.

        Args:
            task_id: Unique identifier for the PRD task

        Returns:
            Current DryRunStatus (defaults to UNTESTED if not tracked)
        """
        if task_id not in self._tasks:
            return DryRunStatus.UNTESTED
        return self._tasks[task_id].status

    def get_task(self, task_id: str) -> TaskStatus | None:
        """Get the full TaskStatus record for a task.

        Args:
            task_id: Unique identifier for the PRD task

        Returns:
            TaskStatus record or None if task not tracked
        """
        return self._tasks.get(task_id)

    def mark_dry_run_pass(self, task_id: str) -> TaskStatus:
        """Mark a task as having passed dry-run validation.

        Args:
            task_id: Unique identifier for the PRD task

        Returns:
            Updated TaskStatus record
        """
        task = self._tasks.get(task_id) or TaskStatus(task_id=task_id)
        old_status = task.status

        task.status = DryRunStatus.DRY_RUN_PASS
        task.last_dry_run_at = _now_iso()
        task.last_errors = []
        task.history.append({
            "timestamp": _now_iso(),
            "from_status": old_status.value,
            "to_status": DryRunStatus.DRY_RUN_PASS.value,
            "event": "dry_run_pass",
        })

        self._tasks[task_id] = task
        self._save()
        return task

    def mark_dry_run_fail(self, task_id: str, errors: list[str] | None = None) -> TaskStatus:
        """Mark a task as having failed dry-run validation.

        Args:
            task_id: Unique identifier for the PRD task
            errors: List of error messages from the dry-run

        Returns:
            Updated TaskStatus record
        """
        task = self._tasks.get(task_id) or TaskStatus(task_id=task_id)
        old_status = task.status

        task.status = DryRunStatus.DRY_RUN_FAIL
        task.last_dry_run_at = _now_iso()
        task.last_errors = errors or []
        task.history.append({
            "timestamp": _now_iso(),
            "from_status": old_status.value,
            "to_status": DryRunStatus.DRY_RUN_FAIL.value,
            "event": "dry_run_fail",
            "errors": errors or [],
        })

        self._tasks[task_id] = task
        self._save()
        return task

    def mark_ready(self, task_id: str) -> TaskStatus:
        """Mark a task as ready for sprint execution.

        This should only be called after a task has passed dry-run validation.
        The transition from dry_run_pass to ready is typically automatic.

        Args:
            task_id: Unique identifier for the PRD task

        Returns:
            Updated TaskStatus record

        Raises:
            ValueError: If task hasn't passed dry-run validation
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found. Cannot mark as ready.")

        if task.status != DryRunStatus.DRY_RUN_PASS:
            raise ValueError(
                f"Task {task_id} has status {task.status.value}. "
                "Only tasks with dry_run_pass status can be marked ready."
            )

        old_status = task.status
        task.status = DryRunStatus.READY
        task.marked_ready_at = _now_iso()
        task.history.append({
            "timestamp": _now_iso(),
            "from_status": old_status.value,
            "to_status": DryRunStatus.READY.value,
            "event": "marked_ready",
        })

        self._tasks[task_id] = task
        self._save()
        return task

    def auto_transition_to_ready(self, task_id: str) -> TaskStatus | None:
        """Automatically transition a task from dry_run_pass to ready.

        This is the main entry point for the automatic transition that happens
        when a dry-run passes with no errors.

        Args:
            task_id: Unique identifier for the PRD task

        Returns:
            Updated TaskStatus if transition occurred, None otherwise
        """
        task = self._tasks.get(task_id)
        if task is None:
            return None

        if task.status != DryRunStatus.DRY_RUN_PASS:
            return None

        return self.mark_ready(task_id)

    def list_by_status(self, status: DryRunStatus) -> list[TaskStatus]:
        """List all tasks with a specific status.

        Args:
            status: The DryRunStatus to filter by

        Returns:
            List of TaskStatus records matching the status
        """
        return [task for task in self._tasks.values() if task.status == status]

    def list_ready_tasks(self) -> list[TaskStatus]:
        """List all tasks that are ready for sprint execution.

        Returns:
            List of TaskStatus records with READY status
        """
        return self.list_by_status(DryRunStatus.READY)

    def list_all(self) -> list[TaskStatus]:
        """List all tracked tasks.

        Returns:
            List of all TaskStatus records
        """
        return list(self._tasks.values())

    def reset_task(self, task_id: str) -> TaskStatus:
        """Reset a task back to untested status.

        Args:
            task_id: Unique identifier for the PRD task

        Returns:
            Updated TaskStatus record
        """
        task = self._tasks.get(task_id) or TaskStatus(task_id=task_id)
        old_status = task.status

        task.status = DryRunStatus.UNTESTED
        task.history.append({
            "timestamp": _now_iso(),
            "from_status": old_status.value,
            "to_status": DryRunStatus.UNTESTED.value,
            "event": "reset",
        })

        self._tasks[task_id] = task
        self._save()
        return task

    def clear(self) -> None:
        """Clear all task statuses."""
        self._tasks = {}
        self._save()
