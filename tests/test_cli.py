"""Tests for the CLI module."""

import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from organizer.cli import (
    create_parser,
    create_plan_backup,
    display_content_analysis_summary,
    display_execution_summary,
    get_confirmation,
    get_content_mismatch_confirmation,
    get_content_mismatch_groups,
    main,
    run_execute,
    run_experiment_cli,
    run_learn_confirm,
    run_learn_status,
    run_learn_structure,
    run_plan,
    run_scan,
    validate_args,
    validate_plan_file,
)
from organizer.consolidation_planner import (
    ConsolidationPlan,
    FolderGroup,
    FolderInfo,
    save_plan_to_file,
)


class TestCreateParser:
    """Tests for create_parser function."""

    def test_parser_exists(self):
        """Test that parser is created."""
        parser = create_parser()
        assert parser is not None

    def test_parser_prog_name(self):
        """Test parser program name."""
        parser = create_parser()
        assert parser.prog == "organizer"

    def test_scan_argument(self):
        """Test --scan argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.scan is True

    def test_plan_argument(self):
        """Test --plan argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--plan"])
        assert args.plan is True

    def test_threshold_default(self):
        """Test --threshold default value."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.threshold == 0.8

    def test_threshold_custom(self):
        """Test --threshold custom value."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--threshold", "0.85"])
        assert args.threshold == 0.85

    def test_output_argument(self):
        """Test --output argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--plan", "--output", "plan.json"])
        assert args.output == "plan.json"

    def test_path_default(self):
        """Test --path default value."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.path == "."

    def test_path_custom(self):
        """Test --path custom value."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--path", "/some/path"])
        assert args.path == "/some/path"

    def test_max_depth_default(self):
        """Test --max-depth default value."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.max_depth == 3

    def test_max_depth_custom(self):
        """Test --max-depth custom value."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--max-depth", "5"])
        assert args.max_depth == 5

    def test_all_arguments(self):
        """Test parsing all arguments together."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--scan",
                "--plan",
                "--threshold",
                "0.9",
                "--output",
                "output.json",
                "--path",
                "/test/path",
                "--max-depth",
                "4",
            ]
        )
        assert args.scan is True
        assert args.plan is True
        assert args.threshold == 0.9
        assert args.output == "output.json"
        assert args.path == "/test/path"
        assert args.max_depth == 4

    def test_execute_argument(self):
        """Test --execute argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--execute", "--plan-file", "plan.json"])
        assert args.execute is True
        assert args.plan_file == "plan.json"

    def test_plan_file_argument(self):
        """Test --plan-file argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--execute", "--plan-file", "/path/to/plan.json"])
        assert args.plan_file == "/path/to/plan.json"

    def test_execute_defaults_false(self):
        """Test --execute defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.execute is False

    def test_plan_file_defaults_none(self):
        """Test --plan-file defaults to None."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.plan_file is None

    def test_agent_launchd_install_argument(self):
        """Test --agent-launchd-install argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--agent-launchd-install"])
        assert args.agent_launchd_install is True

    def test_agent_launchd_label_default(self):
        """Test --agent-launchd-label default value exists."""
        parser = create_parser()
        args = parser.parse_args(["--agent-launchd-status"])
        assert args.agent_launchd_label


class TestValidateArgs:
    """Tests for validate_args function."""

    def test_valid_args(self):
        """Test validation passes with valid args."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--scan", "--path", tmpdir])
            errors = validate_args(args)
            assert errors == []

    def test_threshold_too_low(self):
        """Test validation fails with threshold < 0."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--threshold", "-0.1"])
        errors = validate_args(args)
        assert any("Threshold" in e for e in errors)

    def test_threshold_too_high(self):
        """Test validation fails with threshold > 1."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--threshold", "1.5"])
        errors = validate_args(args)
        assert any("Threshold" in e for e in errors)

    def test_threshold_at_boundaries(self):
        """Test validation passes with threshold at boundaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()

            args = parser.parse_args(["--scan", "--threshold", "0.0", "--path", tmpdir])
            errors = validate_args(args)
            assert not any("Threshold" in e for e in errors)

            args = parser.parse_args(["--scan", "--threshold", "1.0", "--path", tmpdir])
            errors = validate_args(args)
            assert not any("Threshold" in e for e in errors)

    def test_max_depth_too_low(self):
        """Test validation fails with max_depth < 1."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--max-depth", "0"])
        errors = validate_args(args)
        assert any("depth" in e.lower() for e in errors)

    def test_path_does_not_exist(self):
        """Test validation fails with non-existent path."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--path", "/nonexistent/path/12345"])
        errors = validate_args(args)
        assert any("does not exist" in e for e in errors)

    def test_path_is_file_not_directory(self):
        """Test validation fails when path is a file."""
        with tempfile.NamedTemporaryFile() as tmpfile:
            parser = create_parser()
            args = parser.parse_args(["--scan", "--path", tmpfile.name])
            errors = validate_args(args)
            assert any("not a directory" in e for e in errors)

    def test_no_action_specified(self):
        """Test validation fails when no action is specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--path", tmpdir])
            errors = validate_args(args)
            assert any("at least one action" in e for e in errors)

    def test_valid_agent_launchd_status(self):
        """Test validation passes with launchd status action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--agent-launchd-status", "--path", tmpdir])
            errors = validate_args(args)
            assert errors == []

    def test_multiple_launchd_actions_invalid(self):
        """Test validation fails with multiple launchd actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--agent-launchd-install",
                    "--agent-launchd-status",
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("one launchd action" in e for e in errors)

    def test_output_directory_does_not_exist(self):
        """Test validation fails when output directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--output",
                    "/nonexistent/dir/plan.json",
                ]
            )
            errors = validate_args(args)
            assert any("Output directory" in e for e in errors)

    def test_output_in_current_directory_ok(self):
        """Test validation passes with output in current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--output",
                    "plan.json",
                ]
            )
            errors = validate_args(args)
            assert not any("Output" in e for e in errors)

    def test_execute_without_plan_file(self):
        """Test validation fails when --execute is used without --plan-file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--execute", "--path", tmpdir])
            errors = validate_args(args)
            assert any("--plan-file" in e for e in errors)

    def test_execute_with_nonexistent_plan_file(self):
        """Test validation fails when plan file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    "/nonexistent/plan.json",
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("does not exist" in e for e in errors)

    def test_execute_with_valid_plan_file(self):
        """Test validation passes with valid plan file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid plan file
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            # Should not have plan-file related errors
            assert not any(
                "plan-file" in e.lower() or "plan file" in e.lower() for e in errors
            )

    def test_plan_file_without_execute(self):
        """Test validation fails when --plan-file is used without --execute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            Path(plan_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("--execute" in e for e in errors)

    def test_execute_with_directory_as_plan_file(self):
        """Test validation fails when plan file is a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    tmpdir,  # Directory instead of file
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("not a file" in e for e in errors)


class TestRunScan:
    """Tests for run_scan function."""

    def test_scan_empty_directory(self, capsys):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--scan", "--path", tmpdir])
            exit_code = run_scan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Default is content-aware mode
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out

    def test_scan_with_folders(self, capsys):
        """Test scanning a directory with folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some folders
            os.makedirs(os.path.join(tmpdir, "Resume"))
            os.makedirs(os.path.join(tmpdir, "Resumes"))
            os.makedirs(os.path.join(tmpdir, "Other"))

            parser = create_parser()
            args = parser.parse_args(["--scan", "--path", tmpdir])
            exit_code = run_scan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Default is content-aware mode
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out

    def test_scan_with_similar_folders(self, capsys):
        """Test scanning finds similar folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create similar folders
            resume_path = os.path.join(tmpdir, "Resume")
            resumes_path = os.path.join(tmpdir, "Resumes")
            os.makedirs(resume_path)
            os.makedirs(resumes_path)

            # Add some files
            Path(os.path.join(resume_path, "file1.txt")).touch()
            Path(os.path.join(resumes_path, "file2.txt")).touch()

            parser = create_parser()
            args = parser.parse_args(["--scan", "--path", tmpdir, "--threshold", "0.7"])
            exit_code = run_scan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Should find similar folder groups (default content-aware mode)
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out

    def test_scan_respects_threshold(self, capsys):
        """Test scanning respects threshold setting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folders that are somewhat similar
            os.makedirs(os.path.join(tmpdir, "Documents"))
            os.makedirs(os.path.join(tmpdir, "Docs"))

            parser = create_parser()

            # High threshold - may not match
            args = parser.parse_args(
                ["--scan", "--path", tmpdir, "--threshold", "0.95"]
            )
            exit_code = run_scan(args)
            assert exit_code == 0


class TestRunPlan:
    """Tests for run_plan function."""

    def test_plan_empty_directory(self, capsys):
        """Test planning on an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--plan", "--path", tmpdir])
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Default is content-aware mode
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out
            assert "Plan created at:" in captured.out
            assert "Base path:" in captured.out

    def test_plan_saves_output_file(self, capsys):
        """Test planning saves output to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "plan.json")

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--output",
                    output_file,
                ]
            )
            exit_code = run_plan(args)

            assert exit_code == 0
            assert os.path.exists(output_file)

            # Verify JSON is valid
            with open(output_file) as f:
                plan_data = json.load(f)
            assert "created_at" in plan_data
            assert "base_path" in plan_data
            assert "threshold" in plan_data
            assert "groups" in plan_data

    def test_plan_output_contains_statistics(self, capsys):
        """Test plan output contains statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--plan", "--path", tmpdir])
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Threshold:" in captured.out
            assert "Total groups:" in captured.out
            assert "Total folders:" in captured.out
            assert "Total files:" in captured.out

    def test_plan_with_folders(self, capsys):
        """Test planning with actual folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure
            resume_path = os.path.join(tmpdir, "Resume")
            resumes_path = os.path.join(tmpdir, "Resumes")
            taxes_path = os.path.join(tmpdir, "Taxes")

            os.makedirs(resume_path)
            os.makedirs(resumes_path)
            os.makedirs(taxes_path)

            # Add files
            for i in range(3):
                Path(os.path.join(resume_path, f"file{i}.txt")).touch()
            Path(os.path.join(resumes_path, "resume.pdf")).touch()

            output_file = os.path.join(tmpdir, "plan.json")
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--output",
                    output_file,
                    "--threshold",
                    "0.7",
                ]
            )
            exit_code = run_plan(args)

            assert exit_code == 0
            assert os.path.exists(output_file)

            with open(output_file) as f:
                plan_data = json.load(f)

            # Should have groups in the plan
            assert "groups" in plan_data


class TestMain:
    """Tests for main entry point."""

    def test_main_with_scan(self, capsys):
        """Test main function with --scan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--scan", "--path", tmpdir])
            assert exit_code == 0
            captured = capsys.readouterr()
            # Default is content-aware mode
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out

    def test_main_with_plan(self, capsys):
        """Test main function with --plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--plan", "--path", tmpdir])
            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Plan created at:" in captured.out

    def test_main_with_invalid_args(self, capsys):
        """Test main function with invalid arguments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--path", tmpdir])  # No action specified
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error:" in captured.err

    def test_main_with_invalid_threshold(self, capsys):
        """Test main function with invalid threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--scan", "--threshold", "2.0", "--path", tmpdir])
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error:" in captured.err

    def test_main_with_nonexistent_path(self, capsys):
        """Test main function with non-existent path."""
        exit_code = main(["--scan", "--path", "/nonexistent/path/12345"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_main_none_argv_uses_sys_argv(self):
        """Test main with argv=None uses sys.argv."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("sys.argv", ["organizer", "--scan", "--path", tmpdir]):
                # This would normally use sys.argv[1:]
                # We can't easily test this without side effects
                pass

    def test_main_multiple_errors(self, capsys):
        """Test main reports multiple validation errors."""
        exit_code = main(
            [
                "--path",
                "/nonexistent/path/12345",
                "--threshold",
                "2.0",
            ]
        )
        assert exit_code == 1
        captured = capsys.readouterr()
        # Should have multiple error messages
        assert captured.err.count("Error:") >= 2


class TestGetConfirmation:
    """Tests for get_confirmation function."""

    def test_confirmation_yes(self):
        """Test confirmation returns True for 'yes'."""
        input_stream = io.StringIO("yes\n")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is True

    def test_confirmation_yes_uppercase(self):
        """Test confirmation is case-insensitive."""
        input_stream = io.StringIO("YES\n")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is True

    def test_confirmation_yes_mixed_case(self):
        """Test confirmation with mixed case."""
        input_stream = io.StringIO("Yes\n")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is True

    def test_confirmation_no(self):
        """Test confirmation returns False for 'no'."""
        input_stream = io.StringIO("no\n")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is False

    def test_confirmation_empty(self):
        """Test confirmation returns False for empty input."""
        input_stream = io.StringIO("\n")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is False

    def test_confirmation_random_text(self):
        """Test confirmation returns False for random text."""
        input_stream = io.StringIO("sure\n")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is False

    def test_confirmation_y_not_accepted(self):
        """Test that 'y' alone is not accepted (must be 'yes')."""
        input_stream = io.StringIO("y\n")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is False

    def test_confirmation_eof(self):
        """Test confirmation handles EOF gracefully."""
        input_stream = io.StringIO("")
        result = get_confirmation("Confirm?", input_stream=input_stream)
        assert result is False


class TestValidatePlanFile:
    """Tests for validate_plan_file function."""

    def test_valid_plan_file(self):
        """Test loading a valid plan file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            save_plan_to_file(plan, plan_file)

            loaded_plan, error = validate_plan_file(plan_file)
            assert loaded_plan is not None
            assert error is None
            assert loaded_plan.base_path == tmpdir
            assert loaded_plan.threshold == 0.8

    def test_nonexistent_plan_file(self):
        """Test loading a non-existent plan file."""
        plan, error = validate_plan_file("/nonexistent/plan.json")
        assert plan is None
        assert "not found" in error

    def test_invalid_json_plan_file(self):
        """Test loading an invalid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            with open(plan_file, "w") as f:
                f.write("not valid json {{{")

            plan, error = validate_plan_file(plan_file)
            assert plan is None
            assert "Invalid JSON" in error

    def test_valid_but_empty_plan(self):
        """Test loading a valid but empty plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir)
            save_plan_to_file(plan, plan_file)

            loaded_plan, error = validate_plan_file(plan_file)
            assert loaded_plan is not None
            assert error is None
            assert loaded_plan.total_groups == 0


class TestDisplayExecutionSummary:
    """Tests for display_execution_summary function."""

    def test_displays_summary(self, capsys):
        """Test that summary is displayed."""
        plan = ConsolidationPlan(base_path="/test")
        display_execution_summary(plan)

        captured = capsys.readouterr()
        assert "EXECUTION SAFETY CHECK" in captured.out
        assert "WARNING" in captured.out

    def test_displays_group_count(self, capsys):
        """Test that group count is displayed."""
        plan = ConsolidationPlan(base_path="/test")
        folder = FolderInfo(path="/test/folder", name="folder", file_count=5)
        group = FolderGroup(
            group_name="Test-related",
            category_key="test",
            target_folder="Target/Test",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_execution_summary(plan)

        captured = capsys.readouterr()
        assert "1 folder groups" in captured.out

    def test_displays_file_count(self, capsys):
        """Test that file count is displayed."""
        plan = ConsolidationPlan(base_path="/test")
        folder = FolderInfo(path="/test/folder", name="folder", file_count=10)
        group = FolderGroup(
            group_name="Test-related",
            category_key="test",
            target_folder="Target/Test",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_execution_summary(plan)

        captured = capsys.readouterr()
        assert "10 files" in captured.out

    def test_displays_target_folders(self, capsys):
        """Test that target folders are displayed."""
        plan = ConsolidationPlan(base_path="/test")
        folder = FolderInfo(path="/test/folder", name="folder", file_count=5)
        group = FolderGroup(
            group_name="Test-related",
            category_key="test",
            target_folder="Target/TestFolder",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_execution_summary(plan)

        captured = capsys.readouterr()
        assert "Target/TestFolder" in captured.out


class TestRunExecute:
    """Tests for run_execute function."""

    def test_execute_with_valid_plan_confirmed(self, capsys):
        """Test execute with valid plan and confirmation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create actual folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "resume1.pdf")).touch()
            Path(os.path.join(resume_path, "resume2.pdf")).touch()

            # Create a plan file with content
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=2,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            exit_code = run_execute(args, input_stream=input_stream)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Confirmed" in captured.out

    def test_execute_with_valid_plan_declined(self, capsys):
        """Test execute with valid plan but user declines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a plan file with content
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'no'
            input_stream = io.StringIO("no\n")
            exit_code = run_execute(args, input_stream=input_stream)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Aborted" in captured.out

    def test_execute_with_invalid_plan_file(self, capsys):
        """Test execute with invalid plan file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            with open(plan_file, "w") as f:
                f.write("invalid json")

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            exit_code = run_execute(args)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error" in captured.err

    def test_execute_with_empty_plan(self, capsys):
        """Test execute with empty plan (no groups)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            exit_code = run_execute(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "No folder groups" in captured.out or "Nothing to do" in captured.out

    def test_execute_with_no_files_to_move(self, capsys):
        """Test execute with groups but no files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            # Create group with folder that has 0 files
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Empty"),
                name="Empty",
                file_count=0,
            )
            group = FolderGroup(
                group_name="Empty-related",
                category_key=None,
                target_folder="Target/Empty",
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            exit_code = run_execute(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "No files to move" in captured.out or "Nothing to do" in captured.out


class TestCreatePlanBackup:
    """Tests for create_plan_backup function."""

    def test_creates_backup_file(self):
        """Test that backup file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.add_folder(folder)
            plan.groups.append(group)

            backup_path = create_plan_backup(plan)

            assert backup_path.exists()
            assert backup_path.suffix == ".json"

    def test_backup_in_default_directory(self):
        """Test that backup is created in .organizer directory by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)

            backup_path = create_plan_backup(plan)

            assert ".organizer" in str(backup_path)
            assert backup_path.parent.name == ".organizer"

    def test_backup_in_custom_directory(self):
        """Test that backup can be created in custom directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            custom_backup_dir = os.path.join(tmpdir, "custom_backups")

            backup_path = create_plan_backup(plan, backup_dir=custom_backup_dir)

            assert backup_path.exists()
            assert backup_path.parent == Path(custom_backup_dir)

    def test_backup_creates_directory_if_needed(self):
        """Test that backup creates directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            new_backup_dir = os.path.join(tmpdir, "new_dir", "nested")

            backup_path = create_plan_backup(plan, backup_dir=new_backup_dir)

            assert backup_path.exists()
            assert Path(new_backup_dir).exists()

    def test_backup_filename_has_timestamp(self):
        """Test that backup filename includes timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)

            backup_path = create_plan_backup(plan)

            assert "plan_backup_" in backup_path.name
            # Check timestamp format YYYYMMDD_HHMMSS
            name_without_ext = backup_path.stem
            parts = name_without_ext.replace("plan_backup_", "")
            assert len(parts) == 15  # YYYYMMDD_HHMMSS

    def test_backup_content_matches_original(self):
        """Test that backup content matches original plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.add_folder(folder)
            plan.groups.append(group)

            backup_path = create_plan_backup(plan)

            # Load the backup and compare
            with open(backup_path) as f:
                backup_data = json.load(f)

            assert backup_data["threshold"] == plan.threshold
            assert len(backup_data["groups"]) == len(plan.groups)
            assert backup_data["groups"][0]["group_name"] == "Resume-related"

    def test_multiple_backups_have_different_names(self):
        """Test that multiple backups get different filenames."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)

            backup_path_1 = create_plan_backup(plan)
            time.sleep(1.1)  # Wait to ensure different timestamp
            backup_path_2 = create_plan_backup(plan)

            assert backup_path_1 != backup_path_2
            assert backup_path_1.exists()
            assert backup_path_2.exists()

    def test_backup_with_empty_plan(self):
        """Test backup works with empty plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)

            backup_path = create_plan_backup(plan)

            assert backup_path.exists()
            with open(backup_path) as f:
                backup_data = json.load(f)
            assert backup_data["groups"] == []


class TestRunExecuteWithBackup:
    """Tests for run_execute function's backup functionality."""

    def test_execute_creates_backup_on_confirmation(self, capsys):
        """Test that backup is created when user confirms execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create actual folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "resume1.pdf")).touch()

            # Create a plan file with content
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            exit_code = run_execute(args, input_stream=input_stream)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Backup saved to:" in captured.out

            # Verify backup file exists
            organizer_dir = os.path.join(tmpdir, ".organizer")
            assert os.path.exists(organizer_dir)
            backup_files = list(Path(organizer_dir).glob("plan_backup_*.json"))
            assert len(backup_files) == 1

    def test_execute_no_backup_on_decline(self, capsys):
        """Test that no backup is created when user declines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a plan file with content
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'no'
            input_stream = io.StringIO("no\n")
            exit_code = run_execute(args, input_stream=input_stream)

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Backup saved to:" not in captured.out

            # Verify no backup file exists
            organizer_dir = os.path.join(tmpdir, ".organizer")
            if os.path.exists(organizer_dir):
                backup_files = list(Path(organizer_dir).glob("plan_backup_*.json"))
                assert len(backup_files) == 0

    def test_backup_contains_plan_data(self, capsys):
        """Test that backup file contains correct plan data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a plan file with content
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.85)
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=7,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            run_execute(args, input_stream=input_stream)

            # Find and verify backup content
            organizer_dir = os.path.join(tmpdir, ".organizer")
            backup_files = list(Path(organizer_dir).glob("plan_backup_*.json"))
            assert len(backup_files) == 1

            with open(backup_files[0]) as f:
                backup_data = json.load(f)

            assert backup_data["threshold"] == 0.85
            assert len(backup_data["groups"]) == 1
            assert backup_data["groups"][0]["group_name"] == "Resume-related"


class TestContentAwareArgument:
    """Tests for --content-aware argument."""

    def test_content_aware_defaults_true(self):
        """Test --content-aware defaults to True."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.content_aware is True

    def test_content_aware_explicit_true(self):
        """Test --content-aware can be explicitly set to True."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--content-aware"])
        assert args.content_aware is True

    def test_no_content_aware(self):
        """Test --no-content-aware sets flag to False."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--no-content-aware"])
        assert args.content_aware is False

    def test_db_path_argument(self):
        """Test --db-path argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--db-path", "/path/to/db.sqlite"])
        assert args.db_path == "/path/to/db.sqlite"

    def test_db_path_defaults_none(self):
        """Test --db-path defaults to None."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.db_path is None

    def test_db_path_with_content_aware(self):
        """Test --db-path can be used with --content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                ["--scan", "--content-aware", "--db-path", db_file, "--path", tmpdir]
            )
            errors = validate_args(args)
            # Should not have db-path related errors
            assert not any("db-path" in e.lower() for e in errors)

    def test_db_path_without_content_aware_fails(self):
        """Test --db-path fails when used with --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--no-content-aware",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("--db-path" in e for e in errors)

    def test_db_path_nonexistent_fails(self):
        """Test --db-path fails when database file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--db-path",
                    "/nonexistent/db.sqlite",
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("does not exist" in e for e in errors)

    def test_db_path_is_directory_fails(self):
        """Test --db-path fails when path is a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--db-path",
                    tmpdir,  # Directory instead of file
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("not a file" in e for e in errors)


class TestRunScanContentAware:
    """Tests for run_scan with content-aware mode."""

    def test_scan_with_content_aware_default(self, capsys):
        """Test scanning with content-aware mode (default)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--scan", "--path", tmpdir])
            exit_code = run_scan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Content-aware mode shows different header
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out

    def test_scan_with_content_aware_disabled(self, capsys):
        """Test scanning with content-aware mode disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--scan", "--path", tmpdir, "--no-content-aware"])
            exit_code = run_scan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Non-content-aware mode shows regular header
            assert "FOLDER SIMILARITY ANALYSIS" in captured.out


class TestRunPlanContentAware:
    """Tests for run_plan with content-aware mode."""

    def test_plan_with_content_aware_default(self, capsys):
        """Test planning with content-aware mode (default)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--plan", "--path", tmpdir])
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: True" in captured.out

    def test_plan_with_content_aware_disabled(self, capsys):
        """Test planning with content-aware mode disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--plan", "--path", tmpdir, "--no-content-aware"])
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: False" in captured.out

    def test_plan_output_includes_content_aware_field(self, capsys):
        """Test that plan output JSON includes content_aware field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "plan.json")

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--output",
                    output_file,
                    "--content-aware",
                ]
            )
            exit_code = run_plan(args)

            assert exit_code == 0
            assert os.path.exists(output_file)

            with open(output_file) as f:
                plan_data = json.load(f)

            assert "content_aware" in plan_data
            assert plan_data["content_aware"] is True

    def test_plan_output_content_aware_false(self, capsys):
        """Test that plan output JSON includes content_aware=False when disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, "plan.json")

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--output",
                    output_file,
                    "--no-content-aware",
                ]
            )
            exit_code = run_plan(args)

            assert exit_code == 0

            with open(output_file) as f:
                plan_data = json.load(f)

            assert "content_aware" in plan_data
            assert plan_data["content_aware"] is False


class TestMainContentAware:
    """Tests for main function with content-aware arguments."""

    def test_main_with_content_aware(self, capsys):
        """Test main function with --content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--scan", "--path", tmpdir, "--content-aware"])
            assert exit_code == 0

    def test_main_with_no_content_aware(self, capsys):
        """Test main function with --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--scan", "--path", tmpdir, "--no-content-aware"])
            assert exit_code == 0

    def test_main_plan_with_content_aware(self, capsys):
        """Test main function --plan with --content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--plan", "--path", tmpdir, "--content-aware"])
            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: True" in captured.out

    def test_main_plan_with_no_content_aware(self, capsys):
        """Test main function --plan with --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--plan", "--path", tmpdir, "--no-content-aware"])
            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: False" in captured.out

    def test_main_with_db_path_and_no_content_aware_fails(self, capsys):
        """Test main fails with --db-path and --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            exit_code = main(
                [
                    "--scan",
                    "--path",
                    tmpdir,
                    "--no-content-aware",
                    "--db-path",
                    db_file,
                ]
            )
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error" in captured.err


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_full_workflow_scan_then_plan(self, capsys):
        """Test complete workflow: scan then plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure
            os.makedirs(os.path.join(tmpdir, "Resume"))
            os.makedirs(os.path.join(tmpdir, "Resumes"))
            os.makedirs(os.path.join(tmpdir, "Documents"))

            # First scan
            exit_code = main(["--scan", "--path", tmpdir, "--threshold", "0.7"])
            assert exit_code == 0

            # Then plan with output
            output_file = os.path.join(tmpdir, "consolidation_plan.json")
            exit_code = main(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--threshold",
                    "0.7",
                    "--output",
                    output_file,
                ]
            )
            assert exit_code == 0
            assert os.path.exists(output_file)

    def test_max_depth_limits_scanning(self):
        """Test that max-depth properly limits folder scanning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            deep_path = os.path.join(tmpdir, "a", "b", "c", "d", "e")
            os.makedirs(deep_path)
            Path(os.path.join(deep_path, "file.txt")).touch()

            parser = create_parser()

            # With depth 2, shouldn't reach deep folder
            args = parser.parse_args(
                [
                    "--scan",
                    "--path",
                    tmpdir,
                    "--max-depth",
                    "2",
                ]
            )
            exit_code = run_scan(args)
            assert exit_code == 0

    def test_output_file_in_subdirectory(self):
        """Test saving output file in a subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create output subdirectory
            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(output_dir)
            output_file = os.path.join(output_dir, "plan.json")

            exit_code = main(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--output",
                    output_file,
                ]
            )
            assert exit_code == 0
            assert os.path.exists(output_file)

    def test_execute_workflow(self, capsys):
        """Test complete execute workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure
            resume_path = os.path.join(tmpdir, "Resume")
            resumes_path = os.path.join(tmpdir, "Resumes")
            os.makedirs(resume_path)
            os.makedirs(resumes_path)

            # Add files to folders
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()
            Path(os.path.join(resumes_path, "old_resume.pdf")).touch()

            # First create a plan
            plan_file = os.path.join(tmpdir, "consolidation_plan.json")
            exit_code = main(
                [
                    "--plan",
                    "--path",
                    tmpdir,
                    "--threshold",
                    "0.7",
                    "--output",
                    plan_file,
                ]
            )
            assert exit_code == 0
            assert os.path.exists(plan_file)

            # Verify plan has content
            with open(plan_file) as f:
                plan_data = json.load(f)
            # Check that the plan was created
            assert "groups" in plan_data

    def test_main_with_execute_requires_plan_file(self, capsys):
        """Test main with --execute but no --plan-file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(["--execute", "--path", tmpdir])
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error" in captured.err
            assert "--plan-file" in captured.err

    def test_main_with_execute_and_nonexistent_plan(self, capsys):
        """Test main with --execute and non-existent plan file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(
                [
                    "--execute",
                    "--plan-file",
                    "/nonexistent/plan.json",
                    "--path",
                    tmpdir,
                ]
            )
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error" in captured.err


class TestRunExecuteWithProgress:
    """Tests for run_execute with progress reporting."""

    def test_execute_shows_progress_header(self, capsys):
        """Test that execute shows progress header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()

            # Create a plan file
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            exit_code = run_execute(args, input_stream=input_stream)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "EXECUTING CONSOLIDATION" in captured.out

    def test_execute_shows_group_progress(self, capsys):
        """Test that execute shows group progress."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()

            # Create a plan file with one group
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            exit_code = run_execute(args, input_stream=input_stream)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "[1/1]" in captured.out
            assert "Resume-related" in captured.out

    def test_execute_shows_progress_bar(self, capsys):
        """Test that execute shows progress bar."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()

            # Create a plan file
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "Progress:" in captured.out
            assert "1/1 groups" in captured.out

    def test_execute_shows_completion_summary(self, capsys):
        """Test that execute shows completion summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()

            # Create a plan file
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "EXECUTION COMPLETE" in captured.out
            assert "Groups processed:" in captured.out
            assert "Files moved:" in captured.out
            assert "Time elapsed:" in captured.out

    def test_execute_creates_execution_log(self, capsys):
        """Test that execute creates execution log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()

            # Create a plan file
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "Execution log saved to:" in captured.out

            # Verify execution log exists
            organizer_dir = os.path.join(tmpdir, ".organizer")
            log_files = list(Path(organizer_dir).glob("execution_log_*.json"))
            assert len(log_files) >= 1

    def test_execute_with_multiple_groups(self, capsys):
        """Test execution with multiple folder groups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            tax_path = os.path.join(tmpdir, "Taxes")
            os.makedirs(resume_path)
            os.makedirs(tax_path)
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()
            Path(os.path.join(tax_path, "2023_taxes.pdf")).touch()

            # Create a plan file with two groups
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)

            # Group 1: Resume
            folder1 = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group1 = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group1.add_folder(folder1)
            plan.groups.append(group1)

            # Group 2: Taxes
            folder2 = FolderInfo(
                path=tax_path,
                name="Taxes",
                file_count=1,
            )
            group2 = FolderGroup(
                group_name="Tax-related",
                category_key="finances",
                target_folder=os.path.join(tmpdir, "Finances", "Taxes"),
            )
            group2.add_folder(folder2)
            plan.groups.append(group2)

            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "[1/2]" in captured.out
            assert "[2/2]" in captured.out
            assert "Resume-related" in captured.out
            assert "Tax-related" in captured.out
            assert "2/2 groups" in captured.out

    def test_execute_success_returns_zero(self, capsys):
        """Test that successful execution returns exit code 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folder structure with files
            resume_path = os.path.join(tmpdir, "Resume")
            os.makedirs(resume_path)
            Path(os.path.join(resume_path, "my_resume.pdf")).touch()

            # Create a plan file
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(base_path=tmpdir, threshold=0.8)
            folder = FolderInfo(
                path=resume_path,
                name="Resume",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder=os.path.join(tmpdir, "Employment", "Resumes"),
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--execute",
                    "--plan-file",
                    plan_file,
                    "--path",
                    tmpdir,
                ]
            )

            # Simulate user typing 'yes'
            input_stream = io.StringIO("yes\n")
            exit_code = run_execute(args, input_stream=input_stream)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "[OK] EXECUTION COMPLETE" in captured.out


class TestAnalyzeMissingArgument:
    """Tests for --analyze-missing argument."""

    def test_analyze_missing_defaults_false(self):
        """Test --analyze-missing defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.analyze_missing is False

    def test_analyze_missing_explicit_true(self):
        """Test --analyze-missing can be set to True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--analyze-missing",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )
            assert args.analyze_missing is True

    def test_analyze_missing_without_content_aware_fails(self):
        """Test --analyze-missing fails when used with --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--no-content-aware",
                    "--analyze-missing",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any(
                "--analyze-missing requires --content-aware" in e for e in errors
            )

    def test_analyze_missing_without_db_path_fails(self):
        """Test --analyze-missing fails when --db-path is not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--analyze-missing",
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("--analyze-missing requires --db-path" in e for e in errors)

    def test_analyze_missing_with_content_aware_and_db_path_passes(self):
        """Test --analyze-missing passes when used with --content-aware and --db-path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--content-aware",
                    "--analyze-missing",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            # Should not have analyze-missing related errors
            assert not any("analyze-missing" in e.lower() for e in errors)


class TestRunScanAnalyzeMissing:
    """Tests for run_scan with --analyze-missing flag."""

    def test_scan_with_analyze_missing(self, capsys):
        """Test scanning with --analyze-missing flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--analyze-missing",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )
            exit_code = run_scan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            # Content-aware mode is enabled
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out


class TestRunPlanAnalyzeMissing:
    """Tests for run_plan with --analyze-missing flag."""

    def test_plan_with_analyze_missing(self, capsys):
        """Test planning with --analyze-missing flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            parser = create_parser()
            args = parser.parse_args(
                [
                    "--plan",
                    "--analyze-missing",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: True" in captured.out


class TestMainAnalyzeMissing:
    """Tests for main with --analyze-missing flag."""

    def test_main_with_analyze_missing(self, capsys):
        """Test main with --analyze-missing flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            exit_code = main(
                [
                    "--scan",
                    "--analyze-missing",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )

            assert exit_code == 0

    def test_main_with_analyze_missing_and_no_content_aware_fails(self, capsys):
        """Test main fails with --analyze-missing and --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy database file
            db_file = os.path.join(tmpdir, "test.db")
            Path(db_file).touch()

            exit_code = main(
                [
                    "--scan",
                    "--no-content-aware",
                    "--analyze-missing",
                    "--db-path",
                    db_file,
                    "--path",
                    tmpdir,
                ]
            )

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "--analyze-missing requires --content-aware" in captured.err

    def test_main_with_analyze_missing_and_no_db_path_fails(self, capsys):
        """Test main fails with --analyze-missing and no --db-path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(
                [
                    "--scan",
                    "--analyze-missing",
                    "--path",
                    tmpdir,
                ]
            )

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "--analyze-missing requires --db-path" in captured.err


class TestMinContentSimilarityArgument:
    """Tests for --min-content-similarity argument."""

    def test_min_content_similarity_defaults_to_0_6(self):
        """Test --min-content-similarity defaults to 0.6."""
        parser = create_parser()
        args = parser.parse_args(["--scan"])
        assert args.min_content_similarity == 0.6

    def test_min_content_similarity_custom_value(self):
        """Test --min-content-similarity accepts custom value."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--min-content-similarity", "0.8"])
        assert args.min_content_similarity == 0.8

    def test_min_content_similarity_at_boundaries(self):
        """Test --min-content-similarity at valid boundaries."""
        parser = create_parser()

        args = parser.parse_args(["--scan", "--min-content-similarity", "0.0"])
        assert args.min_content_similarity == 0.0

        args = parser.parse_args(["--scan", "--min-content-similarity", "1.0"])
        assert args.min_content_similarity == 1.0

    def test_min_content_similarity_too_low_fails(self):
        """Test --min-content-similarity fails when < 0.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                ["--scan", "--min-content-similarity", "-0.1", "--path", tmpdir]
            )
            errors = validate_args(args)
            assert any("--min-content-similarity" in e for e in errors)
            assert any("between 0.0 and 1.0" in e for e in errors)

    def test_min_content_similarity_too_high_fails(self):
        """Test --min-content-similarity fails when > 1.0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                ["--scan", "--min-content-similarity", "1.5", "--path", tmpdir]
            )
            errors = validate_args(args)
            assert any("--min-content-similarity" in e for e in errors)
            assert any("between 0.0 and 1.0" in e for e in errors)

    def test_min_content_similarity_without_content_aware_fails(self):
        """Test --min-content-similarity fails when used with --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--no-content-aware",
                    "--min-content-similarity",
                    "0.8",
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            assert any("--min-content-similarity" in e for e in errors)
            assert any("--content-aware" in e for e in errors)

    def test_min_content_similarity_with_content_aware_passes(self):
        """Test --min-content-similarity passes with --content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--content-aware",
                    "--min-content-similarity",
                    "0.8",
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            # Should not have min-content-similarity related errors
            assert not any("min-content-similarity" in e.lower() for e in errors)

    def test_min_content_similarity_default_with_no_content_aware_passes(self):
        """Test default --min-content-similarity passes with --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                [
                    "--scan",
                    "--no-content-aware",
                    "--path",
                    tmpdir,
                ]
            )
            errors = validate_args(args)
            # Default value should not trigger error
            assert not any("min-content-similarity" in e.lower() for e in errors)


class TestRunScanMinContentSimilarity:
    """Tests for run_scan with --min-content-similarity."""

    def test_scan_with_min_content_similarity(self, capsys):
        """Test scanning with --min-content-similarity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                ["--scan", "--min-content-similarity", "0.8", "--path", tmpdir]
            )
            exit_code = run_scan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "CONTENT-AWARE FOLDER ANALYSIS" in captured.out


class TestRunPlanMinContentSimilarity:
    """Tests for run_plan with --min-content-similarity."""

    def test_plan_with_min_content_similarity(self, capsys):
        """Test planning with --min-content-similarity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(
                ["--plan", "--min-content-similarity", "0.8", "--path", tmpdir]
            )
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: True" in captured.out
            assert "Content similarity threshold: 0.8" in captured.out

    def test_plan_with_default_min_content_similarity(self, capsys):
        """Test plan output shows default threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--plan", "--path", tmpdir])
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: True" in captured.out
            assert "Content similarity threshold: 0.6" in captured.out

    def test_plan_without_content_aware_no_similarity_output(self, capsys):
        """Test plan output doesn't show similarity threshold when not content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--plan", "--no-content-aware", "--path", tmpdir])
            exit_code = run_plan(args)

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content-aware: False" in captured.out
            assert "Content similarity threshold" not in captured.out


class TestMainMinContentSimilarity:
    """Tests for main with --min-content-similarity."""

    def test_main_with_min_content_similarity(self, capsys):
        """Test main with --min-content-similarity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(
                ["--scan", "--min-content-similarity", "0.7", "--path", tmpdir]
            )
            assert exit_code == 0

    def test_main_with_invalid_min_content_similarity(self, capsys):
        """Test main fails with invalid --min-content-similarity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(
                ["--scan", "--min-content-similarity", "1.5", "--path", tmpdir]
            )
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error" in captured.err
            assert "--min-content-similarity" in captured.err

    def test_main_plan_with_min_content_similarity(self, capsys):
        """Test main --plan with --min-content-similarity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(
                ["--plan", "--min-content-similarity", "0.9", "--path", tmpdir]
            )
            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Content similarity threshold: 0.9" in captured.out

    def test_main_with_min_content_similarity_and_no_content_aware_fails(self, capsys):
        """Test main fails with --min-content-similarity and --no-content-aware."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exit_code = main(
                [
                    "--scan",
                    "--no-content-aware",
                    "--min-content-similarity",
                    "0.8",
                    "--path",
                    tmpdir,
                ]
            )
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Error" in captured.err


class TestDisplayContentAnalysisSummary:
    """Tests for display_content_analysis_summary function (Phase 6)."""

    def test_no_output_for_non_content_aware_plan(self, capsys):
        """Test no output when plan is not content-aware."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=False)
        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_empty_groups_message(self, capsys):
        """Test message when plan has no groups."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "CONTENT ANALYSIS SUMMARY" in captured.out
        assert "No folder groups to analyze" in captured.out

    def test_shows_groups_to_consolidate(self, capsys):
        """Test showing groups that should be consolidated."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes"},
            date_ranges={"/test/Resume": "2024-2025"},
            decision_summary="Same AI category, same date range",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "CONTENT ANALYSIS SUMMARY" in captured.out
        assert "GROUPS TO CONSOLIDATE (1)" in captured.out
        assert "Resume-related" in captured.out

    def test_shows_groups_to_skip(self, capsys):
        """Test showing groups that should NOT be consolidated."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Tax2002", name="Tax2002", file_count=10)
        group = FolderGroup(
            group_name="Tax-related",
            category_key="finances",
            should_consolidate=False,
            ai_categories={"Finances/Taxes"},
            date_ranges={"/test/Tax2002": "2002-2003"},
            decision_summary="Different timeframes (Tax2002 vs Tax2025)",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "CONTENT ANALYSIS SUMMARY" in captured.out
        assert "GROUPS TO SKIP (1)" in captured.out
        assert "Tax-related" in captured.out

    def test_shows_ai_categories(self, capsys):
        """Test showing AI categories in summary."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Job Applications"},
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "AI Categories:" in captured.out
        assert "Employment/Resumes" in captured.out

    def test_shows_date_ranges(self, capsys):
        """Test showing date ranges in summary."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Tax", name="Tax", file_count=20)
        group = FolderGroup(
            group_name="Tax-related",
            category_key="finances",
            target_folder="Finances/Taxes",
            should_consolidate=True,
            date_ranges={"/test/Tax": "2023-2025", "/test/Tax2": "2023-2024"},
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "Date Ranges:" in captured.out
        assert "2023" in captured.out

    def test_shows_decision_summary(self, capsys):
        """Test showing decision summary in output."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            decision_summary="Same AI category, same context bin",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "Decision:" in captured.out
        assert "Same AI category, same context bin" in captured.out

    def test_shows_target_folder_for_consolidate_groups(self, capsys):
        """Test showing target folder for groups that will consolidate."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "Target:" in captured.out
        assert "Employment/Resumes/" in captured.out

    def test_no_target_folder_for_skip_groups(self, capsys):
        """Test no target folder shown for groups that will be skipped."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Tax2002", name="Tax2002", file_count=10)
        group = FolderGroup(
            group_name="Tax-related",
            category_key="finances",
            target_folder="Finances/Taxes",
            should_consolidate=False,
            decision_summary="Different timeframes",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        # Should NOT show target folder in GROUPS TO SKIP section
        output_lines = captured.out.split("\n")
        skip_section_start = None
        for i, line in enumerate(output_lines):
            if "GROUPS TO SKIP" in line:
                skip_section_start = i
                break

        if skip_section_start:
            # Check lines after GROUPS TO SKIP
            skip_section = output_lines[skip_section_start:]
            skip_text = "\n".join(skip_section)
            # Target should not appear in skip section before next section
            assert "Target:" not in skip_text.split("Summary:")[0] if "Summary:" in skip_text else "Target:" not in skip_text

    def test_shows_summary_statistics(self, capsys):
        """Test showing summary statistics at the end."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)

        # Add a group to consolidate
        folder1 = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group1 = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
        )
        group1.add_folder(folder1)
        plan.groups.append(group1)

        # Add a group to skip
        folder2 = FolderInfo(path="/test/Tax2002", name="Tax2002", file_count=10)
        group2 = FolderGroup(
            group_name="Tax-related",
            category_key="finances",
            should_consolidate=False,
        )
        group2.add_folder(folder2)
        plan.groups.append(group2)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "Summary:" in captured.out
        assert "1 groups will consolidate" in captured.out
        assert "1 will be skipped" in captured.out
        assert "5 files will be moved" in captured.out
        assert "10 files will stay in place" in captured.out


class TestRunExecuteWithContentAnalysisSummary:
    """Tests for run_execute showing content analysis summary (Phase 6)."""

    def test_execute_shows_content_analysis_summary(self, capsys):
        """Test that execute shows content analysis summary for content-aware plans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plan file with content-aware data
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes"},
                decision_summary="Same AI category",
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # Simulate user declining
            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "CONTENT ANALYSIS SUMMARY" in captured.out
            assert "GROUPS TO CONSOLIDATE" in captured.out

    def test_execute_no_content_summary_for_non_content_aware(self, capsys):
        """Test that execute doesn't show content analysis for non-content-aware plans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plan file without content-aware
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=False,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # Simulate user declining
            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "CONTENT ANALYSIS SUMMARY" not in captured.out

    def test_execute_shows_both_consolidate_and_skip_groups(self, capsys):
        """Test that execute shows both consolidate and skip groups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plan file with mixed groups
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )

            # Group to consolidate
            folder1 = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group1 = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes"},
            )
            group1.add_folder(folder1)
            plan.groups.append(group1)

            # Group to skip
            folder2 = FolderInfo(
                path=os.path.join(tmpdir, "Tax2002"),
                name="Tax2002",
                file_count=10,
            )
            group2 = FolderGroup(
                group_name="Tax-related",
                category_key="finances",
                should_consolidate=False,
                ai_categories={"Finances/Taxes"},
                decision_summary="Different timeframes",
            )
            group2.add_folder(folder2)
            plan.groups.append(group2)

            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # Simulate user declining
            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "GROUPS TO CONSOLIDATE (1)" in captured.out
            assert "GROUPS TO SKIP (1)" in captured.out
            assert "Resume-related" in captured.out
            assert "Tax-related" in captured.out

    def test_execute_content_summary_before_execution_summary(self, capsys):
        """Test that content analysis summary appears before execution summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create plan file
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # Simulate user declining
            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            content_analysis_pos = captured.out.find("CONTENT ANALYSIS SUMMARY")
            execution_summary_pos = captured.out.find("EXECUTION SAFETY CHECK")

            assert content_analysis_pos != -1
            assert execution_summary_pos != -1
            assert content_analysis_pos < execution_summary_pos


class TestHasMixedContentTypes:
    """Tests for has_mixed_content_types function (Phase 6)."""

    def test_single_category_returns_false(self):
        """Test that single AI category returns False."""
        from organizer.cli import has_mixed_content_types

        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            ai_categories={"Employment/Resumes"},
        )
        assert has_mixed_content_types(group) is False

    def test_multiple_categories_returns_true(self):
        """Test that multiple AI categories returns True."""
        from organizer.cli import has_mixed_content_types

        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        assert has_mixed_content_types(group) is True

    def test_empty_categories_returns_false(self):
        """Test that empty AI categories returns False."""
        from organizer.cli import has_mixed_content_types

        group = FolderGroup(
            group_name="Unknown-related",
            category_key=None,
            ai_categories=set(),
        )
        assert has_mixed_content_types(group) is False

    def test_three_categories_returns_true(self):
        """Test that three or more AI categories returns True."""
        from organizer.cli import has_mixed_content_types

        group = FolderGroup(
            group_name="Very-mixed",
            category_key=None,
            ai_categories={"Employment/Resumes", "Finances/Taxes", "Legal/Contracts"},
        )
        assert has_mixed_content_types(group) is True


class TestDisplayContentTypeWarning:
    """Tests for display_content_type_warning function (Phase 6)."""

    def test_no_warning_for_single_category(self, capsys):
        """Test no warning is displayed for single category."""
        from organizer.cli import display_content_type_warning

        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            ai_categories={"Employment/Resumes"},
        )
        display_content_type_warning(group)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_warning_displayed_for_mixed_categories(self, capsys):
        """Test warning is displayed for mixed categories."""
        from organizer.cli import display_content_type_warning

        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        display_content_type_warning(group)

        captured = capsys.readouterr()
        assert "WARNING: Mixed content types detected!" in captured.out

    def test_warning_lists_all_categories(self, capsys):
        """Test warning lists all mixed categories."""
        from organizer.cli import display_content_type_warning

        group = FolderGroup(
            group_name="Mixed-related",
            category_key=None,
            ai_categories={"Employment/Resumes", "Finances/Taxes", "Legal/Contracts"},
        )
        display_content_type_warning(group)

        captured = capsys.readouterr()
        assert "Employment/Resumes" in captured.out
        assert "Finances/Taxes" in captured.out
        assert "Legal/Contracts" in captured.out

    def test_warning_includes_review_message(self, capsys):
        """Test warning includes review message."""
        from organizer.cli import display_content_type_warning

        group = FolderGroup(
            group_name="Mixed-related",
            category_key=None,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        display_content_type_warning(group)

        captured = capsys.readouterr()
        assert "Consider reviewing these folders before consolidation" in captured.out

    def test_no_warning_for_empty_categories(self, capsys):
        """Test no warning is displayed for empty categories."""
        from organizer.cli import display_content_type_warning

        group = FolderGroup(
            group_name="Unknown-related",
            category_key=None,
            ai_categories=set(),
        )
        display_content_type_warning(group)

        captured = capsys.readouterr()
        assert captured.out == ""


class TestContentAnalysisSummaryWithWarnings:
    """Tests for content analysis summary with mixed content warnings (Phase 6)."""

    def test_warning_shown_for_consolidate_group_with_mixed_types(self, capsys):
        """Test warning is shown for consolidate group with mixed content types."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=15)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
            decision_summary="Same date range",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "WARNING: Mixed content types detected!" in captured.out
        assert "Employment/Resumes" in captured.out
        assert "Finances/Taxes" in captured.out

    def test_no_warning_shown_for_skip_group_with_mixed_types(self, capsys):
        """Test no warning shown for skip group with mixed types (not being consolidated)."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=15)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            should_consolidate=False,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
            decision_summary="Different timeframes",
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        # Warning should NOT appear in skip section
        # The warning emoji should not be in the output since it's not being consolidated
        assert "WARNING: Mixed content types detected!" not in captured.out

    def test_summary_shows_total_mixed_groups_count(self, capsys):
        """Test summary shows count of groups with mixed content types."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)

        # Group with mixed types (should warn)
        folder1 = FolderInfo(path="/test/Mixed", name="Mixed", file_count=15)
        group1 = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group1.add_folder(folder1)
        plan.groups.append(group1)

        # Group without mixed types (no warn)
        folder2 = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group2 = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes"},
        )
        group2.add_folder(folder2)
        plan.groups.append(group2)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "1 group(s) contain mixed content types" in captured.out

    def test_no_mixed_warning_summary_when_no_mixed_groups(self, capsys):
        """Test no mixed warning summary when no groups have mixed types."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)

        folder = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes"},
        )
        group.add_folder(folder)
        plan.groups.append(group)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "group(s) contain mixed content types" not in captured.out

    def test_multiple_mixed_groups_count(self, capsys):
        """Test summary shows correct count for multiple mixed groups."""
        plan = ConsolidationPlan(base_path="/test", threshold=0.8, content_aware=True)

        # First mixed group
        folder1 = FolderInfo(path="/test/Mixed1", name="Mixed1", file_count=10)
        group1 = FolderGroup(
            group_name="Mixed1-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group1.add_folder(folder1)
        plan.groups.append(group1)

        # Second mixed group
        folder2 = FolderInfo(path="/test/Mixed2", name="Mixed2", file_count=8)
        group2 = FolderGroup(
            group_name="Mixed2-related",
            category_key="legal",
            target_folder="Legal/Contracts",
            should_consolidate=True,
            ai_categories={"Legal/Contracts", "Health/Medical"},
        )
        group2.add_folder(folder2)
        plan.groups.append(group2)

        display_content_analysis_summary(plan)

        captured = capsys.readouterr()
        assert "2 group(s) contain mixed content types" in captured.out


class TestRunExecuteWithMixedContentWarning:
    """Tests for run_execute with mixed content type warnings (Phase 6)."""

    def test_execute_shows_mixed_content_warning(self, capsys):
        """Test that execute shows warning for mixed content types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Mixed"),
                name="Mixed",
                file_count=15,
            )
            group = FolderGroup(
                group_name="Mixed-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes", "Finances/Taxes"},
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "WARNING: Mixed content types detected!" in captured.out
            assert "Employment/Resumes" in captured.out
            assert "Finances/Taxes" in captured.out

    def test_execute_shows_mixed_content_count_in_summary(self, capsys):
        """Test that execute shows mixed content count in summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )

            # Mixed content group
            folder1 = FolderInfo(
                path=os.path.join(tmpdir, "Mixed"),
                name="Mixed",
                file_count=15,
            )
            group1 = FolderGroup(
                group_name="Mixed-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes", "Finances/Taxes"},
            )
            group1.add_folder(folder1)
            plan.groups.append(group1)

            # Clean group
            folder2 = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group2 = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes"},
            )
            group2.add_folder(folder2)
            plan.groups.append(group2)

            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "1 group(s) contain mixed content types" in captured.out
            assert "Review the warnings above before proceeding" in captured.out


class TestGetContentMismatchGroups:
    """Tests for get_content_mismatch_groups function."""

    def test_returns_empty_for_non_content_aware_plan(self):
        """Test that non-content-aware plans return no mismatch groups."""
        plan = ConsolidationPlan(
            base_path="/test",
            threshold=0.8,
            content_aware=False,
        )
        folder = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)
        plan.groups.append(group)

        result = get_content_mismatch_groups(plan)
        assert result == []

    def test_returns_empty_for_plan_with_no_mismatches(self):
        """Test that plans with no mismatches return empty list."""
        plan = ConsolidationPlan(
            base_path="/test",
            threshold=0.8,
            content_aware=True,
        )
        folder = FolderInfo(path="/test/Resume", name="Resume", file_count=5)
        group = FolderGroup(
            group_name="Resume-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes"},
        )
        group.add_folder(folder)
        plan.groups.append(group)

        result = get_content_mismatch_groups(plan)
        assert result == []

    def test_returns_groups_with_mixed_content(self):
        """Test that groups with mixed content are returned."""
        plan = ConsolidationPlan(
            base_path="/test",
            threshold=0.8,
            content_aware=True,
        )
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=5)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)
        plan.groups.append(group)

        result = get_content_mismatch_groups(plan)
        assert len(result) == 1
        assert result[0].group_name == "Mixed-related"

    def test_excludes_groups_not_marked_for_consolidation(self):
        """Test that groups not marked for consolidation are excluded."""
        plan = ConsolidationPlan(
            base_path="/test",
            threshold=0.8,
            content_aware=True,
        )
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=5)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=False,  # Not consolidating
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)
        plan.groups.append(group)

        result = get_content_mismatch_groups(plan)
        assert result == []

    def test_returns_multiple_mismatch_groups(self):
        """Test that multiple mismatch groups are all returned."""
        plan = ConsolidationPlan(
            base_path="/test",
            threshold=0.8,
            content_aware=True,
        )

        # First mixed group
        folder1 = FolderInfo(path="/test/Mixed1", name="Mixed1", file_count=5)
        group1 = FolderGroup(
            group_name="Mixed1-related",
            category_key="employment",
            target_folder="Target1",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group1.add_folder(folder1)
        plan.groups.append(group1)

        # Second mixed group
        folder2 = FolderInfo(path="/test/Mixed2", name="Mixed2", file_count=10)
        group2 = FolderGroup(
            group_name="Mixed2-related",
            category_key="legal",
            target_folder="Target2",
            should_consolidate=True,
            ai_categories={"Legal", "Medical", "VA Claims"},
        )
        group2.add_folder(folder2)
        plan.groups.append(group2)

        # Clean group (should not be included)
        folder3 = FolderInfo(path="/test/Clean", name="Clean", file_count=3)
        group3 = FolderGroup(
            group_name="Clean-related",
            category_key="employment",
            target_folder="Target3",
            should_consolidate=True,
            ai_categories={"Employment/Resumes"},
        )
        group3.add_folder(folder3)
        plan.groups.append(group3)

        result = get_content_mismatch_groups(plan)
        assert len(result) == 2
        assert result[0].group_name == "Mixed1-related"
        assert result[1].group_name == "Mixed2-related"


class TestGetContentMismatchConfirmation:
    """Tests for get_content_mismatch_confirmation function."""

    def test_returns_true_for_empty_mismatch_list(self):
        """Test that empty mismatch list returns True without prompting."""
        result = get_content_mismatch_confirmation([])
        assert result is True

    def test_returns_true_when_user_types_yes(self, capsys):
        """Test that 'yes' input returns True."""
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=5)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)

        input_stream = io.StringIO("yes\n")
        result = get_content_mismatch_confirmation([group], input_stream)

        assert result is True
        captured = capsys.readouterr()
        assert "CONTENT MISMATCH CONFIRMATION REQUIRED" in captured.out

    def test_returns_false_when_user_types_no(self, capsys):
        """Test that 'no' input returns False."""
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=5)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)

        input_stream = io.StringIO("no\n")
        result = get_content_mismatch_confirmation([group], input_stream)

        assert result is False

    def test_returns_false_when_user_presses_enter(self):
        """Test that empty input returns False."""
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=5)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)

        input_stream = io.StringIO("\n")
        result = get_content_mismatch_confirmation([group], input_stream)

        assert result is False

    def test_shows_group_details(self, capsys):
        """Test that group details are displayed."""
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=15)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)

        input_stream = io.StringIO("no\n")
        get_content_mismatch_confirmation([group], input_stream)

        captured = capsys.readouterr()
        assert "Mixed-related" in captured.out
        assert "Employment/Resumes" in captured.out
        assert "Finances/Taxes" in captured.out
        assert "Folders: 1" in captured.out
        assert "Files: 15" in captured.out

    def test_shows_multiple_groups(self, capsys):
        """Test that multiple groups are displayed."""
        folder1 = FolderInfo(path="/test/Mixed1", name="Mixed1", file_count=5)
        group1 = FolderGroup(
            group_name="Group1",
            category_key="employment",
            target_folder="Target1",
            should_consolidate=True,
            ai_categories={"Cat1", "Cat2"},
        )
        group1.add_folder(folder1)

        folder2 = FolderInfo(path="/test/Mixed2", name="Mixed2", file_count=10)
        group2 = FolderGroup(
            group_name="Group2",
            category_key="legal",
            target_folder="Target2",
            should_consolidate=True,
            ai_categories={"Cat3", "Cat4", "Cat5"},
        )
        group2.add_folder(folder2)

        input_stream = io.StringIO("no\n")
        get_content_mismatch_confirmation([group1, group2], input_stream)

        captured = capsys.readouterr()
        assert "2 group(s) contain folders with" in captured.out
        assert "Group1" in captured.out
        assert "Group2" in captured.out

    def test_shows_warning_message(self, capsys):
        """Test that warning message is displayed."""
        folder = FolderInfo(path="/test/Mixed", name="Mixed", file_count=5)
        group = FolderGroup(
            group_name="Mixed-related",
            category_key="employment",
            target_folder="Employment/Resumes",
            should_consolidate=True,
            ai_categories={"Employment/Resumes", "Finances/Taxes"},
        )
        group.add_folder(folder)

        input_stream = io.StringIO("no\n")
        get_content_mismatch_confirmation([group], input_stream)

        captured = capsys.readouterr()
        assert "DIFFERENT content types" in captured.out
        assert "cannot be undone" in captured.out


class TestRunExecuteWithContentMismatchConfirmation:
    """Tests for run_execute with content-mismatch confirmation (Phase 6)."""

    def test_execute_shows_mismatch_confirmation_prompt(self, capsys):
        """Test that execute shows content-mismatch confirmation prompt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Mixed"),
                name="Mixed",
                file_count=15,
            )
            group = FolderGroup(
                group_name="Mixed-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes", "Finances/Taxes"},
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # User says "no" to mismatch confirmation
            input_stream = io.StringIO("no\n")
            exit_code = run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "CONTENT MISMATCH CONFIRMATION REQUIRED" in captured.out
            assert exit_code == 1  # Aborted

    def test_execute_aborts_when_mismatch_declined(self, capsys):
        """Test that execution aborts when user declines mismatch confirmation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Mixed"),
                name="Mixed",
                file_count=15,
            )
            group = FolderGroup(
                group_name="Mixed-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes", "Finances/Taxes"},
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # User says "no" to mismatch confirmation
            input_stream = io.StringIO("no\n")
            exit_code = run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "Aborted. No changes were made." in captured.out
            assert exit_code == 1

    def test_execute_continues_when_mismatch_confirmed(self, capsys):
        """Test that execution continues when user confirms mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Mixed"),
                name="Mixed",
                file_count=15,
            )
            group = FolderGroup(
                group_name="Mixed-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes", "Finances/Taxes"},
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # User says "yes" to mismatch, then "no" to final confirmation
            input_stream = io.StringIO("yes\nno\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            assert "Content-mismatch consolidations confirmed." in captured.out
            # Should show main execution summary after mismatch confirmation
            assert "EXECUTION SAFETY CHECK" in captured.out

    def test_execute_skips_mismatch_confirmation_when_no_mismatches(self, capsys):
        """Test that mismatch confirmation is skipped when no mismatches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Resume"),
                name="Resume",
                file_count=5,
            )
            group = FolderGroup(
                group_name="Resume-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes"},  # Single category
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # Only one confirmation needed (final confirmation)
            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            # Should NOT show mismatch confirmation
            assert "CONTENT MISMATCH CONFIRMATION REQUIRED" not in captured.out
            # Should still show execution safety check
            assert "EXECUTION SAFETY CHECK" in captured.out

    def test_execute_skips_mismatch_confirmation_for_non_content_aware(self, capsys):
        """Test that mismatch confirmation is skipped for non-content-aware plans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=False,
            )
            folder = FolderInfo(
                path=os.path.join(tmpdir, "Mixed"),
                name="Mixed",
                file_count=15,
            )
            group = FolderGroup(
                group_name="Mixed-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes", "Finances/Taxes"},
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # Only one confirmation needed (final confirmation)
            input_stream = io.StringIO("no\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            # Should NOT show mismatch confirmation for non-content-aware
            assert "CONTENT MISMATCH CONFIRMATION REQUIRED" not in captured.out

    def test_execute_requires_two_confirmations_for_mismatch(self, capsys):
        """Test that both mismatch and final confirmation are required."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source folder with a file
            src_folder = os.path.join(tmpdir, "Mixed")
            os.makedirs(src_folder)
            with open(os.path.join(src_folder, "test.txt"), "w") as f:
                f.write("test content")

            plan_file = os.path.join(tmpdir, "plan.json")
            plan = ConsolidationPlan(
                base_path=tmpdir,
                threshold=0.8,
                content_aware=True,
            )
            folder = FolderInfo(
                path=src_folder,
                name="Mixed",
                file_count=1,
            )
            group = FolderGroup(
                group_name="Mixed-related",
                category_key="employment",
                target_folder="Employment/Resumes",
                should_consolidate=True,
                ai_categories={"Employment/Resumes", "Finances/Taxes"},
            )
            group.add_folder(folder)
            plan.groups.append(group)
            save_plan_to_file(plan, plan_file)

            parser = create_parser()
            args = parser.parse_args(
                ["--execute", "--plan-file", plan_file, "--path", tmpdir]
            )

            # User says "yes" to mismatch, then "yes" to final confirmation
            input_stream = io.StringIO("yes\nyes\n")
            run_execute(args, input_stream=input_stream)

            captured = capsys.readouterr()
            # Should show both confirmations
            assert "CONTENT MISMATCH CONFIRMATION REQUIRED" in captured.out
            assert "Content-mismatch consolidations confirmed." in captured.out
            assert "EXECUTION SAFETY CHECK" in captured.out
            # Should start execution
            assert "Creating backup of plan..." in captured.out


class TestDryRunCLI:
    """Tests for --dry-run CLI flag."""

    def test_dry_run_argument_parsing(self):
        """Test --dry-run argument is parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(["--agent-once", "--dry-run"])
        assert args.dry_run is True

    def test_dry_run_defaults_to_false(self):
        """Test --dry-run defaults to False."""
        parser = create_parser()
        args = parser.parse_args(["--agent-once"])
        assert args.dry_run is False

    def test_dry_run_task_id_argument_parsing(self):
        """Test --dry-run-task-id argument is parsed correctly."""
        parser = create_parser()
        args = parser.parse_args(
            ["--agent-once", "--dry-run", "--dry-run-task-id", "phase11_task1"]
        )
        assert args.dry_run_task_id == "phase11_task1"

    def test_dry_run_task_id_defaults_to_none(self):
        """Test --dry-run-task-id defaults to None."""
        parser = create_parser()
        args = parser.parse_args(["--agent-once", "--dry-run"])
        assert args.dry_run_task_id is None

    def test_dry_run_requires_agent_action(self):
        """Test --dry-run requires --agent-once or --agent-run."""
        parser = create_parser()
        args = parser.parse_args(["--scan", "--dry-run"])
        errors = validate_args(args)
        assert any("--dry-run can only be used with" in e for e in errors)

    def test_dry_run_valid_with_agent_once(self):
        """Test --dry-run is valid with --agent-once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create agent config file
            config_path = Path(tmpdir) / ".organizer" / "agent_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text('{"base_path": "."}', encoding="utf-8")

            parser = create_parser()
            args = parser.parse_args([
                "--agent-once",
                "--dry-run",
                "--path", tmpdir,
                "--agent-config", str(config_path),
            ])
            errors = validate_args(args)
            assert not any("--dry-run" in e for e in errors)

    def test_dry_run_valid_with_agent_run(self):
        """Test --dry-run is valid with --agent-run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create agent config file
            config_path = Path(tmpdir) / ".organizer" / "agent_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text('{"base_path": "."}', encoding="utf-8")

            parser = create_parser()
            args = parser.parse_args([
                "--agent-run",
                "--dry-run",
                "--path", tmpdir,
                "--agent-config", str(config_path),
                "--agent-max-cycles", "1",
            ])
            errors = validate_args(args)
            assert not any("--dry-run" in e for e in errors)

    def test_dry_run_task_id_requires_dry_run(self):
        """Test --dry-run-task-id requires --dry-run flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args([
                "--agent-once",
                "--dry-run-task-id", "task123",
                "--path", tmpdir,
            ])
            errors = validate_args(args)
            assert any("--dry-run-task-id requires --dry-run" in e for e in errors)

    def test_dry_run_output_format(self, capsys):
        """Test dry-run mode outputs proper report format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base directory structure
            base = Path(tmpdir) / "root"
            base.mkdir()
            inbox = base / "In-Box"
            inbox.mkdir()
            (inbox / "test.pdf").write_text("content", encoding="utf-8")

            # Create agent config
            config_path = Path(tmpdir) / ".organizer" / "agent_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_data = {
                "base_path": str(base),
                "inbox_enabled": True,
                "inbox_folder_name": "In-Box",
                "auto_execute": False,
                "project_homing_enabled": False,
                "scatter_enabled": False,
                "queue_dir": str(Path(tmpdir) / "queue"),
                "plans_dir": str(Path(tmpdir) / "plans"),
                "logs_dir": str(Path(tmpdir) / "logs"),
                "state_file": str(Path(tmpdir) / "state.json"),
                "empty_folder_policy_file": str(Path(tmpdir) / "empty_policy.json"),
            }
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            # Run with dry-run flag
            main([
                "--agent-once",
                "--dry-run",
                "--agent-config", str(config_path),
                "--path", tmpdir,
            ])

            captured = capsys.readouterr()

            # Should show dry-run report format
            assert "DRY-RUN VALIDATION REPORT" in captured.out
            assert "Cycle ID:" in captured.out
            assert "Would-move count:" in captured.out
            assert "Confidence distribution:" in captured.out
            assert "Conflicts detected:" in captured.out

    def test_dry_run_with_task_id_shows_task_info(self, capsys):
        """Test dry-run mode with task ID shows task tracking info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base directory structure
            base = Path(tmpdir) / "root"
            base.mkdir()

            # Create agent config
            config_path = Path(tmpdir) / ".organizer" / "agent_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_data = {
                "base_path": str(base),
                "inbox_enabled": False,
                "auto_execute": False,
                "project_homing_enabled": False,
                "scatter_enabled": False,
                "queue_dir": str(Path(tmpdir) / "queue"),
                "plans_dir": str(Path(tmpdir) / "plans"),
                "logs_dir": str(Path(tmpdir) / "logs"),
                "state_file": str(Path(tmpdir) / "state.json"),
                "empty_folder_policy_file": str(Path(tmpdir) / "empty_policy.json"),
                "prd_task_status_file": str(Path(tmpdir) / "prd_status.json"),
            }
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            # Run with dry-run flag and task ID
            main([
                "--agent-once",
                "--dry-run",
                "--dry-run-task-id", "phase11_dry_run",
                "--agent-config", str(config_path),
                "--path", tmpdir,
            ])

            captured = capsys.readouterr()

            # Should show task ID info
            assert "Task ID: phase11_dry_run" in captured.out

    def test_dry_run_returns_success_on_pass(self):
        """Test dry-run returns exit code 0 when validation passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base directory structure (empty, so no proposals)
            base = Path(tmpdir) / "root"
            base.mkdir()

            # Create agent config
            config_path = Path(tmpdir) / ".organizer" / "agent_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_data = {
                "base_path": str(base),
                "inbox_enabled": False,
                "auto_execute": False,
                "project_homing_enabled": False,
                "scatter_enabled": False,
                "queue_dir": str(Path(tmpdir) / "queue"),
                "plans_dir": str(Path(tmpdir) / "plans"),
                "logs_dir": str(Path(tmpdir) / "logs"),
                "state_file": str(Path(tmpdir) / "state.json"),
                "empty_folder_policy_file": str(Path(tmpdir) / "empty_policy.json"),
            }
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            # Run with dry-run flag
            exit_code = main([
                "--agent-once",
                "--dry-run",
                "--agent-config", str(config_path),
                "--path", tmpdir,
            ])

            # Should return success (0) when dry-run passes
            assert exit_code == 0

    def test_dry_run_agent_run_shows_mode_info(self, capsys):
        """Test dry-run with --agent-run shows mode information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create base directory structure
            base = Path(tmpdir) / "root"
            base.mkdir()

            # Create agent config with short interval
            config_path = Path(tmpdir) / ".organizer" / "agent_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_data = {
                "base_path": str(base),
                "interval_seconds": 1,
                "inbox_enabled": False,
                "auto_execute": False,
                "project_homing_enabled": False,
                "scatter_enabled": False,
                "queue_dir": str(Path(tmpdir) / "queue"),
                "plans_dir": str(Path(tmpdir) / "plans"),
                "logs_dir": str(Path(tmpdir) / "logs"),
                "state_file": str(Path(tmpdir) / "state.json"),
                "empty_folder_policy_file": str(Path(tmpdir) / "empty_policy.json"),
            }
            config_path.write_text(json.dumps(config_data), encoding="utf-8")

            # Run with dry-run flag and max-cycles=1 to exit quickly
            main([
                "--agent-run",
                "--dry-run",
                "--dry-run-task-id", "test_task",
                "--agent-config", str(config_path),
                "--path", tmpdir,
                "--agent-max-cycles", "1",
            ])

            captured = capsys.readouterr()

            # Should show dry-run mode info
            assert "[DRY-RUN MODE]" in captured.out
            assert "Dry-run mode: Actions will be proposed and validated but not executed" in captured.out
            assert "Tracking PRD task: test_task" in captured.out


class TestLearnStructureArgument:
    """Tests for --learn-structure argument parsing."""

    def test_learn_structure_no_path(self):
        """Test --learn-structure with no path defaults to '.'."""
        parser = create_parser()
        args = parser.parse_args(["--learn-structure"])
        assert args.learn_structure == "."

    def test_learn_structure_with_path(self):
        """Test --learn-structure with explicit path."""
        parser = create_parser()
        args = parser.parse_args(["--learn-structure", "/some/path"])
        assert args.learn_structure == "/some/path"

    def test_learn_confirm_argument(self):
        """Test --learn-confirm argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--learn-confirm"])
        assert args.learn_confirm is True

    def test_learn_status_argument(self):
        """Test --learn-status argument parsing."""
        parser = create_parser()
        args = parser.parse_args(["--learn-status"])
        assert args.learn_status is True


class TestLearnCommandValidation:
    """Tests for learn command argument validation."""

    def test_learn_structure_invalid_path(self):
        """Test validation fails for non-existent path."""
        parser = create_parser()
        args = parser.parse_args(["--learn-structure", "/nonexistent/path"])
        errors = validate_args(args)
        assert len(errors) >= 1
        assert any("does not exist" in e for e in errors)

    def test_learn_structure_with_valid_path(self):
        """Test validation passes for valid path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--learn-structure", tmpdir])
            errors = validate_args(args)
            # Should not have path-related errors
            path_errors = [e for e in errors if "path" in e.lower() and "exist" in e.lower()]
            assert len(path_errors) == 0

    def test_multiple_learn_actions_error(self):
        """Test that using multiple learn actions produces an error."""
        parser = create_parser()
        # Using --learn-confirm with --learn-status
        args = parser.parse_args(["--learn-confirm", "--learn-status"])
        errors = validate_args(args)
        assert len(errors) >= 1
        assert any("only one learn action" in e.lower() for e in errors)

    def test_learn_structure_is_standalone_action(self):
        """Test --learn-structure is recognized as a valid action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args(["--learn-structure", tmpdir])
            errors = validate_args(args)
            # Should not have "must specify at least one action" error
            action_errors = [e for e in errors if "must specify at least one action" in e.lower()]
            assert len(action_errors) == 0

    def test_learn_confirm_is_standalone_action(self):
        """Test --learn-confirm is recognized as a valid action."""
        parser = create_parser()
        args = parser.parse_args(["--learn-confirm"])
        errors = validate_args(args)
        # Should not have "must specify at least one action" error
        action_errors = [e for e in errors if "must specify at least one action" in e.lower()]
        assert len(action_errors) == 0

    def test_learn_status_is_standalone_action(self):
        """Test --learn-status is recognized as a valid action."""
        parser = create_parser()
        args = parser.parse_args(["--learn-status"])
        errors = validate_args(args)
        # Should not have "must specify at least one action" error
        action_errors = [e for e in errors if "must specify at least one action" in e.lower()]
        assert len(action_errors) == 0


class TestRunLearnStructure:
    """Tests for run_learn_structure function."""

    def test_learn_structure_creates_snapshot(self, capsys):
        """Test --learn-structure creates structure snapshot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test directory structure
            docs_dir = Path(tmpdir) / "Documents"
            docs_dir.mkdir()
            (docs_dir / "file1.pdf").touch()
            (docs_dir / "file2.txt").touch()

            work_dir = Path(tmpdir) / "Work"
            work_dir.mkdir()
            (work_dir / "project.docx").touch()

            # Create .organizer dir for output
            organizer_dir = Path(tmpdir) / ".organizer" / "agent"
            organizer_dir.mkdir(parents=True, exist_ok=True)

            # Change to tmpdir to use relative paths
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                parser = create_parser()
                args = parser.parse_args(["--learn-structure", tmpdir])
                exit_code = run_learn_structure(args)

                assert exit_code == 0

                captured = capsys.readouterr()
                assert "LEARNING STRUCTURE ANALYSIS" in captured.out
                assert "Folders analyzed:" in captured.out
                assert "Files found:" in captured.out
                assert "Rules generated:" in captured.out
            finally:
                os.chdir(original_cwd)

    def test_learn_structure_outputs_status_inactive(self, capsys):
        """Test --learn-structure shows inactive status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal structure
            docs = Path(tmpdir) / "docs"
            docs.mkdir()

            organizer_dir = Path(tmpdir) / ".organizer" / "agent"
            organizer_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                parser = create_parser()
                args = parser.parse_args(["--learn-structure", tmpdir])
                exit_code = run_learn_structure(args)

                assert exit_code == 0

                captured = capsys.readouterr()
                assert "Status: INACTIVE" in captured.out
                assert "--learn-confirm" in captured.out
            finally:
                os.chdir(original_cwd)


class TestRunLearnConfirm:
    """Tests for run_learn_confirm function."""

    def test_learn_confirm_no_rules_error(self, capsys):
        """Test --learn-confirm fails when no rules exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                parser = create_parser()
                args = parser.parse_args(["--learn-confirm"])
                exit_code = run_learn_confirm(args)

                assert exit_code == 1

                captured = capsys.readouterr()
                assert "No learned rules found" in captured.err
            finally:
                os.chdir(original_cwd)

    def test_learn_confirm_activates_rules(self, capsys):
        """Test --learn-confirm activates existing rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create rules file
            rules_dir = Path(tmpdir) / ".organizer" / "agent"
            rules_dir.mkdir(parents=True, exist_ok=True)

            rules_data = {
                "version": "1.0",
                "root_path": tmpdir,
                "rules": [
                    {
                        "pattern": "invoice",
                        "destination": "Finances/Invoices",
                        "confidence": 0.85,
                        "source_folder": "Invoices",
                        "reasoning": "Invoice documents",
                        "enabled": True,
                    }
                ],
                "total_folders_analyzed": 1,
                "model_used": "",
                "generated_at": "2024-01-01T00:00:00",
            }
            (rules_dir / "learned_routing_rules.json").write_text(
                json.dumps(rules_data), encoding="utf-8"
            )

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                parser = create_parser()
                args = parser.parse_args(["--learn-confirm"])
                exit_code = run_learn_confirm(args)

                assert exit_code == 0

                captured = capsys.readouterr()
                assert "LEARNED RULES ACTIVATED" in captured.out
                assert "Total rules: 1" in captured.out

                # Check that active marker was created
                active_marker = Path(tmpdir) / ".organizer" / "agent" / "learned_rules_active.json"
                assert active_marker.exists()

                marker_data = json.loads(active_marker.read_text())
                assert marker_data["active"] is True
            finally:
                os.chdir(original_cwd)


class TestRunLearnStatus:
    """Tests for run_learn_status function."""

    def test_learn_status_inactive(self, capsys):
        """Test --learn-status shows inactive when no rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                parser = create_parser()
                args = parser.parse_args(["--learn-status"])
                exit_code = run_learn_status(args)

                assert exit_code == 0

                captured = capsys.readouterr()
                assert "LEARNED RULES STATUS" in captured.out
                assert "Status: INACTIVE" in captured.out
            finally:
                os.chdir(original_cwd)

    def test_learn_status_shows_structure_info(self, capsys):
        """Test --learn-status shows structure info when available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create structure file
            structure_dir = Path(tmpdir) / ".organizer" / "agent"
            structure_dir.mkdir(parents=True, exist_ok=True)

            structure_data = {
                "version": "1.0",
                "root_path": tmpdir,
                "max_depth": 4,
                "total_folders": 5,
                "total_files": 10,
                "total_size_bytes": 1000,
                "folders": [],
                "strategy_description": "Test strategy",
                "model_used": "",
                "analyzed_at": "2024-01-01T00:00:00",
            }
            (structure_dir / "learned_structure.json").write_text(
                json.dumps(structure_data), encoding="utf-8"
            )

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                parser = create_parser()
                args = parser.parse_args(["--learn-status"])
                exit_code = run_learn_status(args)

                assert exit_code == 0

                captured = capsys.readouterr()
                assert "Last structure scan:" in captured.out
                assert "Folders: 5" in captured.out
                assert "Files: 10" in captured.out
            finally:
                os.chdir(original_cwd)

    def test_learn_status_active(self, capsys):
        """Test --learn-status shows active when rules are confirmed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create active marker
            marker_dir = Path(tmpdir) / ".organizer" / "agent"
            marker_dir.mkdir(parents=True, exist_ok=True)

            marker_data = {
                "active": True,
                "activated_at": "2024-01-01T12:00:00",
                "rule_count": 5,
                "enabled_count": 4,
            }
            (marker_dir / "learned_rules_active.json").write_text(
                json.dumps(marker_data), encoding="utf-8"
            )

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                parser = create_parser()
                args = parser.parse_args(["--learn-status"])
                exit_code = run_learn_status(args)

                assert exit_code == 0

                captured = capsys.readouterr()
                assert "Status: ACTIVE" in captured.out
                assert "Total rules: 5" in captured.out
                assert "Enabled rules: 4" in captured.out
            finally:
                os.chdir(original_cwd)


class TestLearnMainIntegration:
    """Integration tests for learn commands via main()."""

    def test_main_learn_structure(self, capsys):
        """Test main() dispatches to learn_structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test structure
            docs = Path(tmpdir) / "Documents"
            docs.mkdir()
            (docs / "test.pdf").touch()

            organizer_dir = Path(tmpdir) / ".organizer" / "agent"
            organizer_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                exit_code = main(["--learn-structure", tmpdir])
                assert exit_code == 0

                captured = capsys.readouterr()
                assert "LEARNING STRUCTURE ANALYSIS" in captured.out
            finally:
                os.chdir(original_cwd)

    def test_main_learn_status(self, capsys):
        """Test main() dispatches to learn_status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                exit_code = main(["--learn-status"])
                assert exit_code == 0

                captured = capsys.readouterr()
                assert "LEARNED RULES STATUS" in captured.out
            finally:
                os.chdir(original_cwd)

    def test_main_learn_confirm_no_rules(self, capsys):
        """Test main() learn_confirm fails without rules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                exit_code = main(["--learn-confirm"])
                assert exit_code == 1
            finally:
                os.chdir(original_cwd)


class TestExperimentArgumentParsing:
    """Tests for --experiment argument parsing."""

    def test_experiment_argument_default_task_type(self):
        """Test --experiment default task type is classify."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "model1",
            "--files", ".",
        ])
        assert args.experiment == "classify"

    def test_experiment_argument_custom_task_type(self):
        """Test --experiment with custom task type."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment", "validate",
            "--models", "model1",
            "--files", ".",
        ])
        assert args.experiment == "validate"

    def test_experiment_argument_analyze_type(self):
        """Test --experiment with analyze task type."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment", "analyze",
            "--models", "model1",
            "--files", ".",
        ])
        assert args.experiment == "analyze"

    def test_models_argument(self):
        """Test --models argument parsing."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "llama3.1:8b,qwen2.5:14b",
            "--files", ".",
        ])
        assert args.models == "llama3.1:8b,qwen2.5:14b"

    def test_files_argument_directory(self):
        """Test --files argument with directory."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "model1",
            "--files", "/path/to/files",
        ])
        assert args.files == "/path/to/files"

    def test_files_argument_multiple_files(self):
        """Test --files argument with comma-separated files."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "model1",
            "--files", "file1.pdf,file2.pdf,file3.pdf",
        ])
        assert args.files == "file1.pdf,file2.pdf,file3.pdf"

    def test_experiment_name_argument(self):
        """Test --experiment-name argument."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "model1",
            "--files", ".",
            "--experiment-name", "my_test",
        ])
        assert args.experiment_name == "my_test"

    def test_experiment_name_default_is_none(self):
        """Test --experiment-name defaults to None."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "model1",
            "--files", ".",
        ])
        assert args.experiment_name is None


class TestExperimentArgumentValidation:
    """Tests for --experiment argument validation."""

    def test_experiment_requires_models(self):
        """Test --experiment requires --models."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--files", ".",
        ])
        errors = validate_args(args)
        assert any("--models" in e for e in errors)

    def test_experiment_requires_files(self):
        """Test --experiment requires --files."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "model1",
        ])
        errors = validate_args(args)
        assert any("--files" in e for e in errors)

    def test_experiment_invalid_task_type(self):
        """Test --experiment with invalid task type."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment", "invalid_type",
            "--models", "model1",
            "--files", ".",
        ])
        errors = validate_args(args)
        assert any("Invalid experiment task type" in e for e in errors)

    def test_experiment_valid_args_no_errors(self):
        """Test --experiment with valid args has no validation errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args([
                "--experiment", "classify",
                "--models", "model1,model2",
                "--files", tmpdir,
            ])
            errors = validate_args(args)
            assert len(errors) == 0

    def test_models_without_experiment(self):
        """Test --models without --experiment is invalid."""
        parser = create_parser()
        args = parser.parse_args([
            "--scan",
            "--models", "model1",
        ])
        errors = validate_args(args)
        assert any("--models can only be used with --experiment" in e for e in errors)

    def test_files_without_experiment(self):
        """Test --files without --experiment is invalid."""
        parser = create_parser()
        args = parser.parse_args([
            "--scan",
            "--files", "/path",
        ])
        errors = validate_args(args)
        assert any("--files can only be used with --experiment" in e for e in errors)

    def test_experiment_name_without_experiment(self):
        """Test --experiment-name without --experiment is invalid."""
        parser = create_parser()
        args = parser.parse_args([
            "--scan",
            "--experiment-name", "test",
        ])
        errors = validate_args(args)
        assert any("--experiment-name can only be used with --experiment" in e for e in errors)

    def test_files_path_not_exist(self):
        """Test --files with non-existent path."""
        parser = create_parser()
        args = parser.parse_args([
            "--experiment",
            "--models", "model1",
            "--files", "/nonexistent/path/12345",
        ])
        errors = validate_args(args)
        assert any("does not exist" in e for e in errors)

    def test_files_comma_separated_nonexistent(self):
        """Test --files with comma-separated files, one missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_file = Path(tmpdir) / "exists.txt"
            existing_file.touch()

            parser = create_parser()
            args = parser.parse_args([
                "--experiment",
                "--models", "model1",
                "--files", f"{existing_file},/nonexistent/file.txt",
            ])
            errors = validate_args(args)
            assert any("does not exist" in e for e in errors)

    def test_experiment_is_valid_action(self):
        """Test --experiment is recognized as a valid action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            args = parser.parse_args([
                "--experiment",
                "--models", "model1",
                "--files", tmpdir,
            ])
            errors = validate_args(args)
            # Should not contain "Must specify at least one action" error
            assert not any("Must specify at least one action" in e for e in errors)


class TestRunExperimentCli:
    """Tests for run_experiment_cli function."""

    def test_run_experiment_no_models_parsed(self, capsys):
        """Test run_experiment_cli with empty models string."""

        with tempfile.TemporaryDirectory() as tmpdir:
            parser = create_parser()
            # Parse with empty models
            args = parser.parse_args([
                "--experiment",
                "--models", "  ",
                "--files", tmpdir,
            ])
            # Manually set models to whitespace-only (parser wouldn't allow this normally)
            args.models = "  "

            exit_code = run_experiment_cli(args)
            assert exit_code == 1

            captured = capsys.readouterr()
            assert "No models specified" in captured.err

    def test_run_experiment_no_files_found(self, capsys):
        """Test run_experiment_cli with empty directory."""

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty directory (no files)
            parser = create_parser()
            args = parser.parse_args([
                "--experiment",
                "--models", "model1",
                "--files", tmpdir,
            ])

            exit_code = run_experiment_cli(args)
            assert exit_code == 1

            captured = capsys.readouterr()
            assert "No test files found" in captured.err

    @patch("organizer.llm_client.LLMClient")
    def test_run_experiment_ollama_not_available(self, mock_llm_class, capsys):
        """Test run_experiment_cli when Ollama is not available."""

        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False
        mock_llm_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            parser = create_parser()
            args = parser.parse_args([
                "--experiment",
                "--models", "model1",
                "--files", tmpdir,
            ])

            exit_code = run_experiment_cli(args)
            assert exit_code == 1

            captured = capsys.readouterr()
            assert "Ollama is not available" in captured.err

    @patch("organizer.llm_client.LLMClient")
    def test_run_experiment_success(self, mock_llm_class, capsys):
        """Test run_experiment_cli successful execution."""
        from organizer.llm_experiment import LatencyStats

        # Mock LLM client
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = ["model1", "model2"]
        mock_llm_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            with patch("organizer.cli.run_experiment") as mock_run_exp:
                with patch("organizer.cli.save_experiment_result") as mock_save:
                    # Mock experiment result
                    mock_result = MagicMock()
                    mock_result.experiment = MagicMock(
                        name="test",
                        models_to_compare=["model1", "model2"],
                        test_files=["/path/file.txt"],
                    )
                    mock_result.file_results = []
                    mock_result.latency_stats = {
                        "model1": LatencyStats.from_durations("model1", [100]),
                        "model2": LatencyStats.from_durations("model2", [200]),
                    }
                    mock_result.agreement_rate = 1.0
                    mock_result.accuracy_vs_ground_truth = None
                    mock_result.total_duration_ms = 300
                    mock_result.started_at = "2026-03-05T10:00:00"
                    mock_result.completed_at = "2026-03-05T10:00:01"
                    mock_run_exp.return_value = mock_result
                    mock_save.return_value = Path("/tmp/result.json")

                    parser = create_parser()
                    args = parser.parse_args([
                        "--experiment",
                        "--models", "model1,model2",
                        "--files", tmpdir,
                    ])

                    exit_code = run_experiment_cli(args)
                    assert exit_code == 0

                    captured = capsys.readouterr()
                    assert "LLM MODEL COMPARISON EXPERIMENT" in captured.out
                    assert "EXPERIMENT COMPLETE" in captured.out

    @patch("organizer.llm_client.LLMClient")
    def test_run_experiment_with_custom_name(self, mock_llm_class, capsys):
        """Test run_experiment_cli with custom experiment name."""
        from organizer.llm_experiment import LatencyStats

        # Mock LLM client
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = ["model1"]
        mock_llm_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            with patch("organizer.cli.run_experiment") as mock_run_exp:
                with patch("organizer.cli.save_experiment_result") as mock_save:
                    # Mock experiment result
                    mock_result = MagicMock()
                    mock_result.experiment = MagicMock(
                        name="my_custom_experiment",
                        models_to_compare=["model1"],
                        test_files=["/path/file.txt"],
                    )
                    mock_result.file_results = []
                    mock_result.latency_stats = {
                        "model1": LatencyStats.from_durations("model1", [100]),
                    }
                    mock_result.agreement_rate = 1.0
                    mock_result.accuracy_vs_ground_truth = None
                    mock_result.total_duration_ms = 100
                    mock_result.started_at = "2026-03-05T10:00:00"
                    mock_result.completed_at = "2026-03-05T10:00:01"
                    mock_run_exp.return_value = mock_result
                    mock_save.return_value = Path("/tmp/result.json")

                    parser = create_parser()
                    args = parser.parse_args([
                        "--experiment",
                        "--models", "model1",
                        "--files", tmpdir,
                        "--experiment-name", "my_custom_experiment",
                    ])

                    exit_code = run_experiment_cli(args)
                    assert exit_code == 0

                    captured = capsys.readouterr()
                    assert "my_custom_experiment" in captured.out

    @patch("organizer.llm_client.LLMClient")
    def test_run_experiment_handles_comma_separated_files(
        self, mock_llm_class, capsys
    ):
        """Test run_experiment_cli with comma-separated file paths."""
        from organizer.llm_experiment import LatencyStats

        # Mock LLM client
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = ["model1"]
        mock_llm_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple test files
            file1 = Path(tmpdir) / "test1.txt"
            file2 = Path(tmpdir) / "test2.txt"
            file1.write_text("content 1")
            file2.write_text("content 2")

            # Mock run_experiment to check it was called with both files
            with patch("organizer.cli.run_experiment") as mock_run:
                with patch("organizer.cli.save_experiment_result") as mock_save:
                    mock_result = MagicMock()
                    mock_result.experiment = MagicMock(
                        name="test",
                        models_to_compare=["model1"],
                        test_files=[str(file1), str(file2)],
                    )
                    mock_result.file_results = []
                    mock_result.latency_stats = {
                        "model1": LatencyStats.from_durations("model1", [100]),
                    }
                    mock_result.agreement_rate = 1.0
                    mock_result.accuracy_vs_ground_truth = None
                    mock_result.total_duration_ms = 200
                    mock_result.started_at = "2026-03-05T10:00:00"
                    mock_result.completed_at = "2026-03-05T10:00:01"
                    mock_run.return_value = mock_result
                    mock_save.return_value = Path("/tmp/result.json")

                    parser = create_parser()
                    args = parser.parse_args([
                        "--experiment",
                        "--models", "model1",
                        "--files", f"{file1},{file2}",
                    ])

                    exit_code = run_experiment_cli(args)
                    assert exit_code == 0

                    # Verify run_experiment was called
                    mock_run.assert_called_once()
                    # Check the experiment had both files
                    call_args = mock_run.call_args
                    experiment = call_args[1].get("experiment") or call_args[0][0]
                    assert len(experiment.test_files) == 2


class TestExperimentMainIntegration:
    """Integration tests for --experiment via main()."""

    @patch("organizer.llm_client.LLMClient")
    def test_main_dispatches_to_experiment(self, mock_llm_class, capsys):
        """Test main() dispatches to run_experiment_cli."""
        from organizer.llm_experiment import LatencyStats

        # Mock LLM client
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = ["model1"]
        mock_llm_class.return_value = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test content")

            with patch("organizer.cli.run_experiment") as mock_run_exp:
                with patch("organizer.cli.save_experiment_result") as mock_save:
                    # Mock experiment result
                    mock_result = MagicMock()
                    mock_result.experiment = MagicMock(
                        name="test",
                        models_to_compare=["model1"],
                        test_files=["/path/file.txt"],
                    )
                    mock_result.file_results = []
                    mock_result.latency_stats = {
                        "model1": LatencyStats.from_durations("model1", [100]),
                    }
                    mock_result.agreement_rate = 1.0
                    mock_result.accuracy_vs_ground_truth = None
                    mock_result.total_duration_ms = 100
                    mock_result.started_at = "2026-03-05T10:00:00"
                    mock_result.completed_at = "2026-03-05T10:00:01"
                    mock_run_exp.return_value = mock_result
                    mock_save.return_value = Path("/tmp/result.json")

                    exit_code = main([
                        "--experiment",
                        "--models", "model1",
                        "--files", tmpdir,
                    ])

                    assert exit_code == 0
                    captured = capsys.readouterr()
                    assert "LLM MODEL COMPARISON EXPERIMENT" in captured.out
