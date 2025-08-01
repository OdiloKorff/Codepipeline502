"""
Provider broker for CodePipeline.
"""

import os
from typing import Dict, Any, Optional
from codepipeline.logging_config import get_logger
from abc import ABC, abstractmethod

logger = get_logger(__name__)

class Provider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

class OpenAIProvider(Provider):
    def generate(self, prompt: str) -> str:
        # Placeholder for OpenAI API call
        from openai import Completion
        # Simulate API call; in real use replace with actual logic
        return f"OpenAI response for: {prompt}"

class AnthropicProvider(Provider):
    def generate(self, prompt: str) -> str:
        # Placeholder for Anthropic API call
        from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
        return f"Anthropic response for: {prompt}"

class Broker:
    def __init__(self, providers: list[Provider]):
        self.providers = providers

    def generate(self, prompt: str) -> str:
        last_error = None
        for provider in self.providers:
            try:
                return provider.generate(prompt)
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed: {e}")
                last_error = e
        raise RuntimeError(f"All providers failed: {last_error}")