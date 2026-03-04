"""Tests for the progress reporter module."""

import io
from datetime import datetime

from organizer.progress_reporter import (
    ProgressReporter,
    ProgressState,
    create_progress_reporter,
    format_progress_bar,
)


class TestProgressState:
    """Tests for ProgressState dataclass."""

    def test_default_values(self):
        """Test that ProgressState has correct default values."""
        state = ProgressState()
        assert state.total_groups == 0
        assert state.completed_groups == 0
        assert state.current_group == ""
        assert state.current_group_folders == 0
        assert state.current_group_files == 0
        assert state.total_files_moved == 0
        assert state.total_files_failed == 0
        assert state.errors == []
        assert isinstance(state.start_time, datetime)

    def test_custom_values(self):
        """Test ProgressState with custom values."""
        state = ProgressState(
            total_groups=5,
            completed_groups=2,
            current_group="Resume-related",
            current_group_folders=3,
            current_group_files=10,
            total_files_moved=25,
            total_files_failed=1,
            errors=["Error 1"],
        )
        assert state.total_groups == 5
        assert state.completed_groups == 2
        assert state.current_group == "Resume-related"
        assert state.current_group_folders == 3
        assert state.current_group_files == 10
        assert state.total_files_moved == 25
        assert state.total_files_failed == 1
        assert state.errors == ["Error 1"]


class TestProgressReporter:
    """Tests for ProgressReporter class."""

    def test_initialization(self):
        """Test ProgressReporter initialization."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=5, output=output)

        assert reporter.state.total_groups == 5
        assert reporter.bar_width == 30
        assert reporter.show_bar is True

    def test_initialization_with_custom_options(self):
        """Test ProgressReporter with custom options."""
        output = io.StringIO()
        reporter = ProgressReporter(
            total_groups=10,
            output=output,
            bar_width=50,
            show_bar=False,
        )

        assert reporter.state.total_groups == 10
        assert reporter.bar_width == 50
        assert reporter.show_bar is False

    def test_start(self):
        """Test start() prints header."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.start()

        output_str = output.getvalue()
        assert "EXECUTING CONSOLIDATION" in output_str
        assert "=" * 28 in output_str

    def test_start_group(self):
        """Test start_group() reports group info."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.start_group(0, "Resume-related", 5)

        output_str = output.getvalue()
        assert "[1/3]" in output_str
        assert "Group 1" in output_str
        assert "Resume-related" in output_str
        assert "5 folders" in output_str

    def test_start_group_updates_state(self):
        """Test that start_group updates state."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.start_group(0, "Resume-related", 5)

        assert reporter.state.current_group == "Resume-related"
        assert reporter.state.current_group_folders == 5
        assert reporter.state.current_group_files == 0

    def test_report_folder_move_success(self):
        """Test report_folder_move for successful move."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.report_folder_move(
            source_folder="/path/to/Resume",
            target_folder="/path/to/Employment/Resumes",
            file_count=10,
            success=True,
        )

        output_str = output.getvalue()
        assert "[OK]" in output_str
        assert "Resume/" in output_str
        assert "Resumes/" in output_str
        assert "10 files" in output_str

    def test_report_folder_move_failure(self):
        """Test report_folder_move for failed move."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.report_folder_move(
            source_folder="/path/to/Resume",
            target_folder="/path/to/Employment/Resumes",
            file_count=10,
            success=False,
        )

        output_str = output.getvalue()
        assert "[FAILED]" in output_str
        assert reporter.state.total_files_failed == 10
        assert len(reporter.state.errors) == 1

    def test_report_folder_move_updates_counts(self):
        """Test that report_folder_move updates file counts."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.report_folder_move("/a", "/b", 5, success=True)
        reporter.report_folder_move("/c", "/d", 3, success=True)

        assert reporter.state.total_files_moved == 8
        assert reporter.state.current_group_files == 8

    def test_complete_group_success(self):
        """Test complete_group for successful group."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output, show_bar=False)

        reporter.complete_group(0, files_moved=10, files_failed=0, success=True)

        output_str = output.getvalue()
        assert "[OK]" in output_str
        assert "Group 1 complete" in output_str
        assert "10/10 files moved" in output_str

    def test_complete_group_failure(self):
        """Test complete_group for failed group."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output, show_bar=False)

        reporter.complete_group(0, files_moved=8, files_failed=2, success=False)

        output_str = output.getvalue()
        assert "[FAILED]" in output_str
        assert "8 files moved" in output_str
        assert "2 files failed" in output_str

    def test_complete_group_updates_state(self):
        """Test that complete_group updates state."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output, show_bar=False)

        reporter.complete_group(0, files_moved=10, files_failed=0, success=True)

        assert reporter.state.completed_groups == 1

    def test_complete_group_shows_progress_bar(self):
        """Test that complete_group shows progress bar when enabled."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output, show_bar=True)

        reporter.complete_group(0, files_moved=10, files_failed=0, success=True)

        output_str = output.getvalue()
        assert "Progress:" in output_str
        assert "1/3 groups" in output_str

    def test_report_error(self):
        """Test report_error adds to errors list."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.report_error("Test error message")

        output_str = output.getvalue()
        assert "[ERROR]" in output_str
        assert "Test error message" in output_str
        assert "Test error message" in reporter.state.errors

    def test_report_status(self):
        """Test report_status outputs message."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)

        reporter.report_status("Processing...")

        output_str = output.getvalue()
        assert "Processing..." in output_str

    def test_finish_success(self):
        """Test finish() for successful completion."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)
        reporter.state.completed_groups = 3
        reporter.state.total_files_moved = 50
        reporter.state.total_files_failed = 0

        reporter.finish(success=True)

        output_str = output.getvalue()
        assert "[OK] EXECUTION COMPLETE" in output_str
        assert "Groups processed: 3/3" in output_str
        assert "Files moved: 50" in output_str
        assert "Files failed: 0" in output_str
        assert "Time elapsed:" in output_str

    def test_finish_failure(self):
        """Test finish() for failed completion."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=3, output=output)
        reporter.state.completed_groups = 1
        reporter.state.total_files_moved = 10
        reporter.state.total_files_failed = 5
        reporter.state.errors = ["Error 1", "Error 2"]

        reporter.finish(success=False)

        output_str = output.getvalue()
        assert "[FAILED] EXECUTION COMPLETE" in output_str
        assert "Files failed: 5" in output_str
        assert "Errors (2):" in output_str
        assert "Error 1" in output_str
        assert "Error 2" in output_str

    def test_format_duration_seconds(self):
        """Test _format_duration for seconds."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=1, output=output)

        assert reporter._format_duration(5.5) == "5.5s"
        assert reporter._format_duration(59.9) == "59.9s"

    def test_format_duration_minutes(self):
        """Test _format_duration for minutes."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=1, output=output)

        assert reporter._format_duration(60) == "1m 0s"
        assert reporter._format_duration(90) == "1m 30s"
        assert reporter._format_duration(3599) == "59m 59s"

    def test_format_duration_hours(self):
        """Test _format_duration for hours."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=1, output=output)

        assert reporter._format_duration(3600) == "1h 0m 0s"
        assert reporter._format_duration(7265) == "2h 1m 5s"

    def test_get_progress_callback(self):
        """Test get_progress_callback returns callable."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=1, output=output)

        callback = reporter.get_progress_callback()

        assert callable(callback)
        # Should not raise
        callback("test", 1, 10)


class TestCreateProgressReporter:
    """Tests for create_progress_reporter factory function."""

    def test_creates_reporter(self):
        """Test factory creates reporter with correct settings."""
        output = io.StringIO()
        reporter = create_progress_reporter(
            total_groups=5,
            output=output,
            show_bar=True,
        )

        assert isinstance(reporter, ProgressReporter)
        assert reporter.state.total_groups == 5
        assert reporter.show_bar is True

    def test_default_output_is_stdout(self):
        """Test default output is stdout."""
        import sys

        reporter = create_progress_reporter(total_groups=1)
        assert reporter.output == sys.stdout


class TestFormatProgressBar:
    """Tests for format_progress_bar function."""

    def test_empty_progress(self):
        """Test progress bar at 0%."""
        result = format_progress_bar(0, 10, width=10)
        assert result == "[----------] 0/10 (0%)"

    def test_full_progress(self):
        """Test progress bar at 100%."""
        result = format_progress_bar(10, 10, width=10)
        assert result == "[==========] 10/10 (100%)"

    def test_partial_progress(self):
        """Test progress bar at 50%."""
        result = format_progress_bar(5, 10, width=10)
        assert result == "[=====-----] 5/10 (50%)"

    def test_partial_progress_rounded(self):
        """Test progress bar with non-round percentage."""
        result = format_progress_bar(1, 3, width=9)
        assert "[===" in result
        assert "1/3" in result
        assert "33%" in result

    def test_zero_total(self):
        """Test progress bar with zero total."""
        result = format_progress_bar(0, 0, width=10)
        assert result == "[----------] 0/0 (0%)"

    def test_custom_characters(self):
        """Test progress bar with custom characters."""
        result = format_progress_bar(5, 10, width=10, fill_char="#", empty_char=".")
        assert result == "[#####.....] 5/10 (50%)"

    def test_custom_width(self):
        """Test progress bar with custom width."""
        result = format_progress_bar(1, 2, width=20)
        assert "[" in result
        assert "]" in result
        # 10 filled, 10 empty
        assert result.count("=") == 10
        assert result.count("-") == 10


class TestProgressReporterIntegration:
    """Integration tests for progress reporting."""

    def test_full_execution_flow(self):
        """Test complete execution flow with progress reporting."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=2, output=output, show_bar=True)

        # Start execution
        reporter.start()

        # Group 1
        reporter.start_group(0, "Resume-related", 3)
        reporter.report_folder_move("/a/Resume", "/b/Resumes", 5, success=True)
        reporter.report_folder_move("/a/Resume_Docs", "/b/Resumes", 3, success=True)
        reporter.report_folder_move("/a/Resumes_Old", "/b/Resumes", 2, success=True)
        reporter.complete_group(0, files_moved=10, files_failed=0, success=True)

        # Group 2
        reporter.start_group(1, "Tax-related", 2)
        reporter.report_folder_move("/a/Taxes", "/b/Finances/Taxes", 8, success=True)
        reporter.report_folder_move("/a/Tax_2023", "/b/Finances/Taxes", 4, success=True)
        reporter.complete_group(1, files_moved=12, files_failed=0, success=True)

        # Finish
        reporter.finish(success=True)

        output_str = output.getvalue()

        # Check all expected output
        assert "EXECUTING CONSOLIDATION" in output_str
        assert "[1/2]" in output_str
        assert "Resume-related" in output_str
        assert "[2/2]" in output_str
        assert "Tax-related" in output_str
        assert "Progress:" in output_str
        assert "[OK] EXECUTION COMPLETE" in output_str
        assert "Files moved: 22" in output_str

    def test_execution_with_failure(self):
        """Test execution flow with a failure."""
        output = io.StringIO()
        reporter = ProgressReporter(total_groups=2, output=output, show_bar=True)

        reporter.start()

        # Group 1 fails
        reporter.start_group(0, "Resume-related", 2)
        reporter.report_folder_move("/a/Resume", "/b/Resumes", 5, success=True)
        reporter.report_folder_move("/a/Resume_Docs", "/b/Resumes", 3, success=False)
        reporter.complete_group(0, files_moved=5, files_failed=3, success=False)
        reporter.report_error("Stopped due to error")

        reporter.finish(success=False)

        output_str = output.getvalue()

        assert "[FAILED]" in output_str
        assert "[ERROR]" in output_str
        assert "Files failed: 3" in output_str
