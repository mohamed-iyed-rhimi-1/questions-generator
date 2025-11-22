"""
Question generation provider abstraction.

This module provides a provider pattern for question generation services,
allowing seamless switching between local (Ollama) and cloud-based (OpenRouter) providers.
"""

from .base import QuestionGenerationProvider
from .ollama_provider import OllamaProvider
from .openrouter_provider import OpenRouterProvider

__all__ = [
    'QuestionGenerationProvider',
    'OllamaProvider',
    'OpenRouterProvider',
]
