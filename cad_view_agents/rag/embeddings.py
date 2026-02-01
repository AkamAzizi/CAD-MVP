"""
Embedding providers for RAG. Local sentence-transformers by default; pluggable for OpenAI etc.
"""
from typing import List, Protocol


class EmbeddingProvider(Protocol):
    """Protocol for embedding text(s)."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return list of embedding vectors (one per text)."""
        ...


class SentenceTransformerEmbeddings:
    """Local embeddings using sentence-transformers (e.g. all-MiniLM-L6-v2)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required for local embeddings. "
                    "Install with: pip install sentence-transformers"
                ) from e
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._get_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
