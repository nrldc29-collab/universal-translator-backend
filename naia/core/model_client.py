"""Local model client using llama.cpp for NAIA pipeline stages.

The optional ``llama_cpp`` dependency is imported lazily so that NAIA's
runtime, tests, and pipeline stages can run without it. Stages that
need the model call ``get_global_client()``; if the runtime is missing
or the model file is not on disk, they receive ``ModelUnavailable`` and
fall back to deterministic behavior (constitutional invariant 9).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModelUnavailable(RuntimeError):
    """Raised when the local model cannot be loaded or invoked.

    Inherits from ``RuntimeError`` so existing ``except RuntimeError``
    paths continue to catch it. Callers should treat this as a signal
    to fall back to deterministic behavior.
    """


class LocalModelClient:
    """Local model client that loads a quantized GGUF model and serves all NAIA pipeline stages."""

    def __init__(
        self,
        model_path: str | Path,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        verbose: bool = False,
    ) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise ModelUnavailable(f"Model file not found: {model_path}")

        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise ModelUnavailable(
                "llama-cpp-python is not installed. Install it with: "
                "pip install -r requirements-local.txt"
            ) from exc

        try:
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=verbose,
            )
        except Exception as exc:  # noqa: BLE001
            raise ModelUnavailable(f"Failed to load GGUF: {exc}") from exc
        self.n_ctx = n_ctx

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: list[str] | None = None,
        json_mode: bool = False,
    ) -> str:
        try:
            response = self.model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=stop,
            )
            return response["choices"][0]["text"]
        except (KeyError, IndexError) as exc:
            logger.error("model_generate_response_malformed: %s", exc)
            raise ModelUnavailable(f"Model returned malformed response: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        schema_instruction = f"\n\nOutput must be valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        full_prompt = prompt + schema_instruction

        response = self.generate(
            full_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["```"],
        )

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            return json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse model output as JSON: {exc}\nOutput: {response}")

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        try:
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            logger.error("model_chat_response_malformed: %s", exc)
            raise ModelUnavailable(f"Model chat returned malformed response: {exc}") from exc

    def get_model_info(self) -> dict[str, Any]:
        return {
            "model_path": str(self.model_path),
            "n_ctx": self.n_ctx,
            "n_vocab": self.model.n_vocab(),
            "n_embd": self.model.n_embd(),
            "n_layer": self.model.n_layer(),
        }

    def __repr__(self) -> str:
        return f"LocalModelClient(model_path={self.model_path}, n_ctx={self.n_ctx})"


# Singleton instance for use across NAIA pipeline
_global_client: LocalModelClient | None = None
_global_client_lock = threading.Lock()


def get_global_client() -> LocalModelClient:
    """Return the process-wide ``LocalModelClient`` instance.

    Raises ``ModelUnavailable`` if it has not been initialized. Callers
    that want to use the model when available and fall back otherwise
    should catch ``ModelUnavailable``.
    """
    with _global_client_lock:
        if _global_client is None:
            raise ModelUnavailable(
                "Global model client not initialized. "
                "Call initialize_global_client(model_path) first."
            )
        return _global_client


def initialize_global_client(model_path: str | Path, **kwargs: Any) -> LocalModelClient:
    """Initialize the global model client instance."""
    global _global_client
    with _global_client_lock:
        _global_client = LocalModelClient(model_path, **kwargs)
        return _global_client
