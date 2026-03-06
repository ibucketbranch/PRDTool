"""Command-line interface for folder consolidation.

This module provides CLI commands for scanning, analyzing, and planning
folder consolidation operations.

Usage:
    python -m organizer --scan               # Analyze folder structure
    python -m organizer --plan               # Generate consolidation plan
    python -m organizer --execute --plan plan.json  # Execute consolidation plan
    python -m organizer --threshold 0.85     # Set similarity threshold
    python -m organizer --output plan.json   # Save plan to file
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

from organizer.consolidation_planner import (
    ConsolidationPlan,
    ConsolidationPlanner,
    load_plan_from_file,
    save_plan_to_file,
)
from organizer.file_operations import (
    ExecutionResult,
    MoveStatus,
)
from organizer.execution_logger import create_execution_log
from organizer.progress_reporter import ProgressReporter, create_progress_reporter
from organizer.post_verification import (
    verify_files_at_new_locations,
    check_no_files_lost,
    generate_execution_summary,
    save_summary_report,
    format_verification_summary,
    format_summary_report,
)
from organizer.continuous_agent import (
    ContinuousAgentConfig,
    ContinuousOrganizerAgent,
)
from organizer.launchd_agent import (
    DEFAULT_LAUNCHD_LABEL,
    install_launchd_service,
    launchd_status,
    uninstall_launchd_service,
)
from organizer.structure_analyzer import (
    DEFAULT_STRUCTURE_OUTPUT_PATH,
    StructureSnapshot,
    analyze_structure,
)
from organizer.rule_generator import (
    DEFAULT_RULES_OUTPUT_PATH,
    LearnedRulesSnapshot,
    generate_rules,
)
from organizer.domain_detector import (
    detect_domain,
)
from organizer.learned_rules import (
    DEFAULT_RULES_PATH,
)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="organizer",
        description="Folder consolidation tool with fuzzy matching",
        epilog="Example: python -m organizer --scan --threshold 0.85",
    )

    parser.add_argument(
        "--scan",
        action="store_true",
        help="Analyze current folder structure and show similar folder groups",
    )

    parser.add_argument(
        "--plan",
        action="store_true",
        help="Generate consolidation plan without executing",
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        metavar="THRESHOLD",
        help="Similarity threshold for folder matching (0.0 to 1.0, default: 0.8)",
    )

    parser.add_argument(
        "--output",
        type=str,
        metavar="FILE",
        help="Save plan to JSON file (only used with --plan)",
    )

    parser.add_argument(
        "--path",
        type=str,
        default=".",
        metavar="PATH",
        help="Base path to scan (default: current directory)",
    )

    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        metavar="DEPTH",
        help="Maximum directory depth to scan (default: 3)",
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute consolidation plan (requires --plan-file)",
    )

    parser.add_argument(
        "--plan-file",
        type=str,
        metavar="FILE",
        help="Path to existing plan file for execution (used with --execute)",
    )

    parser.add_argument(
        "--content-aware",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable content-aware consolidation using database analysis (default: True). "
        "Use --no-content-aware to disable.",
    )

    parser.add_argument(
        "--db-path",
        type=str,
        metavar="PATH",
        help="Path to SQLite database for content analysis (used with --content-aware)",
    )

    parser.add_argument(
        "--analyze-missing",
        action="store_true",
        default=False,
        help="Analyze folders/files not in database during content-aware scanning. "
        "Requires --content-aware and --db-path. Files without existing analysis "
        "will be processed using the DocumentProcessor.",
    )

    parser.add_argument(
        "--min-content-similarity",
        type=float,
        default=0.6,
        metavar="THRESHOLD",
        help="Minimum content similarity threshold for consolidation (0.0 to 1.0, "
        "default: 0.6). Only used with --content-aware. Lower values allow more "
        "consolidations, higher values require stronger content matches.",
    )

    parser.add_argument(
        "--agent-init-config",
        action="store_true",
        help="Create a default continuous-agent config file and exit",
    )

    parser.add_argument(
        "--agent-run",
        action="store_true",
        help="Run continuous organizer agent loop",
    )

    parser.add_argument(
        "--agent-once",
        action="store_true",
        help="Run one continuous organizer agent cycle and exit",
    )

    parser.add_argument(
        "--agent-config",
        type=str,
        default=".organizer/agent_config.json",
        metavar="FILE",
        help="Path to continuous-agent config JSON "
        "(default: .organizer/agent_config.json)",
    )

    parser.add_argument(
        "--agent-max-cycles",
        type=int,
        metavar="COUNT",
        help="Optional cycle limit when using --agent-run",
    )

    parser.add_argument(
        "--agent-launchd-install",
        action="store_true",
        help="Install + start launchd background service for continuous agent",
    )

    parser.add_argument(
        "--agent-launchd-uninstall",
        action="store_true",
        help="Stop + remove launchd background service",
    )

    parser.add_argument(
        "--agent-launchd-status",
        action="store_true",
        help="Show launchd background service status",
    )

    parser.add_argument(
        "--agent-launchd-label",
        type=str,
        default=DEFAULT_LAUNCHD_LABEL,
        metavar="LABEL",
        help="launchd label for the service "
        f"(default: {DEFAULT_LAUNCHD_LABEL})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run agent in dry-run mode: proposes actions but does not execute. "
        "Validates proposals against filesystem and taxonomy, reports would-move "
        "count, confidence distribution, and conflicts.",
    )

    parser.add_argument(
        "--mcp-server",
        action="store_true",
        help="Start MCP server on stdio for Claude Desktop / Cursor integration",
    )
    parser.add_argument(
        "--dry-run-task-id",
        type=str,
        metavar="TASK_ID",
        help="PRD task ID to track for dry-run validation. When dry-run passes, "
        "the task is marked as 'ready'. Only used with --dry-run.",
    )

    # Learning-Agent onboarding commands
    parser.add_argument(
        "--learn-structure",
        nargs="?",
        const=".",
        metavar="PATH",
        help="Analyze folder structure and generate routing rules. "
        "Outputs summary with folder count, rule count, detected domain. "
        "Optional path (default: current directory or base_path from agent config).",
    )

    parser.add_argument(
        "--learn-confirm",
        action="store_true",
        help="Activate learned rules after user reviews them. "
        "Learned rules will take priority over built-in taxonomy.",
    )

    parser.add_argument(
        "--learn-status",
        action="store_true",
        help="Show current learned rules status: active/inactive, "
        "rule count, last scan date.",
    )

    return parser


def validate_args(args: argparse.Namespace) -> list[str]:
    """Validate command-line arguments.

    Args:
        args: Parsed arguments from argparse.

    Returns:
        List of error messages (empty if valid).
    """
    errors: list[str] = []

    # Check threshold range
    if not 0.0 <= args.threshold <= 1.0:
        errors.append(f"Threshold must be between 0.0 and 1.0, got {args.threshold}")

    # Check max_depth
    if args.max_depth < 1:
        errors.append(f"Max depth must be at least 1, got {args.max_depth}")

    # Check path exists
    if not Path(args.path).exists():
        errors.append(f"Path does not exist: {args.path}")
    elif not Path(args.path).is_dir():
        errors.append(f"Path is not a directory: {args.path}")

    # Check output file can be written
    if args.output:
        output_path = Path(args.output)
        parent = output_path.parent
        if parent != Path() and not parent.exists():
            errors.append(f"Output directory does not exist: {parent}")

    # Check that at least one action is specified
    has_standard_action = args.scan or args.plan or args.execute
    has_agent_action = (
        args.agent_init_config
        or args.agent_run
        or args.agent_once
        or args.agent_launchd_install
        or args.agent_launchd_uninstall
        or args.agent_launchd_status
    )
    has_mcp_action = args.mcp_server
    has_learn_action = (
        args.learn_structure is not None
        or args.learn_confirm
        or args.learn_status
    )
    if (
        not has_standard_action
        and not has_agent_action
        and not has_mcp_action
        and not has_learn_action
    ):
        errors.append(
            "Must specify at least one action: --scan, --plan, --execute, "
            "--agent-init-config, --agent-run, --agent-once, "
            "--agent-launchd-install, --agent-launchd-uninstall, "
            "--agent-launchd-status, --mcp-server, --learn-structure, "
            "--learn-confirm, or --learn-status"
        )

    # Check execute-specific requirements
    if args.execute:
        if not args.plan_file:
            errors.append(
                "--execute requires --plan-file with path to an existing plan file"
            )
        else:
            plan_path = Path(args.plan_file)
            if not plan_path.exists():
                errors.append(f"Plan file does not exist: {args.plan_file}")
            elif not plan_path.is_file():
                errors.append(f"Plan file is not a file: {args.plan_file}")

    # Check --plan-file is not used without --execute
    if args.plan_file and not args.execute:
        errors.append("--plan-file can only be used with --execute")

    if args.agent_max_cycles is not None and args.agent_max_cycles < 1:
        errors.append("--agent-max-cycles must be at least 1")

    if args.agent_max_cycles is not None and not args.agent_run:
        errors.append("--agent-max-cycles can only be used with --agent-run")

    if args.agent_run and args.agent_once:
        errors.append("Use either --agent-run or --agent-once, not both")

    launchd_actions = [
        args.agent_launchd_install,
        args.agent_launchd_uninstall,
        args.agent_launchd_status,
    ]
    if sum(1 for enabled in launchd_actions if enabled) > 1:
        errors.append(
            "Use only one launchd action at a time: "
            "--agent-launchd-install, --agent-launchd-uninstall, "
            "or --agent-launchd-status"
        )

    if args.agent_max_cycles is not None and args.agent_launchd_install:
        errors.append("--agent-max-cycles is not used with --agent-launchd-install")

    if args.agent_init_config and (
        args.scan
        or args.plan
        or args.execute
        or args.agent_run
        or args.agent_once
        or args.agent_launchd_install
        or args.agent_launchd_uninstall
        or args.agent_launchd_status
    ):
        errors.append("--agent-init-config must be used by itself")

    # Validate --dry-run usage
    if args.dry_run:
        if not (args.agent_once or args.agent_run):
            errors.append(
                "--dry-run can only be used with --agent-once or --agent-run"
            )

    # Validate --dry-run-task-id usage
    if args.dry_run_task_id and not args.dry_run:
        errors.append("--dry-run-task-id requires --dry-run")

    # Check --db-path is not used without --content-aware
    if args.db_path and not args.content_aware:
        errors.append(
            "--db-path can only be used with --content-aware (not --no-content-aware)"
        )

    # Validate db_path exists if specified
    if args.db_path:
        db_path = Path(args.db_path)
        if not db_path.exists():
            errors.append(f"Database file does not exist: {args.db_path}")
        elif not db_path.is_file():
            errors.append(f"Database path is not a file: {args.db_path}")

    # Check --analyze-missing requirements
    if args.analyze_missing:
        if not args.content_aware:
            errors.append(
                "--analyze-missing requires --content-aware (not --no-content-aware)"
            )
        if not args.db_path:
            errors.append(
                "--analyze-missing requires --db-path to store analysis results"
            )

    # Check --min-content-similarity range
    if not 0.0 <= args.min_content_similarity <= 1.0:
        errors.append(
            f"--min-content-similarity must be between 0.0 and 1.0, "
            f"got {args.min_content_similarity}"
        )

    # Check --min-content-similarity is not used without --content-aware
    if args.min_content_similarity != 0.6 and not args.content_aware:
        errors.append(
            "--min-content-similarity can only be used with --content-aware "
            "(not --no-content-aware)"
        )

    # Validate --learn-structure path if specified
    if args.learn_structure is not None:
        learn_path = Path(args.learn_structure).resolve()
        if not learn_path.exists():
            errors.append(f"Learn structure path does not exist: {args.learn_structure}")
        elif not learn_path.is_dir():
            errors.append(
                f"Learn structure path is not a directory: {args.learn_structure}"
            )

    # Check that learn commands are not mixed with other commands
    learn_actions = [
        args.learn_structure is not None,
        args.learn_confirm,
        args.learn_status,
    ]
    learn_action_count = sum(1 for action in learn_actions if action)
    if learn_action_count > 1:
        errors.append(
            "Use only one learn action at a time: "
            "--learn-structure, --learn-confirm, or --learn-status"
        )

    return errors


def run_scan(args: argparse.Namespace) -> int:
    """Run the scan command to analyze folder structure.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    base_path = str(Path(args.path).resolve())
    planner = ConsolidationPlanner(
        base_path=base_path,
        threshold=args.threshold,
        content_aware=args.content_aware,
        db_path=args.db_path,
        analyze_missing=args.analyze_missing,
        content_similarity_threshold=args.min_content_similarity,
    )

    plan = planner.create_plan(max_depth=args.max_depth)
    summary = planner.generate_summary(plan)

    print(summary)

    return 0


def run_plan(args: argparse.Namespace) -> int:
    """Run the plan command to generate consolidation plan.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    base_path = str(Path(args.path).resolve())
    planner = ConsolidationPlanner(
        base_path=base_path,
        threshold=args.threshold,
        content_aware=args.content_aware,
        db_path=args.db_path,
        analyze_missing=args.analyze_missing,
        content_similarity_threshold=args.min_content_similarity,
    )

    plan = planner.create_plan(max_depth=args.max_depth)

    if args.output:
        save_plan_to_file(plan, args.output)
        print(f"Plan saved to: {args.output}")
        print()

    # Always show summary
    summary = planner.generate_summary(plan)
    print(summary)

    # Print plan statistics
    print()
    print(f"Plan created at: {plan.created_at}")
    print(f"Base path: {plan.base_path}")
    print(f"Threshold: {plan.threshold}")
    print(f"Content-aware: {plan.content_aware}")
    if plan.content_aware:
        print(f"Content similarity threshold: {args.min_content_similarity}")
    print(f"Total groups: {plan.total_groups}")
    print(f"Total folders: {plan.total_folders}")
    print(f"Total files: {plan.total_files}")

    return 0


def run_agent(args: argparse.Namespace) -> int:
    """Run continuous organizer agent commands."""
    config_path = Path(args.agent_config).resolve()
    logs_dir = (Path(config_path).parent / "agent" / "logs").resolve()

    if args.agent_init_config:
        if config_path.exists():
            print(f"Config already exists: {config_path}")
            return 0
        default_config = ContinuousAgentConfig(base_path=str(Path(args.path).resolve()))
        default_config.save(config_path)
        print(f"Created default agent config: {config_path}")
        return 0

    if args.agent_launchd_install:
        if not config_path.exists():
            default_config = ContinuousAgentConfig(base_path=str(Path(args.path).resolve()))
            default_config.save(config_path)
            print(f"Created default agent config: {config_path}")
        install_result = install_launchd_service(
            label=args.agent_launchd_label,
            config_path=config_path,
            working_directory=Path.cwd().resolve(),
            logs_dir=logs_dir,
        )
        output_stream = sys.stdout if install_result.success else sys.stderr
        print(install_result.message, file=output_stream)
        return 0 if install_result.success else 1

    if args.agent_launchd_uninstall:
        uninstall_result = uninstall_launchd_service(args.agent_launchd_label)
        output_stream = sys.stdout if uninstall_result.success else sys.stderr
        print(uninstall_result.message, file=output_stream)
        return 0 if uninstall_result.success else 1

    if args.agent_launchd_status:
        status_result = launchd_status(args.agent_launchd_label)
        output_stream = sys.stdout if status_result.success else sys.stderr
        print(status_result.message, file=output_stream)
        return 0 if status_result.success else 1

    if not config_path.exists():
        print(
            f"Error: Agent config not found at {config_path}. "
            "Run with --agent-init-config first.",
            file=sys.stderr,
        )
        return 1

    config = ContinuousAgentConfig.load(config_path)

    # Apply dry-run settings from CLI arguments
    if args.dry_run:
        config.dry_run_mode = True
        config.dry_run_task_id = args.dry_run_task_id or ""

    agent = ContinuousOrganizerAgent(config)

    if args.agent_once:
        summary = agent.run_cycle()

        # Check if dry-run mode
        dry_run_info = summary.get("dry_run", {})
        if dry_run_info.get("dry_run_mode"):
            # Dry-run output
            print("DRY-RUN VALIDATION REPORT")
            print("=" * 40)
            print(f"Cycle ID: {summary['cycle_id']}")
            print(f"Task ID: {dry_run_info.get('task_id', 'N/A')}")
            print()

            # Would-move count
            total_proposals = dry_run_info.get("total_proposals", 0)
            print(f"Would-move count: {total_proposals}")

            # Confidence distribution
            high_conf = dry_run_info.get("high_confidence_count", 0)
            low_conf = dry_run_info.get("low_confidence_count", 0)
            print("Confidence distribution:")
            print(f"  High confidence (>= {config.min_auto_confidence}): {high_conf}")
            print(f"  Low confidence (< {config.min_auto_confidence}): {low_conf}")

            # Conflicts
            conflict_count = dry_run_info.get("conflict_count", 0)
            print(f"Conflicts detected: {conflict_count}")

            # Validation result
            print()
            validation_passed = dry_run_info.get("validation_passed", False)
            if validation_passed:
                print("✅ Dry-run validation PASSED")
                if dry_run_info.get("task_id"):
                    print(f"   Task '{dry_run_info['task_id']}' marked as READY")
            else:
                print("❌ Dry-run validation FAILED")
                errors = dry_run_info.get("errors", [])
                if errors:
                    print(f"   Errors ({len(errors)}):")
                    for error in errors[:10]:  # Show first 10 errors
                        print(f"     - {error}")
                    if len(errors) > 10:
                        print(f"     ... and {len(errors) - 10} more")

            print()
            print(f"Plan: {summary['plan']['path']}")
            print(f"Queue: {summary['queue']['path']}")
            return 0 if validation_passed else 1
        else:
            # Normal output
            print(
                "Agent cycle complete: "
                f"{summary['cycle_id']} "
                f"(proposals={summary['queue']['proposal_count']}, "
                f"executed_groups={summary['execution']['executed_group_count']})"
            )
            print(f"Plan: {summary['plan']['path']}")
            print(f"Queue: {summary['queue']['path']}")
            return 0

    if args.agent_run:
        mode_info = " [DRY-RUN MODE]" if config.dry_run_mode else ""
        print(
            f"Starting continuous organizer agent{mode_info} "
            f"(interval={config.interval_seconds}s, base_path={config.base_path})"
        )
        if config.dry_run_mode:
            print(
                "Dry-run mode: Actions will be proposed and validated but not executed."
            )
            if config.dry_run_task_id:
                print(f"Tracking PRD task: {config.dry_run_task_id}")
        agent.run_forever(max_cycles=args.agent_max_cycles)
        return 0

    return 0


def get_confirmation(prompt: str, input_stream: TextIO = sys.stdin) -> bool:
    """Get explicit 'yes' confirmation from user.

    Args:
        prompt: The prompt message to display.
        input_stream: Input stream to read from (default: sys.stdin).

    Returns:
        True if user types 'yes', False otherwise.
    """
    print(prompt, end=" ", flush=True)
    try:
        response = input_stream.readline().strip().lower()
        return response == "yes"
    except (EOFError, KeyboardInterrupt):
        print()  # Newline after interrupt
        return False


def validate_plan_file(plan_path: str) -> tuple[ConsolidationPlan | None, str | None]:
    """Validate that a plan file exists and is valid JSON.

    Args:
        plan_path: Path to the plan file.

    Returns:
        Tuple of (plan, error_message). Plan is None if invalid.
    """
    try:
        plan = load_plan_from_file(plan_path)
        return plan, None
    except FileNotFoundError:
        return None, f"Plan file not found: {plan_path}"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON in plan file: {e}"
    except Exception as e:
        return None, f"Error loading plan file: {e}"


def display_content_analysis_summary(plan: ConsolidationPlan) -> None:
    """Display a content analysis summary before execution.

    Shows the AI categories, date ranges, and consolidation decisions
    for each folder group in the plan. This helps users understand
    what content will be consolidated before confirming execution.

    Args:
        plan: The consolidation plan to summarize.
    """
    if not plan.content_aware:
        return

    print()
    print("CONTENT ANALYSIS SUMMARY")
    print("=" * 28)
    print()

    if not plan.groups:
        print("No folder groups to analyze.")
        return

    # Show groups that will be consolidated
    groups_to_consolidate = plan.groups_to_consolidate
    groups_to_skip = plan.groups_to_skip

    if groups_to_consolidate:
        print(f"✅ GROUPS TO CONSOLIDATE ({len(groups_to_consolidate)}):")
        for group in groups_to_consolidate:
            _display_group_content_summary(group)
        print()

    if groups_to_skip:
        print(f"❌ GROUPS TO SKIP ({len(groups_to_skip)}):")
        for group in groups_to_skip:
            _display_group_content_summary(group, show_warning=False)
        print()

    # Summary statistics
    total_consolidate = len(groups_to_consolidate)
    total_skip = len(groups_to_skip)
    files_to_move = sum(g.total_files for g in groups_to_consolidate)
    files_skipped = sum(g.total_files for g in groups_to_skip)

    # Count groups with mixed content types (warning)
    groups_with_mixed_content = [
        g for g in groups_to_consolidate if has_mixed_content_types(g)
    ]
    mixed_count = len(groups_with_mixed_content)

    print(f"Summary: {total_consolidate} groups will consolidate, {total_skip} will be skipped")
    print(f"         {files_to_move} files will be moved, {files_skipped} files will stay in place")

    if mixed_count > 0:
        print()
        print(f"⚠️  WARNING: {mixed_count} group(s) contain mixed content types!")
        print("    Review the warnings above before proceeding.")


def has_mixed_content_types(group) -> bool:
    """Check if a folder group has mixed content types.

    A group has mixed content types if it has multiple different AI categories.
    This indicates folders that may have different document types and might
    not be appropriate to consolidate together.

    Args:
        group: The FolderGroup to check.

    Returns:
        True if the group has more than one AI category, False otherwise.
    """
    return len(group.ai_categories) > 1


def display_content_type_warning(group) -> None:
    """Display a warning if a folder group has mixed content types.

    Args:
        group: The FolderGroup to check and warn about.
    """
    if not has_mixed_content_types(group):
        return

    categories = sorted(group.ai_categories)
    print()
    print("    ⚠️  WARNING: Mixed content types detected!")
    print("    This group contains folders with different AI categories:")
    for cat in categories:
        print(f"      • {cat}")
    print("    Consider reviewing these folders before consolidation.")


def get_content_mismatch_groups(plan: ConsolidationPlan) -> list:
    """Get all folder groups that have content mismatches.

    Content mismatches are groups that are marked for consolidation
    but contain folders with different AI categories.

    Args:
        plan: The consolidation plan to check.

    Returns:
        List of FolderGroups with content mismatches.
    """
    if not plan.content_aware:
        return []

    groups_to_consolidate = plan.groups_to_consolidate
    return [g for g in groups_to_consolidate if has_mixed_content_types(g)]


def get_content_mismatch_confirmation(
    mismatch_groups: list,
    input_stream: TextIO = sys.stdin,
) -> bool:
    """Get explicit confirmation to proceed with content-mismatch consolidations.

    This function displays the groups with content mismatches and asks
    the user to explicitly confirm they want to proceed despite the
    different content types.

    Args:
        mismatch_groups: List of FolderGroups with content mismatches.
        input_stream: Input stream to read from (default: sys.stdin).

    Returns:
        True if user confirms with 'yes', False otherwise.
    """
    if not mismatch_groups:
        return True  # No mismatches, no confirmation needed

    print()
    print("=" * 60)
    print("CONTENT MISMATCH CONFIRMATION REQUIRED")
    print("=" * 60)
    print()
    print(f"The following {len(mismatch_groups)} group(s) contain folders with")
    print("DIFFERENT content types that will be consolidated together:")
    print()

    for group in mismatch_groups:
        print(f"  • {group.group_name}")
        categories = sorted(group.ai_categories)
        print(f"    Categories: {', '.join(categories)}")
        print(f"    Folders: {len(group.folders)}, Files: {group.total_files}")
        print()

    print("Consolidating folders with different content types may mix")
    print("unrelated documents together. This action cannot be undone.")
    print()

    return get_confirmation(
        "Do you want to proceed with these content-mismatch consolidations? "
        "Type 'yes' to confirm:",
        input_stream=input_stream,
    )


def _display_group_content_summary(group, show_warning: bool = True) -> None:
    """Display content summary for a single folder group.

    Args:
        group: The FolderGroup to display.
        show_warning: If True, show warning for mixed content types.
    """
    print(f"  • {group.group_name} ({len(group.folders)} folders, {group.total_files} files)")

    # Show AI categories if available
    if group.ai_categories:
        categories = ", ".join(sorted(group.ai_categories))
        print(f"    AI Categories: {categories}")

    # Show date ranges if available
    if group.date_ranges:
        # Collect unique date ranges
        unique_ranges = set(group.date_ranges.values())
        ranges_str = ", ".join(sorted(unique_ranges))
        print(f"    Date Ranges: {ranges_str}")

    # Show decision summary if available (Phase 5 addition)
    if group.decision_summary:
        if group.should_consolidate:
            print(f"    Decision: ✅ {group.decision_summary}")
        else:
            print(f"    Decision: ❌ {group.decision_summary}")

    # Show target folder for groups that will consolidate
    if group.should_consolidate and group.target_folder:
        print(f"    Target: {group.target_folder}/")

    # Show warning for mixed content types (only for groups being consolidated)
    if show_warning and group.should_consolidate:
        display_content_type_warning(group)


def display_execution_summary(plan: ConsolidationPlan) -> None:
    """Display a summary of what will be executed.

    Args:
        plan: The consolidation plan to summarize.
    """
    print()
    print("EXECUTION SAFETY CHECK")
    print("=" * 28)
    print()
    print("WARNING: This will move files and folders on disk.")
    print()
    print("CONSOLIDATION PLAN SUMMARY:")
    print(f"   - {plan.total_groups} folder groups to consolidate")
    print(f"   - {plan.total_files} files total to move")

    # List target folders
    if plan.groups:
        targets = [g.target_folder for g in plan.groups if g.target_folder]
        if targets:
            print(f"   - Targets: {', '.join(targets)}")
    print()


def create_plan_backup(
    plan: ConsolidationPlan, backup_dir: str | Path | None = None
) -> Path:
    """Create a backup of the consolidation plan before execution.

    Args:
        plan: The consolidation plan to backup.
        backup_dir: Directory to store backup. Defaults to .organizer/ in plan's base_path.

    Returns:
        Path to the backup file.
    """
    # Determine backup directory
    if backup_dir is None:
        base = Path(plan.base_path) if plan.base_path else Path.cwd()
        backup_dir = base / ".organizer"
    else:
        backup_dir = Path(backup_dir)

    # Ensure backup directory exists
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamped backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"plan_backup_{timestamp}.json"
    backup_path = backup_dir / backup_filename

    # Save the plan to backup file
    save_plan_to_file(plan, str(backup_path))

    return backup_path


def run_execute(args: argparse.Namespace, input_stream: TextIO = sys.stdin) -> int:
    """Run the execute command to perform consolidation.

    Args:
        args: Parsed command-line arguments.
        input_stream: Input stream for confirmation (default: sys.stdin).

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Validate and load plan file
    plan, error = validate_plan_file(args.plan_file)
    if error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    # Display content analysis summary (Phase 6: pre-execution safety)
    display_content_analysis_summary(plan)

    # Check for content mismatches and require explicit confirmation
    mismatch_groups = get_content_mismatch_groups(plan)
    if mismatch_groups:
        if not get_content_mismatch_confirmation(mismatch_groups, input_stream):
            print()
            print("Aborted. No changes were made.")
            return 1
        print()
        print("Content-mismatch consolidations confirmed.")

    # Display what will happen
    display_execution_summary(plan)

    # Check if there's anything to do
    if plan.total_groups == 0:
        print("No folder groups to consolidate. Nothing to do.")
        return 0

    if plan.total_files == 0:
        print("No files to move. Nothing to do.")
        return 0

    # Require explicit confirmation
    if not get_confirmation(
        "Are you absolutely sure you want to proceed? Type 'yes' to confirm:",
        input_stream=input_stream,
    ):
        print()
        print("Aborted. No changes were made.")
        return 1

    print()
    print("Confirmed. Creating backup of plan...")

    # Create backup of consolidation plan
    backup_path = create_plan_backup(plan)
    print(f"Backup saved to: {backup_path}")
    print()

    # Create progress reporter
    reporter = create_progress_reporter(
        total_groups=plan.total_groups,
        output=sys.stdout,
        show_bar=True,
    )

    # Execute the consolidation plan with progress reporting
    reporter.start()
    result = _execute_with_progress(plan, reporter)

    # Create execution log
    log_path = create_execution_log(
        result=result,
        plan_file=args.plan_file,
        base_path=plan.base_path,
        total_groups=plan.total_groups,
    )
    reporter.report_status(f"Execution log saved to: {log_path}")

    # Run post-execution verification
    print()
    verification = verify_files_at_new_locations(result)
    print(format_verification_summary(verification))

    # Check for lost files
    no_files_lost, lost_files = check_no_files_lost(result)
    if not no_files_lost:
        for lost_file in lost_files:
            reporter.report_error(f"File lost: {lost_file}")

    # Generate and save summary report
    summary_report = generate_execution_summary(
        execution_result=result,
        total_groups=plan.total_groups,
        include_verification=True,
    )
    report_path = save_summary_report(summary_report, base_path=plan.base_path)
    reporter.report_status(f"Summary report saved to: {report_path}")

    # Print final summary
    print(format_summary_report(summary_report))

    # Report completion
    success = result.status == MoveStatus.SUCCESS and verification.success
    reporter.finish(success=success)

    return 0 if success else 1


def _execute_with_progress(
    plan: ConsolidationPlan, reporter: ProgressReporter
) -> ExecutionResult:
    """Execute a consolidation plan with progress reporting.

    Args:
        plan: The consolidation plan to execute.
        reporter: Progress reporter for status updates.

    Returns:
        ExecutionResult with details of the entire execution.
    """
    from organizer.file_operations import (
        execute_folder_group,
        ExecutionResult as ExecResult,
        MoveStatus as MS,
    )

    result = ExecResult(status=MS.SUCCESS)

    for i, group in enumerate(plan.groups):
        # Report starting the group
        reporter.start_group(
            group_index=i,
            group_name=group.group_name,
            folder_count=len(group.folders),
        )

        # Execute the group
        group_result = execute_folder_group(
            group=group,
            base_path=plan.base_path,
        )

        result.group_results.append(group_result)
        result.total_files_moved += group_result.total_files_moved
        result.total_files_failed += group_result.total_files_failed

        # Report each folder move in the group
        for folder_result in group_result.folder_results:
            reporter.report_folder_move(
                source_folder=folder_result.source_folder,
                target_folder=folder_result.target_folder,
                file_count=folder_result.files_moved + folder_result.files_failed,
                success=folder_result.status == MS.SUCCESS,
            )

        # Report group completion
        if group_result.status == MS.SUCCESS:
            result.groups_completed += 1
            reporter.complete_group(
                group_index=i,
                files_moved=group_result.total_files_moved,
                files_failed=group_result.total_files_failed,
                success=True,
            )
        else:
            result.groups_failed += 1
            result.status = MS.FAILED
            reporter.complete_group(
                group_index=i,
                files_moved=group_result.total_files_moved,
                files_failed=group_result.total_files_failed,
                success=False,
            )

            # Stop on error
            result.stopped_early = True
            result.error = (
                f"Stopped after group '{group.group_name}' failed. "
                f"Completed {result.groups_completed}/{len(plan.groups)} groups."
            )
            reporter.report_error(result.error)
            break

    return result


def run_learn_structure(args: argparse.Namespace) -> int:
    """Run the learn-structure command to analyze folder structure.

    Triggers a full scan of the specified path, generates routing rules,
    and outputs a summary with folder count, rule count, and detected domain.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Determine the path to analyze
    scan_path = Path(args.learn_structure).resolve()

    print("LEARNING STRUCTURE ANALYSIS")
    print("=" * 40)
    print(f"Scanning: {scan_path}")
    print(f"Max depth: {args.max_depth}")
    print()

    # Try to initialize LLM client for better analysis (optional)
    llm_client = None
    model_router = None
    try:
        from organizer.llm_client import LLMClient
        from organizer.model_router import ModelRouter

        llm_client = LLMClient()
        if llm_client.is_ollama_available(timeout_s=3):
            model_router = ModelRouter()
            print("LLM available: Using AI-powered analysis")
        else:
            llm_client = None
            print("LLM unavailable: Using keyword-based analysis")
    except Exception:
        print("LLM unavailable: Using keyword-based analysis")
    print()

    # Step 1: Analyze structure
    print("Step 1: Analyzing folder structure...")
    try:
        snapshot = analyze_structure(
            root_path=scan_path,
            max_depth=args.max_depth,
            llm_client=llm_client,
            model_router=model_router,
            use_llm=llm_client is not None,
        )
        snapshot.save()
        print(f"  Folders analyzed: {snapshot.total_folders}")
        print(f"  Files found: {snapshot.total_files}")
        print(f"  Structure saved to: {DEFAULT_STRUCTURE_OUTPUT_PATH}")
    except Exception as e:
        print(f"Error analyzing structure: {e}", file=sys.stderr)
        return 1

    # Step 2: Detect domain
    print()
    print("Step 2: Detecting domain...")
    try:
        domain_context = detect_domain(
            snapshot=snapshot,
            llm_client=llm_client,
            model_router=model_router,
        )
        print(f"  Detected domain: {domain_context.detected_domain}")
        print(f"  Confidence: {domain_context.confidence:.0%}")
        if domain_context.evidence:
            print("  Evidence:")
            for evidence in domain_context.evidence[:5]:
                print(f"    - {evidence}")
    except Exception as e:
        print(f"  Domain detection failed: {e}")
        domain_context = None

    # Step 3: Generate routing rules
    print()
    print("Step 3: Generating routing rules...")
    try:
        rules_snapshot = generate_rules(
            snapshot=snapshot,
            llm_client=llm_client,
            model_router=model_router,
        )
        rules_snapshot.save()
        enabled_rules = [r for r in rules_snapshot.rules if r.enabled]
        print(f"  Rules generated: {len(rules_snapshot.rules)}")
        print(f"  Rules enabled: {len(enabled_rules)}")
        print(f"  Rules saved to: {DEFAULT_RULES_OUTPUT_PATH}")
    except Exception as e:
        print(f"Error generating rules: {e}", file=sys.stderr)
        return 1

    # Step 4: Show summary
    print()
    print("=" * 40)
    print("SUMMARY")
    print("=" * 40)
    print(f"Folders analyzed: {snapshot.total_folders}")
    print(f"Files found: {snapshot.total_files}")
    print(f"Rules generated: {len(rules_snapshot.rules)}")
    if domain_context:
        print(f"Detected domain: {domain_context.detected_domain} "
              f"({domain_context.confidence:.0%} confidence)")

    # Show strategy description if available
    if snapshot.strategy_description:
        print()
        print("Organizational strategy:")
        print(f"  {snapshot.strategy_description}")

    # Show sample rules
    if rules_snapshot.rules:
        print()
        print("Sample rules (first 5):")
        for rule in rules_snapshot.rules[:5]:
            status = "enabled" if rule.enabled else "disabled"
            print(f"  - {rule.pattern} → {rule.destination} ({status})")

    print()
    print("Status: INACTIVE")
    print("Run `python3 -m organizer --learn-confirm` to activate these rules.")

    return 0


def run_learn_confirm(args: argparse.Namespace) -> int:
    """Run the learn-confirm command to activate learned rules.

    Activates learned rules after user reviews them. Learned rules
    will take priority over built-in taxonomy.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    # Check if rules file exists
    rules_path = Path(DEFAULT_RULES_OUTPUT_PATH)
    if not rules_path.exists():
        print("Error: No learned rules found.", file=sys.stderr)
        print("Run `python3 -m organizer --learn-structure [path]` first.",
              file=sys.stderr)
        return 1

    # Load rules
    try:
        rules_snapshot = LearnedRulesSnapshot.load(rules_path)
    except Exception as e:
        print(f"Error loading rules: {e}", file=sys.stderr)
        return 1

    if not rules_snapshot.rules:
        print("Error: No rules to activate.", file=sys.stderr)
        return 1

    # Check if already active (look for the active marker file)
    active_marker = Path(".organizer/agent/learned_rules_active.json")
    if active_marker.exists():
        print("Learned rules are already active.")
        try:
            marker_data = json.loads(active_marker.read_text())
            print(f"Activated: {marker_data.get('activated_at', 'unknown')}")
            print(f"Rules: {marker_data.get('rule_count', 0)}")
        except Exception:
            pass
        return 0

    # Enable all rules and copy to active location
    enabled_count = 0
    for rule in rules_snapshot.rules:
        if rule.enabled:
            enabled_count += 1

    # Create active marker with activation info
    active_marker.parent.mkdir(parents=True, exist_ok=True)
    marker_data = {
        "active": True,
        "activated_at": datetime.now().isoformat(),
        "rule_count": len(rules_snapshot.rules),
        "enabled_count": enabled_count,
        "source_file": str(rules_path),
    }
    active_marker.write_text(json.dumps(marker_data, indent=2))

    # Copy rules to active location (learned_routing_rules.json)
    # The LearnedRuleStore expects rules at DEFAULT_RULES_PATH
    active_rules_path = Path(DEFAULT_RULES_PATH)
    active_rules_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert rules snapshot to LearnedRuleStore format
    store_data = {
        "version": "1.0",
        "rules": [],
        "active": True,
        "activated_at": datetime.now().isoformat(),
    }
    for rule in rules_snapshot.rules:
        store_data["rules"].append({
            "pattern": rule.pattern,
            "destination": rule.destination,
            "confidence": rule.confidence,
            "pattern_type": "keyword",
            "source_folder": rule.source_folder,
            "reasoning": rule.reasoning,
            "enabled": rule.enabled,
            "hit_count": 0,
            "created_at": rule.generated_at if hasattr(rule, 'generated_at') else "",
        })
    active_rules_path.write_text(json.dumps(store_data, indent=2))

    print("LEARNED RULES ACTIVATED")
    print("=" * 40)
    print(f"Total rules: {len(rules_snapshot.rules)}")
    print(f"Enabled rules: {enabled_count}")
    print()
    print("Learned rules will now take priority over built-in taxonomy.")
    print("Run `python3 -m organizer --learn-status` to check status.")

    return 0


def run_learn_status(args: argparse.Namespace) -> int:
    """Run the learn-status command to show learned rules status.

    Shows current learned rules status: active/inactive, rule count,
    and last scan date.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    print("LEARNED RULES STATUS")
    print("=" * 40)

    # Check for active marker
    active_marker = Path(".organizer/agent/learned_rules_active.json")
    if active_marker.exists():
        try:
            marker_data = json.loads(active_marker.read_text())
            print("Status: ACTIVE")
            print(f"Activated: {marker_data.get('activated_at', 'unknown')}")
            print(f"Total rules: {marker_data.get('rule_count', 0)}")
            print(f"Enabled rules: {marker_data.get('enabled_count', 0)}")
        except Exception:
            print("Status: ACTIVE (metadata unavailable)")
    else:
        print("Status: INACTIVE")

    print()

    # Check for structure snapshot
    structure_path = Path(DEFAULT_STRUCTURE_OUTPUT_PATH)
    if structure_path.exists():
        try:
            snapshot = StructureSnapshot.load(structure_path)
            print("Last structure scan:")
            print(f"  Scanned: {snapshot.analyzed_at}")
            print(f"  Root path: {snapshot.root_path}")
            print(f"  Folders: {snapshot.total_folders}")
            print(f"  Files: {snapshot.total_files}")
            if snapshot.model_used:
                print(f"  Model used: {snapshot.model_used}")
        except Exception as e:
            print(f"Structure data unavailable: {e}")
    else:
        print("No structure scan found.")
        print("Run `python3 -m organizer --learn-structure [path]` to scan.")

    print()

    # Check for generated rules
    rules_path = Path(DEFAULT_RULES_OUTPUT_PATH)
    if rules_path.exists():
        try:
            rules_snapshot = LearnedRulesSnapshot.load(rules_path)
            enabled = [r for r in rules_snapshot.rules if r.enabled]
            print("Generated rules:")
            print(f"  Total: {len(rules_snapshot.rules)}")
            print(f"  Enabled: {len(enabled)}")
            print(f"  Generated: {rules_snapshot.generated_at}")
            if rules_snapshot.model_used:
                print(f"  Model: {rules_snapshot.model_used}")
        except Exception as e:
            print(f"Rules data unavailable: {e}")
    else:
        print("No generated rules found.")

    # Check for active rules (what LearnedRuleStore uses)
    active_rules_path = Path(DEFAULT_RULES_PATH)
    if active_rules_path.exists():
        print()
        print("Active rules file:")
        print(f"  Location: {active_rules_path}")
        try:
            data = json.loads(active_rules_path.read_text())
            rule_count = len(data.get("rules", []))
            print(f"  Rules loaded: {rule_count}")
        except Exception:
            print("  Unable to read rules file")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments. If None, uses sys.argv[1:].

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Validate arguments
    errors = validate_args(args)
    if errors:
        for error in errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1

    # Run appropriate command(s)
    exit_code = 0

    if args.mcp_server:
        from organizer.mcp_server import run
        run()
        return 0
    if args.learn_structure is not None:
        exit_code = run_learn_structure(args)
    elif args.learn_confirm:
        exit_code = run_learn_confirm(args)
    elif args.learn_status:
        exit_code = run_learn_status(args)
    elif (
        args.agent_init_config
        or args.agent_run
        or args.agent_once
        or args.agent_launchd_install
        or args.agent_launchd_uninstall
        or args.agent_launchd_status
    ):
        exit_code = run_agent(args)
    elif args.execute:
        # Execute mode - process plan file
        exit_code = run_execute(args)
    elif args.scan and not args.plan:
        # Scan only
        exit_code = run_scan(args)
    elif args.plan:
        # Plan (includes scan output)
        exit_code = run_plan(args)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
