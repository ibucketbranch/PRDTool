"""Tests for the PRDTaskStatusTracker and related classes."""

import json
import tempfile
from pathlib import Path

import pytest

from organizer.prd_task_status import (
    DryRunStatus,
    PRDTaskStatusTracker,
    TaskStatus,
)


class TestDryRunStatus:
    """Tests for the DryRunStatus enum."""

    def test_untested_value(self):
        """Test UNTESTED enum value."""
        assert DryRunStatus.UNTESTED.value == "untested"

    def test_dry_run_pass_value(self):
        """Test DRY_RUN_PASS enum value."""
        assert DryRunStatus.DRY_RUN_PASS.value == "dry_run_pass"

    def test_dry_run_fail_value(self):
        """Test DRY_RUN_FAIL enum value."""
        assert DryRunStatus.DRY_RUN_FAIL.value == "dry_run_fail"

    def test_ready_value(self):
        """Test READY enum value."""
        assert DryRunStatus.READY.value == "ready"

    def test_create_from_string(self):
        """Test creating enum from string value."""
        assert DryRunStatus("untested") == DryRunStatus.UNTESTED
        assert DryRunStatus("dry_run_pass") == DryRunStatus.DRY_RUN_PASS
        assert DryRunStatus("dry_run_fail") == DryRunStatus.DRY_RUN_FAIL
        assert DryRunStatus("ready") == DryRunStatus.READY

    def test_invalid_value_raises(self):
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError):
            DryRunStatus("invalid_status")


class TestTaskStatus:
    """Tests for the TaskStatus dataclass."""

    def test_create_with_defaults(self):
        """Test creating TaskStatus with default values."""
        task = TaskStatus(task_id="phase11.1")
        assert task.task_id == "phase11.1"
        assert task.status == DryRunStatus.UNTESTED
        assert task.last_dry_run_at is None
        assert task.last_errors == []
        assert task.marked_ready_at is None
        assert task.history == []

    def test_create_with_all_fields(self):
        """Test creating TaskStatus with all fields specified."""
        task = TaskStatus(
            task_id="phase11.2",
            status=DryRunStatus.DRY_RUN_PASS,
            last_dry_run_at="2026-03-03T10:00:00",
            last_errors=[],
            marked_ready_at=None,
            history=[{"event": "dry_run_pass"}],
        )
        assert task.task_id == "phase11.2"
        assert task.status == DryRunStatus.DRY_RUN_PASS
        assert task.last_dry_run_at == "2026-03-03T10:00:00"
        assert task.history == [{"event": "dry_run_pass"}]

    def test_to_dict(self):
        """Test converting TaskStatus to dictionary."""
        task = TaskStatus(
            task_id="phase11.3",
            status=DryRunStatus.READY,
            last_dry_run_at="2026-03-03T10:00:00",
            marked_ready_at="2026-03-03T10:01:00",
        )
        result = task.to_dict()
        assert result["task_id"] == "phase11.3"
        assert result["status"] == "ready"
        assert result["last_dry_run_at"] == "2026-03-03T10:00:00"
        assert result["marked_ready_at"] == "2026-03-03T10:01:00"
        assert result["last_errors"] == []
        assert result["history"] == []

    def test_from_dict(self):
        """Test creating TaskStatus from dictionary."""
        data = {
            "task_id": "phase11.4",
            "status": "dry_run_fail",
            "last_dry_run_at": "2026-03-03T09:00:00",
            "last_errors": ["Test failed: assertion error"],
            "marked_ready_at": None,
            "history": [],
        }
        task = TaskStatus.from_dict(data)
        assert task.task_id == "phase11.4"
        assert task.status == DryRunStatus.DRY_RUN_FAIL
        assert task.last_dry_run_at == "2026-03-03T09:00:00"
        assert task.last_errors == ["Test failed: assertion error"]

    def test_from_dict_with_missing_fields(self):
        """Test creating TaskStatus from dictionary with missing optional fields."""
        data = {"task_id": "phase11.5"}
        task = TaskStatus.from_dict(data)
        assert task.task_id == "phase11.5"
        assert task.status == DryRunStatus.UNTESTED
        assert task.last_dry_run_at is None
        assert task.last_errors == []

    def test_roundtrip_serialization(self):
        """Test that to_dict and from_dict are inverses."""
        original = TaskStatus(
            task_id="roundtrip_test",
            status=DryRunStatus.DRY_RUN_PASS,
            last_dry_run_at="2026-03-03T12:00:00",
            last_errors=[],
            marked_ready_at=None,
            history=[{"event": "test", "timestamp": "2026-03-03T12:00:00"}],
        )
        data = original.to_dict()
        restored = TaskStatus.from_dict(data)
        assert restored.task_id == original.task_id
        assert restored.status == original.status
        assert restored.last_dry_run_at == original.last_dry_run_at
        assert restored.history == original.history


class TestPRDTaskStatusTracker:
    """Tests for the PRDTaskStatusTracker class."""

    @pytest.fixture
    def temp_status_file(self):
        """Create a temporary file for status tracking."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            yield Path(f.name)
        # Cleanup
        Path(f.name).unlink(missing_ok=True)

    @pytest.fixture
    def tracker(self, temp_status_file):
        """Create a tracker with a temporary status file."""
        return PRDTaskStatusTracker(status_file=temp_status_file)

    def test_create_tracker_default_path(self):
        """Test creating tracker with default path."""
        tracker = PRDTaskStatusTracker()
        assert tracker.status_file == Path(".organizer/agent/prd_task_status.json")

    def test_create_tracker_custom_path(self, temp_status_file):
        """Test creating tracker with custom path."""
        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        assert tracker.status_file == temp_status_file

    def test_get_status_unknown_task(self, tracker):
        """Test getting status for unknown task returns UNTESTED."""
        status = tracker.get_status("unknown_task")
        assert status == DryRunStatus.UNTESTED

    def test_get_task_unknown_returns_none(self, tracker):
        """Test getting task record for unknown task returns None."""
        task = tracker.get_task("unknown_task")
        assert task is None

    def test_mark_dry_run_pass(self, tracker):
        """Test marking a task as passing dry-run."""
        task = tracker.mark_dry_run_pass("task_1")
        assert task.status == DryRunStatus.DRY_RUN_PASS
        assert task.last_dry_run_at is not None
        assert task.last_errors == []
        assert len(task.history) == 1
        assert task.history[0]["event"] == "dry_run_pass"

    def test_mark_dry_run_pass_clears_previous_errors(self, tracker):
        """Test that passing dry-run clears previous errors."""
        # First fail
        tracker.mark_dry_run_fail("task_2", errors=["Error 1", "Error 2"])
        # Then pass
        task = tracker.mark_dry_run_pass("task_2")
        assert task.last_errors == []

    def test_mark_dry_run_fail(self, tracker):
        """Test marking a task as failing dry-run."""
        errors = ["Test failed", "Lint error"]
        task = tracker.mark_dry_run_fail("task_3", errors=errors)
        assert task.status == DryRunStatus.DRY_RUN_FAIL
        assert task.last_dry_run_at is not None
        assert task.last_errors == errors
        assert len(task.history) == 1
        assert task.history[0]["event"] == "dry_run_fail"
        assert task.history[0]["errors"] == errors

    def test_mark_dry_run_fail_no_errors(self, tracker):
        """Test marking a task as failing without error list."""
        task = tracker.mark_dry_run_fail("task_4")
        assert task.status == DryRunStatus.DRY_RUN_FAIL
        assert task.last_errors == []

    def test_mark_ready_after_pass(self, tracker):
        """Test marking a task as ready after it passed dry-run."""
        tracker.mark_dry_run_pass("task_5")
        task = tracker.mark_ready("task_5")
        assert task.status == DryRunStatus.READY
        assert task.marked_ready_at is not None
        assert len(task.history) == 2

    def test_mark_ready_without_pass_raises(self, tracker):
        """Test that marking ready without dry_run_pass raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            tracker.mark_ready("nonexistent_task")

    def test_mark_ready_from_untested_raises(self, tracker):
        """Test that marking ready from untested status raises ValueError."""
        tracker.mark_dry_run_fail("task_6")  # Create task with fail status
        with pytest.raises(ValueError, match="dry_run_fail"):
            tracker.mark_ready("task_6")

    def test_auto_transition_to_ready(self, tracker):
        """Test automatic transition from dry_run_pass to ready."""
        tracker.mark_dry_run_pass("task_7")
        task = tracker.auto_transition_to_ready("task_7")
        assert task is not None
        assert task.status == DryRunStatus.READY

    def test_auto_transition_returns_none_for_wrong_status(self, tracker):
        """Test auto_transition returns None for non-passing tasks."""
        tracker.mark_dry_run_fail("task_8")
        result = tracker.auto_transition_to_ready("task_8")
        assert result is None

    def test_auto_transition_returns_none_for_unknown(self, tracker):
        """Test auto_transition returns None for unknown tasks."""
        result = tracker.auto_transition_to_ready("unknown")
        assert result is None

    def test_list_by_status(self, tracker):
        """Test listing tasks by status."""
        tracker.mark_dry_run_pass("pass_1")
        tracker.mark_dry_run_pass("pass_2")
        tracker.mark_dry_run_fail("fail_1")
        tracker.mark_ready("pass_1")

        passing = tracker.list_by_status(DryRunStatus.DRY_RUN_PASS)
        assert len(passing) == 1
        assert passing[0].task_id == "pass_2"

        failing = tracker.list_by_status(DryRunStatus.DRY_RUN_FAIL)
        assert len(failing) == 1
        assert failing[0].task_id == "fail_1"

        ready = tracker.list_by_status(DryRunStatus.READY)
        assert len(ready) == 1
        assert ready[0].task_id == "pass_1"

    def test_list_ready_tasks(self, tracker):
        """Test listing ready tasks."""
        tracker.mark_dry_run_pass("ready_1")
        tracker.mark_dry_run_pass("ready_2")
        tracker.mark_ready("ready_1")
        tracker.mark_ready("ready_2")
        tracker.mark_dry_run_fail("not_ready")

        ready = tracker.list_ready_tasks()
        task_ids = {t.task_id for t in ready}
        assert task_ids == {"ready_1", "ready_2"}

    def test_list_all(self, tracker):
        """Test listing all tracked tasks."""
        tracker.mark_dry_run_pass("all_1")
        tracker.mark_dry_run_fail("all_2")

        all_tasks = tracker.list_all()
        task_ids = {t.task_id for t in all_tasks}
        assert task_ids == {"all_1", "all_2"}

    def test_reset_task(self, tracker):
        """Test resetting a task to untested."""
        tracker.mark_dry_run_pass("reset_task")
        tracker.mark_ready("reset_task")

        task = tracker.reset_task("reset_task")
        assert task.status == DryRunStatus.UNTESTED
        assert len(task.history) == 3  # pass, ready, reset

    def test_reset_unknown_task(self, tracker):
        """Test resetting an unknown task creates it as untested."""
        task = tracker.reset_task("new_task")
        assert task.status == DryRunStatus.UNTESTED
        assert task.task_id == "new_task"

    def test_clear(self, tracker):
        """Test clearing all task statuses."""
        tracker.mark_dry_run_pass("clear_1")
        tracker.mark_dry_run_fail("clear_2")

        tracker.clear()

        assert tracker.list_all() == []
        assert tracker.get_status("clear_1") == DryRunStatus.UNTESTED

    def test_persistence_across_instances(self, temp_status_file):
        """Test that status persists across tracker instances."""
        # Create and populate first tracker
        tracker1 = PRDTaskStatusTracker(status_file=temp_status_file)
        tracker1.mark_dry_run_pass("persist_task")

        # Create new tracker with same file
        tracker2 = PRDTaskStatusTracker(status_file=temp_status_file)
        task = tracker2.get_task("persist_task")

        assert task is not None
        assert task.status == DryRunStatus.DRY_RUN_PASS

    def test_creates_parent_directories(self, tmp_path):
        """Test that tracker creates parent directories if needed."""
        status_file = tmp_path / "nested" / "dir" / "status.json"
        tracker = PRDTaskStatusTracker(status_file=status_file)
        tracker.mark_dry_run_pass("dir_test")

        assert status_file.exists()

    def test_handles_corrupted_file(self, temp_status_file):
        """Test that tracker handles corrupted JSON gracefully."""
        temp_status_file.write_text("not valid json {{{")

        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        # Should start fresh with no tasks
        assert tracker.list_all() == []

    def test_handles_empty_file(self, temp_status_file):
        """Test that tracker handles empty file gracefully."""
        temp_status_file.write_text("")

        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        assert tracker.list_all() == []

    def test_history_accumulates(self, tracker):
        """Test that history accumulates across state transitions."""
        tracker.mark_dry_run_fail("history_task", errors=["First error"])
        tracker.mark_dry_run_fail("history_task", errors=["Second error"])
        tracker.mark_dry_run_pass("history_task")
        tracker.mark_ready("history_task")

        task = tracker.get_task("history_task")
        assert len(task.history) == 4
        assert task.history[0]["event"] == "dry_run_fail"
        assert task.history[1]["event"] == "dry_run_fail"
        assert task.history[2]["event"] == "dry_run_pass"
        assert task.history[3]["event"] == "marked_ready"

    def test_status_file_format(self, temp_status_file, tracker):
        """Test that saved file has correct format."""
        tracker.mark_dry_run_pass("format_task")

        data = json.loads(temp_status_file.read_text())
        assert "updated_at" in data
        assert "tasks" in data
        assert "format_task" in data["tasks"]
        assert data["tasks"]["format_task"]["status"] == "dry_run_pass"
