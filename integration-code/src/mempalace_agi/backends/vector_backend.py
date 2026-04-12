"""
vector_backend.py — Abstract vector-search backend for MemPalace-AGI
=====================================================================

Defines the :class:`VectorBackend` ABC whose methods mirror the subset of
the ChromaDB ``Collection`` API that ``palace_discovery_memory.py`` actually
calls.  Concrete implementations (``ChromaDBVectorBackend``,
future ``LanceDBVectorBackend``) translate these calls to their respective
storage engines.

ChromaDB API surface consumed by palace_discovery_memory.py
-----------------------------------------------------------

Method          | Call-sites | Notes
----------------|------------|----------------------------------------------
count()         | 5          | Sync guard, n_results cap, init log, …
add()           | 1          | In _safe_upsert after delete (HNSW workaround)
delete(ids)     | 1          | In _safe_upsert before add (HNSW workaround)
query()         | 4          | semantic_search, record_discovery, diary_read
get()           | 6          | update_discovery_status, consolidation, domain_context, wing_counts, diary_write check
get_or_create…  | 1          | __init__
delete_collect… | 1          | __init__ fallback

Additional ChromaDB patterns we abstract away:
- ``PersistentClient`` instantiation (path-based)
- ``get_or_create_collection`` / ``delete_collection`` (lifecycle)
- ``metadata={"hnsw:space": "cosine"}`` on collection creation

Design decisions
----------------
1. **``query`` returns a dict** matching ChromaDB's return shape
   (``{"ids": [[...]], "documents": [[...]], "metadatas": [[...]], "distances": [[...]]}``).
   Callers already destructure this; keeping the shape avoids rewriting them.

2. **``get`` returns a dict** with the same keys but single-level lists
   (no nested first-element access needed — ``ids``, ``documents``, ``metadatas``).

3. **``upsert``** is provided as a first-class method.  The current code
   uses delete-then-add as a ChromaDB HNSW workaround; a LanceDB backend
   can implement true upsert natively.

4. **No embedding management here** — embeddings are handled by the vector
   engine internally (ChromaDB's default model, LanceDB's pluggable embedders).
   If callers need to pass pre-computed embeddings, they use the ``embeddings``
   param.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence


# ── Type aliases for readability ──────────────────────────────────────

QueryResult = Dict[str, List[List[Any]]]
"""ChromaDB-shaped query result:
``{"ids": [[...]], "documents": [[...]], "metadatas": [[...]], "distances": [[...]]}``
"""

GetResult = Dict[str, List[Any]]
"""ChromaDB-shaped get result:
``{"ids": [...], "documents": [...], "metadatas": [...]}``
"""


class VectorBackend(ABC):
    """Abstract interface for vector-search storage.

    Mirrors the ChromaDB ``Collection`` methods actually used by
    ``palace_discovery_memory.py``.  New backends (LanceDB, etc.) implement
    this interface so the rest of the codebase needs zero changes.

    Lifecycle:
        backend = ChromaDBVectorBackend(path="/data/palace", collection_name="discoveries")
        # ... use ...
        backend.close()   # optional cleanup
    """

    # ── Lifecycle ─────────────────────────────────────────────────────

    @abstractmethod
    def __init__(
        self,
        path: str,
        collection_name: str,
        **kwargs: Any,
    ) -> None:
        """Initialize the backend.

        Args:
            path: Filesystem directory for persistent storage.
            collection_name: Logical name of the collection / table.
            **kwargs: Backend-specific options.
                ChromaDB: ``metadata`` dict (e.g. ``{"hnsw:space": "cosine"}``).
                LanceDB:  ``embedding_fn``, ``mode``, etc.
        """
        ...

    def close(self) -> None:
        """Release any resources held by the backend.

        Default is a no-op; backends with connection pools or file handles
        should override.
        """
        pass

    # ── Write operations ──────────────────────────────────────────────

    @abstractmethod
    def add(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[Dict[str, Any]],
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        """Add documents.  IDs MUST NOT already exist (use ``upsert`` otherwise).

        Args:
            ids: Unique document identifiers.
            documents: Text content to embed and store.
            metadatas: Per-document metadata dicts (values: str|int|float|bool).
            embeddings: Optional pre-computed embeddings (bypasses internal model).

        Raises:
            ValueError (or backend-specific error) if any ID already exists.
        """
        ...

    @abstractmethod
    def upsert(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[Dict[str, Any]],
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        """Insert-or-update documents.

        Semantics: if an ID exists, overwrite its document, metadata, and
        (optionally) embedding.  If it doesn't, insert.

        Note: the current ChromaDB implementation uses delete-then-add as a
        workaround for HNSW bugs (#521, #525).  A LanceDB backend can use
        native upsert.

        Args:
            ids: Unique document identifiers.
            documents: Text content.
            metadatas: Per-document metadata dicts.
            embeddings: Optional pre-computed embeddings.
        """
        ...

    @abstractmethod
    def delete(
        self,
        ids: Optional[Sequence[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Delete documents by IDs and/or metadata filter.

        At least one of ``ids`` or ``where`` must be provided.

        Args:
            ids: Specific document IDs to delete.
            where: Metadata filter (ChromaDB where-clause syntax).
        """
        ...

    # ── Read operations ───────────────────────────────────────────────

    @abstractmethod
    def query(
        self,
        query_texts: Optional[Sequence[str]] = None,
        query_embeddings: Optional[Sequence[Sequence[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> QueryResult:
        """Semantic similarity search.

        At least one of ``query_texts`` or ``query_embeddings`` must be set.

        Args:
            query_texts: Natural-language queries (one search per element).
            query_embeddings: Pre-computed query vectors.
            n_results: Max results per query.
            where: Metadata filter (ChromaDB ``$and``/``$or``/``$ne`` syntax).
            where_document: Document content filter.
            include: What to return — subset of
                ``["documents", "metadatas", "distances", "embeddings"]``.
                Defaults to ``["documents", "metadatas", "distances"]``.

        Returns:
            Dict with keys ``"ids"``, ``"documents"``, ``"metadatas"``,
            ``"distances"`` — each a list-of-lists (one inner list per query).
            Missing include fields are ``None``.
        """
        ...

    @abstractmethod
    def get(
        self,
        ids: Optional[Sequence[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
    ) -> GetResult:
        """Retrieve documents by ID and/or metadata filter (no ranking).

        Args:
            ids: Specific document IDs.
            where: Metadata filter.
            limit: Maximum number of results.
            include: What to return — subset of
                ``["documents", "metadatas", "embeddings"]``.
                Defaults to ``["documents", "metadatas"]``.

        Returns:
            Dict with keys ``"ids"``, ``"documents"``, ``"metadatas"`` —
            each a flat list.
        """
        ...

    @abstractmethod
    def count(self) -> int:
        """Return the total number of documents in the collection."""
        ...

    def peek(self, limit: int = 10) -> GetResult:
        """Return a sample of documents (for debugging).

        Default implementation delegates to ``get(limit=limit)``.
        """
        return self.get(limit=limit)

    # ── Embedding access ─────────────────────────────────────────────

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate embeddings for the given texts using the backend's model.

        Args:
            texts: Strings to embed.

        Returns:
            List of embedding vectors (one per input text).
        """
        ...

    def get_embedding_function(self):
        """Return the backend's embedding callable, or ``None`` if unavailable.

        The callable must accept a list of strings and return a list of
        embedding vectors (list[list[float]]).  This is used by the
        dedup reranker (``llm_rerank_duplicates``) to compute structural
        similarity between candidate texts.

        Backends that don't expose an embedding function should return
        ``None``; callers must gracefully degrade.
        """
        return None

    # ── Utility ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


__all__ = ["VectorBackend", "QueryResult", "GetResult"]
