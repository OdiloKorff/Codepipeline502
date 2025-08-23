"""Unified LLM Gateway wrapping *openai-python* with transparent retries.

Other modules should **not** access ``openai.OpenAI`` directly.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from openai import OpenAI

from app_secrets import ensure_env, validate_required_secrets
from logging_config import get_logger

# Optional import für Token Budget Gate
try:
    from token_budget_gate import TokenBudgetGate, TokenUsage
    TOKEN_BUDGET_AVAILABLE = True
except ImportError:
    TOKEN_BUDGET_AVAILABLE = False

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

    def __init__(self, client: OpenAI | None = None, validate_secrets: bool = True, token_budget_gate: 'TokenBudgetGate' = None):
        """
        Initialize LLM Gateway.
        
        Args:
            client: Optional pre-configured OpenAI client
            validate_secrets: If True, validates required secrets on initialization
            token_budget_gate: Optional Token Budget Gate for tracking usage
            
        Raises:
            SecretNotAvailableError: If validate_secrets=True and required secrets 
                                   are not available
        """
        if client is not None:
            self._client = client
        else:
            if validate_secrets:
                # Validate secrets before creating client to fail fast
                validate_required_secrets("OPENAI_API_KEY")
            self._client = _default_client()
        
        self._token_budget_gate = token_budget_gate

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
        
        # Token-Verbrauch erfassen falls Budget Gate verfügbar
        if self._token_budget_gate is not None and TOKEN_BUDGET_AVAILABLE and resp.usage:
            from datetime import datetime
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
                total_tokens=resp.usage.total_tokens,
                model=model,
                timestamp=datetime.now().isoformat()
            )
            self._token_budget_gate.record_usage(usage)
        
        return resp.choices[0].message.content  # type: ignore[attr-defined]
