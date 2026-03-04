"""Tests for LLMClient - Ollama API wrapper."""

from unittest.mock import MagicMock, patch

import requests

from organizer.llm_client import (
    DEFAULT_OLLAMA_URL,
    LLMClient,
    LLMResponse,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_response(self) -> None:
        """Should create a response with all fields."""
        response = LLMResponse(
            text="Hello, world!",
            model_used="llama3.1:8b",
            duration_ms=1500,
            tokens_eval=50,
            success=True,
        )
        assert response.text == "Hello, world!"
        assert response.model_used == "llama3.1:8b"
        assert response.duration_ms == 1500
        assert response.tokens_eval == 50
        assert response.success is True
        assert response.error == ""

    def test_create_response_with_error(self) -> None:
        """Should create a response with error field."""
        response = LLMResponse(
            text="",
            model_used="llama3.1:8b",
            duration_ms=0,
            tokens_eval=0,
            success=False,
            error="Connection failed",
        )
        assert response.success is False
        assert response.error == "Connection failed"

    def test_from_error(self) -> None:
        """Should create a failed response from error message."""
        response = LLMResponse.from_error("Timeout occurred", model="test-model")
        assert response.success is False
        assert response.error == "Timeout occurred"
        assert response.model_used == "test-model"
        assert response.text == ""
        assert response.duration_ms == 0
        assert response.tokens_eval == 0

    def test_from_error_without_model(self) -> None:
        """Should create error response without model."""
        response = LLMResponse.from_error("Some error")
        assert response.model_used == ""
        assert response.error == "Some error"


class TestLLMClientInit:
    """Tests for LLMClient initialization."""

    def test_default_init(self) -> None:
        """Should initialize with default values."""
        client = LLMClient()
        assert client._base_url == DEFAULT_OLLAMA_URL
        assert client._default_timeout_s == 60

    def test_custom_url(self) -> None:
        """Should accept custom base URL."""
        client = LLMClient(base_url="http://custom:8080")
        assert client._base_url == "http://custom:8080"

    def test_url_trailing_slash_stripped(self) -> None:
        """Should strip trailing slash from URL."""
        client = LLMClient(base_url="http://localhost:11434/")
        assert client._base_url == "http://localhost:11434"

    def test_custom_timeout(self) -> None:
        """Should accept custom timeout."""
        client = LLMClient(default_timeout_s=120)
        assert client._default_timeout_s == 120

    def test_session_created(self) -> None:
        """Should create a requests session."""
        client = LLMClient()
        assert client._session is not None
        assert isinstance(client._session, requests.Session)


class TestLLMClientGenerate:
    """Tests for LLMClient.generate() method."""

    @patch.object(requests.Session, "post")
    def test_generate_success(self, mock_post: MagicMock) -> None:
        """Should return successful response on valid API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Hello!",
            "model": "llama3.1:8b",
            "eval_count": 10,
        }
        mock_post.return_value = mock_response

        client = LLMClient()
        response = client.generate("Say hello")

        assert response.success is True
        assert response.text == "Hello!"
        assert response.model_used == "llama3.1:8b"
        assert response.tokens_eval == 10
        assert response.duration_ms >= 0  # May be 0 on fast machines

    @patch.object(requests.Session, "post")
    def test_generate_with_custom_params(self, mock_post: MagicMock) -> None:
        """Should pass custom parameters to API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Result", "model": "custom-model"}
        mock_post.return_value = mock_response

        client = LLMClient()
        client.generate(
            "Test prompt",
            model="custom-model",
            temperature=0.5,
            max_tokens=512,
            timeout_s=30,
        )

        call_args = mock_post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")

        assert payload["model"] == "custom-model"
        assert payload["prompt"] == "Test prompt"
        assert payload["options"]["temperature"] == 0.5
        assert payload["options"]["num_predict"] == 512

    @patch.object(requests.Session, "post")
    def test_generate_timeout(self, mock_post: MagicMock) -> None:
        """Should handle timeout errors gracefully."""
        mock_post.side_effect = requests.exceptions.Timeout()

        client = LLMClient(default_timeout_s=10)
        response = client.generate("Test")

        assert response.success is False
        assert "timed out" in response.error.lower()
        assert "10s" in response.error

    @patch.object(requests.Session, "post")
    def test_generate_connection_error(self, mock_post: MagicMock) -> None:
        """Should handle connection errors gracefully."""
        mock_post.side_effect = requests.exceptions.ConnectionError()

        client = LLMClient()
        response = client.generate("Test")

        assert response.success is False
        assert "connect" in response.error.lower()

    @patch.object(requests.Session, "post")
    def test_generate_http_error(self, mock_post: MagicMock) -> None:
        """Should handle HTTP errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        client = LLMClient()
        response = client.generate("Test")

        assert response.success is False
        assert "500" in response.error

    @patch.object(requests.Session, "post")
    def test_generate_unexpected_error(self, mock_post: MagicMock) -> None:
        """Should handle unexpected errors gracefully."""
        mock_post.side_effect = ValueError("Unexpected")

        client = LLMClient()
        response = client.generate("Test")

        assert response.success is False
        assert "Unexpected" in response.error


class TestLLMClientListModels:
    """Tests for LLMClient.list_models() method."""

    @patch.object(requests.Session, "get")
    def test_list_models_success(self, mock_get: MagicMock) -> None:
        """Should return list of models on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b", "size": 4000000000},
                {"name": "qwen2.5:14b", "size": 8000000000},
            ]
        }
        mock_get.return_value = mock_response

        client = LLMClient()
        models = client.list_models()

        assert len(models) == 2
        assert models[0]["name"] == "llama3.1:8b"
        assert models[1]["name"] == "qwen2.5:14b"

    @patch.object(requests.Session, "get")
    def test_list_models_empty(self, mock_get: MagicMock) -> None:
        """Should return empty list when no models available."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": []}
        mock_get.return_value = mock_response

        client = LLMClient()
        models = client.list_models()

        assert models == []

    @patch.object(requests.Session, "get")
    def test_list_models_error(self, mock_get: MagicMock) -> None:
        """Should return empty list on error."""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        client = LLMClient()
        models = client.list_models()

        assert models == []


class TestLLMClientIsModelAvailable:
    """Tests for LLMClient.is_model_available() method."""

    @patch.object(requests.Session, "get")
    def test_model_available_exact_match(self, mock_get: MagicMock) -> None:
        """Should return True for exact model match."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.1:8b"}]
        }
        mock_get.return_value = mock_response

        client = LLMClient()
        assert client.is_model_available("llama3.1:8b") is True

    @patch.object(requests.Session, "get")
    def test_model_available_prefix_match(self, mock_get: MagicMock) -> None:
        """Should return True for model prefix match."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.1:8b-instruct-q8_0"}]
        }
        mock_get.return_value = mock_response

        client = LLMClient()
        # Should match because "llama3.1" starts with "llama3.1:"
        assert client.is_model_available("llama3.1") is True

    @patch.object(requests.Session, "get")
    def test_model_not_available(self, mock_get: MagicMock) -> None:
        """Should return False when model not found."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"name": "llama3.1:8b"}]
        }
        mock_get.return_value = mock_response

        client = LLMClient()
        assert client.is_model_available("nonexistent-model") is False

    @patch.object(requests.Session, "get")
    def test_model_available_with_model_field(self, mock_get: MagicMock) -> None:
        """Should handle 'model' field instead of 'name'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [{"model": "llama3.1:8b"}]
        }
        mock_get.return_value = mock_response

        client = LLMClient()
        assert client.is_model_available("llama3.1:8b") is True


class TestLLMClientIsOllamaAvailable:
    """Tests for LLMClient.is_ollama_available() method."""

    @patch.object(requests.Session, "get")
    def test_ollama_available(self, mock_get: MagicMock) -> None:
        """Should return True when Ollama responds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        client = LLMClient()
        assert client.is_ollama_available() is True

    @patch.object(requests.Session, "get")
    def test_ollama_not_available_connection_error(self, mock_get: MagicMock) -> None:
        """Should return False on connection error."""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        client = LLMClient()
        assert client.is_ollama_available() is False

    @patch.object(requests.Session, "get")
    def test_ollama_not_available_bad_status(self, mock_get: MagicMock) -> None:
        """Should return False on non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        client = LLMClient()
        assert client.is_ollama_available() is False


class TestLLMClientContextManager:
    """Tests for context manager support."""

    def test_context_manager_enter(self) -> None:
        """Should return self on enter."""
        with LLMClient() as client:
            assert isinstance(client, LLMClient)

    @patch.object(requests.Session, "close")
    def test_context_manager_exit_closes_session(self, mock_close: MagicMock) -> None:
        """Should close session on exit."""
        with LLMClient():
            pass
        mock_close.assert_called_once()

    @patch.object(requests.Session, "close")
    def test_close_method(self, mock_close: MagicMock) -> None:
        """Should close session when close() is called."""
        client = LLMClient()
        client.close()
        mock_close.assert_called_once()


class TestLLMClientIntegration:
    """Integration-style tests (still using mocks but testing realistic scenarios)."""

    @patch.object(requests.Session, "post")
    def test_classification_prompt(self, mock_post: MagicMock) -> None:
        """Should handle a typical classification prompt."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"bin": "Finances Bin", "confidence": 0.92, "reason": "Contains invoice keywords"}',
            "model": "llama3.1:8b-instruct-q8_0",
            "eval_count": 25,
        }
        mock_post.return_value = mock_response

        client = LLMClient()
        response = client.generate(
            'Classify file: "invoice_verizon_2024.pdf"',
            temperature=0.3,
        )

        assert response.success is True
        assert "Finances Bin" in response.text
        assert response.tokens_eval == 25

    @patch.object(requests.Session, "post")
    @patch.object(requests.Session, "get")
    def test_fallback_scenario(self, mock_get: MagicMock, mock_post: MagicMock) -> None:
        """Should handle Ollama down scenario."""
        # Simulate Ollama down
        mock_get.side_effect = requests.exceptions.ConnectionError()
        mock_post.side_effect = requests.exceptions.ConnectionError()

        client = LLMClient()

        # Check availability
        assert client.is_ollama_available() is False

        # Try to generate (should fail gracefully)
        response = client.generate("Test prompt")
        assert response.success is False
        assert "connect" in response.error.lower()
