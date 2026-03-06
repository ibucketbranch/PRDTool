"""Multi-LLM Experiment Framework.

Provides infrastructure for running experiments comparing different LLM models
on the same set of test files. This enables data-driven model selection and
tuning of routing thresholds.

Example usage:
    experiment = Experiment(
        name="classify_comparison",
        models_to_compare=["llama3.1:8b-instruct-q8_0", "qwen2.5-coder:14b"],
        test_files=["/path/to/invoice.pdf", "/path/to/contract.pdf"],
    )
    result = run_experiment(experiment, llm_client=client)
    print(result.agreement_rate)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient


DEFAULT_EXPERIMENTS_DIR = ".organizer/experiments"


@dataclass
class ModelResult:
    """Result from a single model on a single test file.

    Attributes:
        model: The model name that produced this result.
        file_path: Path to the test file.
        response_text: The raw response text from the model.
        parsed_result: Parsed JSON result (if response was valid JSON).
        confidence: Extracted confidence score (0.0-1.0) or None.
        duration_ms: Time taken for generation in milliseconds.
        success: Whether the generation succeeded.
        error: Error message if generation failed.
    """

    model: str
    file_path: str
    response_text: str
    parsed_result: dict[str, Any] | None
    confidence: float | None
    duration_ms: int
    success: bool
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "model": self.model,
            "file_path": self.file_path,
            "response_text": self.response_text,
            "parsed_result": self.parsed_result,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelResult":
        """Create from dictionary."""
        return cls(
            model=data.get("model", ""),
            file_path=data.get("file_path", ""),
            response_text=data.get("response_text", ""),
            parsed_result=data.get("parsed_result"),
            confidence=data.get("confidence"),
            duration_ms=data.get("duration_ms", 0),
            success=data.get("success", False),
            error=data.get("error", ""),
        )


@dataclass
class FileResults:
    """Results for all models on a single test file.

    Attributes:
        file_path: Path to the test file.
        results: Dictionary mapping model name to ModelResult.
        ground_truth: Optional expected result for accuracy calculation.
    """

    file_path: str
    results: dict[str, ModelResult] = field(default_factory=dict)
    ground_truth: dict[str, Any] | None = None

    def agreement_count(self) -> int:
        """Count how many models agree on the result.

        Returns:
            Number of models that agree on the bin/category.
        """
        if len(self.results) < 2:
            return len(self.results)

        # Extract the 'bin' or 'category' field from each result
        values: list[str] = []
        for result in self.results.values():
            if result.parsed_result:
                # Check common field names
                val = (
                    result.parsed_result.get("bin")
                    or result.parsed_result.get("category")
                    or result.parsed_result.get("document_type")
                    or result.parsed_result.get("result")
                )
                if val:
                    values.append(str(val).lower())

        if not values:
            return 0

        # Find the most common value
        from collections import Counter

        counter = Counter(values)
        most_common_count = counter.most_common(1)[0][1] if counter else 0
        return most_common_count

    def models_agree(self) -> bool:
        """Check if all models agree on the result.

        Returns:
            True if all models agree on the bin/category.
        """
        return self.agreement_count() == len(self.results)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "ground_truth": self.ground_truth,
            "agreement_count": self.agreement_count(),
            "models_agree": self.models_agree(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileResults":
        """Create from dictionary."""
        results = {
            k: ModelResult.from_dict(v) for k, v in data.get("results", {}).items()
        }
        return cls(
            file_path=data.get("file_path", ""),
            results=results,
            ground_truth=data.get("ground_truth"),
        )


@dataclass
class LatencyStats:
    """Latency statistics for a model.

    Attributes:
        model: The model name.
        p50_ms: 50th percentile latency (median).
        p95_ms: 95th percentile latency.
        p99_ms: 99th percentile latency.
        avg_ms: Average latency.
        min_ms: Minimum latency.
        max_ms: Maximum latency.
        sample_count: Number of samples.
    """

    model: str
    p50_ms: int
    p95_ms: int
    p99_ms: int
    avg_ms: int
    min_ms: int
    max_ms: int
    sample_count: int

    @classmethod
    def from_durations(cls, model: str, durations: list[int]) -> "LatencyStats":
        """Calculate statistics from a list of durations.

        Args:
            model: The model name.
            durations: List of durations in milliseconds.

        Returns:
            LatencyStats with calculated percentiles.
        """
        if not durations:
            return cls(
                model=model,
                p50_ms=0,
                p95_ms=0,
                p99_ms=0,
                avg_ms=0,
                min_ms=0,
                max_ms=0,
                sample_count=0,
            )

        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        def percentile(p: float) -> int:
            """Calculate the p-th percentile."""
            if n == 1:
                return sorted_durations[0]
            idx = (p / 100) * (n - 1)
            lower = int(idx)
            upper = min(lower + 1, n - 1)
            weight = idx - lower
            return int(sorted_durations[lower] * (1 - weight) + sorted_durations[upper] * weight)

        return cls(
            model=model,
            p50_ms=percentile(50),
            p95_ms=percentile(95),
            p99_ms=percentile(99),
            avg_ms=int(sum(sorted_durations) / n),
            min_ms=sorted_durations[0],
            max_ms=sorted_durations[-1],
            sample_count=n,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "model": self.model,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "avg_ms": self.avg_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "sample_count": self.sample_count,
        }


@dataclass
class Experiment:
    """Configuration for an LLM comparison experiment.

    Attributes:
        name: Human-readable name for the experiment.
        models_to_compare: List of model names to test.
        test_files: List of file paths to test against.
        expected_results: Optional ground truth for accuracy calculation.
            Maps file path to expected result dictionary.
        prompt_template: Optional custom prompt template. If None, uses classify_file.
        task_type: Type of task being tested (classify, validate, analyze, etc.).
    """

    name: str
    models_to_compare: list[str]
    test_files: list[str]
    expected_results: dict[str, dict[str, Any]] | None = None
    prompt_template: str | None = None
    task_type: str = "classify"

    def __post_init__(self) -> None:
        """Validate experiment configuration."""
        if not self.models_to_compare:
            raise ValueError("At least one model must be specified")
        if not self.test_files:
            raise ValueError("At least one test file must be specified")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "models_to_compare": self.models_to_compare,
            "test_files": self.test_files,
            "expected_results": self.expected_results,
            "prompt_template": self.prompt_template,
            "task_type": self.task_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Experiment":
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            models_to_compare=data.get("models_to_compare", []),
            test_files=data.get("test_files", []),
            expected_results=data.get("expected_results"),
            prompt_template=data.get("prompt_template"),
            task_type=data.get("task_type", "classify"),
        )


@dataclass
class ExperimentResult:
    """Result of running an experiment.

    Attributes:
        experiment: The experiment configuration.
        file_results: Results for each test file.
        latency_stats: Latency statistics per model.
        agreement_rate: Percentage of files where all models agreed.
        accuracy_vs_ground_truth: Per-model accuracy if ground truth provided.
        total_duration_ms: Total time for the entire experiment.
        started_at: ISO timestamp when experiment started.
        completed_at: ISO timestamp when experiment completed.
    """

    experiment: Experiment
    file_results: list[FileResults]
    latency_stats: dict[str, LatencyStats]
    agreement_rate: float
    accuracy_vs_ground_truth: dict[str, float] | None
    total_duration_ms: int
    started_at: str
    completed_at: str

    @property
    def agreement_matrix(self) -> dict[str, dict[str, int]]:
        """Calculate agreement matrix between models.

        Returns:
            Dictionary mapping model pairs to agreement counts.
            Example: {"llama:qwen": 8, "llama:mistral": 7}
        """
        models = self.experiment.models_to_compare
        matrix: dict[str, dict[str, int]] = {m: {m2: 0 for m2 in models} for m in models}

        for file_result in self.file_results:
            # Get all model results for this file
            results_by_model: dict[str, str] = {}
            for model, result in file_result.results.items():
                if result.parsed_result:
                    val = (
                        result.parsed_result.get("bin")
                        or result.parsed_result.get("category")
                        or result.parsed_result.get("document_type")
                        or result.parsed_result.get("result")
                    )
                    if val:
                        results_by_model[model] = str(val).lower()

            # Count agreements between each pair
            for m1 in models:
                for m2 in models:
                    if m1 in results_by_model and m2 in results_by_model:
                        if results_by_model[m1] == results_by_model[m2]:
                            matrix[m1][m2] += 1

        return matrix

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "experiment": self.experiment.to_dict(),
            "file_results": [fr.to_dict() for fr in self.file_results],
            "latency_stats": {k: v.to_dict() for k, v in self.latency_stats.items()},
            "agreement_rate": self.agreement_rate,
            "agreement_matrix": self.agreement_matrix,
            "accuracy_vs_ground_truth": self.accuracy_vs_ground_truth,
            "total_duration_ms": self.total_duration_ms,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentResult":
        """Create from dictionary."""
        experiment = Experiment.from_dict(data.get("experiment", {}))
        file_results = [
            FileResults.from_dict(fr) for fr in data.get("file_results", [])
        ]

        latency_stats: dict[str, LatencyStats] = {}
        for model, stats_data in data.get("latency_stats", {}).items():
            latency_stats[model] = LatencyStats(
                model=stats_data.get("model", model),
                p50_ms=stats_data.get("p50_ms", 0),
                p95_ms=stats_data.get("p95_ms", 0),
                p99_ms=stats_data.get("p99_ms", 0),
                avg_ms=stats_data.get("avg_ms", 0),
                min_ms=stats_data.get("min_ms", 0),
                max_ms=stats_data.get("max_ms", 0),
                sample_count=stats_data.get("sample_count", 0),
            )

        return cls(
            experiment=experiment,
            file_results=file_results,
            latency_stats=latency_stats,
            agreement_rate=data.get("agreement_rate", 0.0),
            accuracy_vs_ground_truth=data.get("accuracy_vs_ground_truth"),
            total_duration_ms=data.get("total_duration_ms", 0),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
        )


def _read_file_content(file_path: str, max_chars: int = 500) -> str:
    """Read file content for prompt context.

    Args:
        file_path: Path to the file.
        max_chars: Maximum characters to read.

    Returns:
        File content preview or error message.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"[File not found: {file_path}]"

        # Handle different file types
        suffix = path.suffix.lower()
        if suffix in {".pdf", ".docx", ".xlsx", ".pptx"}:
            return f"[Binary file: {path.name}]"

        content = path.read_text(errors="replace")
        if len(content) > max_chars:
            content = content[:max_chars] + "..."
        return content
    except Exception as e:
        return f"[Error reading file: {e}]"


def _parse_json_response(text: str) -> dict[str, Any] | None:
    """Parse JSON from LLM response.

    Args:
        text: The response text from the LLM.

    Returns:
        Parsed JSON dictionary or None if parsing failed.
    """
    # Try to find JSON in the response
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Look for JSON block in markdown code blocks
    import re

    json_match = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Look for JSON object anywhere in text
    json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _extract_confidence(parsed: dict[str, Any] | None) -> float | None:
    """Extract confidence score from parsed result.

    Args:
        parsed: Parsed JSON result.

    Returns:
        Confidence score (0.0-1.0) or None.
    """
    if not parsed:
        return None

    confidence = parsed.get("confidence")
    if confidence is None:
        return None

    try:
        conf_float = float(confidence)
        # Ensure it's in valid range
        if 0.0 <= conf_float <= 1.0:
            return conf_float
        return None
    except (ValueError, TypeError):
        return None


def _get_default_prompt(task_type: str, filename: str, content: str) -> str:
    """Get default prompt for a task type.

    Args:
        task_type: Type of task (classify, validate, etc.).
        filename: The filename to classify.
        content: Content preview.

    Returns:
        Prompt string.
    """
    if task_type == "classify":
        return f"""Classify this file into a category.

Filename: {filename}
Content Preview: {content}

Reply with JSON:
{{
    "bin": "category_name",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}"""
    elif task_type == "validate":
        return f"""Validate if this file belongs in its category.

Filename: {filename}
Content Preview: {content}

Reply with JSON:
{{
    "valid": true/false,
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}"""
    else:
        return f"""Analyze this file.

Filename: {filename}
Content Preview: {content}

Reply with JSON:
{{
    "result": "analysis result",
    "confidence": 0.0 to 1.0,
    "reason": "brief explanation"
}}"""


def run_experiment(
    experiment: Experiment,
    llm_client: "LLMClient",
    progress_callback: Any | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> ExperimentResult:
    """Run an experiment comparing multiple models.

    Args:
        experiment: The experiment configuration.
        llm_client: LLM client for making requests.
        progress_callback: Optional callback for progress updates.
            Called with (current_step, total_steps, message).
        temperature: Temperature for generation (default 0.0 for consistency).
        max_tokens: Maximum tokens to generate.

    Returns:
        ExperimentResult with all results and statistics.
    """
    started_at = datetime.now().isoformat()
    start_time = time.time()

    file_results: list[FileResults] = []
    durations_by_model: dict[str, list[int]] = {
        model: [] for model in experiment.models_to_compare
    }

    total_steps = len(experiment.test_files) * len(experiment.models_to_compare)
    current_step = 0

    for file_path in experiment.test_files:
        filename = Path(file_path).name
        content = _read_file_content(file_path)

        # Build prompt
        if experiment.prompt_template:
            prompt = experiment.prompt_template.format(
                filename=filename,
                content=content,
                file_path=file_path,
            )
        else:
            prompt = _get_default_prompt(experiment.task_type, filename, content)

        # Get ground truth if available
        ground_truth = None
        if experiment.expected_results:
            ground_truth = experiment.expected_results.get(file_path)

        file_result = FileResults(
            file_path=file_path,
            ground_truth=ground_truth,
        )

        for model in experiment.models_to_compare:
            current_step += 1
            if progress_callback:
                progress_callback(
                    current_step,
                    total_steps,
                    f"Testing {model} on {filename}",
                )

            # Generate response
            response = llm_client.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Parse result
            parsed = None
            confidence = None
            if response.success:
                parsed = _parse_json_response(response.text)
                confidence = _extract_confidence(parsed)

            result = ModelResult(
                model=model,
                file_path=file_path,
                response_text=response.text,
                parsed_result=parsed,
                confidence=confidence,
                duration_ms=response.duration_ms,
                success=response.success,
                error=response.error,
            )

            file_result.results[model] = result
            if response.success:
                durations_by_model[model].append(response.duration_ms)

        file_results.append(file_result)

    # Calculate latency stats
    latency_stats = {
        model: LatencyStats.from_durations(model, durations)
        for model, durations in durations_by_model.items()
    }

    # Calculate agreement rate
    if file_results:
        agreements = sum(1 for fr in file_results if fr.models_agree())
        agreement_rate = agreements / len(file_results)
    else:
        agreement_rate = 0.0

    # Calculate accuracy vs ground truth
    accuracy_vs_ground_truth = None
    if experiment.expected_results:
        accuracy_vs_ground_truth = {}
        for model in experiment.models_to_compare:
            correct = 0
            total = 0
            for file_result in file_results:
                if file_result.ground_truth and model in file_result.results:
                    total += 1
                    result = file_result.results[model]
                    if result.parsed_result:
                        # Compare bin/category
                        expected_bin = str(
                            file_result.ground_truth.get("bin", "")
                            or file_result.ground_truth.get("category", "")
                        ).lower()
                        actual_bin = str(
                            result.parsed_result.get("bin", "")
                            or result.parsed_result.get("category", "")
                        ).lower()
                        if expected_bin and actual_bin and expected_bin == actual_bin:
                            correct += 1
            accuracy_vs_ground_truth[model] = correct / total if total > 0 else 0.0

    completed_at = datetime.now().isoformat()
    total_duration_ms = int((time.time() - start_time) * 1000)

    return ExperimentResult(
        experiment=experiment,
        file_results=file_results,
        latency_stats=latency_stats,
        agreement_rate=agreement_rate,
        accuracy_vs_ground_truth=accuracy_vs_ground_truth,
        total_duration_ms=total_duration_ms,
        started_at=started_at,
        completed_at=completed_at,
    )


def save_experiment_result(
    result: ExperimentResult,
    output_dir: str | Path | None = None,
) -> Path:
    """Save experiment results to a JSON file.

    Args:
        result: The experiment result to save.
        output_dir: Directory to save results. If None, uses default.

    Returns:
        Path to the saved results file.
    """
    if output_dir is None:
        output_dir = Path(DEFAULT_EXPERIMENTS_DIR)
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename from experiment name and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = result.experiment.name.replace(" ", "_").replace("/", "_")
    filename = f"{safe_name}_{timestamp}.json"

    filepath = output_dir / filename
    with open(filepath, "w") as f:
        json.dump(result.to_dict(), f, indent=2)

    return filepath


def load_experiment_result(filepath: str | Path) -> ExperimentResult:
    """Load experiment results from a JSON file.

    Args:
        filepath: Path to the results file.

    Returns:
        Loaded ExperimentResult.
    """
    with open(filepath) as f:
        data = json.load(f)
    return ExperimentResult.from_dict(data)


def generate_comparison_table(result: ExperimentResult) -> str:
    """Generate a human-readable comparison table.

    Args:
        result: The experiment result.

    Returns:
        Formatted comparison table string.
    """
    lines = [
        f"Experiment: {result.experiment.name}",
        f"Models: {', '.join(result.experiment.models_to_compare)}",
        f"Test Files: {len(result.experiment.test_files)}",
        f"Agreement Rate: {result.agreement_rate:.1%}",
        "",
        "Latency Statistics (ms):",
        "-" * 60,
        f"{'Model':<30} {'P50':<8} {'P95':<8} {'P99':<8} {'Avg':<8}",
        "-" * 60,
    ]

    for model, stats in result.latency_stats.items():
        lines.append(
            f"{model:<30} {stats.p50_ms:<8} {stats.p95_ms:<8} "
            f"{stats.p99_ms:<8} {stats.avg_ms:<8}"
        )

    if result.accuracy_vs_ground_truth:
        lines.extend([
            "",
            "Accuracy vs Ground Truth:",
            "-" * 40,
        ])
        for model, accuracy in result.accuracy_vs_ground_truth.items():
            lines.append(f"  {model}: {accuracy:.1%}")

    lines.extend([
        "",
        f"Total Duration: {result.total_duration_ms}ms",
        f"Started: {result.started_at}",
        f"Completed: {result.completed_at}",
    ])

    return "\n".join(lines)


def list_experiment_results(
    experiments_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List all saved experiment results.

    Args:
        experiments_dir: Directory containing results. If None, uses default.

    Returns:
        List of experiment summaries (name, timestamp, filepath).
    """
    if experiments_dir is None:
        experiments_dir = Path(DEFAULT_EXPERIMENTS_DIR)
    else:
        experiments_dir = Path(experiments_dir)

    results: list[dict[str, Any]] = []

    if not experiments_dir.exists():
        return results

    for filepath in sorted(experiments_dir.glob("*.json"), reverse=True):
        try:
            with open(filepath) as f:
                data = json.load(f)
            results.append({
                "name": data.get("experiment", {}).get("name", "Unknown"),
                "models": data.get("experiment", {}).get("models_to_compare", []),
                "agreement_rate": data.get("agreement_rate", 0.0),
                "completed_at": data.get("completed_at", ""),
                "filepath": str(filepath),
            })
        except (json.JSONDecodeError, OSError):
            continue

    return results
