"""Post-execution verification for folder consolidation operations.

This module provides verification functions to ensure all files are accessible
at their new locations after consolidation, check that no files were lost,
and generate execution summary reports.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from organizer.file_operations import (
    ExecutionResult,
    FileMoveResult,
    MoveStatus,
)


@dataclass
class FileVerificationResult:
    """Result of verifying a single file's accessibility."""

    file_path: str
    exists: bool
    accessible: bool
    error: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "exists": self.exists,
            "accessible": self.accessible,
            "error": self.error,
        }


@dataclass
class VerificationResult:
    """Result of verifying all files after consolidation."""

    status: str  # "verified", "failed", "partial"
    total_files_expected: int = 0
    total_files_verified: int = 0
    files_at_target: int = 0
    files_missing: int = 0
    files_inaccessible: int = 0
    verification_details: list[FileVerificationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "total_files_expected": self.total_files_expected,
            "total_files_verified": self.total_files_verified,
            "files_at_target": self.files_at_target,
            "files_missing": self.files_missing,
            "files_inaccessible": self.files_inaccessible,
            "verification_details": [d.to_dict() for d in self.verification_details],
            "errors": self.errors,
        }

    @property
    def success(self) -> bool:
        """Return True if all files were verified successfully."""
        return self.status == "verified"


@dataclass
class ExecutionSummaryReport:
    """Complete summary report for a consolidation execution."""

    timestamp: str
    execution_status: str
    total_groups: int
    groups_completed: int
    groups_failed: int
    total_files_moved: int
    total_files_failed: int
    verification_result: VerificationResult | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "timestamp": self.timestamp,
            "execution_status": self.execution_status,
            "total_groups": self.total_groups,
            "groups_completed": self.groups_completed,
            "groups_failed": self.groups_failed,
            "total_files_moved": self.total_files_moved,
            "total_files_failed": self.total_files_failed,
            "errors": self.errors,
        }
        if self.verification_result:
            result["verification"] = self.verification_result.to_dict()
        return result

    @property
    def overall_success(self) -> bool:
        """Return True if execution and verification both succeeded."""
        execution_ok = self.execution_status == "success"
        verification_ok = (
            self.verification_result is None or self.verification_result.success
        )
        return execution_ok and verification_ok


def verify_file_accessible(file_path: str) -> FileVerificationResult:
    """Verify that a single file exists and is accessible.

    Args:
        file_path: Path to the file to verify.

    Returns:
        FileVerificationResult with accessibility status.
    """
    path = Path(file_path)

    try:
        if not path.exists():
            return FileVerificationResult(
                file_path=file_path,
                exists=False,
                accessible=False,
                error="File does not exist",
            )

        # Try to read file metadata to verify accessibility
        _ = path.stat()

        return FileVerificationResult(
            file_path=file_path,
            exists=True,
            accessible=True,
        )

    except PermissionError as e:
        return FileVerificationResult(
            file_path=file_path,
            exists=True,
            accessible=False,
            error=f"Permission denied: {e}",
        )
    except OSError as e:
        return FileVerificationResult(
            file_path=file_path,
            exists=False,
            accessible=False,
            error=f"OS error: {e}",
        )


def verify_files_at_new_locations(
    execution_result: ExecutionResult,
) -> VerificationResult:
    """Verify all successfully moved files are accessible at their new locations.

    Args:
        execution_result: The result from executing a consolidation plan.

    Returns:
        VerificationResult with details of verification status.
    """
    result = VerificationResult(status="verified")

    # Collect all successful file moves
    successful_moves: list[FileMoveResult] = []
    for group_result in execution_result.group_results:
        for folder_result in group_result.folder_results:
            for file_result in folder_result.file_results:
                if file_result.status == MoveStatus.SUCCESS:
                    successful_moves.append(file_result)

    result.total_files_expected = len(successful_moves)

    # Verify each file at its target location
    for file_move in successful_moves:
        verification = verify_file_accessible(file_move.target_path)
        result.verification_details.append(verification)

        if verification.exists and verification.accessible:
            result.files_at_target += 1
            result.total_files_verified += 1
        elif verification.exists and not verification.accessible:
            result.files_inaccessible += 1
            result.errors.append(
                f"File inaccessible at {file_move.target_path}: {verification.error}"
            )
        else:
            result.files_missing += 1
            result.errors.append(
                f"File missing at {file_move.target_path}: {verification.error}"
            )

    # Determine overall status
    if result.files_missing > 0 or result.files_inaccessible > 0:
        if result.total_files_verified > 0:
            result.status = "partial"
        else:
            result.status = "failed"
    else:
        result.status = "verified"

    return result


def check_no_files_lost(
    execution_result: ExecutionResult,
) -> tuple[bool, list[str]]:
    """Check that no files were lost during consolidation.

    A file is considered lost if it was supposed to be moved but:
    - It doesn't exist at the target location
    - AND it doesn't exist at the source location

    Args:
        execution_result: The result from executing a consolidation plan.

    Returns:
        Tuple of (all_files_accounted_for, list_of_lost_files).
    """
    lost_files: list[str] = []

    for group_result in execution_result.group_results:
        for folder_result in group_result.folder_results:
            for file_result in folder_result.file_results:
                if file_result.status == MoveStatus.SUCCESS:
                    # Check if file exists at target
                    target_exists = Path(file_result.target_path).exists()
                    if not target_exists:
                        # File might have been moved but with different name
                        # Check if source still exists (move failed silently)
                        source_exists = Path(file_result.source_path).exists()
                        if not source_exists:
                            # File is truly lost - not at source or target
                            lost_files.append(file_result.target_path)

    return len(lost_files) == 0, lost_files


def generate_execution_summary(
    execution_result: ExecutionResult,
    total_groups: int,
    include_verification: bool = True,
) -> ExecutionSummaryReport:
    """Generate a complete execution summary report.

    Args:
        execution_result: The result from executing a consolidation plan.
        total_groups: Total number of groups in the original plan.
        include_verification: Whether to include verification results.

    Returns:
        ExecutionSummaryReport with complete execution details.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine execution status
    if execution_result.status == MoveStatus.SUCCESS:
        execution_status = "success"
    else:
        execution_status = "failed"

    report = ExecutionSummaryReport(
        timestamp=timestamp,
        execution_status=execution_status,
        total_groups=total_groups,
        groups_completed=execution_result.groups_completed,
        groups_failed=execution_result.groups_failed,
        total_files_moved=execution_result.total_files_moved,
        total_files_failed=execution_result.total_files_failed,
    )

    # Add execution error if any
    if execution_result.error:
        report.errors.append(execution_result.error)

    # Include verification if requested
    if include_verification:
        verification = verify_files_at_new_locations(execution_result)
        report.verification_result = verification

        # Check for lost files
        no_files_lost, lost_files = check_no_files_lost(execution_result)
        if not no_files_lost:
            for lost_file in lost_files:
                report.errors.append(f"File lost during consolidation: {lost_file}")

    return report


def save_summary_report(
    report: ExecutionSummaryReport,
    output_path: str | Path | None = None,
    base_path: str | Path | None = None,
) -> Path:
    """Save an execution summary report to a JSON file.

    Args:
        report: The summary report to save.
        output_path: Path to save the report. If None, uses default location.
        base_path: Base path for default location (used if output_path is None).

    Returns:
        Path to the saved report file.
    """
    if output_path is None:
        if base_path is None:
            base_path = Path.cwd()
        else:
            base_path = Path(base_path)

        report_dir = base_path / ".organizer"
        report_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = report_dir / f"summary_report_{timestamp}.json"
    else:
        output_path = Path(output_path)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)

    return output_path


def load_summary_report(report_path: str | Path) -> ExecutionSummaryReport:
    """Load an execution summary report from a JSON file.

    Args:
        report_path: Path to the report file.

    Returns:
        ExecutionSummaryReport loaded from the file.

    Raises:
        FileNotFoundError: If the report file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with open(report_path) as f:
        data = json.load(f)

    # Reconstruct VerificationResult if present
    verification = None
    if "verification" in data:
        v_data = data["verification"]
        verification_details = [
            FileVerificationResult(**d) for d in v_data.get("verification_details", [])
        ]
        verification = VerificationResult(
            status=v_data["status"],
            total_files_expected=v_data["total_files_expected"],
            total_files_verified=v_data["total_files_verified"],
            files_at_target=v_data["files_at_target"],
            files_missing=v_data["files_missing"],
            files_inaccessible=v_data["files_inaccessible"],
            verification_details=verification_details,
            errors=v_data.get("errors", []),
        )

    return ExecutionSummaryReport(
        timestamp=data["timestamp"],
        execution_status=data["execution_status"],
        total_groups=data["total_groups"],
        groups_completed=data["groups_completed"],
        groups_failed=data["groups_failed"],
        total_files_moved=data["total_files_moved"],
        total_files_failed=data["total_files_failed"],
        verification_result=verification,
        errors=data.get("errors", []),
    )


def format_verification_summary(verification: VerificationResult) -> str:
    """Format verification results as a human-readable string.

    Args:
        verification: The verification result to format.

    Returns:
        Formatted string summary.
    """
    lines = [
        "VERIFICATION COMPLETE",
        "=" * 28,
        f"  - All {verification.total_files_expected} files verified at new locations"
        if verification.success
        else f"  - {verification.total_files_verified}/{verification.total_files_expected} files verified",
    ]

    if verification.files_missing > 0:
        lines.append(f"  - {verification.files_missing} files MISSING")

    if verification.files_inaccessible > 0:
        lines.append(f"  - {verification.files_inaccessible} files INACCESSIBLE")

    return "\n".join(lines)


def format_summary_report(report: ExecutionSummaryReport) -> str:
    """Format an execution summary report as a human-readable string.

    Args:
        report: The summary report to format.

    Returns:
        Formatted string summary.
    """
    lines = [
        "",
        "FINAL SUMMARY",
        "=" * 28,
        f"  [{'OK' if report.execution_status == 'success' else 'FAILED'}] "
        f"{report.groups_completed} folder groups consolidated",
        f"  [{'OK' if report.total_files_failed == 0 else 'FAILED'}] "
        f"{report.total_files_moved} files moved successfully",
        f"  [{'OK' if report.total_files_failed == 0 else 'FAILED'}] "
        f"{report.total_files_failed} errors",
    ]

    if report.verification_result:
        v = report.verification_result
        lines.append(
            f"  [{'OK' if v.success else 'FAILED'}] {v.files_missing} files lost"
        )

    if report.errors:
        lines.append("")
        lines.append(f"Errors ({len(report.errors)}):")
        for error in report.errors[:10]:  # Limit to first 10 errors
            lines.append(f"  - {error}")
        if len(report.errors) > 10:
            lines.append(f"  ... and {len(report.errors) - 10} more errors")

    return "\n".join(lines)
