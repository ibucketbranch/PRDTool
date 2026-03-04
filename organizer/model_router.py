"""Model router for multi-LLM task routing.

Routes tasks to the appropriate model tier based on task profile, availability,
and configuration. Supports a multi-tier architecture:
- T1 Fast: 8B models for high-volume decisions (~3s)
- T2 Smart: 14B models for complex reasoning (~10s)
- T3 Cloud: 480B/671B remote models for hardest problems (~15-30s)

Example usage:
    router = ModelRouter(llm_client=client)
    model = router.select_model(TaskProfile(task_type="classify", complexity="low"))
    response = client.generate(prompt, model=model)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from organizer.llm_client import LLMClient


class ModelTier(Enum):
    """Model capability tiers for task routing.

    FAST: 8B models, ~3s response time, for classification and yes/no validation
    SMART: 14B models, ~10s response time, for complex reasoning
    CLOUD: 480B/671B remote models, ~15-30s, for hardest problems (opt-in)
    """

    FAST = "fast"
    SMART = "smart"
    CLOUD = "cloud"


class TaskType(Enum):
    """Types of tasks that can be routed to LLM models."""

    CLASSIFY = "classify"  # File/document classification
    VALIDATE = "validate"  # Yes/no validation decisions
    ANALYZE = "analyze"  # Complex analysis requiring reasoning
    ENRICH = "enrich"  # Metadata extraction and enrichment
    GENERATE = "generate"  # Text generation (summaries, descriptions)


class Complexity(Enum):
    """Task complexity levels."""

    LOW = "low"  # Simple, straightforward tasks
    MEDIUM = "medium"  # Moderate reasoning required
    HIGH = "high"  # Complex reasoning, multi-step analysis


# Default model names for each tier
DEFAULT_FAST_MODEL = "llama3.1:8b-instruct-q8_0"
DEFAULT_SMART_MODEL = "qwen2.5-coder:14b"
DEFAULT_CLOUD_MODEL = None  # Cloud is opt-in, no default

# Default escalation threshold
DEFAULT_ESCALATION_THRESHOLD = 0.75

# Health cache duration in seconds
HEALTH_CACHE_DURATION_S = 60


@dataclass
class TaskProfile:
    """Profile describing a task for model routing.

    Attributes:
        task_type: The type of task (classify, validate, analyze, enrich, generate).
        complexity: Task complexity level (low, medium, high).
        content_length: Length of content to process (affects model selection).
    """

    task_type: str
    complexity: str = "low"
    content_length: int = 0

    def __post_init__(self) -> None:
        """Validate task_type and complexity values."""
        valid_types = {t.value for t in TaskType}
        if self.task_type not in valid_types:
            raise ValueError(
                f"Invalid task_type '{self.task_type}'. Must be one of: {valid_types}"
            )

        valid_complexities = {c.value for c in Complexity}
        if self.complexity not in valid_complexities:
            raise ValueError(
                f"Invalid complexity '{self.complexity}'. Must be one of: {valid_complexities}"
            )


@dataclass
class ModelConfig:
    """Configuration for model routing.

    Attributes:
        fast: Model name for T1 Fast tier.
        smart: Model name for T2 Smart tier.
        cloud: Model name for T3 Cloud tier (optional).
        cloud_enabled: Whether cloud models are enabled.
        escalation_threshold: Confidence threshold for escalation (0.0-1.0).
    """

    fast: str = DEFAULT_FAST_MODEL
    smart: str = DEFAULT_SMART_MODEL
    cloud: str | None = DEFAULT_CLOUD_MODEL
    cloud_enabled: bool = False
    escalation_threshold: float = DEFAULT_ESCALATION_THRESHOLD

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelConfig":
        """Create ModelConfig from a dictionary."""
        return cls(
            fast=data.get("fast", DEFAULT_FAST_MODEL),
            smart=data.get("smart", DEFAULT_SMART_MODEL),
            cloud=data.get("cloud"),
            cloud_enabled=data.get("cloud_enabled", False),
            escalation_threshold=data.get(
                "escalation_threshold", DEFAULT_ESCALATION_THRESHOLD
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "fast": self.fast,
            "smart": self.smart,
            "cloud": self.cloud,
            "cloud_enabled": self.cloud_enabled,
            "escalation_threshold": self.escalation_threshold,
        }


@dataclass
class RoutingDecision:
    """Result of a model routing decision.

    Attributes:
        model: The selected model name.
        tier: The tier of the selected model.
        reason: Why this model was selected.
        fallback_used: Whether a fallback model was used due to unavailability.
    """

    model: str
    tier: ModelTier
    reason: str
    fallback_used: bool = False


@dataclass
class HealthState:
    """Cached health state for Ollama and models.

    Attributes:
        ollama_available: Whether Ollama is accessible.
        available_models: Set of model names that are loaded.
        timestamp: When this health state was captured.
    """

    ollama_available: bool
    available_models: set[str] = field(default_factory=set)
    timestamp: float = 0.0

    def is_expired(self) -> bool:
        """Check if the health state cache has expired."""
        return time.time() - self.timestamp > HEALTH_CACHE_DURATION_S


# Default routing table: maps (task_type, complexity) to preferred tier
DEFAULT_ROUTING_TABLE: dict[tuple[str, str], ModelTier] = {
    # FAST tier for high-volume, simple tasks
    ("classify", "low"): ModelTier.FAST,
    ("classify", "medium"): ModelTier.FAST,
    ("validate", "low"): ModelTier.FAST,
    ("validate", "medium"): ModelTier.FAST,
    # SMART tier for complex reasoning
    ("classify", "high"): ModelTier.SMART,
    ("validate", "high"): ModelTier.SMART,
    ("analyze", "low"): ModelTier.SMART,
    ("analyze", "medium"): ModelTier.SMART,
    ("analyze", "high"): ModelTier.SMART,
    ("enrich", "low"): ModelTier.SMART,
    ("enrich", "medium"): ModelTier.SMART,
    ("enrich", "high"): ModelTier.SMART,
    # GENERATE can vary
    ("generate", "low"): ModelTier.FAST,
    ("generate", "medium"): ModelTier.SMART,
    ("generate", "high"): ModelTier.SMART,
}


class ModelRouter:
    """Routes tasks to the appropriate LLM model tier.

    Uses a multi-tier architecture to route tasks based on complexity and
    requirements. Supports availability checking and graceful degradation
    when preferred models are unavailable.

    Example:
        router = ModelRouter(llm_client=client)
        model = router.select_model(TaskProfile(task_type="classify", complexity="low"))
        response = client.generate(prompt, model=model)
    """

    def __init__(
        self,
        llm_client: "LLMClient | None" = None,
        config: ModelConfig | None = None,
        config_path: str | Path | None = None,
    ):
        """Initialize the model router.

        Args:
            llm_client: LLM client for availability checks. If None, availability
                checks are skipped.
            config: Model configuration. If None, loads from config_path or uses defaults.
            config_path: Path to agent_config.json. If None, uses default path.
        """
        self._llm_client = llm_client
        self._config = config or self._load_config(config_path)
        self._health_state: HealthState | None = None
        self._routing_table = DEFAULT_ROUTING_TABLE.copy()

    def _load_config(self, config_path: str | Path | None = None) -> ModelConfig:
        """Load model configuration from file or use defaults.

        Args:
            config_path: Path to config file. If None, uses default path.

        Returns:
            ModelConfig with loaded or default values.
        """
        if config_path is None:
            config_path = Path(".organizer/agent/agent_config.json")
        else:
            config_path = Path(config_path)

        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                    llm_models = data.get("llm_models", {})
                    return ModelConfig.from_dict(llm_models)
            except (json.JSONDecodeError, OSError):
                pass

        return ModelConfig()

    def _refresh_health_state(self) -> HealthState:
        """Refresh the cached health state.

        Returns:
            Updated HealthState with current Ollama and model availability.
        """
        if self._llm_client is None:
            # No client, assume all models are available (for testing)
            return HealthState(
                ollama_available=True,
                available_models={self._config.fast, self._config.smart},
                timestamp=time.time(),
            )

        ollama_available = self._llm_client.is_ollama_available(timeout_s=5)

        available_models: set[str] = set()
        if ollama_available:
            models = self._llm_client.list_models(timeout_s=5)
            for model in models:
                model_name = model.get("name") or model.get("model", "")
                if model_name:
                    available_models.add(model_name)
                    # Also add the base name without tag for partial matching
                    if ":" in model_name:
                        base_name = model_name.split(":")[0]
                        available_models.add(base_name)

        self._health_state = HealthState(
            ollama_available=ollama_available,
            available_models=available_models,
            timestamp=time.time(),
        )
        return self._health_state

    def _get_health_state(self) -> HealthState:
        """Get current health state, refreshing if expired.

        Returns:
            Current HealthState.
        """
        if self._health_state is None or self._health_state.is_expired():
            return self._refresh_health_state()
        return self._health_state

    def _is_model_available(self, model: str | None) -> bool:
        """Check if a model is available.

        Args:
            model: Model name to check.

        Returns:
            True if model is available, False otherwise.
        """
        if model is None:
            return False

        health = self._get_health_state()
        if not health.ollama_available:
            return False

        # Check exact match
        if model in health.available_models:
            return True

        # Check if any available model starts with this name
        for available in health.available_models:
            if available.startswith(f"{model}:") or available == model:
                return True

        return False

    def _get_model_for_tier(self, tier: ModelTier) -> str | None:
        """Get the configured model name for a tier.

        Args:
            tier: The model tier.

        Returns:
            Model name or None if not configured.
        """
        if tier == ModelTier.FAST:
            return self._config.fast
        elif tier == ModelTier.SMART:
            return self._config.smart
        elif tier == ModelTier.CLOUD:
            return self._config.cloud if self._config.cloud_enabled else None
        return None

    def _get_preferred_tier(self, profile: TaskProfile) -> ModelTier:
        """Get the preferred tier for a task profile.

        Args:
            profile: The task profile.

        Returns:
            The preferred ModelTier for this task.
        """
        key = (profile.task_type, profile.complexity)
        return self._routing_table.get(key, ModelTier.FAST)

    def select_model(self, profile: TaskProfile) -> str:
        """Select the best available model for a task.

        Considers task requirements, model availability, and configuration
        to select the most appropriate model. Falls back to lower tiers
        if preferred models are unavailable.

        Args:
            profile: Task profile describing the work to be done.

        Returns:
            Model name to use for the task.

        Raises:
            RuntimeError: If no models are available (Ollama down).
        """
        decision = self.route(profile)
        return decision.model

    def route(self, profile: TaskProfile) -> RoutingDecision:
        """Route a task to the appropriate model with detailed decision info.

        Args:
            profile: Task profile describing the work to be done.

        Returns:
            RoutingDecision with model selection details.

        Raises:
            RuntimeError: If no models are available (Ollama down).
        """
        preferred_tier = self._get_preferred_tier(profile)
        preferred_model = self._get_model_for_tier(preferred_tier)

        # Check if preferred model is available
        if self._is_model_available(preferred_model):
            return RoutingDecision(
                model=preferred_model,  # type: ignore[arg-type]
                tier=preferred_tier,
                reason=f"Preferred model for {profile.task_type}/{profile.complexity}",
                fallback_used=False,
            )

        # Try fallback chain: SMART -> FAST -> error
        fallback_chain: list[ModelTier] = []
        if preferred_tier == ModelTier.CLOUD:
            fallback_chain = [ModelTier.SMART, ModelTier.FAST]
        elif preferred_tier == ModelTier.SMART:
            fallback_chain = [ModelTier.FAST]
        # FAST has no fallback to lower tier

        for fallback_tier in fallback_chain:
            fallback_model = self._get_model_for_tier(fallback_tier)
            if self._is_model_available(fallback_model):
                return RoutingDecision(
                    model=fallback_model,  # type: ignore[arg-type]
                    tier=fallback_tier,
                    reason=f"Fallback from {preferred_tier.value} to {fallback_tier.value}",
                    fallback_used=True,
                )

        # Check if Ollama is even available
        health = self._get_health_state()
        if not health.ollama_available:
            raise RuntimeError(
                "Ollama is not available. Use keyword-based fallback logic."
            )

        # Ollama is up but no models available
        raise RuntimeError(
            f"No models available. Preferred: {preferred_model}, "
            f"Available: {health.available_models}"
        )

    def get_escalation_threshold(self) -> float:
        """Get the configured escalation threshold.

        Returns:
            Confidence threshold for escalation (0.0-1.0).
        """
        return self._config.escalation_threshold

    def should_escalate(self, confidence: float, current_tier: ModelTier) -> bool:
        """Determine if a task should be escalated to a higher tier.

        Args:
            confidence: The confidence score from the current model (0.0-1.0).
            current_tier: The current model tier.

        Returns:
            True if the task should be escalated, False otherwise.
        """
        if confidence >= self._config.escalation_threshold:
            return False

        # Can only escalate from FAST to SMART, or SMART to CLOUD
        if current_tier == ModelTier.FAST:
            return True
        elif current_tier == ModelTier.SMART and self._config.cloud_enabled:
            return True

        return False

    def get_escalation_tier(self, current_tier: ModelTier) -> ModelTier | None:
        """Get the next tier for escalation.

        Args:
            current_tier: The current model tier.

        Returns:
            The next tier to escalate to, or None if at highest tier.
        """
        if current_tier == ModelTier.FAST:
            return ModelTier.SMART
        elif current_tier == ModelTier.SMART and self._config.cloud_enabled:
            return ModelTier.CLOUD
        return None

    def is_ollama_available(self) -> bool:
        """Check if Ollama is available.

        Returns:
            True if Ollama is accessible, False otherwise.
        """
        health = self._get_health_state()
        return health.ollama_available

    def get_available_models(self) -> set[str]:
        """Get the set of available model names.

        Returns:
            Set of model names that are currently loaded.
        """
        health = self._get_health_state()
        return health.available_models.copy()

    def invalidate_cache(self) -> None:
        """Invalidate the health state cache, forcing a refresh on next check."""
        self._health_state = None

    @property
    def config(self) -> ModelConfig:
        """Get the current model configuration."""
        return self._config
