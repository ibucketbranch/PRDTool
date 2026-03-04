"""Tests for the dry_run_validator module."""

import tempfile
from pathlib import Path

import pytest

from organizer.dry_run_validator import (
    DryRunResult,
    _check_failure_patterns,
    _check_success_patterns,
    _extract_errors,
    get_ready_tasks,
    get_task_status,
    mark_ready,
    validate_dry_run,
)
from organizer.prd_task_status import DryRunStatus, PRDTaskStatusTracker


class TestDryRunResult:
    """Tests for the DryRunResult dataclass."""

    def test_create_passing_result(self):
        """Test creating a passing DryRunResult."""
        result = DryRunResult(task_id="task_1", passed=True)
        assert result.task_id == "task_1"
        assert result.passed is True
        assert result.errors == []
        assert result.timestamp is not None

    def test_create_failing_result_with_errors(self):
        """Test creating a failing DryRunResult with errors."""
        errors = ["Test failed", "Lint error"]
        result = DryRunResult(task_id="task_2", passed=False, errors=errors)
        assert result.task_id == "task_2"
        assert result.passed is False
        assert result.errors == errors

    def test_to_dict(self):
        """Test converting DryRunResult to dictionary."""
        result = DryRunResult(
            task_id="task_3",
            passed=True,
            errors=[],
            timestamp="2026-03-03T10:00:00",
        )
        data = result.to_dict()
        assert data["task_id"] == "task_3"
        assert data["passed"] is True
        assert data["errors"] == []
        assert data["timestamp"] == "2026-03-03T10:00:00"

    def test_from_dict(self):
        """Test creating DryRunResult from dictionary."""
        data = {
            "task_id": "task_4",
            "passed": False,
            "errors": ["Error message"],
            "timestamp": "2026-03-03T11:00:00",
        }
        result = DryRunResult.from_dict(data)
        assert result.task_id == "task_4"
        assert result.passed is False
        assert result.errors == ["Error message"]
        assert result.timestamp == "2026-03-03T11:00:00"

    def test_from_dict_with_missing_optional_fields(self):
        """Test creating DryRunResult with missing optional fields."""
        data = {"task_id": "task_5", "passed": True}
        result = DryRunResult.from_dict(data)
        assert result.task_id == "task_5"
        assert result.passed is True
        assert result.errors == []

    def test_roundtrip_serialization(self):
        """Test that to_dict and from_dict are inverses."""
        original = DryRunResult(
            task_id="roundtrip",
            passed=False,
            errors=["Error 1", "Error 2"],
            timestamp="2026-03-03T12:00:00",
        )
        data = original.to_dict()
        restored = DryRunResult.from_dict(data)
        assert restored.task_id == original.task_id
        assert restored.passed == original.passed
        assert restored.errors == original.errors
        assert restored.timestamp == original.timestamp


class TestFailurePatterns:
    """Tests for failure pattern detection."""

    def test_detect_pytest_failed(self):
        """Test detecting pytest FAILED output."""
        output = "FAILED tests/test_example.py::test_something"
        assert _check_failure_patterns(output) is True

    def test_detect_pytest_error(self):
        """Test detecting pytest ERROR output."""
        output = "ERROR tests/test_example.py::test_something"
        assert _check_failure_patterns(output) is True

    def test_detect_failed_count(self):
        """Test detecting '1 failed' in pytest output."""
        output = "========== 3 passed, 1 failed in 2.34s =========="
        assert _check_failure_patterns(output) is True

    def test_detect_error_count(self):
        """Test detecting '2 error' in pytest output."""
        output = "========== 2 error in 0.05s =========="
        assert _check_failure_patterns(output) is True

    def test_detect_assertion_error(self):
        """Test detecting AssertionError."""
        output = "AssertionError: 1 != 2"
        assert _check_failure_patterns(output) is True

    def test_detect_ruff_error(self):
        """Test detecting ruff lint error."""
        output = "example.py:10:1: ruff error E501 line too long"
        assert _check_failure_patterns(output) is True

    def test_detect_mypy_error(self):
        """Test detecting mypy type error."""
        output = "mypy found 3 errors"
        assert _check_failure_patterns(output) is True

    def test_detect_build_failed(self):
        """Test detecting build failure."""
        output = "Build failed with errors"
        assert _check_failure_patterns(output) is True

    def test_detect_lint_failed(self):
        """Test detecting lint failure."""
        output = "Linting failed"
        assert _check_failure_patterns(output) is True

    def test_detect_exit_code_nonzero(self):
        """Test detecting non-zero exit code."""
        output = "Process exited with code 1"
        assert _check_failure_patterns(output) is True

    def test_detect_returned_nonzero(self):
        """Test detecting returned non-zero."""
        output = "Command returned non-zero exit status"
        assert _check_failure_patterns(output) is True

    def test_detect_syntax_error(self):
        """Test detecting syntax error."""
        output = "SyntaxError: invalid syntax"
        assert _check_failure_patterns(output) is True

    def test_detect_collection_error(self):
        """Test detecting pytest collection error."""
        output = "Collection error: ImportError"
        assert _check_failure_patterns(output) is True

    def test_no_failure_patterns_in_success(self):
        """Test that success output doesn't match failure patterns."""
        output = "========== 10 passed in 1.23s =========="
        assert _check_failure_patterns(output) is False


class TestSuccessPatterns:
    """Tests for success pattern detection."""

    def test_detect_pytest_passed(self):
        """Test detecting pytest passed output."""
        output = "========== 10 passed in 1.23s =========="
        assert _check_success_patterns(output) is True

    def test_detect_passed_zero_failed(self):
        """Test detecting passed with 0 failed."""
        output = "5 passed, 0 failed"
        assert _check_success_patterns(output) is True

    def test_detect_all_tests_passed(self):
        """Test detecting 'all tests passed'."""
        output = "All tests passed successfully"
        assert _check_success_patterns(output) is True

    def test_detect_tests_passed(self):
        """Test detecting 'tests passed'."""
        output = "Tests passed"
        assert _check_success_patterns(output) is True

    def test_detect_ok_tests(self):
        """Test detecting 'OK (N tests)'."""
        output = "OK (42 tests)"
        assert _check_success_patterns(output) is True

    def test_detect_build_succeeded(self):
        """Test detecting build success."""
        output = "Build succeeded"
        assert _check_success_patterns(output) is True

    def test_detect_lint_passed(self):
        """Test detecting lint passed."""
        output = "Linting passed"
        assert _check_success_patterns(output) is True

    def test_detect_no_issues_found(self):
        """Test detecting 'no issues found'."""
        output = "Ruff: No issues found"
        assert _check_success_patterns(output) is True

    def test_detect_exit_code_zero(self):
        """Test detecting exit code 0."""
        output = "Process exited with code 0"
        assert _check_success_patterns(output) is True

    def test_no_success_patterns_in_failure(self):
        """Test that failure output doesn't match success patterns."""
        output = "FAILED tests/test_example.py::test_something"
        assert _check_success_patterns(output) is False


class TestErrorExtraction:
    """Tests for error message extraction."""

    def test_extract_pytest_failed_line(self):
        """Test extracting FAILED test name."""
        output = "FAILED tests/test_example.py::test_something - AssertionError"
        errors = _extract_errors(output)
        assert len(errors) == 1
        assert "FAILED tests/test_example.py::test_something" in errors[0]

    def test_extract_assertion_error(self):
        """Test extracting AssertionError details."""
        output = "E       AssertionError: expected 1 but got 2"
        errors = _extract_errors(output)
        assert len(errors) >= 1
        assert any("AssertionError" in e for e in errors)

    def test_extract_lint_error(self):
        """Test extracting lint error."""
        output = "example.py:10:5: E501 line too long (100 > 88 characters)"
        errors = _extract_errors(output)
        assert len(errors) == 1
        assert "example.py:10:5" in errors[0]

    def test_extract_mypy_error(self):
        """Test extracting mypy error."""
        output = 'example.py:15: error: Argument 1 has incompatible type "str"'
        errors = _extract_errors(output)
        assert len(errors) >= 1
        assert any("example.py:15" in e for e in errors)

    def test_extract_multiple_errors(self):
        """Test extracting multiple different errors."""
        output = """
FAILED tests/test_a.py::test_one
FAILED tests/test_b.py::test_two
example.py:10:5: E501 line too long
"""
        errors = _extract_errors(output)
        assert len(errors) == 3

    def test_deduplicate_errors(self):
        """Test that duplicate errors are removed."""
        output = """
FAILED tests/test_a.py::test_one
FAILED tests/test_a.py::test_one
FAILED tests/test_a.py::test_one
"""
        errors = _extract_errors(output)
        assert len(errors) == 1

    def test_truncate_long_errors(self):
        """Test that very long errors are truncated."""
        long_message = "Error: " + "x" * 300
        output = f"Error: {long_message}"
        errors = _extract_errors(output)
        # Should be truncated
        for error in errors:
            assert len(error) <= 200

    def test_limit_error_count(self):
        """Test that error count is limited to 20."""
        # Generate 30 unique errors
        lines = [f"FAILED tests/test_{i}.py::test_func" for i in range(30)]
        output = "\n".join(lines)
        errors = _extract_errors(output)
        assert len(errors) <= 20

    def test_extract_no_errors_from_success(self):
        """Test no errors extracted from success output."""
        output = "========== 10 passed in 1.23s =========="
        errors = _extract_errors(output)
        assert errors == []


class TestValidateDryRun:
    """Tests for the validate_dry_run function."""

    @pytest.fixture
    def temp_status_file(self):
        """Create a temporary file for status tracking."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_validate_passing_tests(self, temp_status_file):
        """Test validating passing test output."""
        output = "========== 10 passed in 1.23s =========="
        result = validate_dry_run(
            "task_pass", output, status_file=temp_status_file
        )
        assert result.passed is True
        assert result.errors == []
        assert result.task_id == "task_pass"

    def test_validate_failing_tests(self, temp_status_file):
        """Test validating failing test output."""
        output = """
FAILED tests/test_example.py::test_something
========== 1 failed in 0.50s ==========
"""
        result = validate_dry_run(
            "task_fail", output, status_file=temp_status_file
        )
        assert result.passed is False
        assert len(result.errors) > 0
        assert result.task_id == "task_fail"

    def test_validate_updates_tracker_on_pass(self, temp_status_file):
        """Test that validate_dry_run updates tracker on pass."""
        output = "All tests passed"
        validate_dry_run(
            "task_tracker_pass", output, status_file=temp_status_file
        )

        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        # With auto_mark_ready=True (default), should be READY
        status = tracker.get_status("task_tracker_pass")
        assert status == DryRunStatus.READY

    def test_validate_updates_tracker_on_fail(self, temp_status_file):
        """Test that validate_dry_run updates tracker on fail."""
        output = "FAILED tests/test_example.py::test_something"
        validate_dry_run(
            "task_tracker_fail", output, status_file=temp_status_file
        )

        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        status = tracker.get_status("task_tracker_fail")
        assert status == DryRunStatus.DRY_RUN_FAIL

    def test_validate_auto_mark_ready_disabled(self, temp_status_file):
        """Test validate_dry_run with auto_mark_ready=False."""
        output = "All tests passed"
        validate_dry_run(
            "task_no_auto",
            output,
            status_file=temp_status_file,
            auto_mark_ready=False,
        )

        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        status = tracker.get_status("task_no_auto")
        # Should stay at DRY_RUN_PASS, not transition to READY
        assert status == DryRunStatus.DRY_RUN_PASS

    def test_validate_empty_output_fails(self, temp_status_file):
        """Test that empty output is treated as failure."""
        result = validate_dry_run("task_empty", "", status_file=temp_status_file)
        assert result.passed is False
        assert "No test output received" in result.errors[0]

    def test_validate_ambiguous_output_fails(self, temp_status_file):
        """Test that ambiguous output (no clear signals) fails."""
        output = "Some random output with no test indicators"
        result = validate_dry_run(
            "task_ambiguous", output, status_file=temp_status_file
        )
        assert result.passed is False

    def test_failure_takes_precedence_over_success(self, temp_status_file):
        """Test that failure patterns take precedence over success patterns."""
        output = """
========== 9 passed, 1 failed in 2.00s ==========
Tests passed
"""
        result = validate_dry_run(
            "task_mixed", output, status_file=temp_status_file
        )
        # Should fail because "1 failed" is present
        assert result.passed is False

    def test_validate_records_errors_in_tracker(self, temp_status_file):
        """Test that errors are recorded in tracker on failure."""
        output = "FAILED tests/test_example.py::test_one"
        validate_dry_run("task_errors", output, status_file=temp_status_file)

        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        task = tracker.get_task("task_errors")
        assert task is not None
        assert len(task.last_errors) > 0


class TestMarkReady:
    """Tests for the mark_ready function."""

    @pytest.fixture
    def temp_status_file(self):
        """Create a temporary file for status tracking."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_mark_ready_after_pass(self, temp_status_file):
        """Test marking ready after dry-run pass."""
        # First, pass dry-run without auto-ready
        output = "All tests passed"
        validate_dry_run(
            "task_ready",
            output,
            status_file=temp_status_file,
            auto_mark_ready=False,
        )

        # Now manually mark ready
        result = mark_ready("task_ready", status_file=temp_status_file)
        assert result is True

        tracker = PRDTaskStatusTracker(status_file=temp_status_file)
        assert tracker.get_status("task_ready") == DryRunStatus.READY

    def test_mark_ready_already_ready(self, temp_status_file):
        """Test marking ready when already ready."""
        output = "All tests passed"
        validate_dry_run(
            "task_already_ready",
            output,
            status_file=temp_status_file,
        )

        # Should return True even if already ready
        result = mark_ready("task_already_ready", status_file=temp_status_file)
        assert result is True

    def test_mark_ready_from_failed(self, temp_status_file):
        """Test that mark_ready fails from failed state."""
        output = "FAILED tests/test_example.py::test_one"
        validate_dry_run(
            "task_failed", output, status_file=temp_status_file
        )

        result = mark_ready("task_failed", status_file=temp_status_file)
        assert result is False

    def test_mark_ready_unknown_task(self, temp_status_file):
        """Test mark_ready for unknown task."""
        result = mark_ready("unknown_task", status_file=temp_status_file)
        assert result is False


class TestGetReadyTasks:
    """Tests for the get_ready_tasks function."""

    @pytest.fixture
    def temp_status_file(self):
        """Create a temporary file for status tracking."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_get_ready_tasks_empty(self, temp_status_file):
        """Test getting ready tasks when none exist."""
        tasks = get_ready_tasks(status_file=temp_status_file)
        assert tasks == []

    def test_get_ready_tasks_multiple(self, temp_status_file):
        """Test getting multiple ready tasks."""
        output = "All tests passed"
        validate_dry_run("ready_1", output, status_file=temp_status_file)
        validate_dry_run("ready_2", output, status_file=temp_status_file)

        tasks = get_ready_tasks(status_file=temp_status_file)
        task_ids = {t["task_id"] for t in tasks}
        assert task_ids == {"ready_1", "ready_2"}

    def test_get_ready_tasks_excludes_failed(self, temp_status_file):
        """Test that get_ready_tasks excludes failed tasks."""
        validate_dry_run(
            "ready_one", "All tests passed", status_file=temp_status_file
        )
        validate_dry_run(
            "failed_one", "FAILED test", status_file=temp_status_file
        )

        tasks = get_ready_tasks(status_file=temp_status_file)
        task_ids = {t["task_id"] for t in tasks}
        assert "ready_one" in task_ids
        assert "failed_one" not in task_ids


class TestGetTaskStatus:
    """Tests for the get_task_status function."""

    @pytest.fixture
    def temp_status_file(self):
        """Create a temporary file for status tracking."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_get_task_status_untested(self, temp_status_file):
        """Test getting status for untested task."""
        status = get_task_status("unknown_task", status_file=temp_status_file)
        assert status == "untested"

    def test_get_task_status_passed(self, temp_status_file):
        """Test getting status for passed task."""
        validate_dry_run(
            "passed_task",
            "All tests passed",
            status_file=temp_status_file,
            auto_mark_ready=False,
        )
        status = get_task_status("passed_task", status_file=temp_status_file)
        assert status == "dry_run_pass"

    def test_get_task_status_failed(self, temp_status_file):
        """Test getting status for failed task."""
        validate_dry_run(
            "failed_task", "FAILED test", status_file=temp_status_file
        )
        status = get_task_status("failed_task", status_file=temp_status_file)
        assert status == "dry_run_fail"

    def test_get_task_status_ready(self, temp_status_file):
        """Test getting status for ready task."""
        validate_dry_run(
            "ready_task", "All tests passed", status_file=temp_status_file
        )
        status = get_task_status("ready_task", status_file=temp_status_file)
        assert status == "ready"


class TestStatusTransitions:
    """Tests for status transition flows."""

    @pytest.fixture
    def temp_status_file(self):
        """Create a temporary file for status tracking."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)

    def test_happy_path_transition(self, temp_status_file):
        """Test happy path: untested -> dry_run_pass -> ready."""
        # Start untested
        status = get_task_status("happy_task", status_file=temp_status_file)
        assert status == "untested"

        # Pass dry-run (with auto_mark_ready)
        validate_dry_run(
            "happy_task", "All tests passed", status_file=temp_status_file
        )
        status = get_task_status("happy_task", status_file=temp_status_file)
        assert status == "ready"

    def test_fail_then_pass_transition(self, temp_status_file):
        """Test transition: untested -> fail -> pass -> ready."""
        # Fail first
        validate_dry_run(
            "retry_task", "FAILED test", status_file=temp_status_file
        )
        status = get_task_status("retry_task", status_file=temp_status_file)
        assert status == "dry_run_fail"

        # Then pass
        validate_dry_run(
            "retry_task", "All tests passed", status_file=temp_status_file
        )
        status = get_task_status("retry_task", status_file=temp_status_file)
        assert status == "ready"

    def test_manual_ready_transition(self, temp_status_file):
        """Test manual transition to ready."""
        # Pass without auto_mark_ready
        validate_dry_run(
            "manual_task",
            "All tests passed",
            status_file=temp_status_file,
            auto_mark_ready=False,
        )
        status = get_task_status("manual_task", status_file=temp_status_file)
        assert status == "dry_run_pass"

        # Manually mark ready
        mark_ready("manual_task", status_file=temp_status_file)
        status = get_task_status("manual_task", status_file=temp_status_file)
        assert status == "ready"
