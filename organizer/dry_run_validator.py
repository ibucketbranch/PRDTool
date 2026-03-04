"""Dry-run validation for PRD task execution.

Parses test and build output to determine pass/fail status, then updates
the PRDTaskStatusTracker. When a dry-run passes, the associated task
automatically transitions to "ready for sprint" status.

Example usage:
    from organizer.dry_run_validator import validate_dry_run, mark_ready

    # Validate test output
    result = validate_dry_run("phase11.2", test_output_text)
    if result.passed:
        print(f"Task {result.task_id} passed dry-run validation")
    else:
        print(f"Errors: {result.errors}")

    # Mark ready (usually done automatically by validate_dry_run)
    mark_ready("phase11.2")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from organizer.prd_task_status import DryRunStatus, PRDTaskStatusTracker


def _now_iso() -> str:
    return datetime.now().isoformat()


@dataclass
class DryRunResult:
    """Result of validating a dry-run for a PRD task.

    Attributes:
        task_id: Unique identifier for the PRD task.
        passed: Whether the dry-run passed validation.
        errors: List of error messages extracted from output.
        timestamp: ISO timestamp when validation was performed.
    """

    task_id: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "task_id": self.task_id,
            "passed": self.passed,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DryRunResult":
        """Create DryRunResult from dictionary."""
        return cls(
            task_id=data["task_id"],
            passed=data["passed"],
            errors=data.get("errors", []),
            timestamp=data.get("timestamp", _now_iso()),
        )


# Patterns that indicate test/build failure
FAILURE_PATTERNS = [
    # pytest patterns
    re.compile(r"(\d+)\s+(?:failed|error)", re.IGNORECASE),
    re.compile(r"FAILED\s+\S+", re.IGNORECASE),
    re.compile(r"ERROR\s+\S+", re.IGNORECASE),
    re.compile(r"pytest:?\s*error", re.IGNORECASE),
    re.compile(r"collection\s+error", re.IGNORECASE),
    # General test failure patterns
    re.compile(r"AssertionError", re.IGNORECASE),
    re.compile(r"test\s+failed", re.IGNORECASE),
    re.compile(r"tests?\s+(?:did\s+)?not\s+pass", re.IGNORECASE),
    # Build/lint failure patterns
    re.compile(r"(?:ruff|flake8|mypy|pylint|black).*error", re.IGNORECASE),
    re.compile(r"lint(?:ing)?\s+failed", re.IGNORECASE),
    re.compile(r"type\s*check(?:ing)?\s+failed", re.IGNORECASE),
    re.compile(r"build\s+failed", re.IGNORECASE),
    re.compile(r"compilation\s+(?:error|failed)", re.IGNORECASE),
    re.compile(r"syntax\s*error", re.IGNORECASE),
    # Exit code patterns
    re.compile(r"exit(?:ed)?\s+(?:with\s+)?(?:code\s+)?[1-9]\d*", re.IGNORECASE),
    re.compile(r"returned?\s+(?:non-?zero|[1-9]\d*)", re.IGNORECASE),
]

# Patterns that indicate test/build success
SUCCESS_PATTERNS = [
    # pytest success patterns
    re.compile(r"(\d+)\s+passed(?:,\s+0\s+(?:failed|error))?", re.IGNORECASE),
    re.compile(r"all\s+tests?\s+passed", re.IGNORECASE),
    re.compile(r"tests?\s+passed", re.IGNORECASE),
    re.compile(r"OK\s*\(\d+\s+tests?\)", re.IGNORECASE),
    # Build success patterns
    re.compile(r"build\s+(?:succeeded|successful|passed)", re.IGNORECASE),
    re.compile(r"lint(?:ing)?\s+passed", re.IGNORECASE),
    re.compile(r"no\s+(?:issues?|errors?|problems?)\s+found", re.IGNORECASE),
    # Exit code success
    re.compile(r"exit(?:ed)?\s+(?:with\s+)?(?:code\s+)?0", re.IGNORECASE),
]

# Patterns to extract specific error messages
ERROR_EXTRACTION_PATTERNS = [
    # pytest FAILED lines
    re.compile(r"(FAILED\s+\S+::\S+)", re.IGNORECASE),
    # pytest error summary
    re.compile(r"(E\s+(?:AssertionError|TypeError|ValueError|KeyError|AttributeError)[^\n]*)", re.IGNORECASE),
    # Ruff/lint errors
    re.compile(r"(\S+\.py:\d+:\d+:\s*(?:error|E\d+)[^\n]*)", re.IGNORECASE),
    # mypy errors
    re.compile(r"(\S+\.py:\d+:\s*error:[^\n]*)", re.IGNORECASE),
    # General error lines
    re.compile(r"((?:Error|ERROR):\s+[^\n]{10,100})", re.IGNORECASE),
]


def _extract_errors(output: str) -> list[str]:
    """Extract specific error messages from test/build output.

    Args:
        output: Raw test/build output text.

    Returns:
        List of extracted error message strings.
    """
    errors = []
    seen = set()

    for pattern in ERROR_EXTRACTION_PATTERNS:
        for match in pattern.finditer(output):
            error_msg = match.group(1).strip()
            # Normalize whitespace
            error_msg = " ".join(error_msg.split())
            # Truncate very long error messages
            if len(error_msg) > 200:
                error_msg = error_msg[:197] + "..."
            # Deduplicate
            if error_msg not in seen:
                seen.add(error_msg)
                errors.append(error_msg)

    return errors[:20]  # Limit to 20 errors


def _check_failure_patterns(output: str) -> bool:
    """Check if output contains failure patterns.

    Args:
        output: Raw test/build output text.

    Returns:
        True if failure patterns are found.
    """
    for pattern in FAILURE_PATTERNS:
        if pattern.search(output):
            return True
    return False


def _check_success_patterns(output: str) -> bool:
    """Check if output contains success patterns.

    Args:
        output: Raw test/build output text.

    Returns:
        True if success patterns are found.
    """
    for pattern in SUCCESS_PATTERNS:
        if pattern.search(output):
            return True
    return False


def validate_dry_run(
    task_id: str,
    test_output: str,
    status_file: str | Path | None = None,
    auto_mark_ready: bool = True,
) -> DryRunResult:
    """Validate dry-run output for a PRD task.

    Parses the test/build output to determine if the dry-run passed or failed.
    If passed and auto_mark_ready is True, automatically transitions the task
    to "ready" status.

    Args:
        task_id: Unique identifier for the PRD task.
        test_output: Raw test/build output text to parse.
        status_file: Optional path to the status file (uses default if None).
        auto_mark_ready: If True, automatically mark task as ready on pass.

    Returns:
        DryRunResult with pass/fail status and any extracted errors.
    """
    # Normalize whitespace for consistent parsing
    output = test_output.strip()

    # Check for failures first (failures take precedence)
    has_failures = _check_failure_patterns(output)
    has_successes = _check_success_patterns(output)

    # Determine pass/fail
    if has_failures:
        passed = False
    elif has_successes:
        passed = True
    elif output == "":
        # Empty output is ambiguous - treat as failure
        passed = False
    else:
        # No clear signals - treat as failure (conservative)
        passed = False

    # Extract error messages if failed
    errors = _extract_errors(output) if not passed else []

    # If no specific errors extracted but we failed, add generic message
    if not passed and not errors:
        if output == "":
            errors = ["No test output received"]
        else:
            errors = ["Dry-run validation failed (no specific error extracted)"]

    result = DryRunResult(
        task_id=task_id,
        passed=passed,
        errors=errors,
    )

    # Update tracker
    tracker = PRDTaskStatusTracker(status_file=status_file)
    if passed:
        tracker.mark_dry_run_pass(task_id)
        if auto_mark_ready:
            tracker.auto_transition_to_ready(task_id)
    else:
        tracker.mark_dry_run_fail(task_id, errors=errors)

    return result


def mark_ready(
    task_id: str,
    status_file: str | Path | None = None,
) -> bool:
    """Mark a task as ready for sprint execution.

    This is typically called automatically by validate_dry_run when a task
    passes, but can be called manually if needed.

    Args:
        task_id: Unique identifier for the PRD task.
        status_file: Optional path to the status file (uses default if None).

    Returns:
        True if task was successfully marked as ready, False otherwise.
    """
    tracker = PRDTaskStatusTracker(status_file=status_file)

    # Check current status
    current_status = tracker.get_status(task_id)

    if current_status == DryRunStatus.DRY_RUN_PASS:
        tracker.mark_ready(task_id)
        return True
    elif current_status == DryRunStatus.READY:
        # Already ready
        return True
    else:
        # Cannot mark as ready from current state
        return False


def get_ready_tasks(
    status_file: str | Path | None = None,
) -> list[dict]:
    """Get all tasks that are ready for sprint execution.

    Args:
        status_file: Optional path to the status file (uses default if None).

    Returns:
        List of task status dictionaries for ready tasks.
    """
    tracker = PRDTaskStatusTracker(status_file=status_file)
    return [task.to_dict() for task in tracker.list_ready_tasks()]


def get_task_status(
    task_id: str,
    status_file: str | Path | None = None,
) -> str:
    """Get the current status of a task.

    Args:
        task_id: Unique identifier for the PRD task.
        status_file: Optional path to the status file (uses default if None).

    Returns:
        Status string (untested, dry_run_pass, dry_run_fail, or ready).
    """
    tracker = PRDTaskStatusTracker(status_file=status_file)
    return tracker.get_status(task_id).value
