"""Tests for Model Routing Tuner."""

import json
import tempfile
from pathlib import Path

from organizer.llm_experiment import (
    Experiment,
    ExperimentResult,
    FileResults,
    LatencyStats,
    ModelResult,
)
from organizer.model_router import (
    ModelTier,
)
from organizer.routing_tuner import (
    ExperimentAnalysis,
    RoutingRecommendation,
    RoutingTuner,
    TaskAnalysis,
    TierPerformance,
    _calculate_agreement_rate_for_model,
    _extract_confidences_for_model,
    _infer_tier_from_model_name,
    analyze_experiment_file,
    generate_tuning_report,
)


class TestTierPerformance:
    """Tests for TierPerformance dataclass."""

    def test_create_tier_performance(self) -> None:
        """Should create TierPerformance with all fields."""
        perf = TierPerformance(
            tier=ModelTier.FAST,
            task_type="classify",
            model_name="llama3.1:8b",
            sample_count=10,
            accuracy=0.9,
            avg_confidence=0.85,
            p50_latency_ms=100,
            p95_latency_ms=200,
            avg_latency_ms=120,
            agreement_rate=0.95,
        )
        assert perf.tier == ModelTier.FAST
        assert perf.accuracy == 0.9
        assert perf.p95_latency_ms == 200

    def test_is_good_enough_with_accuracy(self) -> None:
        """Should check against accuracy when available."""
        perf = TierPerformance(
            tier=ModelTier.FAST,
            task_type="classify",
            model_name="llama3.1:8b",
            sample_count=10,
            accuracy=0.9,
            avg_confidence=0.85,
            p50_latency_ms=100,
            p95_latency_ms=200,
            avg_latency_ms=120,
            agreement_rate=0.95,
        )
        assert perf.is_good_enough(min_accuracy=0.85) is True
        assert perf.is_good_enough(min_accuracy=0.95) is False

    def test_is_good_enough_with_agreement_rate(self) -> None:
        """Should use agreement rate when accuracy not available."""
        perf = TierPerformance(
            tier=ModelTier.FAST,
            task_type="classify",
            model_name="llama3.1:8b",
            sample_count=10,
            accuracy=None,
            avg_confidence=0.85,
            p50_latency_ms=100,
            p95_latency_ms=200,
            avg_latency_ms=120,
            agreement_rate=0.90,
        )
        assert perf.is_good_enough(min_accuracy=0.85) is True
        assert perf.is_good_enough(min_accuracy=0.95) is False

    def test_is_good_enough_latency_check(self) -> None:
        """Should check latency constraint."""
        perf = TierPerformance(
            tier=ModelTier.FAST,
            task_type="classify",
            model_name="llama3.1:8b",
            sample_count=10,
            accuracy=0.95,
            avg_confidence=0.85,
            p50_latency_ms=100,
            p95_latency_ms=6000,  # Exceeds default max
            avg_latency_ms=120,
            agreement_rate=0.95,
        )
        assert perf.is_good_enough(max_latency_ms=5000) is False
        assert perf.is_good_enough(max_latency_ms=7000) is True

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        perf = TierPerformance(
            tier=ModelTier.FAST,
            task_type="classify",
            model_name="llama3.1:8b",
            sample_count=10,
            accuracy=0.9,
            avg_confidence=0.85,
            p50_latency_ms=100,
            p95_latency_ms=200,
            avg_latency_ms=120,
            agreement_rate=0.95,
        )
        d = perf.to_dict()
        assert d["tier"] == "fast"
        assert d["model_name"] == "llama3.1:8b"
        assert d["accuracy"] == 0.9


class TestInferTierFromModelName:
    """Tests for _infer_tier_from_model_name helper."""

    def test_infer_fast_tier_8b(self) -> None:
        """Should infer FAST tier for 8B models."""
        assert _infer_tier_from_model_name("llama3.1:8b-instruct-q8_0") == ModelTier.FAST
        assert _infer_tier_from_model_name("qwen2.5-coder:7b") == ModelTier.FAST

    def test_infer_smart_tier_14b(self) -> None:
        """Should infer SMART tier for 14B models."""
        assert _infer_tier_from_model_name("qwen2.5-coder:14b") == ModelTier.SMART
        assert _infer_tier_from_model_name("mixtral:20b") == ModelTier.SMART

    def test_infer_cloud_tier_large(self) -> None:
        """Should infer CLOUD tier for large models."""
        assert _infer_tier_from_model_name("qwen3-coder:480b-cloud") == ModelTier.CLOUD
        assert _infer_tier_from_model_name("deepseek-v3.1:671b") == ModelTier.CLOUD

    def test_infer_unknown_defaults_to_fast(self) -> None:
        """Should default to FAST tier for unknown models."""
        assert _infer_tier_from_model_name("unknown-model") == ModelTier.FAST


class TestCalculateAgreementRate:
    """Tests for _calculate_agreement_rate_for_model helper."""

    def test_empty_results(self) -> None:
        """Should return 0 for empty results."""
        assert _calculate_agreement_rate_for_model("model1", []) == 0.0

    def test_single_model_results(self) -> None:
        """Should return 1.0 when model always agrees with majority (itself)."""
        fr = FileResults(file_path="/test.pdf")
        fr.results["model1"] = ModelResult(
            model="model1",
            file_path="/test.pdf",
            response_text='{"bin": "Finances"}',
            parsed_result={"bin": "Finances"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        rate = _calculate_agreement_rate_for_model("model1", [fr])
        assert rate == 1.0

    def test_agreement_with_majority(self) -> None:
        """Should calculate agreement with majority answer."""
        fr = FileResults(file_path="/test.pdf")
        # Two models agree on "Finances"
        fr.results["model1"] = ModelResult(
            model="model1",
            file_path="/test.pdf",
            response_text='{"bin": "Finances"}',
            parsed_result={"bin": "Finances"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        fr.results["model2"] = ModelResult(
            model="model2",
            file_path="/test.pdf",
            response_text='{"bin": "Finances"}',
            parsed_result={"bin": "Finances"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        # One disagrees
        fr.results["model3"] = ModelResult(
            model="model3",
            file_path="/test.pdf",
            response_text='{"bin": "Work"}',
            parsed_result={"bin": "Work"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )

        # Model1 agrees with majority
        assert _calculate_agreement_rate_for_model("model1", [fr]) == 1.0
        # Model3 disagrees with majority
        assert _calculate_agreement_rate_for_model("model3", [fr]) == 0.0


class TestExtractConfidences:
    """Tests for _extract_confidences_for_model helper."""

    def test_empty_results(self) -> None:
        """Should return empty list for empty results."""
        assert _extract_confidences_for_model("model1", []) == []

    def test_extract_confidences(self) -> None:
        """Should extract confidence scores."""
        fr1 = FileResults(file_path="/test1.pdf")
        fr1.results["model1"] = ModelResult(
            model="model1",
            file_path="/test1.pdf",
            response_text="",
            parsed_result={"bin": "Test"},
            confidence=0.9,
            duration_ms=100,
            success=True,
        )
        fr2 = FileResults(file_path="/test2.pdf")
        fr2.results["model1"] = ModelResult(
            model="model1",
            file_path="/test2.pdf",
            response_text="",
            parsed_result={"bin": "Test"},
            confidence=0.85,
            duration_ms=100,
            success=True,
        )

        confidences = _extract_confidences_for_model("model1", [fr1, fr2])
        assert len(confidences) == 2
        assert 0.9 in confidences
        assert 0.85 in confidences


class TestRoutingTuner:
    """Tests for RoutingTuner class."""

    def _create_sample_experiment_result(
        self,
        model_confidences: dict[str, list[float]] | None = None,
    ) -> ExperimentResult:
        """Create a sample experiment result for testing."""
        if model_confidences is None:
            model_confidences = {
                "llama3.1:8b": [0.85, 0.90, 0.88, 0.92, 0.86],
                "qwen2.5:14b": [0.92, 0.95, 0.91, 0.96, 0.93],
            }

        models = list(model_confidences.keys())
        exp = Experiment(
            name="tuning_test",
            models_to_compare=models,
            test_files=[f"/path/file{i}.pdf" for i in range(5)],
            task_type="classify",
        )

        file_results = []
        for i, file_path in enumerate(exp.test_files):
            fr = FileResults(file_path=file_path)
            for model, confs in model_confidences.items():
                conf = confs[i] if i < len(confs) else 0.9
                fr.results[model] = ModelResult(
                    model=model,
                    file_path=file_path,
                    response_text=f'{{"bin": "Finances", "confidence": {conf}}}',
                    parsed_result={"bin": "Finances", "confidence": conf},
                    confidence=conf,
                    duration_ms=100 if "8b" in model else 200,
                    success=True,
                )
            file_results.append(fr)

        latency_stats = {}
        for model, confs in model_confidences.items():
            base_latency = 100 if "8b" in model else 200
            latency_stats[model] = LatencyStats.from_durations(
                model, [base_latency] * len(confs)
            )

        return ExperimentResult(
            experiment=exp,
            file_results=file_results,
            latency_stats=latency_stats,
            agreement_rate=1.0,
            accuracy_vs_ground_truth=None,
            total_duration_ms=1000,
            started_at="2026-03-05T10:00:00",
            completed_at="2026-03-05T10:00:01",
        )

    def test_analyze_experiment(self) -> None:
        """Should analyze experiment and produce metrics."""
        result = self._create_sample_experiment_result()
        tuner = RoutingTuner()
        analysis = tuner.analyze_experiment(result)

        assert analysis.experiment_name == "tuning_test"
        assert len(analysis.models_analyzed) == 2
        assert "classify" in analysis.task_analyses

    def test_analyze_assigns_tiers(self) -> None:
        """Should assign correct tiers to models."""
        result = self._create_sample_experiment_result()
        tuner = RoutingTuner()
        analysis = tuner.analyze_experiment(result)

        assert analysis.model_tier_mapping["llama3.1:8b"] == ModelTier.FAST
        assert analysis.model_tier_mapping["qwen2.5:14b"] == ModelTier.SMART

    def test_analyze_calculates_performance(self) -> None:
        """Should calculate per-tier performance metrics."""
        result = self._create_sample_experiment_result()
        tuner = RoutingTuner()
        analysis = tuner.analyze_experiment(result)

        classify_analysis = analysis.task_analyses["classify"]

        # FAST tier should have lower latency
        if ModelTier.FAST in classify_analysis.tier_performance:
            fast_perf = classify_analysis.tier_performance[ModelTier.FAST]
            assert fast_perf.p50_latency_ms <= 150

        # SMART tier should have higher latency but potentially better confidence
        if ModelTier.SMART in classify_analysis.tier_performance:
            smart_perf = classify_analysis.tier_performance[ModelTier.SMART]
            assert smart_perf.p50_latency_ms >= 150

    def test_determine_recommended_tier_fast_good_enough(self) -> None:
        """Should recommend FAST tier when it's good enough."""
        # Create high-confidence FAST model
        model_confidences = {
            "llama3.1:8b": [0.92, 0.93, 0.94, 0.91, 0.95],
        }
        result = self._create_sample_experiment_result(model_confidences)
        tuner = RoutingTuner(min_accuracy=0.85)
        analysis = tuner.analyze_experiment(result)

        classify_analysis = analysis.task_analyses["classify"]
        assert classify_analysis.recommended_tier == ModelTier.FAST

    def test_generate_recommendations(self) -> None:
        """Should generate routing recommendations."""
        result = self._create_sample_experiment_result()
        tuner = RoutingTuner()
        analysis = tuner.analyze_experiment(result)
        recommendations = tuner.generate_recommendations(analysis)

        assert isinstance(recommendations, RoutingRecommendation)
        assert 0.0 <= recommendations.escalation_threshold <= 1.0
        assert recommendations.reasoning

    def test_generate_recommendations_sets_threshold(self) -> None:
        """Should set threshold based on average confidence."""
        model_confidences = {
            "llama3.1:8b": [0.85, 0.90, 0.88, 0.92, 0.86],
        }
        result = self._create_sample_experiment_result(model_confidences)
        tuner = RoutingTuner()
        analysis = tuner.analyze_experiment(result)
        recommendations = tuner.generate_recommendations(analysis)

        # Threshold should be slightly below average confidence
        # Average confidence is ~0.88, so threshold should be around 0.78
        assert 0.5 <= recommendations.escalation_threshold <= 0.95

    def test_generate_recommendations_includes_warnings(self) -> None:
        """Should include warnings when data is insufficient."""
        # Create result with few samples
        model_confidences = {
            "llama3.1:8b": [0.9, 0.9],  # Only 2 samples
        }
        result = self._create_sample_experiment_result(model_confidences)
        # Modify to have only 2 files
        result.experiment.test_files = result.experiment.test_files[:2]
        result.file_results = result.file_results[:2]

        tuner = RoutingTuner(min_sample_size=5)
        analysis = tuner.analyze_experiment(result)
        recommendations = tuner.generate_recommendations(analysis)

        # Should have warning about low sample count
        assert any("sample" in w.lower() for w in recommendations.warnings)


class TestApplyRecommendations:
    """Tests for applying recommendations to config."""

    def test_apply_recommendations_dry_run(self) -> None:
        """Should report changes without modifying files in dry run."""
        recommendations = RoutingRecommendation(
            escalation_threshold=0.70,
            routing_table_updates={
                ("classify", "low"): ModelTier.FAST,
            },
            confidence_in_recommendations=0.9,
            reasoning="Test recommendation",
            warnings=[],
        )

        tuner = RoutingTuner()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".organizer" / "agent" / "agent_config.json"
            changes = tuner.apply_recommendations(
                recommendations, config_path=config_path, dry_run=True
            )

            assert changes["dry_run"] is True
            assert changes["applied"] is False
            # File should not exist
            assert not config_path.exists()

    def test_apply_recommendations_writes_config(self) -> None:
        """Should write config file when not dry run."""
        recommendations = RoutingRecommendation(
            escalation_threshold=0.70,
            routing_table_updates={},
            confidence_in_recommendations=0.9,
            reasoning="Test recommendation",
            warnings=[],
        )

        tuner = RoutingTuner()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".organizer" / "agent" / "agent_config.json"
            changes = tuner.apply_recommendations(
                recommendations, config_path=config_path, dry_run=False
            )

            assert changes["applied"] is True
            assert config_path.exists()

            # Verify content
            with open(config_path) as f:
                config = json.load(f)
            assert config["llm_models"]["escalation_threshold"] == 0.70

    def test_apply_recommendations_preserves_existing_config(self) -> None:
        """Should preserve existing config values."""
        recommendations = RoutingRecommendation(
            escalation_threshold=0.70,
            routing_table_updates={},
            confidence_in_recommendations=0.9,
            reasoning="Test recommendation",
            warnings=[],
        )

        tuner = RoutingTuner()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".organizer" / "agent" / "agent_config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write existing config
            existing = {
                "some_setting": "preserved",
                "llm_models": {
                    "fast": "existing-model:8b",
                    "escalation_threshold": 0.75,
                },
            }
            with open(config_path, "w") as f:
                json.dump(existing, f)

            tuner.apply_recommendations(
                recommendations, config_path=config_path, dry_run=False
            )

            # Verify content
            with open(config_path) as f:
                config = json.load(f)

            assert config["some_setting"] == "preserved"
            assert config["llm_models"]["fast"] == "existing-model:8b"
            assert config["llm_models"]["escalation_threshold"] == 0.70


class TestAnalyzeExperimentFile:
    """Tests for analyze_experiment_file function."""

    def test_analyze_experiment_file(self) -> None:
        """Should load and analyze experiment from file."""
        # Create a minimal experiment result file
        exp = Experiment(
            name="file_test",
            models_to_compare=["llama3.1:8b"],
            test_files=["/test.pdf"],
            task_type="classify",
        )

        file_results = [
            FileResults(
                file_path="/test.pdf",
                results={
                    "llama3.1:8b": ModelResult(
                        model="llama3.1:8b",
                        file_path="/test.pdf",
                        response_text='{"bin": "Test"}',
                        parsed_result={"bin": "Test"},
                        confidence=0.9,
                        duration_ms=100,
                        success=True,
                    )
                },
            )
        ]

        result = ExperimentResult(
            experiment=exp,
            file_results=file_results,
            latency_stats={
                "llama3.1:8b": LatencyStats.from_durations("llama3.1:8b", [100] * 5)
            },
            agreement_rate=1.0,
            accuracy_vs_ground_truth=None,
            total_duration_ms=100,
            started_at="2026-03-05T10:00:00",
            completed_at="2026-03-05T10:00:01",
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(result.to_dict(), f)
            filepath = f.name

        try:
            analysis = analyze_experiment_file(filepath)
            assert analysis.experiment_name == "file_test"
        finally:
            Path(filepath).unlink()


class TestGenerateTuningReport:
    """Tests for generate_tuning_report function."""

    def test_generate_tuning_report(self) -> None:
        """Should generate human-readable report."""
        analysis = ExperimentAnalysis(
            experiment_name="test_report",
            models_analyzed=["llama3.1:8b", "qwen2.5:14b"],
            total_files=10,
            task_analyses={
                "classify": TaskAnalysis(
                    task_type="classify",
                    tier_performance={
                        ModelTier.FAST: TierPerformance(
                            tier=ModelTier.FAST,
                            task_type="classify",
                            model_name="llama3.1:8b",
                            sample_count=10,
                            accuracy=0.9,
                            avg_confidence=0.85,
                            p50_latency_ms=100,
                            p95_latency_ms=200,
                            avg_latency_ms=120,
                            agreement_rate=0.95,
                        ),
                    },
                    recommended_tier=ModelTier.FAST,
                    recommended_threshold=0.75,
                    recommendation_reason="FAST tier is good enough",
                )
            },
            overall_agreement_rate=0.95,
            model_tier_mapping={
                "llama3.1:8b": ModelTier.FAST,
                "qwen2.5:14b": ModelTier.SMART,
            },
        )

        recommendations = RoutingRecommendation(
            escalation_threshold=0.75,
            routing_table_updates={},
            confidence_in_recommendations=0.9,
            reasoning="Based on analysis...",
            warnings=["Low sample count"],
        )

        report = generate_tuning_report(analysis, recommendations)

        assert "test_report" in report
        assert "CLASSIFY" in report
        assert "llama3.1:8b" in report
        assert "0.75" in report
        assert "Low sample count" in report


class TestTaskAnalysis:
    """Tests for TaskAnalysis dataclass."""

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        analysis = TaskAnalysis(
            task_type="classify",
            recommended_tier=ModelTier.FAST,
            recommended_threshold=0.75,
            recommendation_reason="Test reason",
        )
        d = analysis.to_dict()
        assert d["task_type"] == "classify"
        assert d["recommended_tier"] == "fast"
        assert d["recommended_threshold"] == 0.75


class TestExperimentAnalysis:
    """Tests for ExperimentAnalysis dataclass."""

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        analysis = ExperimentAnalysis(
            experiment_name="test",
            models_analyzed=["model1", "model2"],
            total_files=5,
            overall_agreement_rate=0.95,
            model_tier_mapping={
                "model1": ModelTier.FAST,
                "model2": ModelTier.SMART,
            },
        )
        d = analysis.to_dict()
        assert d["experiment_name"] == "test"
        assert d["overall_agreement_rate"] == 0.95
        assert d["model_tier_mapping"]["model1"] == "fast"


class TestRoutingRecommendation:
    """Tests for RoutingRecommendation dataclass."""

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        rec = RoutingRecommendation(
            escalation_threshold=0.75,
            routing_table_updates={
                ("classify", "low"): ModelTier.FAST,
            },
            confidence_in_recommendations=0.9,
            reasoning="Test",
            warnings=["Warning 1"],
        )
        d = rec.to_dict()
        assert d["escalation_threshold"] == 0.75
        assert "classify,low" in d["routing_table_updates"]
        assert d["routing_table_updates"]["classify,low"] == "fast"
