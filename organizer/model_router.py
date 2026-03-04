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
from typing import TYPE_CHECKING, Any, Callable

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
class EscalationStep:
    """Record of a single step in the escalation chain.

    Attributes:
        model: The model used for this step.
        tier: The tier of the model.
        confidence: The confidence score returned (if available).
        duration_ms: Time taken for this step.
        escalated: Whether this step triggered escalation to a higher tier.
        response_text: The response text from the model.
    """

    model: str
    tier: ModelTier
    confidence: float | None
    duration_ms: int
    escalated: bool
    response_text: str


@dataclass
class EscalationResult:
    """Result of a generation request with automatic escalation.

    Attributes:
        text: The final response text from the model.
        model_used: The final model that produced the accepted response.
        tier_used: The tier of the final model.
        confidence: The final confidence score (if available).
        total_duration_ms: Total time across all steps.
        steps: List of all escalation steps attempted.
        escalation_count: Number of times the task was escalated.
        used_keyword_fallback: Whether keyword fallback was used instead of LLM.
    """

    text: str
    model_used: str
    tier_used: ModelTier
    confidence: float | None
    total_duration_ms: int
    steps: list[EscalationStep]
    escalation_count: int
    used_keyword_fallback: bool = False

    @classmethod
    def from_keyword_fallback(cls, text: str, duration_ms: int = 0) -> "EscalationResult":
        """Create a result from keyword-based fallback logic.

        Args:
            text: The result from keyword fallback.
            duration_ms: Time taken for keyword fallback.

        Returns:
            EscalationResult indicating keyword fallback was used.
        """
        return cls(
            text=text,
            model_used="keyword_fallback",
            tier_used=ModelTier.FAST,  # Treat as FAST tier equivalent
            confidence=None,
            total_duration_ms=duration_ms,
            steps=[],
            escalation_count=0,
            used_keyword_fallback=True,
        )


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


@dataclass
class DegradationResult:
    """Result of a graceful degradation attempt.

    Attributes:
        text: The result text (from LLM or keyword fallback).
        model_used: The model that produced the result (or "keyword_fallback").
        tier_used: The tier of the model used (FAST for keyword fallback).
        used_llm: Whether an LLM was used (False if keyword fallback).
        degradation_reason: Why degradation occurred (if applicable).
        duration_ms: Time taken for the operation.
    """

    text: str
    model_used: str
    tier_used: ModelTier
    used_llm: bool
    degradation_reason: str | None
    duration_ms: int


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

    def generate_with_escalation(
        self,
        prompt: str,
        profile: TaskProfile,
        confidence_extractor: Callable[[str], float | None] | None = None,
        keyword_fallback: Callable[[str], str] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> EscalationResult:
        """Generate a response with automatic confidence-based escalation.

        This method implements the full escalation workflow:
        1. Start with the preferred model for the task profile
        2. If confidence < threshold, escalate to next tier
        3. Chain: T1 → T2 → T3 → keyword fallback (never loops)
        4. Log each escalation step with original and new confidence

        Args:
            prompt: The prompt to send to the model.
            profile: Task profile describing the work to be done.
            confidence_extractor: Function to extract confidence from model response.
                Takes response text, returns confidence (0.0-1.0) or None if not found.
                If None, no escalation based on confidence will occur.
            keyword_fallback: Function to use when LLM is unavailable.
                Takes the prompt, returns a result string.
                If None and LLM is unavailable, raises RuntimeError.
            temperature: Temperature for generation (default 0.0 for determinism).
            max_tokens: Maximum tokens to generate.

        Returns:
            EscalationResult with the final response and escalation history.

        Raises:
            RuntimeError: If LLM is unavailable and no keyword_fallback provided.
        """
        if self._llm_client is None:
            raise RuntimeError("LLM client is required for generate_with_escalation")

        steps: list[EscalationStep] = []
        total_duration_ms = 0
        escalation_count = 0

        # Check if Ollama is available
        if not self.is_ollama_available():
            if keyword_fallback is not None:
                start_time = time.time()
                result = keyword_fallback(prompt)
                duration_ms = int((time.time() - start_time) * 1000)
                return EscalationResult.from_keyword_fallback(result, duration_ms)
            raise RuntimeError(
                "Ollama is not available and no keyword_fallback provided"
            )

        # Get initial routing decision
        try:
            decision = self.route(profile)
        except RuntimeError:
            # No models available
            if keyword_fallback is not None:
                start_time = time.time()
                result = keyword_fallback(prompt)
                duration_ms = int((time.time() - start_time) * 1000)
                return EscalationResult.from_keyword_fallback(result, duration_ms)
            raise

        current_model = decision.model
        current_tier = decision.tier
        final_text = ""
        final_confidence: float | None = None

        # Escalation loop: T1 → T2 → T3 → keyword fallback
        max_iterations = 4  # Prevent infinite loops
        for iteration in range(max_iterations):
            # Generate response
            response = self._llm_client.generate(
                prompt=prompt,
                model=current_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            duration_ms = response.duration_ms
            total_duration_ms += duration_ms

            if not response.success:
                # Model failed, try to escalate or fall back
                step = EscalationStep(
                    model=current_model,
                    tier=current_tier,
                    confidence=None,
                    duration_ms=duration_ms,
                    escalated=True,
                    response_text=response.error or "Generation failed",
                )
                steps.append(step)

                # Try next tier
                next_tier = self.get_escalation_tier(current_tier)
                if next_tier is not None:
                    next_model = self._get_model_for_tier(next_tier)
                    if next_model and self._is_model_available(next_model):
                        current_model = next_model
                        current_tier = next_tier
                        escalation_count += 1
                        continue

                # No higher tier available, try keyword fallback
                if keyword_fallback is not None:
                    start_time = time.time()
                    result = keyword_fallback(prompt)
                    fallback_duration = int((time.time() - start_time) * 1000)
                    total_duration_ms += fallback_duration
                    return EscalationResult(
                        text=result,
                        model_used="keyword_fallback",
                        tier_used=current_tier,
                        confidence=None,
                        total_duration_ms=total_duration_ms,
                        steps=steps,
                        escalation_count=escalation_count,
                        used_keyword_fallback=True,
                    )
                raise RuntimeError(f"Generation failed: {response.error}")

            # Extract confidence if extractor provided
            confidence: float | None = None
            if confidence_extractor is not None:
                confidence = confidence_extractor(response.text)

            # Check if we should escalate
            should_escalate = False
            if confidence is not None and self.should_escalate(confidence, current_tier):
                next_tier = self.get_escalation_tier(current_tier)
                if next_tier is not None:
                    next_model = self._get_model_for_tier(next_tier)
                    if next_model and self._is_model_available(next_model):
                        should_escalate = True

            # Record this step
            step = EscalationStep(
                model=current_model,
                tier=current_tier,
                confidence=confidence,
                duration_ms=duration_ms,
                escalated=should_escalate,
                response_text=response.text,
            )
            steps.append(step)

            if should_escalate:
                # Escalate to next tier
                next_tier = self.get_escalation_tier(current_tier)
                next_model = self._get_model_for_tier(next_tier)  # type: ignore
                current_model = next_model  # type: ignore
                current_tier = next_tier  # type: ignore
                escalation_count += 1
                continue

            # Accept this response
            final_text = response.text
            final_confidence = confidence
            break

        return EscalationResult(
            text=final_text,
            model_used=current_model,
            tier_used=current_tier,
            confidence=final_confidence,
            total_duration_ms=total_duration_ms,
            steps=steps,
            escalation_count=escalation_count,
            used_keyword_fallback=False,
        )

    def get_degradation_chain(self, preferred_tier: ModelTier) -> list[ModelTier]:
        """Get the degradation chain from a preferred tier.

        Returns the fallback sequence when the preferred tier is unavailable.
        The chain goes: preferred → lower tiers → keyword fallback.

        Args:
            preferred_tier: The tier to start from.

        Returns:
            List of tiers to try in order (including the preferred tier first).
        """
        if preferred_tier == ModelTier.CLOUD:
            return [ModelTier.CLOUD, ModelTier.SMART, ModelTier.FAST]
        elif preferred_tier == ModelTier.SMART:
            return [ModelTier.SMART, ModelTier.FAST]
        else:
            return [ModelTier.FAST]

    def get_best_available_tier(self) -> ModelTier | None:
        """Get the highest available model tier.

        Returns:
            The highest available tier, or None if no models available.
        """
        health = self._get_health_state()
        if not health.ollama_available:
            return None

        # Check from highest to lowest
        if self._config.cloud_enabled and self._is_model_available(self._config.cloud):
            return ModelTier.CLOUD
        if self._is_model_available(self._config.smart):
            return ModelTier.SMART
        if self._is_model_available(self._config.fast):
            return ModelTier.FAST

        return None

    def generate_with_degradation(
        self,
        prompt: str,
        profile: TaskProfile,
        keyword_fallback: Callable[[str], str],
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> DegradationResult:
        """Generate a response with graceful degradation.

        This method provides a simpler interface than generate_with_escalation
        for cases where you just want the best available result with automatic
        fallback to keyword-based logic.

        Degradation chain: T2 → T1 → keyword rules

        The method:
        1. Checks if Ollama is available
        2. If not, immediately uses keyword fallback
        3. If available, tries to route to best model
        4. Falls back through tiers if higher ones unavailable
        5. Uses keyword fallback as last resort

        Args:
            prompt: The prompt to send to the model.
            profile: Task profile describing the work to be done.
            keyword_fallback: Function to use when LLM is unavailable.
                Takes the prompt, returns a result string.
            temperature: Temperature for generation (default 0.0 for determinism).
            max_tokens: Maximum tokens to generate.

        Returns:
            DegradationResult with the result and degradation info.
        """
        start_time = time.time()

        # Check if Ollama is available at all
        if not self.is_ollama_available():
            result = keyword_fallback(prompt)
            duration_ms = int((time.time() - start_time) * 1000)
            return DegradationResult(
                text=result,
                model_used="keyword_fallback",
                tier_used=ModelTier.FAST,
                used_llm=False,
                degradation_reason="Ollama is not available",
                duration_ms=duration_ms,
            )

        # Try to route to a model
        try:
            decision = self.route(profile)
        except RuntimeError as e:
            # No models available, use keyword fallback
            result = keyword_fallback(prompt)
            duration_ms = int((time.time() - start_time) * 1000)
            return DegradationResult(
                text=result,
                model_used="keyword_fallback",
                tier_used=ModelTier.FAST,
                used_llm=False,
                degradation_reason=str(e),
                duration_ms=duration_ms,
            )

        # We have a model, try to generate
        if self._llm_client is None:
            # No client configured, use keyword fallback
            result = keyword_fallback(prompt)
            duration_ms = int((time.time() - start_time) * 1000)
            return DegradationResult(
                text=result,
                model_used="keyword_fallback",
                tier_used=ModelTier.FAST,
                used_llm=False,
                degradation_reason="No LLM client configured",
                duration_ms=duration_ms,
            )

        response = self._llm_client.generate(
            prompt=prompt,
            model=decision.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if response.success:
            duration_ms = int((time.time() - start_time) * 1000)
            degradation_reason = None
            if decision.fallback_used:
                degradation_reason = decision.reason
            return DegradationResult(
                text=response.text,
                model_used=decision.model,
                tier_used=decision.tier,
                used_llm=True,
                degradation_reason=degradation_reason,
                duration_ms=duration_ms,
            )

        # Generation failed, try degradation chain
        degradation_chain = self.get_degradation_chain(decision.tier)

        # Skip the tier we already tried
        for tier in degradation_chain:
            if tier == decision.tier:
                continue

            model = self._get_model_for_tier(tier)
            if model and self._is_model_available(model):
                response = self._llm_client.generate(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                if response.success:
                    duration_ms = int((time.time() - start_time) * 1000)
                    return DegradationResult(
                        text=response.text,
                        model_used=model,
                        tier_used=tier,
                        used_llm=True,
                        degradation_reason=f"Degraded from {decision.tier.value} to {tier.value}",
                        duration_ms=duration_ms,
                    )

        # All tiers failed, use keyword fallback
        result = keyword_fallback(prompt)
        duration_ms = int((time.time() - start_time) * 1000)
        return DegradationResult(
            text=result,
            model_used="keyword_fallback",
            tier_used=ModelTier.FAST,
            used_llm=False,
            degradation_reason="All LLM tiers failed, using keyword fallback",
            duration_ms=duration_ms,
        )

    def is_llm_operational(self) -> bool:
        """Check if any LLM model is operational.

        This is a quick check that can be used to decide whether to
        attempt LLM-based logic or go straight to keyword fallback.

        Returns:
            True if Ollama is available and at least one model is loaded.
        """
        health = self._get_health_state()
        if not health.ollama_available:
            return False

        # Check if any configured model is available
        if self._is_model_available(self._config.fast):
            return True
        if self._is_model_available(self._config.smart):
            return True
        if self._config.cloud_enabled and self._is_model_available(self._config.cloud):
            return True

        return False

    def get_degradation_status(self) -> dict[str, Any]:
        """Get current degradation status for observability.

        Returns:
            Dictionary with:
                - ollama_available: Whether Ollama is accessible
                - available_tiers: List of available model tiers
                - preferred_tier: The highest available tier
                - will_use_keyword_fallback: Whether keyword fallback will be used
                - health_cache_age_s: Age of the health cache in seconds
        """
        health = self._get_health_state()

        available_tiers: list[str] = []
        if self._is_model_available(self._config.fast):
            available_tiers.append("fast")
        if self._is_model_available(self._config.smart):
            available_tiers.append("smart")
        if self._config.cloud_enabled and self._is_model_available(self._config.cloud):
            available_tiers.append("cloud")

        best_tier = self.get_best_available_tier()

        cache_age = time.time() - health.timestamp if health.timestamp > 0 else 0

        return {
            "ollama_available": health.ollama_available,
            "available_tiers": available_tiers,
            "preferred_tier": best_tier.value if best_tier else None,
            "will_use_keyword_fallback": not health.ollama_available
            or len(available_tiers) == 0,
            "health_cache_age_s": round(cache_age, 2),
        }
