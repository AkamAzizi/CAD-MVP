"""
LLM provider interface for RAG. NoOpLLM for retrieval-only MVP; OpenAI etc. can be plugged in later.
"""
from typing import Optional, Protocol


class LLMProvider(Protocol):
    """Protocol for generating answer from prompt + context."""

    def generate(self, prompt: str, context: str) -> str:
        """Generate answer given system/user prompt and retrieved context."""
        ...


class NoOpLLM:
    """Retrieval-only: no LLM call. Returns empty string; answer_builder uses rule-based reply."""

    def generate(self, prompt: str, context: str) -> str:
        return ""
