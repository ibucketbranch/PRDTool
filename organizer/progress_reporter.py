"""Progress reporting for folder consolidation execution.

This module provides progress bars and real-time status updates during
consolidation operations, including group and file level progress tracking.
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import TextIO


@dataclass
class ProgressState:
    """State of the current progress reporting."""

    total_groups: int = 0
    completed_groups: int = 0
    current_group: str = ""
    current_group_folders: int = 0
    current_group_files: int = 0
    total_files_moved: int = 0
    total_files_failed: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    errors: list[str] = field(default_factory=list)


class ProgressReporter:
    """Reports progress during consolidation execution.

    Provides real-time status updates including:
    - Progress bar showing X/Y folder groups completed
    - Current operation being performed
    - File counts and status
    """

    def __init__(
        self,
        total_groups: int,
        output: TextIO = sys.stdout,
        bar_width: int = 30,
        show_bar: bool = True,
    ):
        """Initialize the progress reporter.

        Args:
            total_groups: Total number of folder groups to process.
            output: Output stream for progress updates (default: stdout).
            bar_width: Width of the progress bar in characters (default: 30).
            show_bar: Whether to show the progress bar (default: True).
        """
        self.output = output
        self.bar_width = bar_width
        self.show_bar = show_bar
        self.state = ProgressState(total_groups=total_groups)
        self._last_line_length = 0

    def start(self) -> None:
        """Start progress reporting."""
        self.state.start_time = datetime.now()
        self._print_header()

    def _print_header(self) -> None:
        """Print the execution header."""
        self._writeln("EXECUTING CONSOLIDATION")
        self._writeln("=" * 28)
        self._writeln("")

    def start_group(self, group_index: int, group_name: str, folder_count: int) -> None:
        """Report starting a new folder group.

        Args:
            group_index: Index of the group (0-based).
            group_name: Name of the folder group.
            folder_count: Number of folders in the group.
        """
        self.state.current_group = group_name
        self.state.current_group_folders = folder_count
        self.state.current_group_files = 0

        group_num = group_index + 1
        self._writeln(
            f"[{group_num}/{self.state.total_groups}] Group {group_num}: "
            f"{group_name} ({folder_count} folders)"
        )

    def report_folder_move(
        self,
        source_folder: str,
        target_folder: str,
        file_count: int,
        success: bool = True,
    ) -> None:
        """Report moving files from a folder.

        Args:
            source_folder: Name of the source folder being moved.
            target_folder: Name of the target folder.
            file_count: Number of files being moved.
            success: Whether the move was successful.
        """
        status = "OK" if success else "FAILED"
        source_name = source_folder.split("/")[-1] or source_folder
        target_name = target_folder.split("/")[-1] or target_folder

        self._writeln(
            f"  [{status}] Moving {source_name}/ -> {target_name}/ ({file_count} files)"
        )

        if success:
            self.state.current_group_files += file_count
            self.state.total_files_moved += file_count
        else:
            self.state.total_files_failed += file_count
            self.state.errors.append(f"Failed to move {source_folder}")

    def complete_group(
        self,
        group_index: int,
        files_moved: int,
        files_failed: int,
        success: bool = True,
    ) -> None:
        """Report completion of a folder group.

        Args:
            group_index: Index of the completed group (0-based).
            files_moved: Number of files successfully moved.
            files_failed: Number of files that failed to move.
            success: Whether the group completed successfully.
        """
        self.state.completed_groups = group_index + 1
        group_num = group_index + 1

        if success:
            self._writeln(
                f"  [OK] Group {group_num} complete: "
                f"{files_moved}/{files_moved + files_failed} files moved successfully"
            )
        else:
            self._writeln(
                f"  [FAILED] Group {group_num} failed: "
                f"{files_moved} files moved, {files_failed} files failed"
            )

        self._writeln("")

        # Show progress bar after each group
        if self.show_bar:
            self._print_progress_bar()

    def _print_progress_bar(self) -> None:
        """Print the progress bar."""
        completed = self.state.completed_groups
        total = self.state.total_groups
        percentage = (completed / total * 100) if total > 0 else 0

        filled = int(self.bar_width * completed / total) if total > 0 else 0
        bar = "=" * filled + "-" * (self.bar_width - filled)

        self._writeln(
            f"Progress: [{bar}] {completed}/{total} groups ({percentage:.0f}%)"
        )
        self._writeln("")

    def report_error(self, message: str) -> None:
        """Report an error during execution.

        Args:
            message: Error message to report.
        """
        self.state.errors.append(message)
        self._writeln(f"  [ERROR] {message}")

    def report_status(self, message: str) -> None:
        """Report a general status message.

        Args:
            message: Status message to report.
        """
        self._writeln(f"  {message}")

    def finish(self, success: bool = True) -> None:
        """Report completion of the entire consolidation.

        Args:
            success: Whether the overall consolidation succeeded.
        """
        elapsed = datetime.now() - self.state.start_time
        elapsed_str = self._format_duration(elapsed.total_seconds())

        self._writeln("")
        status_icon = "OK" if success else "FAILED"
        self._writeln(f"[{status_icon}] EXECUTION COMPLETE")
        self._writeln("=" * 28)
        self._writeln(
            f"  Groups processed: {self.state.completed_groups}/{self.state.total_groups}"
        )
        self._writeln(f"  Files moved: {self.state.total_files_moved}")
        self._writeln(f"  Files failed: {self.state.total_files_failed}")
        self._writeln(f"  Time elapsed: {elapsed_str}")

        if self.state.errors:
            self._writeln("")
            self._writeln(f"Errors ({len(self.state.errors)}):")
            for error in self.state.errors:
                self._writeln(f"  - {error}")

    def _format_duration(self, seconds: float) -> str:
        """Format a duration in seconds to a human-readable string.

        Args:
            seconds: Duration in seconds.

        Returns:
            Formatted duration string.
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = seconds % 60
        if minutes < 60:
            return f"{minutes}m {secs:.0f}s"
        hours = int(minutes // 60)
        mins = minutes % 60
        return f"{hours}h {mins}m {secs:.0f}s"

    def _writeln(self, message: str) -> None:
        """Write a line to output.

        Args:
            message: Message to write.
        """
        self.output.write(message + "\n")
        self.output.flush()

    def get_progress_callback(self) -> "ProgressCallback":
        """Get a callback function for use with file_operations.

        Returns:
            A callback function compatible with execute_consolidation_plan.
        """
        return self._progress_callback

    def _progress_callback(self, message: str, current: int, total: int) -> None:
        """Internal progress callback for file operations.

        Args:
            message: Progress message.
            current: Current item number.
            total: Total item count.
        """
        # This is called during file operations
        # We don't print every file move, just track them
        pass


# Type alias for progress callbacks
ProgressCallback = type[ProgressReporter._progress_callback]


def create_progress_reporter(
    total_groups: int,
    output: TextIO = sys.stdout,
    show_bar: bool = True,
) -> ProgressReporter:
    """Create a progress reporter for consolidation execution.

    Args:
        total_groups: Total number of folder groups to process.
        output: Output stream for progress updates (default: stdout).
        show_bar: Whether to show the progress bar (default: True).

    Returns:
        Configured ProgressReporter instance.
    """
    return ProgressReporter(
        total_groups=total_groups,
        output=output,
        show_bar=show_bar,
    )


def format_progress_bar(
    completed: int,
    total: int,
    width: int = 30,
    fill_char: str = "=",
    empty_char: str = "-",
) -> str:
    """Format a progress bar string.

    Args:
        completed: Number of completed items.
        total: Total number of items.
        width: Width of the bar in characters.
        fill_char: Character for completed portion.
        empty_char: Character for incomplete portion.

    Returns:
        Formatted progress bar string like "[====------] 4/10 (40%)"
    """
    if total == 0:
        percentage = 0
        filled = 0
    else:
        percentage = completed / total * 100
        filled = int(width * completed / total)

    bar = fill_char * filled + empty_char * (width - filled)
    return f"[{bar}] {completed}/{total} ({percentage:.0f}%)"
