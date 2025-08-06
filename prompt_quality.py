
"""Prompt quality evaluator.

Provides heuristics to detect vague prompts and suggest improvements.
"""

from __future__ import annotations

import re


class PromptQualityError(ValueError):
    """Raised when a prompt is considered too vague or low quality."""

_STOPWORDS = {'ein', 'eine', 'der', 'die', 'das', 'to', 'the', 'a', 'an'}

def _has_examples(text: str) -> bool:
    """Rudimentary check for code fences or numbered examples."""
    return bool(re.search(r"```|\n\d+\. ", text))

def evaluate_prompt(prompt: str) -> str | None:
    """Return feedback message if the prompt is low quality, else None."""
    words = [w for w in re.findall(r"\w+", prompt.lower()) if w not in _STOPWORDS]
    if len(words) < 6:
        return "Dein Prompt war zu kurz – füge bitte mehr Details ein."
    if not _has_examples(prompt) and len(words) < 30:
        return "Dein Prompt war zu vage – füge bitte Beispiele ein."
    return None
