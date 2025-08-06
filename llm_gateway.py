"""Unified LLM Gateway wrapping *openai-python* with transparent retries.

Other modules should **not** access ``openai.OpenAI`` directly.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from openai import OpenAI

from codepipeline.logging_config import get_logger
from codepipeline.secrets import ensure_env

_T = TypeVar("_T")

def _default_client() -> OpenAI:
    """Initialise the OpenAI client with API‑Key sourced via Vault helper."""
    ensure_env("OPENAI_API_KEY")
    return OpenAI()

def retry(times: int = 3, delay: float = 1.0, backoff: float = 2.0) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """Very small retry decorator with exponential backoff."""
    def _decorator(fn: Callable[..., _T]) -> Callable[..., _T]:
        def _wrapper(*args: Any, **kwargs: Any) -> _T:
            _delay = delay
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:  # pragma: no cover
                    if attempt == times:
                        raise
                    get_logger(__name__).warning("LLM call failed (attempt %s/%s): %s – retrying in %.1fs", attempt, times, exc, _delay)
                    time.sleep(_delay)
                    _delay *= backoff
        return _wrapper
    return _decorator

class LLMGateway:
    """Production‑grade thin wrapper around OpenAI Chat Completions."""

    def __init__(self, client: OpenAI | None = None):
        self._client = client or _default_client()

    @retry()
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "gpt-4o-mini",
        **kwargs: Any,
    ) -> str:
        """Send chat completion request and return raw content."""
        resp = self._client.chat.completions.create(model=model, messages=messages, **kwargs)
        return resp.choices[0].message.content  # type: ignore[attr-defined]
