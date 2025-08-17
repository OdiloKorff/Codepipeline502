
"""RAG Core module – **work in progress**.

Temporarily disabled detailed implementation until integration stabilises.
"""

from __future__ import annotations


class RAGCore:  # pragma: no cover
    """Placeholder stub to satisfy static tooling until full implementation."""

    def __init__(self, collection_name: str = "code_chunks") -> None:
        self._collection_name = collection_name

    def chunk_and_store(self, source: str) -> None:
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError
