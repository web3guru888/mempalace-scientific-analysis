"""
backends — Pluggable storage abstractions for MemPalace-AGI
============================================================

This package provides abstract backend interfaces for vector search and
knowledge-graph storage, plus concrete implementations for the *current*
stack (ChromaDB + SQLite).

**Why?**
MemPalace upstream is migrating from ChromaDB to LanceDB (PR #574).  Our
integration has ~50 ChromaDB call-sites and ~20 raw sqlite3 KG call-sites.
These abstractions let us swap backends without touching business logic:

    Current:  ChromaDBVectorBackend  +  SQLiteKGBackend
    Future:   LanceDBVectorBackend   +  (whatever replaces raw sqlite3)

**Quick start**::

    from mempalace_agi.backends import create_vector_backend, create_kg_backend

    vec = create_vector_backend("chromadb", path="/tmp/palace", collection_name="discoveries")
    vec.add(ids=["d1"], documents=["hello world"], metadatas=[{"k": "v"}])
    results = vec.query(query_texts=["hello"], n_results=5)

    kg = create_kg_backend("sqlite", db_path="/tmp/kg.db")
    kg.add_triple("A", "causes", "B", confidence=0.9)
    triples = kg.query_triples(subject="A")
"""

from .vector_backend import VectorBackend
from .chromadb_backend import ChromaDBVectorBackend
from .kg_backend import KGBackend
from .sqlite_kg_backend import SQLiteKGBackend


def create_vector_backend(
    backend_type: str = "chromadb",
    *,
    path: str = "",
    collection_name: str = "mempalace_discoveries",
    **kwargs,
) -> VectorBackend:
    """Factory: create a VectorBackend by name.

    Args:
        backend_type: ``"chromadb"`` (default) or ``"lancedb"`` (future).
        path: Filesystem path for persistent storage.
        collection_name: Name of the collection / table.
        **kwargs: Backend-specific options (e.g. ``metadata`` for ChromaDB HNSW config).

    Returns:
        A concrete :class:`VectorBackend` instance.

    Raises:
        ValueError: Unknown ``backend_type``.
    """
    backend_type = backend_type.lower().strip()

    if backend_type == "chromadb":
        return ChromaDBVectorBackend(
            path=path,
            collection_name=collection_name,
            **kwargs,
        )
    # elif backend_type == "lancedb":
    #     from .lancedb_backend import LanceDBVectorBackend
    #     return LanceDBVectorBackend(path=path, collection_name=collection_name, **kwargs)
    else:
        raise ValueError(
            f"Unknown vector backend: {backend_type!r}. "
            f"Supported: 'chromadb'.  (Future: 'lancedb')"
        )


def create_kg_backend(
    backend_type: str = "sqlite",
    *,
    db_path: str = "",
    **kwargs,
) -> KGBackend:
    """Factory: create a KGBackend by name.

    Args:
        backend_type: ``"sqlite"`` (default).
        db_path: Filesystem path for the SQLite database.
        **kwargs: Backend-specific options.

    Returns:
        A concrete :class:`KGBackend` instance.

    Raises:
        ValueError: Unknown ``backend_type``.
    """
    backend_type = backend_type.lower().strip()

    if backend_type == "sqlite":
        return SQLiteKGBackend(db_path=db_path, **kwargs)
    else:
        raise ValueError(
            f"Unknown KG backend: {backend_type!r}. "
            f"Supported: 'sqlite'."
        )


__all__ = [
    "VectorBackend",
    "ChromaDBVectorBackend",
    "KGBackend",
    "SQLiteKGBackend",
    "create_vector_backend",
    "create_kg_backend",
]
