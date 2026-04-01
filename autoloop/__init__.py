"""
autoloop — autoresearch for everything.
"""

from autoloop.core import AutoLoop
from autoloop.metrics import CompositeMetric
from autoloop.backends import (
    AnthropicBackend,
    OpenAIBackend,
    OllamaBackend,
    ClaudeBackend,
    CodexBackend,
)

__version__ = "0.1.0"
__all__ = [
    "AutoLoop",
    "CompositeMetric",
    "AnthropicBackend",
    "OpenAIBackend",
    "OllamaBackend",
    "ClaudeBackend",
    "CodexBackend",
]
