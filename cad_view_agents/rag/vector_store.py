"""
Vector store for RAG: add chunks per assembly_id, search by query.
Uses Chroma per assembly_id (one collection per assembly).
"""
from typing import Any, Dict, List, Optional, Protocol

# Optional Chroma import so pipeline can run without RAG deps if needed
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class VectorStore(Protocol):
    """Protocol for vector store: add and search per assembly_id."""

    def add(self, assembly_id: str, chunks: List[Dict[str, Any]], embedding_provider: Any) -> None:
        """Index chunks for this assembly_id. Chunks have 'text' and 'metadata'."""
        ...

    def search(
        self, assembly_id: str, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Return list of {text, metadata, score} for query."""
        ...


def _sanitize_collection_name(aid: str) -> str:
    """Chroma collection names: replace non-alphanumeric with underscore."""
    return "".join(c if c.isalnum() else "_" for c in aid)[:50]


class ChromaVectorStore:
    """Chroma-backed vector store; one collection per assembly_id."""

    def __init__(self, persist_directory: Optional[str] = None):
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb is required. Install with: pip install chromadb")
        self._persist_directory = persist_directory or "./rag_chroma"
        self._client = chromadb.PersistentClient(
            path=self._persist_directory,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def add(
        self,
        assembly_id: str,
        chunks: List[Dict[str, Any]],
        embedding_provider: Any,
    ) -> None:
        texts = [c.get("text", "") for c in chunks]
        if not texts:
            return
        embeddings = embedding_provider.embed(texts)
        coll_name = _sanitize_collection_name(assembly_id)
        collection = self._client.get_or_create_collection(
            name=coll_name,
            metadata={"assembly_id": assembly_id},
        )
        # Chroma expects id, embedding, document, metadatas (no nested dicts; flat only)
        ids = [f"{assembly_id}_{i}" for i in range(len(chunks))]
        metadatas = []
        for c in chunks:
            meta = dict(c.get("metadata", {}))
            # Chroma accepts only str, int, float; flatten or stringify
            for k, v in list(meta.items()):
                if v is not None and not isinstance(v, (str, int, float)):
                    meta[k] = str(v)
            metadatas.append(meta)
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def search(
        self,
        assembly_id: str,
        query: str,
        top_k: int = 5,
        embedding_provider: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        coll_name = _sanitize_collection_name(assembly_id)
        try:
            collection = self._client.get_collection(name=coll_name)
        except Exception:
            return []
        # Use same embedding provider as at index time for correct similarity
        if embedding_provider is not None:
            q_emb = embedding_provider.embed([query])
            res = collection.query(query_embeddings=q_emb, n_results=top_k)
        else:
            res = collection.query(query_texts=[query], n_results=top_k)
        results = []
        if res and res.get("documents") and res["documents"][0]:
            for i, doc in enumerate(res["documents"][0]):
                meta = (res.get("metadatas") or [[]])[0]
                meta = meta[i] if i < len(meta) else {}
                dist = (res.get("distances") or [[]])[0]
                score = 1.0 - (dist[i] if i < len(dist) else 0)  # distance -> similarity
                results.append({"text": doc, "metadata": meta, "score": float(score)})
        return results
