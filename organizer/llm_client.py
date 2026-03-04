"""LLM client for Ollama API integration.

Provides a unified interface for calling local LLM models via Ollama's REST API.
The client supports connection pooling, timeout handling, and graceful degradation.

Example usage:
    client = LLMClient()
    response = client.generate("Classify this document: invoice.pdf", model="llama3.1:8b")
    if response.success:
        print(response.text)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT_S = 60
DEFAULT_MODEL = "llama3.1:8b-instruct-q8_0"


@dataclass
class LLMResponse:
    """Response from an LLM generation request.

    Attributes:
        text: The generated text from the model.
        model_used: The model that produced the response.
        duration_ms: Time taken for generation in milliseconds.
        tokens_eval: Number of tokens evaluated (if available).
        success: Whether the request succeeded.
        error: Error message if the request failed.
    """

    text: str
    model_used: str
    duration_ms: int
    tokens_eval: int
    success: bool
    error: str = ""

    @classmethod
    def from_error(cls, error: str, model: str = "") -> "LLMResponse":
        """Create a failed response from an error message."""
        return cls(
            text="",
            model_used=model,
            duration_ms=0,
            tokens_eval=0,
            success=False,
            error=error,
        )


class LLMClient:
    """Client for calling Ollama LLM API.

    Uses connection pooling via requests.Session for efficiency across
    multiple calls in the same agent cycle.

    Example:
        client = LLMClient()
        response = client.generate("What is 2+2?")
        print(response.text)  # "4"
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        default_timeout_s: int = DEFAULT_TIMEOUT_S,
    ):
        """Initialize the LLM client.

        Args:
            base_url: Base URL for the Ollama API (default: http://localhost:11434).
            default_timeout_s: Default timeout for requests in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._default_timeout_s = default_timeout_s
        self._session = requests.Session()

    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout_s: int | None = None,
    ) -> LLMResponse:
        """Generate text from a prompt using the specified model.

        Args:
            prompt: The prompt to send to the model.
            model: The model name to use (e.g., "llama3.1:8b-instruct-q8_0").
            temperature: Sampling temperature (0.0 to 1.0).
            max_tokens: Maximum tokens to generate.
            timeout_s: Request timeout in seconds (uses default if None).

        Returns:
            LLMResponse with the generated text or error information.
        """
        timeout = timeout_s if timeout_s is not None else self._default_timeout_s

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        start_time = time.time()

        try:
            response = self._session.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            duration_ms = int((time.time() - start_time) * 1000)

            return LLMResponse(
                text=data.get("response", ""),
                model_used=data.get("model", model),
                duration_ms=duration_ms,
                tokens_eval=data.get("eval_count", 0),
                success=True,
            )

        except requests.exceptions.Timeout:
            return LLMResponse.from_error(
                f"Request timed out after {timeout}s",
                model=model,
            )
        except requests.exceptions.ConnectionError:
            return LLMResponse.from_error(
                f"Failed to connect to Ollama at {self._base_url}",
                model=model,
            )
        except requests.exceptions.HTTPError as e:
            return LLMResponse.from_error(
                f"HTTP error: {e.response.status_code} - {e.response.text}",
                model=model,
            )
        except Exception as e:
            return LLMResponse.from_error(
                f"Unexpected error: {e}",
                model=model,
            )

    def list_models(self, timeout_s: int | None = None) -> list[dict[str, Any]]:
        """List all available models from Ollama.

        Args:
            timeout_s: Request timeout in seconds.

        Returns:
            List of model information dictionaries, or empty list on error.
        """
        timeout = timeout_s if timeout_s is not None else self._default_timeout_s

        try:
            response = self._session.get(
                f"{self._base_url}/api/tags",
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("models", [])
        except Exception:
            return []

    def is_model_available(self, model: str, timeout_s: int = 5) -> bool:
        """Check if a specific model is available.

        Args:
            model: The model name to check.
            timeout_s: Request timeout in seconds.

        Returns:
            True if the model is available, False otherwise.
        """
        models = self.list_models(timeout_s=timeout_s)
        for m in models:
            # Handle both "name" and "model" fields
            model_name = m.get("name") or m.get("model", "")
            if model_name == model or model_name.startswith(f"{model}:"):
                return True
        return False

    def is_ollama_available(self, timeout_s: int = 5) -> bool:
        """Check if Ollama is running and accessible.

        Args:
            timeout_s: Request timeout in seconds.

        Returns:
            True if Ollama is accessible, False otherwise.
        """
        try:
            response = self._session.get(
                f"{self._base_url}/api/tags",
                timeout=timeout_s,
            )
            return response.status_code == 200
        except Exception:
            return False

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> "LLMClient":
        """Support context manager usage."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Close session on context exit."""
        self.close()
