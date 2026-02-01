"""
Embedding provider interface and implementations.
Local sentence-transformers by default; OpenAI etc. can be added later.
"""
from typing import List, Protocol

# Re-export from top-level rag.embeddings for single place of implementation
from rag.embeddings import EmbeddingProvider  # noqa: F401
from rag.embeddings import SentenceTransformerEmbeddings  # noqa: F401

__all__ = ["EmbeddingProvider", "SentenceTransformerEmbeddings"]
