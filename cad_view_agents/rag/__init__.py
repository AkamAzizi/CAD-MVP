"""
RAG (Retrieval-Augmented Generation) for Assembly Q&A.
Chunking, vector store, embeddings, intent routing, and answer building.
"""
from .chunking import chunk_snapshot
from .vector_store import VectorStore, ChromaVectorStore
from .embeddings import EmbeddingProvider, SentenceTransformerEmbeddings
from .intent_router import Intent, IntentResult, route, is_deterministic_intent
from .answer_builder import build_answer

__all__ = [
    # Chunking
    "chunk_snapshot",
    # Vector store
    "VectorStore",
    "ChromaVectorStore",
    # Embeddings
    "EmbeddingProvider",
    "SentenceTransformerEmbeddings",
    # Intent routing
    "Intent",
    "IntentResult",
    "route",
    "is_deterministic_intent",
    # Answer building
    "build_answer",
]
