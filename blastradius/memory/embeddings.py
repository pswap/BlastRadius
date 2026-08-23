"""Optional embedding boundary for semantic memory search.

Applications can inject a provider backed by their configured LLM provider.
No external embedding call is made in demo mode.
"""
from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]: ...
