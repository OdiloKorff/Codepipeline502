"""Prompt templating, quality scoring and sanitizing utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "PromptTemplate",
    "evaluate_prompt_quality",
    "sanitize_input",
    "apply_fewshot_template",
    "SoftAbort",
]

_BAD_PATTERNS = [
    re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL),
    re.compile(r"(?:DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO)", re.IGNORECASE),
]

class SoftAbort(Exception):
    """Raised when prompt quality is below acceptable threshold."""

@dataclass(slots=True)
class PromptTemplate:
    name: str
    system: str
    examples: list[dict[str, str]] = field(default_factory=list)
    min_score: float = 0.4  # thresholds 0..1

# ------------------------------------------------------------------
# Heuristic quality evaluation (very lightweight, no ML)
# ------------------------------------------------------------------
_KEY_SIGNALS = [
    "example",
    "expected output",
    "step",
    "please",
    "given",
    "return",
    "input",
]

def evaluate_prompt_quality(prompt: str) -> float:
    """Return float 0..1 – higher is better."""
    if not prompt:
        return 0.0
    length_score = min(len(prompt) / 200.0, 1.0)  # encourage >=200 chars
    structure_score = sum(1 for k in _KEY_SIGNALS if k in prompt.lower()) / len(_KEY_SIGNALS)
    return (length_score * 0.6) + (structure_score * 0.4)

# ------------------------------------------------------------------
# Sanitizing helpers
# ------------------------------------------------------------------
def sanitize_input(prompt: str) -> str:
    cleaned = prompt
    for pat in _BAD_PATTERNS:
        cleaned = pat.sub("", cleaned)
    return cleaned.strip()

# ------------------------------------------------------------------
# Template application
# ------------------------------------------------------------------
def apply_fewshot_template(prompt: str, tpl: PromptTemplate) -> list[dict[str, str]]:
    """Return message list ready for Chat API."""
    score = evaluate_prompt_quality(prompt)
    if score < tpl.min_score:
        raise SoftAbort(f"Prompt score {score:.2f} below threshold {tpl.min_score}")
    sanitized = sanitize_input(prompt)
    msgs: list[dict[str, str]] = []
    msgs.append({ "role": "system", "content": tpl.system })
    msgs.extend(tpl.examples)
    msgs.append({ "role": "user", "content": sanitized })
    return msgs
