"""
autoloop — autoresearch for everything.
"""

from autoloop.core import AutoLoop
from autoloop.metrics import CompositeMetric
from autoloop.backends import ClaudeBackend, CodexBackend, OllamaBackend

__version__ = "0.1.0"
__all__ = ["AutoLoop", "CompositeMetric", "ClaudeBackend", "CodexBackend", "OllamaBackend"]
