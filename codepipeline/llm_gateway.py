"""
LLM Gateway (MVP) mit deterministischen Parametern und Token-Accounting.

- Temperatur = 0.0, fester Seed
- Token-Verbrauch (prompt_tokens, completion_tokens, total_tokens) wird zurückgegeben
- Secrets ausschließlich über den zentralen Resolver bezogen
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Any

from .secret_resolver import get_secret, SecretError


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResult:
    content: str
    usage: TokenUsage
    model: str
    temperature: float
    seed: int


DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMP = 0.0
DEFAULT_SEED = 7


def generate_unified_diff(prompt: str, model: str | None = None, seed: int | None = None, require_secret: bool = True) -> LLMResult:
    """
    MVP-Generator für Unified Diffs – simuliert Ausgabe deterministisch.
    """
    # Geheimnisse früh prüfen (z. B. API-Key) – nur wenn erforderlich
    if require_secret:
        try:
            get_secret("LLM_API_KEY")
        except SecretError:
            # Früher Fail bei fehlendem Secret
            raise

    model_used = model or DEFAULT_MODEL
    temp = DEFAULT_TEMP
    rng_seed = DEFAULT_SEED if seed is None else seed
    random.seed(rng_seed)

    # Simuliere deterministische Token-Kosten basierend auf Prompt-Länge
    prompt_tokens = max(1, len(prompt) // 12)
    completion_tokens = 15  # MVP: fixer, deterministischer Wert

    # Simulierter Diff-Inhalt
    changed_lines = 15
    content = f"--- a/file.txt\n+++ b/file.txt\n@@ -1,1 +1,{changed_lines} @@\n+// simulated diff lines\n"

    return LLMResult(
        content=content,
        usage=TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        model=model_used,
        temperature=temp,
        seed=rng_seed,
    )


