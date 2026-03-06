"""Tests for LLM Experiment Framework."""

import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from organizer.llm_experiment import (
    Experiment,
    ExperimentResult,
    FileResults,
    LatencyStats,
    ModelResult,
    generate_comparison_table,
    list_experiment_results,
    load_experiment_result,
    run_experiment,
    save_experiment_result,
)


class TestModelResult:
    """Tests for ModelResult dataclass."""

    def test_create_model_result(self) -> None:
        """Should create a ModelResult with all fields."""
        result = ModelResult(
            model="llama3.1:8b",
            file_path="/path/to/file.pdf",
            response_text='{"bin": "Finances", "confidence": 0.95}',
            parsed_result={"bin": "Finances", "confidence": 0.95},
            confidence=0.95,
            duration_ms=1500,
            success=True,
        )
        assert result.model == "llama3.1:8b"
        assert result.file_path == "/path/to/file.pdf"
        assert result.confidence == 0.95
        assert result.success is True
        assert result.error == ""

    def test_model_result_with_error(self) -> None:
        """Should create a failed ModelResult with error."""
        result = ModelResult(
            model="llama3.1:8b",
            file_path="/path/to/file.pdf",
            response_text="",
            parsed_result=None,
            confidence=None,
            duration_ms=0,
            success=False,
            error="Connection timeout",
        )
        assert result.success is False
        assert result.error == "Connection timeout"

    def test_model_result_to_dict(self) -> None:
        """Should convert to dictionary."""
        result = ModelResult(
            model="llama3.1:8b",
            file_path="/path/to/file.pdf",
            response_text="test",
            parsed_result={"bin": "Test"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        d = result.to_dict()
        assert d["model"] == "llama3.1:8b"
        assert d["confidence"] == 0.9
        assert d["success"] is True

    def test_model_result_from_dict(self) -> None:
        """Should create from dictionary."""
        data = {
            "model": "qwen2.5:14b",
            "file_path": "/path/file.txt",
            "response_text": "response",
            "parsed_result": {"bin": "Work"},
            "confidence": 0.85,
            "duration_ms": 2000,
            "success": True,
            "error": "",
        }
        result = ModelResult.from_dict(data)
        assert result.model == "qwen2.5:14b"
        assert result.confidence == 0.85


class TestFileResults:
    """Tests for FileResults dataclass."""

    def test_create_file_results(self) -> None:
        """Should create FileResults with results dict."""
        file_results = FileResults(file_path="/path/to/file.pdf")
        assert file_results.file_path == "/path/to/file.pdf"
        assert file_results.results == {}
        assert file_results.ground_truth is None

    def test_agreement_count_empty(self) -> None:
        """Should return 0 for empty results."""
        file_results = FileResults(file_path="/path/to/file.pdf")
        assert file_results.agreement_count() == 0

    def test_agreement_count_single_model(self) -> None:
        """Should return 1 for single model."""
        file_results = FileResults(file_path="/path/to/file.pdf")
        file_results.results["model1"] = ModelResult(
            model="model1",
            file_path="/path/to/file.pdf",
            response_text='{"bin": "Finances"}',
            parsed_result={"bin": "Finances"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        assert file_results.agreement_count() == 1

    def test_agreement_count_all_agree(self) -> None:
        """Should count all when models agree."""
        file_results = FileResults(file_path="/path/to/file.pdf")
        for i, model in enumerate(["model1", "model2", "model3"]):
            file_results.results[model] = ModelResult(
                model=model,
                file_path="/path/to/file.pdf",
                response_text='{"bin": "Finances"}',
                parsed_result={"bin": "Finances"},
                confidence=0.9,
                duration_ms=100,
                success=True,
            )
        assert file_results.agreement_count() == 3
        assert file_results.models_agree() is True

    def test_agreement_count_partial(self) -> None:
        """Should count largest agreement group."""
        file_results = FileResults(file_path="/path/to/file.pdf")
        # Two models agree on "Finances"
        for model in ["model1", "model2"]:
            file_results.results[model] = ModelResult(
                model=model,
                file_path="/path/to/file.pdf",
                response_text='{"bin": "Finances"}',
                parsed_result={"bin": "Finances"},
                confidence=0.9,
                duration_ms=100,
                success=True,
            )
        # One model disagrees
        file_results.results["model3"] = ModelResult(
            model="model3",
            file_path="/path/to/file.pdf",
            response_text='{"bin": "Work"}',
            parsed_result={"bin": "Work"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        assert file_results.agreement_count() == 2
        assert file_results.models_agree() is False

    def test_models_agree_case_insensitive(self) -> None:
        """Should be case-insensitive when comparing."""
        file_results = FileResults(file_path="/path/to/file.pdf")
        file_results.results["model1"] = ModelResult(
            model="model1",
            file_path="/path/to/file.pdf",
            response_text='{"bin": "FINANCES"}',
            parsed_result={"bin": "FINANCES"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        file_results.results["model2"] = ModelResult(
            model="model2",
            file_path="/path/to/file.pdf",
            response_text='{"bin": "finances"}',
            parsed_result={"bin": "finances"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        assert file_results.models_agree() is True

    def test_file_results_to_dict(self) -> None:
        """Should convert to dictionary."""
        file_results = FileResults(
            file_path="/path/to/file.pdf",
            ground_truth={"bin": "Expected"},
        )
        d = file_results.to_dict()
        assert d["file_path"] == "/path/to/file.pdf"
        assert d["ground_truth"] == {"bin": "Expected"}
        assert "agreement_count" in d
        assert "models_agree" in d


class TestLatencyStats:
    """Tests for LatencyStats dataclass."""

    def test_latency_stats_empty(self) -> None:
        """Should handle empty durations."""
        stats = LatencyStats.from_durations("model1", [])
        assert stats.model == "model1"
        assert stats.p50_ms == 0
        assert stats.p95_ms == 0
        assert stats.p99_ms == 0
        assert stats.avg_ms == 0
        assert stats.sample_count == 0

    def test_latency_stats_single(self) -> None:
        """Should handle single duration."""
        stats = LatencyStats.from_durations("model1", [100])
        assert stats.p50_ms == 100
        assert stats.p95_ms == 100
        assert stats.p99_ms == 100
        assert stats.avg_ms == 100
        assert stats.min_ms == 100
        assert stats.max_ms == 100
        assert stats.sample_count == 1

    def test_latency_stats_multiple(self) -> None:
        """Should calculate percentiles correctly."""
        durations = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        stats = LatencyStats.from_durations("model1", durations)
        assert stats.min_ms == 100
        assert stats.max_ms == 1000
        assert stats.avg_ms == 550
        assert stats.sample_count == 10
        # P50 should be around 500-550
        assert 400 <= stats.p50_ms <= 600

    def test_latency_stats_to_dict(self) -> None:
        """Should convert to dictionary."""
        stats = LatencyStats.from_durations("model1", [100, 200, 300])
        d = stats.to_dict()
        assert d["model"] == "model1"
        assert "p50_ms" in d
        assert "p95_ms" in d
        assert "avg_ms" in d


class TestExperiment:
    """Tests for Experiment dataclass."""

    def test_create_experiment(self) -> None:
        """Should create experiment with required fields."""
        exp = Experiment(
            name="test_experiment",
            models_to_compare=["llama3.1:8b", "qwen2.5:14b"],
            test_files=["/path/to/file1.pdf", "/path/to/file2.pdf"],
        )
        assert exp.name == "test_experiment"
        assert len(exp.models_to_compare) == 2
        assert len(exp.test_files) == 2
        assert exp.task_type == "classify"

    def test_experiment_validation_no_models(self) -> None:
        """Should raise error if no models specified."""
        with pytest.raises(ValueError, match="(?i)at least one model"):
            Experiment(
                name="test",
                models_to_compare=[],
                test_files=["/path/to/file.pdf"],
            )

    def test_experiment_validation_no_files(self) -> None:
        """Should raise error if no test files specified."""
        with pytest.raises(ValueError, match="(?i)at least one test file"):
            Experiment(
                name="test",
                models_to_compare=["model1"],
                test_files=[],
            )

    def test_experiment_with_ground_truth(self) -> None:
        """Should accept ground truth mapping."""
        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/to/file.pdf"],
            expected_results={"/path/to/file.pdf": {"bin": "Finances"}},
        )
        assert exp.expected_results is not None
        assert "/path/to/file.pdf" in exp.expected_results

    def test_experiment_to_dict(self) -> None:
        """Should convert to dictionary."""
        exp = Experiment(
            name="test",
            models_to_compare=["model1", "model2"],
            test_files=["/path/file1.pdf"],
            task_type="validate",
        )
        d = exp.to_dict()
        assert d["name"] == "test"
        assert d["task_type"] == "validate"
        assert len(d["models_to_compare"]) == 2

    def test_experiment_from_dict(self) -> None:
        """Should create from dictionary."""
        data = {
            "name": "loaded_experiment",
            "models_to_compare": ["model1"],
            "test_files": ["/path/file.pdf"],
            "task_type": "analyze",
        }
        exp = Experiment.from_dict(data)
        assert exp.name == "loaded_experiment"
        assert exp.task_type == "analyze"


class TestExperimentResult:
    """Tests for ExperimentResult dataclass."""

    def _create_sample_result(self) -> ExperimentResult:
        """Create a sample experiment result for testing."""
        exp = Experiment(
            name="sample",
            models_to_compare=["model1", "model2"],
            test_files=["/path/file1.pdf", "/path/file2.pdf"],
        )

        file_results = []
        for file_path in exp.test_files:
            fr = FileResults(file_path=file_path)
            for model in exp.models_to_compare:
                fr.results[model] = ModelResult(
                    model=model,
                    file_path=file_path,
                    response_text='{"bin": "Finances", "confidence": 0.9}',
                    parsed_result={"bin": "Finances", "confidence": 0.9},
                    confidence=0.9,
                    duration_ms=100,
                    success=True,
                )
            file_results.append(fr)

        latency_stats = {
            "model1": LatencyStats.from_durations("model1", [100, 150]),
            "model2": LatencyStats.from_durations("model2", [200, 250]),
        }

        return ExperimentResult(
            experiment=exp,
            file_results=file_results,
            latency_stats=latency_stats,
            agreement_rate=1.0,
            accuracy_vs_ground_truth=None,
            total_duration_ms=700,
            started_at="2026-03-05T10:00:00",
            completed_at="2026-03-05T10:00:01",
        )

    def test_experiment_result_to_dict(self) -> None:
        """Should convert to dictionary."""
        result = self._create_sample_result()
        d = result.to_dict()
        assert "experiment" in d
        assert "file_results" in d
        assert "latency_stats" in d
        assert "agreement_rate" in d
        assert d["agreement_rate"] == 1.0

    def test_experiment_result_from_dict(self) -> None:
        """Should create from dictionary."""
        result = self._create_sample_result()
        d = result.to_dict()
        loaded = ExperimentResult.from_dict(d)
        assert loaded.agreement_rate == result.agreement_rate
        assert len(loaded.file_results) == len(result.file_results)

    def test_agreement_matrix(self) -> None:
        """Should calculate agreement matrix."""
        result = self._create_sample_result()
        matrix = result.agreement_matrix
        assert "model1" in matrix
        assert "model2" in matrix
        # Both models agree on both files
        assert matrix["model1"]["model2"] == 2
        assert matrix["model2"]["model1"] == 2


class TestRunExperiment:
    """Tests for run_experiment function."""

    @patch("organizer.llm_experiment._read_file_content")
    def test_run_experiment_basic(self, mock_read: MagicMock) -> None:
        """Should run experiment with mock LLM client."""
        mock_read.return_value = "sample content"

        mock_client = MagicMock()
        mock_client.generate.return_value = MagicMock(
            text='{"bin": "Finances", "confidence": 0.92, "reason": "test"}',
            success=True,
            duration_ms=100,
            error="",
        )

        exp = Experiment(
            name="test",
            models_to_compare=["model1", "model2"],
            test_files=["/path/file1.pdf"],
        )

        result = run_experiment(exp, mock_client)

        assert result.experiment.name == "test"
        assert len(result.file_results) == 1
        assert "model1" in result.latency_stats
        assert "model2" in result.latency_stats
        assert result.started_at
        assert result.completed_at

    @patch("organizer.llm_experiment._read_file_content")
    def test_run_experiment_with_progress_callback(self, mock_read: MagicMock) -> None:
        """Should call progress callback."""
        mock_read.return_value = "content"

        mock_client = MagicMock()
        mock_client.generate.return_value = MagicMock(
            text='{"bin": "Test"}',
            success=True,
            duration_ms=50,
            error="",
        )

        progress_calls: list[tuple[int, int, str]] = []

        def progress_callback(current: int, total: int, msg: str) -> None:
            progress_calls.append((current, total, msg))

        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/file1.pdf", "/path/file2.pdf"],
        )

        run_experiment(exp, mock_client, progress_callback=progress_callback)

        assert len(progress_calls) == 2
        assert progress_calls[-1][0] == 2  # current step
        assert progress_calls[-1][1] == 2  # total steps

    @patch("organizer.llm_experiment._read_file_content")
    def test_run_experiment_with_ground_truth(self, mock_read: MagicMock) -> None:
        """Should calculate accuracy vs ground truth."""
        mock_read.return_value = "content"

        mock_client = MagicMock()
        mock_client.generate.return_value = MagicMock(
            text='{"bin": "finances", "confidence": 0.9}',
            success=True,
            duration_ms=100,
            error="",
        )

        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/file1.pdf"],
            expected_results={"/path/file1.pdf": {"bin": "Finances"}},
        )

        result = run_experiment(exp, mock_client)

        assert result.accuracy_vs_ground_truth is not None
        assert "model1" in result.accuracy_vs_ground_truth
        # Model returns "finances", ground truth is "Finances" - case insensitive match
        assert result.accuracy_vs_ground_truth["model1"] == 1.0

    @patch("organizer.llm_experiment._read_file_content")
    def test_run_experiment_handles_failure(self, mock_read: MagicMock) -> None:
        """Should handle failed LLM calls."""
        mock_read.return_value = "content"

        mock_client = MagicMock()
        mock_client.generate.return_value = MagicMock(
            text="",
            success=False,
            duration_ms=0,
            error="Connection failed",
        )

        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/file1.pdf"],
        )

        result = run_experiment(exp, mock_client)

        assert len(result.file_results) == 1
        model_result = result.file_results[0].results["model1"]
        assert model_result.success is False
        assert model_result.error == "Connection failed"


class TestSaveAndLoadExperimentResult:
    """Tests for saving and loading experiment results."""

    def _create_sample_result(self) -> ExperimentResult:
        """Create a sample experiment result for testing."""
        exp = Experiment(
            name="save_test",
            models_to_compare=["model1"],
            test_files=["/path/file.pdf"],
        )

        return ExperimentResult(
            experiment=exp,
            file_results=[],
            latency_stats={"model1": LatencyStats.from_durations("model1", [100])},
            agreement_rate=1.0,
            accuracy_vs_ground_truth=None,
            total_duration_ms=100,
            started_at="2026-03-05T10:00:00",
            completed_at="2026-03-05T10:00:01",
        )

    def test_save_experiment_result(self) -> None:
        """Should save result to JSON file."""
        result = self._create_sample_result()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = save_experiment_result(result, output_dir=tmpdir)

            assert filepath.exists()
            assert filepath.suffix == ".json"
            assert "save_test" in filepath.name

            # Verify content
            with open(filepath) as f:
                data = json.load(f)
            assert data["experiment"]["name"] == "save_test"

    def test_load_experiment_result(self) -> None:
        """Should load result from JSON file."""
        result = self._create_sample_result()

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = save_experiment_result(result, output_dir=tmpdir)
            loaded = load_experiment_result(filepath)

            assert loaded.experiment.name == result.experiment.name
            assert loaded.agreement_rate == result.agreement_rate

    def test_list_experiment_results(self) -> None:
        """Should list all saved results."""
        result = self._create_sample_result()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Save multiple results
            save_experiment_result(result, output_dir=tmpdir)
            result.experiment.name = "second_test"
            save_experiment_result(result, output_dir=tmpdir)

            results = list_experiment_results(tmpdir)
            assert len(results) == 2
            assert "filepath" in results[0]
            assert "name" in results[0]

    def test_list_experiment_results_empty(self) -> None:
        """Should return empty list for empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = list_experiment_results(tmpdir)
            assert results == []


class TestGenerateComparisonTable:
    """Tests for generate_comparison_table function."""

    def test_generate_comparison_table(self) -> None:
        """Should generate readable comparison table."""
        exp = Experiment(
            name="comparison_test",
            models_to_compare=["model1", "model2"],
            test_files=["/path/file.pdf"],
        )

        result = ExperimentResult(
            experiment=exp,
            file_results=[],
            latency_stats={
                "model1": LatencyStats.from_durations("model1", [100, 150]),
                "model2": LatencyStats.from_durations("model2", [200, 250]),
            },
            agreement_rate=0.85,
            accuracy_vs_ground_truth=None,
            total_duration_ms=500,
            started_at="2026-03-05T10:00:00",
            completed_at="2026-03-05T10:00:01",
        )

        table = generate_comparison_table(result)

        assert "comparison_test" in table
        assert "model1" in table
        assert "model2" in table
        assert "85.0%" in table
        assert "P50" in table
        assert "P95" in table

    def test_generate_comparison_table_with_accuracy(self) -> None:
        """Should include accuracy when available."""
        exp = Experiment(
            name="accuracy_test",
            models_to_compare=["model1"],
            test_files=["/path/file.pdf"],
        )

        result = ExperimentResult(
            experiment=exp,
            file_results=[],
            latency_stats={"model1": LatencyStats.from_durations("model1", [100])},
            agreement_rate=1.0,
            accuracy_vs_ground_truth={"model1": 0.92},
            total_duration_ms=100,
            started_at="2026-03-05T10:00:00",
            completed_at="2026-03-05T10:00:01",
        )

        table = generate_comparison_table(result)

        assert "Accuracy vs Ground Truth" in table
        assert "92.0%" in table


class TestJsonParsing:
    """Tests for JSON parsing from LLM responses."""

    @patch("organizer.llm_experiment._read_file_content")
    def test_parses_plain_json(self, mock_read: MagicMock) -> None:
        """Should parse plain JSON response."""
        mock_read.return_value = "content"

        mock_client = MagicMock()
        mock_client.generate.return_value = MagicMock(
            text='{"bin": "Finances", "confidence": 0.9}',
            success=True,
            duration_ms=100,
            error="",
        )

        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/file.pdf"],
        )

        result = run_experiment(exp, mock_client)
        model_result = result.file_results[0].results["model1"]

        assert model_result.parsed_result is not None
        assert model_result.parsed_result["bin"] == "Finances"
        assert model_result.confidence == 0.9

    @patch("organizer.llm_experiment._read_file_content")
    def test_parses_json_in_markdown(self, mock_read: MagicMock) -> None:
        """Should parse JSON in markdown code block."""
        mock_read.return_value = "content"

        mock_client = MagicMock()
        mock_client.generate.return_value = MagicMock(
            text='Here is the result:\n```json\n{"bin": "Work", "confidence": 0.85}\n```',
            success=True,
            duration_ms=100,
            error="",
        )

        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/file.pdf"],
        )

        result = run_experiment(exp, mock_client)
        model_result = result.file_results[0].results["model1"]

        assert model_result.parsed_result is not None
        assert model_result.parsed_result["bin"] == "Work"

    @patch("organizer.llm_experiment._read_file_content")
    def test_handles_invalid_json(self, mock_read: MagicMock) -> None:
        """Should handle invalid JSON gracefully."""
        mock_read.return_value = "content"

        mock_client = MagicMock()
        mock_client.generate.return_value = MagicMock(
            text="This is not JSON at all",
            success=True,
            duration_ms=100,
            error="",
        )

        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/file.pdf"],
        )

        result = run_experiment(exp, mock_client)
        model_result = result.file_results[0].results["model1"]

        assert model_result.parsed_result is None
        assert model_result.confidence is None
        assert model_result.success is True  # Generation succeeded, just parsing failed


class TestCustomPromptTemplate:
    """Tests for custom prompt templates."""

    @patch("organizer.llm_experiment._read_file_content")
    def test_uses_custom_prompt_template(self, mock_read: MagicMock) -> None:
        """Should use custom prompt template when provided."""
        mock_read.return_value = "sample content"

        captured_prompts: list[str] = []

        def capture_generate(prompt: str, **kwargs: dict[str, object]) -> MagicMock:
            captured_prompts.append(prompt)
            return MagicMock(
                text='{"result": "ok"}',
                success=True,
                duration_ms=100,
                error="",
            )

        mock_client = MagicMock()
        mock_client.generate.side_effect = capture_generate

        exp = Experiment(
            name="test",
            models_to_compare=["model1"],
            test_files=["/path/file.pdf"],
            prompt_template="Custom prompt for {filename}: {content}",
        )

        run_experiment(exp, mock_client)

        assert len(captured_prompts) == 1
        assert "Custom prompt for" in captured_prompts[0]
        assert "file.pdf" in captured_prompts[0]
