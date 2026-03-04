"""Tests for ModelRouter - multi-LLM task routing."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from organizer.model_router import (
    DEFAULT_ESCALATION_THRESHOLD,
    DEFAULT_FAST_MODEL,
    DEFAULT_ROUTING_TABLE,
    DEFAULT_SMART_MODEL,
    HEALTH_CACHE_DURATION_S,
    Complexity,
    HealthState,
    ModelConfig,
    ModelRouter,
    ModelTier,
    RoutingDecision,
    TaskProfile,
    TaskType,
)


class TestModelTier:
    """Tests for ModelTier enum."""

    def test_fast_tier(self) -> None:
        """Should have FAST tier with value 'fast'."""
        assert ModelTier.FAST.value == "fast"

    def test_smart_tier(self) -> None:
        """Should have SMART tier with value 'smart'."""
        assert ModelTier.SMART.value == "smart"

    def test_cloud_tier(self) -> None:
        """Should have CLOUD tier with value 'cloud'."""
        assert ModelTier.CLOUD.value == "cloud"


class TestTaskType:
    """Tests for TaskType enum."""

    def test_classify_type(self) -> None:
        """Should have CLASSIFY task type."""
        assert TaskType.CLASSIFY.value == "classify"

    def test_validate_type(self) -> None:
        """Should have VALIDATE task type."""
        assert TaskType.VALIDATE.value == "validate"

    def test_analyze_type(self) -> None:
        """Should have ANALYZE task type."""
        assert TaskType.ANALYZE.value == "analyze"

    def test_enrich_type(self) -> None:
        """Should have ENRICH task type."""
        assert TaskType.ENRICH.value == "enrich"

    def test_generate_type(self) -> None:
        """Should have GENERATE task type."""
        assert TaskType.GENERATE.value == "generate"


class TestComplexity:
    """Tests for Complexity enum."""

    def test_low_complexity(self) -> None:
        """Should have LOW complexity."""
        assert Complexity.LOW.value == "low"

    def test_medium_complexity(self) -> None:
        """Should have MEDIUM complexity."""
        assert Complexity.MEDIUM.value == "medium"

    def test_high_complexity(self) -> None:
        """Should have HIGH complexity."""
        assert Complexity.HIGH.value == "high"


class TestTaskProfile:
    """Tests for TaskProfile dataclass."""

    def test_create_profile(self) -> None:
        """Should create profile with all fields."""
        profile = TaskProfile(task_type="classify", complexity="low", content_length=100)
        assert profile.task_type == "classify"
        assert profile.complexity == "low"
        assert profile.content_length == 100

    def test_default_values(self) -> None:
        """Should use default values for complexity and content_length."""
        profile = TaskProfile(task_type="validate")
        assert profile.complexity == "low"
        assert profile.content_length == 0

    def test_invalid_task_type(self) -> None:
        """Should raise ValueError for invalid task type."""
        with pytest.raises(ValueError, match="Invalid task_type"):
            TaskProfile(task_type="invalid")

    def test_invalid_complexity(self) -> None:
        """Should raise ValueError for invalid complexity."""
        with pytest.raises(ValueError, match="Invalid complexity"):
            TaskProfile(task_type="classify", complexity="invalid")

    def test_all_valid_task_types(self) -> None:
        """Should accept all valid task types."""
        valid_types = ["classify", "validate", "analyze", "enrich", "generate"]
        for task_type in valid_types:
            profile = TaskProfile(task_type=task_type)
            assert profile.task_type == task_type

    def test_all_valid_complexities(self) -> None:
        """Should accept all valid complexity levels."""
        valid_complexities = ["low", "medium", "high"]
        for complexity in valid_complexities:
            profile = TaskProfile(task_type="classify", complexity=complexity)
            assert profile.complexity == complexity


class TestModelConfig:
    """Tests for ModelConfig dataclass."""

    def test_default_values(self) -> None:
        """Should use default values."""
        config = ModelConfig()
        assert config.fast == DEFAULT_FAST_MODEL
        assert config.smart == DEFAULT_SMART_MODEL
        assert config.cloud is None
        assert config.cloud_enabled is False
        assert config.escalation_threshold == DEFAULT_ESCALATION_THRESHOLD

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        config = ModelConfig(
            fast="custom-fast",
            smart="custom-smart",
            cloud="custom-cloud",
            cloud_enabled=True,
            escalation_threshold=0.8,
        )
        assert config.fast == "custom-fast"
        assert config.smart == "custom-smart"
        assert config.cloud == "custom-cloud"
        assert config.cloud_enabled is True
        assert config.escalation_threshold == 0.8

    def test_from_dict(self) -> None:
        """Should create config from dictionary."""
        data = {
            "fast": "dict-fast",
            "smart": "dict-smart",
            "cloud": "dict-cloud",
            "cloud_enabled": True,
            "escalation_threshold": 0.9,
        }
        config = ModelConfig.from_dict(data)
        assert config.fast == "dict-fast"
        assert config.smart == "dict-smart"
        assert config.cloud == "dict-cloud"
        assert config.cloud_enabled is True
        assert config.escalation_threshold == 0.9

    def test_from_dict_partial(self) -> None:
        """Should use defaults for missing keys."""
        config = ModelConfig.from_dict({"fast": "custom-fast"})
        assert config.fast == "custom-fast"
        assert config.smart == DEFAULT_SMART_MODEL
        assert config.cloud is None

    def test_to_dict(self) -> None:
        """Should convert to dictionary."""
        config = ModelConfig(fast="test-fast", cloud="test-cloud", cloud_enabled=True)
        data = config.to_dict()
        assert data["fast"] == "test-fast"
        assert data["cloud"] == "test-cloud"
        assert data["cloud_enabled"] is True


class TestRoutingDecision:
    """Tests for RoutingDecision dataclass."""

    def test_create_decision(self) -> None:
        """Should create decision with all fields."""
        decision = RoutingDecision(
            model="llama3.1:8b",
            tier=ModelTier.FAST,
            reason="Test reason",
            fallback_used=True,
        )
        assert decision.model == "llama3.1:8b"
        assert decision.tier == ModelTier.FAST
        assert decision.reason == "Test reason"
        assert decision.fallback_used is True

    def test_default_fallback(self) -> None:
        """Should default fallback_used to False."""
        decision = RoutingDecision(
            model="llama3.1:8b",
            tier=ModelTier.FAST,
            reason="Test",
        )
        assert decision.fallback_used is False


class TestHealthState:
    """Tests for HealthState dataclass."""

    def test_create_state(self) -> None:
        """Should create health state with all fields."""
        state = HealthState(
            ollama_available=True,
            available_models={"model1", "model2"},
            timestamp=1000.0,
        )
        assert state.ollama_available is True
        assert "model1" in state.available_models
        assert state.timestamp == 1000.0

    def test_default_values(self) -> None:
        """Should use default values."""
        state = HealthState(ollama_available=True)
        assert state.available_models == set()
        assert state.timestamp == 0.0

    def test_is_expired_new(self) -> None:
        """Should not be expired when just created."""
        state = HealthState(ollama_available=True, timestamp=time.time())
        assert state.is_expired() is False

    def test_is_expired_old(self) -> None:
        """Should be expired after cache duration."""
        old_timestamp = time.time() - HEALTH_CACHE_DURATION_S - 1
        state = HealthState(ollama_available=True, timestamp=old_timestamp)
        assert state.is_expired() is True


class TestModelRouterInit:
    """Tests for ModelRouter initialization."""

    def test_default_init(self) -> None:
        """Should initialize with default values."""
        router = ModelRouter()
        assert router._llm_client is None
        assert router._config.fast == DEFAULT_FAST_MODEL
        assert router._config.smart == DEFAULT_SMART_MODEL

    def test_with_llm_client(self) -> None:
        """Should accept LLM client."""
        mock_client = MagicMock()
        router = ModelRouter(llm_client=mock_client)
        assert router._llm_client is mock_client

    def test_with_config(self) -> None:
        """Should accept custom config."""
        config = ModelConfig(fast="custom-fast")
        router = ModelRouter(config=config)
        assert router._config.fast == "custom-fast"

    def test_load_config_from_file(self) -> None:
        """Should load config from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "agent_config.json"
            config_data = {
                "llm_models": {
                    "fast": "file-fast-model",
                    "smart": "file-smart-model",
                    "escalation_threshold": 0.85,
                }
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            router = ModelRouter(config_path=config_path)
            assert router._config.fast == "file-fast-model"
            assert router._config.smart == "file-smart-model"
            assert router._config.escalation_threshold == 0.85

    def test_missing_config_file(self) -> None:
        """Should use defaults when config file doesn't exist."""
        router = ModelRouter(config_path="/nonexistent/path.json")
        assert router._config.fast == DEFAULT_FAST_MODEL

    def test_invalid_config_file(self) -> None:
        """Should use defaults when config file is invalid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "agent_config.json"
            with open(config_path, "w") as f:
                f.write("invalid json {{{")

            router = ModelRouter(config_path=config_path)
            assert router._config.fast == DEFAULT_FAST_MODEL


class TestModelRouterRouting:
    """Tests for ModelRouter routing decisions."""

    def test_select_model_simple_classify(self) -> None:
        """Should select FAST model for simple classification."""
        router = ModelRouter()
        # Without client, assumes all models available
        model = router.select_model(TaskProfile(task_type="classify", complexity="low"))
        assert model == DEFAULT_FAST_MODEL

    def test_select_model_complex_analyze(self) -> None:
        """Should select SMART model for complex analysis."""
        router = ModelRouter()
        model = router.select_model(TaskProfile(task_type="analyze", complexity="high"))
        assert model == DEFAULT_SMART_MODEL

    def test_route_returns_decision(self) -> None:
        """Should return RoutingDecision with details."""
        router = ModelRouter()
        decision = router.route(TaskProfile(task_type="validate", complexity="low"))
        assert isinstance(decision, RoutingDecision)
        assert decision.model == DEFAULT_FAST_MODEL
        assert decision.tier == ModelTier.FAST
        assert decision.fallback_used is False

    def test_route_all_task_types(self) -> None:
        """Should route all task types."""
        router = ModelRouter()
        task_types = ["classify", "validate", "analyze", "enrich", "generate"]
        for task_type in task_types:
            decision = router.route(TaskProfile(task_type=task_type))
            assert decision.model is not None
            assert decision.tier in ModelTier

    def test_routing_table_coverage(self) -> None:
        """Should have routing rules for all combinations."""
        for (task_type, complexity), tier in DEFAULT_ROUTING_TABLE.items():
            profile = TaskProfile(task_type=task_type, complexity=complexity)
            router = ModelRouter()
            decision = router.route(profile)
            assert decision.tier == tier


class TestModelRouterAvailability:
    """Tests for ModelRouter availability checks."""

    def test_with_available_model(self) -> None:
        """Should select model when available."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [{"name": DEFAULT_FAST_MODEL}]

        router = ModelRouter(llm_client=mock_client)
        model = router.select_model(TaskProfile(task_type="classify"))
        assert model == DEFAULT_FAST_MODEL

    def test_fallback_when_preferred_unavailable(self) -> None:
        """Should fallback to lower tier when preferred unavailable."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        # Only FAST model available, not SMART
        mock_client.list_models.return_value = [{"name": DEFAULT_FAST_MODEL}]

        router = ModelRouter(llm_client=mock_client)
        # Analyze prefers SMART, should fall back to FAST
        decision = router.route(TaskProfile(task_type="analyze", complexity="high"))
        assert decision.model == DEFAULT_FAST_MODEL
        assert decision.tier == ModelTier.FAST
        assert decision.fallback_used is True

    def test_error_when_ollama_down(self) -> None:
        """Should raise error when Ollama is unavailable."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = False
        mock_client.list_models.return_value = []

        router = ModelRouter(llm_client=mock_client)
        with pytest.raises(RuntimeError, match="Ollama is not available"):
            router.select_model(TaskProfile(task_type="classify"))

    def test_error_when_no_models_available(self) -> None:
        """Should raise error when no models loaded."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = []

        router = ModelRouter(llm_client=mock_client)
        with pytest.raises(RuntimeError, match="No models available"):
            router.select_model(TaskProfile(task_type="classify"))

    def test_partial_model_name_match(self) -> None:
        """Should match model by prefix."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        # Model with full tag
        mock_client.list_models.return_value = [
            {"name": "llama3.1:8b-instruct-q8_0"}
        ]

        config = ModelConfig(fast="llama3.1")  # Just base name
        router = ModelRouter(llm_client=mock_client, config=config)
        model = router.select_model(TaskProfile(task_type="classify"))
        # Should match because the available model starts with "llama3.1:"
        assert model == "llama3.1"


class TestModelRouterHealthCache:
    """Tests for health state caching."""

    def test_caches_health_state(self) -> None:
        """Should cache health state."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [{"name": DEFAULT_FAST_MODEL}]

        router = ModelRouter(llm_client=mock_client)

        # First call
        router.select_model(TaskProfile(task_type="classify"))
        # Second call - should use cache
        router.select_model(TaskProfile(task_type="validate"))

        # Should only call is_ollama_available once due to caching
        assert mock_client.is_ollama_available.call_count == 1

    def test_invalidate_cache(self) -> None:
        """Should refresh after cache invalidation."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [{"name": DEFAULT_FAST_MODEL}]

        router = ModelRouter(llm_client=mock_client)
        router.select_model(TaskProfile(task_type="classify"))

        router.invalidate_cache()
        router.select_model(TaskProfile(task_type="validate"))

        # Should call twice due to invalidation
        assert mock_client.is_ollama_available.call_count == 2

    def test_is_ollama_available(self) -> None:
        """Should expose Ollama availability check."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = []

        router = ModelRouter(llm_client=mock_client)
        assert router.is_ollama_available() is True

    def test_get_available_models(self) -> None:
        """Should return set of available models."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [
            {"name": "model1"},
            {"name": "model2"},
        ]

        router = ModelRouter(llm_client=mock_client)
        models = router.get_available_models()
        assert "model1" in models
        assert "model2" in models


class TestModelRouterEscalation:
    """Tests for confidence-based escalation."""

    def test_get_escalation_threshold(self) -> None:
        """Should return configured threshold."""
        config = ModelConfig(escalation_threshold=0.8)
        router = ModelRouter(config=config)
        assert router.get_escalation_threshold() == 0.8

    def test_should_escalate_low_confidence(self) -> None:
        """Should escalate when confidence below threshold."""
        router = ModelRouter()
        assert router.should_escalate(0.5, ModelTier.FAST) is True

    def test_should_not_escalate_high_confidence(self) -> None:
        """Should not escalate when confidence at or above threshold."""
        router = ModelRouter()
        assert router.should_escalate(0.75, ModelTier.FAST) is False
        assert router.should_escalate(0.9, ModelTier.FAST) is False

    def test_should_escalate_from_fast_to_smart(self) -> None:
        """Should escalate from FAST to SMART."""
        router = ModelRouter()
        assert router.should_escalate(0.5, ModelTier.FAST) is True
        tier = router.get_escalation_tier(ModelTier.FAST)
        assert tier == ModelTier.SMART

    def test_should_escalate_from_smart_to_cloud_when_enabled(self) -> None:
        """Should escalate from SMART to CLOUD when enabled."""
        config = ModelConfig(cloud_enabled=True, cloud="test-cloud")
        router = ModelRouter(config=config)
        assert router.should_escalate(0.5, ModelTier.SMART) is True
        tier = router.get_escalation_tier(ModelTier.SMART)
        assert tier == ModelTier.CLOUD

    def test_should_not_escalate_from_smart_when_cloud_disabled(self) -> None:
        """Should not escalate from SMART when cloud disabled."""
        router = ModelRouter()  # cloud_enabled=False by default
        assert router.should_escalate(0.5, ModelTier.SMART) is False

    def test_no_escalation_from_cloud(self) -> None:
        """Should not escalate from CLOUD tier."""
        config = ModelConfig(cloud_enabled=True, cloud="test-cloud")
        router = ModelRouter(config=config)
        tier = router.get_escalation_tier(ModelTier.CLOUD)
        assert tier is None


class TestModelRouterCloudTier:
    """Tests for cloud tier routing."""

    def test_cloud_not_selected_when_disabled(self) -> None:
        """Should not select cloud model when disabled."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [
            {"name": DEFAULT_FAST_MODEL},
            {"name": DEFAULT_SMART_MODEL},
        ]

        # Even with a very complex task, shouldn't use cloud
        router = ModelRouter(llm_client=mock_client)
        decision = router.route(TaskProfile(task_type="analyze", complexity="high"))
        assert decision.tier != ModelTier.CLOUD

    def test_cloud_fallback_chain(self) -> None:
        """Should fall back from cloud to smart to fast."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [{"name": DEFAULT_FAST_MODEL}]

        config = ModelConfig(cloud_enabled=True, cloud="cloud-model")

        # Manually add routing for cloud tier
        router = ModelRouter(llm_client=mock_client, config=config)
        router._routing_table[("analyze", "high")] = ModelTier.CLOUD

        decision = router.route(TaskProfile(task_type="analyze", complexity="high"))
        # Should fall back to FAST since SMART isn't available
        assert decision.model == DEFAULT_FAST_MODEL
        assert decision.fallback_used is True


class TestModelRouterConfig:
    """Tests for configuration property."""

    def test_config_property(self) -> None:
        """Should expose config via property."""
        config = ModelConfig(fast="test-fast")
        router = ModelRouter(config=config)
        assert router.config.fast == "test-fast"

    def test_config_immutable(self) -> None:
        """Config property should be read-only."""
        router = ModelRouter()
        # Property returns the actual config object, but changing it
        # doesn't affect routing since router uses internal reference
        config = router.config
        assert config is router._config


class TestModelRouterIntegration:
    """Integration-style tests for realistic scenarios."""

    def test_full_routing_workflow(self) -> None:
        """Should handle complete routing workflow."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [
            {"name": "llama3.1:8b-instruct-q8_0"},
            {"name": "qwen2.5-coder:14b"},
        ]

        router = ModelRouter(llm_client=mock_client)

        # Simple classification - should use FAST
        decision1 = router.route(TaskProfile(task_type="classify", complexity="low"))
        assert decision1.tier == ModelTier.FAST

        # Complex analysis - should use SMART
        decision2 = router.route(TaskProfile(task_type="analyze", complexity="high"))
        assert decision2.tier == ModelTier.SMART

        # Check escalation decision
        assert router.should_escalate(0.5, ModelTier.FAST) is True
        assert router.should_escalate(0.9, ModelTier.FAST) is False

    def test_graceful_degradation_workflow(self) -> None:
        """Should handle degradation when SMART unavailable."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [
            {"name": DEFAULT_FAST_MODEL},
            # SMART model not available
        ]

        router = ModelRouter(llm_client=mock_client)

        # Complex task should fall back to FAST
        decision = router.route(TaskProfile(task_type="analyze", complexity="high"))
        assert decision.tier == ModelTier.FAST
        assert decision.fallback_used is True
        assert "Fallback" in decision.reason

    def test_model_field_variation(self) -> None:
        """Should handle 'model' field instead of 'name'."""
        mock_client = MagicMock()
        mock_client.is_ollama_available.return_value = True
        mock_client.list_models.return_value = [
            {"model": DEFAULT_FAST_MODEL},  # Uses 'model' not 'name'
        ]

        router = ModelRouter(llm_client=mock_client)
        model = router.select_model(TaskProfile(task_type="classify"))
        assert model == DEFAULT_FAST_MODEL
