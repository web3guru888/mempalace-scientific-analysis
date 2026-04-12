"""
chromadb_backend.py — ChromaDB concrete VectorBackend
=====================================================

Wraps ``chromadb.PersistentClient`` and a single ``Collection`` to implement
the :class:`VectorBackend` interface.  This is the *current* production
backend; it will eventually be replaced by a LanceDB backend once MemPalace
upstream completes PR #574.

Implementation notes
--------------------
* **HNSW workaround**: ``upsert()`` uses delete-then-add (not ChromaDB's
  native ``collection.upsert()``) to avoid the segfault/index-corruption
  bugs documented in ChromaDB #521 and #525.  When ChromaDB fixes these
  (or when we move to LanceDB), the workaround can be removed.

* **Collection metadata**: defaults to ``{"hnsw:space": "cosine"}`` for
  cosine-distance scoring (similarity = 1 − distance).

* **Error recovery**: if ``get_or_create_collection`` fails (stale index),
  the collection is deleted and recreated.  This matches the existing
  behaviour in ``palace_discovery_memory.py``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import chromadb

from .vector_backend import GetResult, QueryResult, VectorBackend

logger = logging.getLogger(__name__)

# Default collection config — cosine space for similarity = 1 − distance
_DEFAULT_COLLECTION_METADATA: Dict[str, Any] = {"hnsw:space": "cosine"}


class ChromaDBVectorBackend(VectorBackend):
    """ChromaDB-backed :class:`VectorBackend`.

    Args:
        path: Directory for ChromaDB's persistent storage.
        collection_name: Name of the ChromaDB collection.
        metadata: Collection-level metadata (default: cosine HNSW).
        **kwargs: Passed to ``chromadb.PersistentClient``.
    """

    def __init__(
        self,
        path: str,
        collection_name: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        self._path = path
        self._collection_name = collection_name
        self._metadata = metadata or _DEFAULT_COLLECTION_METADATA

        self._client: chromadb.ClientAPI = chromadb.PersistentClient(
            path=path,
            **kwargs,
        )

        try:
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata=self._metadata,
            )
        except (KeyError, Exception) as exc:
            logger.warning(
                "Stale ChromaDB collection detected (%s), recreating…", exc,
            )
            try:
                self._client.delete_collection(collection_name)
            except Exception:
                pass
            self._collection = self._client.create_collection(
                name=collection_name,
                metadata=self._metadata,
            )

        logger.debug(
            "ChromaDBVectorBackend ready: path=%s collection=%s count=%d",
            path, collection_name, self._collection.count(),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────

    def close(self) -> None:
        """ChromaDB PersistentClient doesn't expose a close method, so no-op."""
        pass

    # ── Write operations ──────────────────────────────────────────────

    def add(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[Dict[str, Any]],
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        kwargs: Dict[str, Any] = {
            "ids": list(ids),
            "documents": list(documents),
            "metadatas": list(metadatas),
        }
        if embeddings is not None:
            kwargs["embeddings"] = list(embeddings)
        self._collection.add(**kwargs)

    def upsert(
        self,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[Dict[str, Any]],
        embeddings: Optional[Sequence[Sequence[float]]] = None,
    ) -> None:
        """Delete-then-add to avoid HNSW corruption (ChromaDB #521, #525).

        When MemPalace migrates to LanceDB (PR #574) or ChromaDB fixes
        the ``repairConnectionsForUpdate`` bug, this can become a true
        upsert.
        """
        # 1. Pre-delete — only delete IDs that actually exist to avoid
        #    ChromaDB's "Delete of nonexisting embedding ID" warnings
        #    (17,354 warnings observed in 574-cycle continuous run).
        try:
            existing = self._collection.get(ids=list(ids), include=[])
            existing_ids = existing.get("ids", []) if existing else []
            if existing_ids:
                self._collection.delete(ids=existing_ids)
        except Exception:
            pass  # Collection empty or IDs didn't exist — fine

        # 2. Pure insert — always takes the safe HNSW code path.
        kwargs: Dict[str, Any] = {
            "ids": list(ids),
            "documents": list(documents),
            "metadatas": list(metadatas),
        }
        if embeddings is not None:
            kwargs["embeddings"] = list(embeddings)
        self._collection.add(**kwargs)

    def delete(
        self,
        ids: Optional[Sequence[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        kwargs: Dict[str, Any] = {}
        if ids is not None:
            kwargs["ids"] = list(ids)
        if where is not None:
            kwargs["where"] = where
        if not kwargs:
            raise ValueError("delete() requires at least one of ids or where")
        self._collection.delete(**kwargs)

    # ── Read operations ───────────────────────────────────────────────

    def query(
        self,
        query_texts: Optional[Sequence[str]] = None,
        query_embeddings: Optional[Sequence[Sequence[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> QueryResult:
        kwargs: Dict[str, Any] = {"n_results": n_results}

        if query_texts is not None:
            kwargs["query_texts"] = list(query_texts)
        if query_embeddings is not None:
            kwargs["query_embeddings"] = list(query_embeddings)
        if where is not None:
            kwargs["where"] = where
        if where_document is not None:
            kwargs["where_document"] = where_document
        if include is not None:
            kwargs["include"] = include

        return self._collection.query(**kwargs)

    def get(
        self,
        ids: Optional[Sequence[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
    ) -> GetResult:
        kwargs: Dict[str, Any] = {}
        if ids is not None:
            kwargs["ids"] = list(ids)
        if where is not None:
            kwargs["where"] = where
        if limit is not None:
            kwargs["limit"] = limit
        if include is not None:
            kwargs["include"] = include
        return self._collection.get(**kwargs)

    def count(self) -> int:
        return self._collection.count()

    def peek(self, limit: int = 10) -> GetResult:
        return self._collection.peek(limit=limit)

    # ── Embedding access ─────────────────────────────────────────────

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        """Generate embeddings using ChromaDB's embedding function.

        Returns plain Python lists regardless of what the underlying
        embedding function produces (numpy arrays, etc.).
        """
        ef = self._collection._embedding_function
        raw = ef(list(texts))
        # Normalize to List[List[float]] — ChromaDB's default model returns
        # numpy arrays; other embedding functions may return plain lists.
        return [
            v.tolist() if hasattr(v, "tolist") else list(v)
            for v in raw
        ]

    def get_embedding_function(self):
        """Return the ChromaDB collection's internal embedding function.

        ChromaDB stores the embedding function on the collection as
        ``_embedding_function``.  Callers use this for structural comparison
        in the dedup reranker.  Returns ``None`` if unavailable.
        """
        try:
            return self._collection._embedding_function
        except AttributeError:
            return None

    # ── Utility ───────────────────────────────────────────────────────

    @property
    def collection(self) -> chromadb.Collection:
        """Direct access to the underlying ChromaDB collection.

        Escape hatch for callers that need ChromaDB-specific features
        not exposed by the abstract interface.  **Avoid in new code.**
        """
        return self._collection

    @property
    def client(self) -> chromadb.ClientAPI:
        """Direct access to the underlying ChromaDB client.

        Escape hatch.  **Avoid in new code.**
        """
        return self._client

    def __repr__(self) -> str:
        return (
            f"<ChromaDBVectorBackend path={self._path!r} "
            f"collection={self._collection_name!r} "
            f"count={self._collection.count()}>"
        )


__all__ = ["ChromaDBVectorBackend"]
