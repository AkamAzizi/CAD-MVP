"""
RAG Agent: answers questions about an assembly using snapshot + vector retrieval.
Can be called by Head Agent as a tool: ask(assembly_id, question) -> {answer, facts, sources}.
"""
import json
import os
from typing import Any, Callable, Dict, Optional


def load_snapshot(assembly_id: str, snapshots_dir: str = "output") -> Optional[Dict[str, Any]]:
    """
    Load snapshot JSON by assembly_id. Looks for {assembly_id}_snapshot.json in snapshots_dir.
    assembly_id can be full (e.g. asm_pump_abc12345) or short alias (e.g. pump) matching filename stem.
    """
    if not os.path.isdir(snapshots_dir):
        return None
    target = f"{assembly_id}_snapshot.json"
    path = os.path.join(snapshots_dir, target)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    # Try alias: find any snapshot whose assembly_id contains the alias or filename matches
    for name in os.listdir(snapshots_dir):
        if name.endswith("_snapshot.json"):
            p = os.path.join(snapshots_dir, name)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    snap = json.load(f)
                aid = snap.get("assembly_id", "")
                stem = name.replace("_snapshot.json", "")
                if assembly_id in aid or assembly_id in stem or stem.startswith(f"asm_{assembly_id}"):
                    return snap
            except Exception:
                continue
    return None


def ask(
    assembly_id: str,
    question: str,
    vector_store: Optional[Any] = None,
    snapshot_loader: Optional[Callable[[str], Optional[Dict]]] = None,
    snapshots_dir: str = "output",
    rag_dir: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Answer a question about an assembly using snapshot + retrieval.

    Args:
        assembly_id: Assembly ID or short alias (e.g. pump)
        question: Natural language question
        vector_store: Optional VectorStore; if None, created from rag_dir when possible
        snapshot_loader: Optional (assembly_id) -> snapshot dict; if None, load from snapshots_dir
        snapshots_dir: Directory containing *_snapshot.json files
        rag_dir: Directory for Chroma DB (default: snapshots_dir/rag_chroma)
        top_k: Number of chunks to retrieve

    Returns:
        {"assembly_id", "question", "answer", "facts", "sources"}
    """
    from rag.answer_builder import build_answer

    loader = snapshot_loader or (lambda aid: load_snapshot(aid, snapshots_dir))
    snapshot = loader(assembly_id)
    if not snapshot:
        return {
            "assembly_id": assembly_id,
            "question": question,
            "answer": f"Kunde inte hitta snapshot för assembly '{assembly_id}'.",
            "facts": [],
            "sources": [],
        }
    resolved_id = snapshot.get("assembly_id", assembly_id)
    retrieved = []

    if vector_store is not None:
        try:
            from rag.embeddings import SentenceTransformerEmbeddings
            emb = SentenceTransformerEmbeddings()
            retrieved = vector_store.search(resolved_id, question, top_k=top_k, embedding_provider=emb)
        except Exception:
            pass
    else:
        try:
            from rag.vector_store import ChromaVectorStore
            from rag.embeddings import SentenceTransformerEmbeddings
            store = ChromaVectorStore(persist_directory=rag_dir or os.path.join(snapshots_dir, "rag_chroma"))
            emb = SentenceTransformerEmbeddings()
            retrieved = store.search(resolved_id, question, top_k=top_k, embedding_provider=emb)
        except Exception:
            pass

    result = build_answer(question, retrieved, snapshot)
    result["assembly_id"] = resolved_id
    result["question"] = question
    return result
