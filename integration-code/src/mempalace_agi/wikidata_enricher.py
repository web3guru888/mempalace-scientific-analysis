"""
Wikidata Enricher — Optional KG enrichment via Wikidata SPARQL.

Ported from STAN_X v8's expansion module.  Adapted for our SQLite-based
KG (not Memgraph).  Entirely optional — degrades gracefully when the
``requests`` library is unavailable or Wikidata is unreachable.

Usage:
    from mempalace_agi.wikidata_enricher import WikidataEnricher, WikidataClient

    client = WikidataClient()
    enricher = WikidataEnricher(kg_bridge=bridge, client=client)
    result = enricher.enrich_entity("artificial intelligence")
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("mempalace_agi")

# Graceful degradation
try:
    import requests as _requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    _requests = None  # type: ignore[assignment]


__all__ = [
    "WikidataEntity",
    "WikidataRelation",
    "WikidataClient",
    "WikidataEnricher",
    "EnrichmentResult",
]


# ── Data models ─────────────────────────────────────────────────────

@dataclass
class WikidataEntity:
    """A Wikidata entity."""
    qid: str
    label: str = ""
    description: str = ""
    types: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)


@dataclass
class WikidataRelation:
    """A Wikidata relationship (edge)."""
    source_qid: str
    target_qid: str
    property_id: str
    property_label: str
    target_label: str = ""


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation."""
    new_triples: int = 0
    new_entities: int = 0
    source_qid: str = ""
    wikidata_url: str = ""
    errors: List[str] = field(default_factory=list)


# ── Token bucket rate limiter (synchronous) ─────────────────────────

class _TokenBucket:
    """Synchronous token-bucket rate limiter.

    STAN_X uses an async version; we adapt for sync ``requests``.
    """

    def __init__(self, requests_per_minute: int = 60, burst: int = 10):
        self.rate = requests_per_minute / 60.0  # tokens/sec
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a token is available."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens < 1.0:
                wait = (1.0 - self.tokens) / self.rate
                time.sleep(wait)
                self.tokens = 1.0
                self.last_update = time.monotonic()

            self.tokens -= 1.0


# ── SPARQL client ───────────────────────────────────────────────────

class WikidataClient:
    """Synchronous Wikidata SPARQL client with rate limiting.

    Adapted from STAN_X v8's async WikidataClient for our sync codebase.

    Args:
        endpoint: SPARQL endpoint URL.
        requests_per_minute: Rate limit (default 60).
        max_retries: Max retry attempts (default 3).
        timeout: Request timeout in seconds (default 30).
    """

    SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
    USER_AGENT = "MemPalace-AGI/0.1.0 (Research Project; https://github.com/milla-jovovich/mempalace)"

    def __init__(
        self,
        endpoint: Optional[str] = None,
        requests_per_minute: int = 60,
        max_retries: int = 3,
        timeout: float = 30.0,
    ):
        if not HAS_REQUESTS:
            logger.warning(
                "WikidataClient: 'requests' library not available. "
                "Install with: pip install requests"
            )
        self.endpoint = endpoint or self.SPARQL_ENDPOINT
        self.max_retries = max_retries
        self.timeout = timeout
        self._limiter = _TokenBucket(requests_per_minute=requests_per_minute)
        self._session: Optional[Any] = None

    def _get_session(self) -> Any:
        """Lazy-create a requests.Session."""
        if not HAS_REQUESTS:
            raise RuntimeError("requests library is not installed")
        if self._session is None:
            self._session = _requests.Session()
            self._session.headers.update({"User-Agent": self.USER_AGENT})
        return self._session

    def _execute_sparql(self, query: str) -> List[Dict[str, Any]]:
        """Execute a SPARQL query with rate limiting and retry logic."""
        if not HAS_REQUESTS:
            logger.warning("Cannot execute SPARQL: requests not available")
            return []

        session = self._get_session()

        for attempt in range(self.max_retries):
            try:
                self._limiter.acquire()
                resp = session.get(
                    self.endpoint,
                    params={"query": query, "format": "json"},
                    timeout=self.timeout,
                )

                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning("Rate limited (429), waiting %ds", wait)
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data.get("results", {}).get("bindings", [])

            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(
                        "SPARQL attempt %d failed: %s — retrying in %ds",
                        attempt + 1, e, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.warning("SPARQL query failed after %d retries: %s", self.max_retries, e)
                    return []

        return []

    # ── Public methods ──────────────────────────────────────────────

    def search_entity(self, label: str, limit: int = 5) -> List[WikidataEntity]:
        """Search Wikidata for entities matching a label.

        Args:
            label: Entity label to search for.
            limit: Max results (default 5).

        Returns:
            List of WikidataEntity objects (may be empty on error).
        """
        escaped = label.replace('"', '\\"')
        query = f'''
        SELECT DISTINCT ?entity ?label ?description
        WHERE {{
          ?entity rdfs:label ?label .
          FILTER(LANG(?label) = "en")
          FILTER(CONTAINS(LCASE(?label), LCASE("{escaped}")))
          OPTIONAL {{ ?entity schema:description ?description . FILTER(LANG(?description) = "en") }}
          FILTER(STRSTARTS(STR(?entity), "http://www.wikidata.org/entity/Q"))
        }}
        LIMIT {limit}
        '''

        results = self._execute_sparql(query)
        entities = []
        for row in results:
            uri = row.get("entity", {}).get("value", "")
            qid = uri.split("/")[-1] if uri else ""
            entities.append(WikidataEntity(
                qid=qid,
                label=row.get("label", {}).get("value", ""),
                description=row.get("description", {}).get("value", ""),
            ))
        return entities

    def fetch_entity(self, qid: str) -> Optional[WikidataEntity]:
        """Fetch entity details by QID.

        Args:
            qid: Wikidata QID (e.g. "Q11660").

        Returns:
            WikidataEntity or None if not found.
        """
        query = f'''
        SELECT ?label ?description ?alias ?type
        WHERE {{
          OPTIONAL {{ wd:{qid} rdfs:label ?label . FILTER(LANG(?label) = "en") }}
          OPTIONAL {{ wd:{qid} schema:description ?description . FILTER(LANG(?description) = "en") }}
          OPTIONAL {{ wd:{qid} skos:altLabel ?alias . FILTER(LANG(?alias) = "en") }}
          OPTIONAL {{ wd:{qid} wdt:P31 ?type }}
        }}
        '''

        results = self._execute_sparql(query)
        if not results:
            return None

        entity = WikidataEntity(qid=qid)
        aliases_set: set = set()
        types_set: set = set()

        for row in results:
            if not entity.label and "label" in row:
                entity.label = row["label"]["value"]
            if not entity.description and "description" in row:
                entity.description = row["description"]["value"]
            if "alias" in row:
                aliases_set.add(row["alias"]["value"])
            if "type" in row:
                types_set.add(row["type"]["value"].split("/")[-1])

        entity.aliases = sorted(aliases_set)
        entity.types = sorted(types_set)
        return entity

    def fetch_neighbors(self, qid: str, limit: int = 30) -> List[WikidataRelation]:
        """Fetch relationships from a Wikidata entity.

        Args:
            qid: Source entity QID.
            limit: Max neighbors (default 30).

        Returns:
            List of WikidataRelation objects.
        """
        limit = min(limit, 100)
        query = f'''
        SELECT DISTINCT ?neighbor ?neighborLabel ?prop ?propLabel
        WHERE {{
          wd:{qid} ?prop ?neighbor .
          FILTER(STRSTARTS(STR(?neighbor), "http://www.wikidata.org/entity/Q"))
          FILTER(STRSTARTS(STR(?prop), "http://www.wikidata.org/prop/direct/P"))
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        '''

        results = self._execute_sparql(query)
        relations = []
        for row in results:
            neighbor_uri = row.get("neighbor", {}).get("value", "")
            target_qid = neighbor_uri.split("/")[-1] if neighbor_uri else ""
            prop_uri = row.get("prop", {}).get("value", "")
            prop_id = prop_uri.split("/")[-1] if prop_uri else ""
            relations.append(WikidataRelation(
                source_qid=qid,
                target_qid=target_qid,
                property_id=prop_id,
                property_label=row.get("propLabel", {}).get("value", prop_id),
                target_label=row.get("neighborLabel", {}).get("value", target_qid),
            ))
        return relations

    def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


# ── Enricher (bridge between Wikidata and our KG) ──────────────────

class WikidataEnricher:
    """Bridge between WikidataClient and our KnowledgeGraphBridge.

    Searches Wikidata for entities, fetches their relationships, and
    inserts them as triples in our KG with ``source="wikidata"`` provenance.

    Args:
        kg_bridge: Our KnowledgeGraphBridge instance.
        client: Optional WikidataClient (creates a default if None).
    """

    def __init__(self, kg_bridge: Any, client: Optional[WikidataClient] = None):
        self.kg = kg_bridge
        self.client = client or WikidataClient()

    def enrich_entity(self, entity_name: str) -> EnrichmentResult:
        """Search Wikidata for *entity_name* and add relationships to our KG.

        Workflow:
        1. Search Wikidata for the entity label.
        2. Take the top match.
        3. Fetch its neighbors (relationships).
        4. Convert each Wikidata relation → KG triple.

        Args:
            entity_name: Entity name or label to search for.

        Returns:
            EnrichmentResult with counts and any errors.
        """
        result = EnrichmentResult()

        try:
            # 1. Search
            candidates = self.client.search_entity(entity_name, limit=1)
            if not candidates:
                result.errors.append(f"No Wikidata entity found for '{entity_name}'")
                return result

            top = candidates[0]
            result.source_qid = top.qid
            result.wikidata_url = f"https://www.wikidata.org/wiki/{top.qid}"

            # 2. Fetch neighbors
            relations = self.client.fetch_neighbors(top.qid, limit=30)

            # 3. Convert to KG triples
            seen_entities: set = set()
            timestamp = datetime.now().isoformat()

            for rel in relations:
                try:
                    # Ensure entities exist
                    if top.qid not in seen_entities:
                        self.kg.kg.add_entity(
                            name=top.label or entity_name,
                            entity_type="wikidata_entity",
                            properties={
                                "qid": top.qid,
                                "description": top.description,
                                "source": "wikidata",
                            },
                        )
                        seen_entities.add(top.qid)
                        result.new_entities += 1

                    target_label = rel.target_label or rel.target_qid
                    if rel.target_qid not in seen_entities:
                        self.kg.kg.add_entity(
                            name=target_label,
                            entity_type="wikidata_entity",
                            properties={
                                "qid": rel.target_qid,
                                "source": "wikidata",
                            },
                        )
                        seen_entities.add(rel.target_qid)
                        result.new_entities += 1

                    # Add triple
                    source_label = top.label or entity_name
                    predicate = rel.property_label.replace(" ", "_").lower()
                    triple_id = self.kg.kg.add_triple(
                        subject=source_label,
                        predicate=predicate,
                        obj=target_label,
                        valid_from=timestamp,
                        confidence=0.8,  # Wikidata relations are generally reliable
                        source_closet="wikidata",
                        source_file=f"wikidata:{rel.source_qid}:{rel.property_id}",
                    )

                    # Store provenance
                    self.kg._store_provenance(
                        triple_id=triple_id,
                        agent_id="wikidata_enricher",
                        cycle_id="enrichment",
                        evidence_chain=[
                            f"wikidata:{rel.source_qid}",
                            f"property:{rel.property_id}",
                        ],
                        confidence=0.8,
                        reason=f"Wikidata enrichment: {source_label} {predicate} {target_label}",
                    )
                    result.new_triples += 1

                except Exception as e:
                    result.errors.append(f"Failed to add relation {rel.property_id}: {e}")

        except Exception as e:
            result.errors.append(f"Enrichment failed: {e}")
            logger.warning("enrich_entity failed for '%s': %s", entity_name, e)

        logger.info(
            "Enriched '%s': %d triples, %d entities (qid=%s)",
            entity_name, result.new_triples, result.new_entities, result.source_qid,
        )
        return result

    def expand_entity(self, qid: str, max_neighbors: int = 30) -> EnrichmentResult:
        """Fetch neighbors for a known QID and add as KG triples.

        Args:
            qid: Wikidata QID (e.g. "Q11660").
            max_neighbors: Maximum neighbors to fetch.

        Returns:
            EnrichmentResult.
        """
        result = EnrichmentResult(source_qid=qid)
        result.wikidata_url = f"https://www.wikidata.org/wiki/{qid}"

        try:
            # Fetch entity details
            entity = self.client.fetch_entity(qid)
            if entity is None:
                result.errors.append(f"Entity {qid} not found on Wikidata")
                return result

            # Fetch neighbors
            relations = self.client.fetch_neighbors(qid, limit=max_neighbors)

            timestamp = datetime.now().isoformat()
            seen: set = set()

            for rel in relations:
                try:
                    target_label = rel.target_label or rel.target_qid

                    if rel.target_qid not in seen:
                        self.kg.kg.add_entity(
                            name=target_label,
                            entity_type="wikidata_entity",
                            properties={"qid": rel.target_qid, "source": "wikidata"},
                        )
                        seen.add(rel.target_qid)
                        result.new_entities += 1

                    predicate = rel.property_label.replace(" ", "_").lower()
                    triple_id = self.kg.kg.add_triple(
                        subject=entity.label or qid,
                        predicate=predicate,
                        obj=target_label,
                        valid_from=timestamp,
                        confidence=0.8,
                        source_closet="wikidata",
                        source_file=f"wikidata:{qid}:{rel.property_id}",
                    )

                    self.kg._store_provenance(
                        triple_id=triple_id,
                        agent_id="wikidata_enricher",
                        cycle_id="expansion",
                        evidence_chain=[f"wikidata:{qid}", f"property:{rel.property_id}"],
                        confidence=0.8,
                        reason=f"Wikidata expansion from {qid}",
                    )
                    result.new_triples += 1

                except Exception as e:
                    result.errors.append(f"Failed to add relation: {e}")

        except Exception as e:
            result.errors.append(f"Expansion failed: {e}")
            logger.warning("expand_entity failed for %s: %s", qid, e)

        return result

    def fill_knowledge_gap(
        self,
        entity_a: str,
        entity_b: str,
        max_expansions: int = 3,
    ) -> Optional[Any]:
        """Try to connect two entities by expanding from both sides.

        Expands entity_a, then entity_b, then checks if a path exists.
        Repeats up to *max_expansions* rounds.

        Args:
            entity_a: First entity name.
            entity_b: Second entity name.
            max_expansions: Max rounds of expansion (default 3).

        Returns:
            PathResult if a path was found after expansion, else None.
        """
        # Import here to avoid circular dependency
        from .kg_pathfinder import find_knowledge_path

        for round_num in range(max_expansions):
            # Try to find path first
            path_result = find_knowledge_path(
                db_path=self.kg.config.kg_db_path,
                start_entity=entity_a,
                goal_entity=entity_b,
                max_iterations=5000,
            )
            if path_result is not None and path_result.complete:
                logger.info(
                    "fill_knowledge_gap: path found after %d rounds", round_num
                )
                return path_result

            # Expand both sides from Wikidata
            logger.info(
                "fill_knowledge_gap round %d: expanding '%s' and '%s'",
                round_num + 1, entity_a, entity_b,
            )
            self.enrich_entity(entity_a)
            self.enrich_entity(entity_b)

        # Final attempt after all expansions
        path_result = find_knowledge_path(
            db_path=self.kg.config.kg_db_path,
            start_entity=entity_a,
            goal_entity=entity_b,
            max_iterations=5000,
        )
        if path_result is not None and path_result.complete:
            return path_result

        logger.info(
            "fill_knowledge_gap: no path found between '%s' and '%s' after %d rounds",
            entity_a, entity_b, max_expansions,
        )
        return None
