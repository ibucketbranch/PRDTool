"""Model routing tuner based on experiment results.

Analyzes experiment results to determine optimal escalation thresholds
and routing table configurations. This module helps tune the model router
by learning from empirical data which model tier performs best for each
task type.

Example usage:
    # Load experiment results
    result = load_experiment_result("experiment_results.json")

    # Analyze and generate recommendations
    tuner = RoutingTuner()
    analysis = tuner.analyze_experiment(result)
    recommendations = tuner.generate_recommendations(analysis)

    # Apply recommendations to config
    tuner.apply_recommendations(recommendations, config_path)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from organizer.llm_experiment import (
    ExperimentResult,
    FileResults,
    load_experiment_result,
)
from organizer.model_router import (
    DEFAULT_ESCALATION_THRESHOLD,
    DEFAULT_ROUTING_TABLE,
    ModelTier,
)


# Minimum sample size for reliable statistics
MIN_SAMPLE_SIZE = 5

# Default minimum acceptable accuracy for a tier to be considered "good enough"
DEFAULT_MIN_ACCURACY = 0.85

# Default maximum acceptable latency (p95) in milliseconds
DEFAULT_MAX_LATENCY_MS = 5000


@dataclass
class TierPerformance:
    """Performance metrics for a model tier on a specific task type.

    Attributes:
        tier: The model tier.
        task_type: The type of task (classify, validate, analyze, etc.).
        model_name: The specific model used for this tier.
        sample_count: Number of samples tested.
        accuracy: Accuracy against ground truth (0.0-1.0) or None if no ground truth.
        avg_confidence: Average confidence score returned by the model.
        p50_latency_ms: 50th percentile latency in milliseconds.
        p95_latency_ms: 95th percentile latency in milliseconds.
        avg_latency_ms: Average latency in milliseconds.
        agreement_rate: Agreement rate with other models.
    """

    tier: ModelTier
    task_type: str
    model_name: str
    sample_count: int
    accuracy: float | None
    avg_confidence: float | None
    p50_latency_ms: int
    p95_latency_ms: int
    avg_latency_ms: int
    agreement_rate: float

    def is_good_enough(
        self,
        min_accuracy: float = DEFAULT_MIN_ACCURACY,
        max_latency_ms: int = DEFAULT_MAX_LATENCY_MS,
    ) -> bool:
        """Check if this tier is "good enough" for the task.

        Args:
            min_accuracy: Minimum acceptable accuracy (0.0-1.0).
            max_latency_ms: Maximum acceptable p95 latency in milliseconds.

        Returns:
            True if the tier meets the minimum requirements.
        """
        # If we have accuracy data, use it
        if self.accuracy is not None:
            if self.accuracy < min_accuracy:
                return False

        # If no accuracy data, use agreement rate as a proxy
        elif self.agreement_rate < min_accuracy:
            return False

        # Check latency constraint
        if self.p95_latency_ms > max_latency_ms:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tier": self.tier.value,
            "task_type": self.task_type,
            "model_name": self.model_name,
            "sample_count": self.sample_count,
            "accuracy": self.accuracy,
            "avg_confidence": self.avg_confidence,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "agreement_rate": self.agreement_rate,
        }


@dataclass
class TaskAnalysis:
    """Analysis results for a specific task type.

    Attributes:
        task_type: The type of task analyzed.
        tier_performance: Performance metrics for each tier tested.
        recommended_tier: The recommended tier for this task.
        recommended_threshold: Recommended escalation threshold.
        recommendation_reason: Explanation of the recommendation.
    """

    task_type: str
    tier_performance: dict[ModelTier, TierPerformance] = field(default_factory=dict)
    recommended_tier: ModelTier | None = None
    recommended_threshold: float | None = None
    recommendation_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_type": self.task_type,
            "tier_performance": {
                tier.value: perf.to_dict()
                for tier, perf in self.tier_performance.items()
            },
            "recommended_tier": self.recommended_tier.value
            if self.recommended_tier
            else None,
            "recommended_threshold": self.recommended_threshold,
            "recommendation_reason": self.recommendation_reason,
        }


@dataclass
class ExperimentAnalysis:
    """Complete analysis of an experiment's results.

    Attributes:
        experiment_name: Name of the analyzed experiment.
        models_analyzed: List of models that were analyzed.
        total_files: Total number of test files in the experiment.
        task_analyses: Analysis for each task type.
        overall_agreement_rate: Overall agreement rate across all models.
        model_tier_mapping: Mapping of model names to their assigned tiers.
    """

    experiment_name: str
    models_analyzed: list[str]
    total_files: int
    task_analyses: dict[str, TaskAnalysis] = field(default_factory=dict)
    overall_agreement_rate: float = 0.0
    model_tier_mapping: dict[str, ModelTier] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "experiment_name": self.experiment_name,
            "models_analyzed": self.models_analyzed,
            "total_files": self.total_files,
            "task_analyses": {
                task: analysis.to_dict()
                for task, analysis in self.task_analyses.items()
            },
            "overall_agreement_rate": self.overall_agreement_rate,
            "model_tier_mapping": {
                model: tier.value for model, tier in self.model_tier_mapping.items()
            },
        }


@dataclass
class RoutingRecommendation:
    """Recommendations for updating routing configuration.

    Attributes:
        escalation_threshold: Recommended escalation threshold (0.0-1.0).
        routing_table_updates: Recommended updates to the routing table.
            Maps (task_type, complexity) to recommended tier.
        confidence_in_recommendations: How confident we are in these recommendations.
            Based on sample size and consistency of results.
        reasoning: Explanation of the recommendations.
        warnings: Any warnings or caveats about the recommendations.
    """

    escalation_threshold: float
    routing_table_updates: dict[tuple[str, str], ModelTier] = field(
        default_factory=dict
    )
    confidence_in_recommendations: float = 0.0
    reasoning: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "escalation_threshold": self.escalation_threshold,
            "routing_table_updates": {
                f"{task},{complexity}": tier.value
                for (task, complexity), tier in self.routing_table_updates.items()
            },
            "confidence_in_recommendations": self.confidence_in_recommendations,
            "reasoning": self.reasoning,
            "warnings": self.warnings,
        }


def _infer_tier_from_model_name(model_name: str) -> ModelTier:
    """Infer the model tier from its name.

    Args:
        model_name: The model name (e.g., "llama3.1:8b-instruct-q8_0").

    Returns:
        The inferred ModelTier based on model size indicators.
    """
    model_lower = model_name.lower()

    # Check for cloud/large model indicators
    cloud_indicators = ["70b", "80b", "100b", "200b", "400b", "480b", "671b", "cloud"]
    if any(ind in model_lower for ind in cloud_indicators):
        return ModelTier.CLOUD

    # Check for smart tier indicators (14B-34B)
    smart_indicators = ["14b", "20b", "27b", "32b", "34b"]
    if any(ind in model_lower for ind in smart_indicators):
        return ModelTier.SMART

    # Default to fast tier (7B-8B or unknown)
    return ModelTier.FAST


def _calculate_agreement_rate_for_model(
    model_name: str, file_results: list[FileResults]
) -> float:
    """Calculate the agreement rate for a specific model.

    Args:
        model_name: The model to calculate agreement for.
        file_results: List of file results from the experiment.

    Returns:
        Agreement rate (0.0-1.0) indicating how often this model
        agrees with the majority result.
    """
    if not file_results:
        return 0.0

    agreements = 0
    total = 0

    for file_result in file_results:
        if model_name not in file_result.results:
            continue

        model_result = file_result.results[model_name]
        if not model_result.parsed_result:
            continue

        # Get this model's answer
        model_answer = (
            model_result.parsed_result.get("bin")
            or model_result.parsed_result.get("category")
            or model_result.parsed_result.get("document_type")
            or model_result.parsed_result.get("result")
        )
        if not model_answer:
            continue

        model_answer = str(model_answer).lower()

        # Get all answers and find the majority
        all_answers: list[str] = []
        for result in file_result.results.values():
            if result.parsed_result:
                answer = (
                    result.parsed_result.get("bin")
                    or result.parsed_result.get("category")
                    or result.parsed_result.get("document_type")
                    or result.parsed_result.get("result")
                )
                if answer:
                    all_answers.append(str(answer).lower())

        if not all_answers:
            continue

        # Find majority answer
        from collections import Counter

        counter = Counter(all_answers)
        majority_answer = counter.most_common(1)[0][0]

        total += 1
        if model_answer == majority_answer:
            agreements += 1

    return agreements / total if total > 0 else 0.0


def _extract_confidences_for_model(
    model_name: str, file_results: list[FileResults]
) -> list[float]:
    """Extract all confidence scores for a model.

    Args:
        model_name: The model to extract confidences for.
        file_results: List of file results from the experiment.

    Returns:
        List of confidence scores (0.0-1.0).
    """
    confidences: list[float] = []

    for file_result in file_results:
        if model_name not in file_result.results:
            continue

        result = file_result.results[model_name]
        if result.confidence is not None:
            confidences.append(result.confidence)

    return confidences


class RoutingTuner:
    """Analyzes experiment results and recommends routing configuration.

    This class helps tune the model router by:
    1. Analyzing experiment results to understand model performance
    2. Determining which tier is "good enough" for each task type
    3. Recommending optimal escalation thresholds
    4. Suggesting routing table updates
    """

    def __init__(
        self,
        min_accuracy: float = DEFAULT_MIN_ACCURACY,
        max_latency_ms: int = DEFAULT_MAX_LATENCY_MS,
        min_sample_size: int = MIN_SAMPLE_SIZE,
    ):
        """Initialize the routing tuner.

        Args:
            min_accuracy: Minimum acceptable accuracy for a tier.
            max_latency_ms: Maximum acceptable p95 latency in milliseconds.
            min_sample_size: Minimum samples needed for reliable statistics.
        """
        self.min_accuracy = min_accuracy
        self.max_latency_ms = max_latency_ms
        self.min_sample_size = min_sample_size

    def analyze_experiment(self, result: ExperimentResult) -> ExperimentAnalysis:
        """Analyze an experiment result to extract performance metrics.

        Args:
            result: The experiment result to analyze.

        Returns:
            ExperimentAnalysis with per-model and per-tier performance metrics.
        """
        # Determine tier mapping for each model
        model_tier_mapping = {
            model: _infer_tier_from_model_name(model)
            for model in result.experiment.models_to_compare
        }

        # Calculate per-model statistics
        task_type = result.experiment.task_type
        task_analysis = TaskAnalysis(task_type=task_type)

        for model in result.experiment.models_to_compare:
            tier = model_tier_mapping[model]

            # Get latency stats
            latency_stats = result.latency_stats.get(model)
            if not latency_stats:
                continue

            # Calculate agreement rate for this model
            agreement_rate = _calculate_agreement_rate_for_model(
                model, result.file_results
            )

            # Calculate accuracy if ground truth available
            accuracy = None
            if result.accuracy_vs_ground_truth:
                accuracy = result.accuracy_vs_ground_truth.get(model)

            # Calculate average confidence
            confidences = _extract_confidences_for_model(model, result.file_results)
            avg_confidence = (
                sum(confidences) / len(confidences) if confidences else None
            )

            tier_performance = TierPerformance(
                tier=tier,
                task_type=task_type,
                model_name=model,
                sample_count=latency_stats.sample_count,
                accuracy=accuracy,
                avg_confidence=avg_confidence,
                p50_latency_ms=latency_stats.p50_ms,
                p95_latency_ms=latency_stats.p95_ms,
                avg_latency_ms=latency_stats.avg_ms,
                agreement_rate=agreement_rate,
            )

            # If we already have this tier, keep the one with more samples
            if tier in task_analysis.tier_performance:
                existing = task_analysis.tier_performance[tier]
                if tier_performance.sample_count > existing.sample_count:
                    task_analysis.tier_performance[tier] = tier_performance
            else:
                task_analysis.tier_performance[tier] = tier_performance

        # Determine recommended tier
        self._determine_recommended_tier(task_analysis)

        return ExperimentAnalysis(
            experiment_name=result.experiment.name,
            models_analyzed=result.experiment.models_to_compare,
            total_files=len(result.experiment.test_files),
            task_analyses={task_type: task_analysis},
            overall_agreement_rate=result.agreement_rate,
            model_tier_mapping=model_tier_mapping,
        )

    def _determine_recommended_tier(self, analysis: TaskAnalysis) -> None:
        """Determine the recommended tier for a task based on performance.

        Updates the TaskAnalysis with recommended tier and threshold.

        Args:
            analysis: The task analysis to update.
        """
        # Sort tiers by preference (FAST first, then SMART, then CLOUD)
        tier_order = [ModelTier.FAST, ModelTier.SMART, ModelTier.CLOUD]

        for tier in tier_order:
            if tier not in analysis.tier_performance:
                continue

            perf = analysis.tier_performance[tier]

            # Check if we have enough samples
            if perf.sample_count < self.min_sample_size:
                continue

            # Check if this tier is good enough
            if perf.is_good_enough(
                min_accuracy=self.min_accuracy, max_latency_ms=self.max_latency_ms
            ):
                analysis.recommended_tier = tier

                # Calculate recommended threshold based on avg confidence
                if perf.avg_confidence is not None:
                    # Set threshold slightly below average confidence
                    # so that most requests stay at this tier
                    analysis.recommended_threshold = max(
                        0.5, min(0.95, perf.avg_confidence - 0.1)
                    )
                else:
                    analysis.recommended_threshold = DEFAULT_ESCALATION_THRESHOLD

                # Build explanation
                accuracy_str = (
                    f"{perf.accuracy:.1%}" if perf.accuracy else f"{perf.agreement_rate:.1%} agreement"
                )
                analysis.recommendation_reason = (
                    f"{tier.value.upper()} tier ({perf.model_name}) achieves "
                    f"{accuracy_str} with {perf.p95_latency_ms}ms p95 latency "
                    f"on {perf.sample_count} samples"
                )
                return

        # No tier met requirements
        analysis.recommendation_reason = (
            "No tier met the minimum requirements. Consider lowering thresholds or "
            "using larger models."
        )

    def generate_recommendations(
        self, analysis: ExperimentAnalysis
    ) -> RoutingRecommendation:
        """Generate routing configuration recommendations from analysis.

        Args:
            analysis: The experiment analysis to generate recommendations from.

        Returns:
            RoutingRecommendation with suggested configuration changes.
        """
        warnings: list[str] = []
        reasoning_parts: list[str] = []
        routing_updates: dict[tuple[str, str], ModelTier] = {}
        thresholds: list[float] = []

        for task_type, task_analysis in analysis.task_analyses.items():
            if task_analysis.recommended_tier:
                # Update routing table for all complexity levels
                for complexity in ["low", "medium", "high"]:
                    current_tier = DEFAULT_ROUTING_TABLE.get((task_type, complexity))

                    # Only suggest changes if different from default
                    if current_tier != task_analysis.recommended_tier:
                        routing_updates[(task_type, complexity)] = (
                            task_analysis.recommended_tier
                        )
                        reasoning_parts.append(
                            f"  - {task_type}/{complexity}: {current_tier.value if current_tier else 'none'} "
                            f"→ {task_analysis.recommended_tier.value}"
                        )

                if task_analysis.recommended_threshold:
                    thresholds.append(task_analysis.recommended_threshold)

                reasoning_parts.append(f"  {task_analysis.recommendation_reason}")
            else:
                warnings.append(
                    f"Insufficient data for {task_type}: "
                    f"{task_analysis.recommendation_reason}"
                )

        # Calculate overall recommended threshold
        recommended_threshold = (
            sum(thresholds) / len(thresholds)
            if thresholds
            else DEFAULT_ESCALATION_THRESHOLD
        )

        # Calculate confidence in recommendations
        total_samples = sum(
            perf.sample_count
            for task_analysis in analysis.task_analyses.values()
            for perf in task_analysis.tier_performance.values()
        )

        if total_samples >= self.min_sample_size * 3:
            confidence = min(1.0, total_samples / (self.min_sample_size * 10))
        else:
            confidence = 0.5
            warnings.append(
                f"Low sample count ({total_samples}). Recommendations may not be reliable."
            )

        # Build overall reasoning
        reasoning = f"Based on analysis of {analysis.total_files} files:\n"
        if routing_updates:
            reasoning += "Suggested routing changes:\n"
            reasoning += "\n".join(reasoning_parts)
        else:
            reasoning += "No changes recommended. Current routing is optimal."

        return RoutingRecommendation(
            escalation_threshold=round(recommended_threshold, 2),
            routing_table_updates=routing_updates,
            confidence_in_recommendations=round(confidence, 2),
            reasoning=reasoning,
            warnings=warnings,
        )

    def apply_recommendations(
        self,
        recommendations: RoutingRecommendation,
        config_path: str | Path | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Apply recommendations to the model configuration.

        Args:
            recommendations: The recommendations to apply.
            config_path: Path to agent_config.json. If None, uses default.
            dry_run: If True, returns what would change without modifying files.

        Returns:
            Dictionary describing the changes made or that would be made.
        """
        if config_path is None:
            config_path = Path(".organizer/agent/agent_config.json")
        else:
            config_path = Path(config_path)

        # Load existing config
        existing_config: dict[str, Any] = {}
        if config_path.exists():
            with open(config_path) as f:
                existing_config = json.load(f)

        llm_models = existing_config.get("llm_models", {})
        old_threshold = llm_models.get(
            "escalation_threshold", DEFAULT_ESCALATION_THRESHOLD
        )

        changes = {
            "config_path": str(config_path),
            "dry_run": dry_run,
            "escalation_threshold": {
                "old": old_threshold,
                "new": recommendations.escalation_threshold,
                "changed": old_threshold != recommendations.escalation_threshold,
            },
            "routing_table_updates": [
                {
                    "task_complexity": f"{task},{complexity}",
                    "new_tier": tier.value,
                }
                for (task, complexity), tier in recommendations.routing_table_updates.items()
            ],
            "warnings": recommendations.warnings,
        }

        if not dry_run:
            # Apply changes
            llm_models["escalation_threshold"] = recommendations.escalation_threshold

            # Note: Routing table updates would need to be stored separately
            # or the routing table would need to be made configurable
            # For now, we just update the threshold
            existing_config["llm_models"] = llm_models

            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(config_path, "w") as f:
                json.dump(existing_config, f, indent=2)

            changes["applied"] = True
        else:
            changes["applied"] = False

        return changes


def analyze_experiment_file(
    filepath: str | Path,
    min_accuracy: float = DEFAULT_MIN_ACCURACY,
    max_latency_ms: int = DEFAULT_MAX_LATENCY_MS,
) -> ExperimentAnalysis:
    """Analyze an experiment result file.

    Args:
        filepath: Path to the experiment result JSON file.
        min_accuracy: Minimum acceptable accuracy.
        max_latency_ms: Maximum acceptable p95 latency.

    Returns:
        ExperimentAnalysis with performance metrics and recommendations.
    """
    result = load_experiment_result(filepath)
    tuner = RoutingTuner(
        min_accuracy=min_accuracy, max_latency_ms=max_latency_ms
    )
    return tuner.analyze_experiment(result)


def generate_tuning_report(
    analysis: ExperimentAnalysis, recommendations: RoutingRecommendation
) -> str:
    """Generate a human-readable tuning report.

    Args:
        analysis: The experiment analysis.
        recommendations: The generated recommendations.

    Returns:
        Formatted report string.
    """
    lines = [
        "=" * 60,
        "MODEL ROUTING TUNING REPORT",
        "=" * 60,
        "",
        f"Experiment: {analysis.experiment_name}",
        f"Models analyzed: {', '.join(analysis.models_analyzed)}",
        f"Total files: {analysis.total_files}",
        f"Overall agreement rate: {analysis.overall_agreement_rate:.1%}",
        "",
        "-" * 60,
        "PER-TASK ANALYSIS",
        "-" * 60,
    ]

    for task_type, task_analysis in analysis.task_analyses.items():
        lines.append(f"\n{task_type.upper()}:")

        for tier, perf in sorted(
            task_analysis.tier_performance.items(), key=lambda x: x[0].value
        ):
            accuracy_str = (
                f"accuracy={perf.accuracy:.1%}"
                if perf.accuracy
                else f"agreement={perf.agreement_rate:.1%}"
            )
            lines.append(
                f"  {tier.value.upper()} ({perf.model_name}):"
            )
            avg_conf_str = f"{perf.avg_confidence:.2f}" if perf.avg_confidence else "N/A"
            lines.append(
                f"    {accuracy_str}, p95={perf.p95_latency_ms}ms, "
                f"avg_conf={avg_conf_str}, "
                f"samples={perf.sample_count}"
            )

        lines.append(f"  Recommendation: {task_analysis.recommendation_reason}")

    lines.extend([
        "",
        "-" * 60,
        "RECOMMENDATIONS",
        "-" * 60,
        "",
        f"Escalation threshold: {recommendations.escalation_threshold}",
        f"Confidence: {recommendations.confidence_in_recommendations:.0%}",
        "",
        recommendations.reasoning,
    ])

    if recommendations.warnings:
        lines.extend([
            "",
            "WARNINGS:",
            *[f"  ⚠️  {w}" for w in recommendations.warnings],
        ])

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
