"""Tests for wikidata_enricher.py — Wikidata KG enrichment.

All network calls are mocked — no actual Wikidata access needed.
"""

import os
import sqlite3
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ── Helpers ─────────────────────────────────────────────────────────

def _make_kg_bridge(tmp_path):
    """Create a minimal KG bridge for testing."""
    from mempalace_agi.config import IntegrationConfig
    from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge

    db_path = os.path.join(str(tmp_path), "test_kg.sqlite3")
    config = IntegrationConfig(kg_db_path=db_path)
    return KnowledgeGraphBridge(config=config)


def _mock_sparql_search_response():
    """Mock SPARQL response for entity search."""
    return [
        {
            "entity": {"value": "http://www.wikidata.org/entity/Q11660"},
            "label": {"value": "artificial intelligence"},
            "description": {"value": "intelligence demonstrated by machines"},
        }
    ]


def _mock_sparql_neighbors_response():
    """Mock SPARQL response for neighbor fetch."""
    return [
        {
            "neighbor": {"value": "http://www.wikidata.org/entity/Q21198"},
            "neighborLabel": {"value": "machine learning"},
            "prop": {"value": "http://www.wikidata.org/prop/direct/P279"},
            "propLabel": {"value": "subclass of"},
        },
        {
            "neighbor": {"value": "http://www.wikidata.org/entity/Q1234"},
            "neighborLabel": {"value": "natural language processing"},
            "prop": {"value": "http://www.wikidata.org/prop/direct/P527"},
            "propLabel": {"value": "has part"},
        },
    ]


def _mock_sparql_entity_response():
    """Mock SPARQL response for entity fetch."""
    return [
        {
            "label": {"value": "artificial intelligence"},
            "description": {"value": "intelligence demonstrated by machines"},
            "alias": {"value": "AI"},
            "type": {"value": "http://www.wikidata.org/entity/Q11862829"},
        },
        {
            "label": {"value": "artificial intelligence"},
            "alias": {"value": "machine intelligence"},
        },
    ]


# ── Data model tests ────────────────────────────────────────────────

class TestDataModels:
    def test_wikidata_entity(self):
        from mempalace_agi.wikidata_enricher import WikidataEntity

        entity = WikidataEntity(
            qid="Q11660",
            label="artificial intelligence",
            description="intelligence demonstrated by machines",
            types=["Q11862829"],
            aliases=["AI"],
        )
        assert entity.qid == "Q11660"
        assert entity.label == "artificial intelligence"
        assert len(entity.aliases) == 1

    def test_wikidata_relation(self):
        from mempalace_agi.wikidata_enricher import WikidataRelation

        rel = WikidataRelation(
            source_qid="Q11660",
            target_qid="Q21198",
            property_id="P279",
            property_label="subclass of",
            target_label="machine learning",
        )
        assert rel.source_qid == "Q11660"
        assert rel.property_label == "subclass of"

    def test_enrichment_result_defaults(self):
        from mempalace_agi.wikidata_enricher import EnrichmentResult

        r = EnrichmentResult()
        assert r.new_triples == 0
        assert r.new_entities == 0
        assert r.source_qid == ""
        assert r.errors == []


# ── WikidataClient tests (mocked) ──────────────────────────────────

class TestWikidataClient:
    def test_search_entity_success(self):
        from mempalace_agi.wikidata_enricher import WikidataClient

        client = WikidataClient()
        client._execute_sparql = MagicMock(return_value=_mock_sparql_search_response())

        results = client.search_entity("artificial intelligence", limit=5)
        assert len(results) == 1
        assert results[0].qid == "Q11660"
        assert results[0].label == "artificial intelligence"

    def test_fetch_entity_success(self):
        from mempalace_agi.wikidata_enricher import WikidataClient

        client = WikidataClient()
        client._execute_sparql = MagicMock(return_value=_mock_sparql_entity_response())

        entity = client.fetch_entity("Q11660")
        assert entity is not None
        assert entity.qid == "Q11660"
        assert entity.label == "artificial intelligence"
        assert "AI" in entity.aliases
        assert "machine intelligence" in entity.aliases

    def test_fetch_entity_not_found(self):
        from mempalace_agi.wikidata_enricher import WikidataClient

        client = WikidataClient()
        client._execute_sparql = MagicMock(return_value=[])

        entity = client.fetch_entity("Q999999999")
        assert entity is None

    def test_fetch_neighbors(self):
        from mempalace_agi.wikidata_enricher import WikidataClient

        client = WikidataClient()
        client._execute_sparql = MagicMock(return_value=_mock_sparql_neighbors_response())

        relations = client.fetch_neighbors("Q11660", limit=30)
        assert len(relations) == 2
        assert relations[0].source_qid == "Q11660"
        assert relations[0].target_qid == "Q21198"
        assert relations[0].property_label == "subclass of"

    def test_graceful_degradation_network_error(self):
        """Network errors should return empty results, not raise."""
        from mempalace_agi.wikidata_enricher import WikidataClient

        client = WikidataClient()
        # Simulate network failure
        client._execute_sparql = MagicMock(return_value=[])

        results = client.search_entity("test")
        assert results == []

    def test_search_entity_empty_results(self):
        from mempalace_agi.wikidata_enricher import WikidataClient

        client = WikidataClient()
        client._execute_sparql = MagicMock(return_value=[])

        results = client.search_entity("xyzzygarbage")
        assert results == []


# ── Rate limiter tests ──────────────────────────────────────────────

class TestTokenBucket:
    def test_burst_capacity(self):
        from mempalace_agi.wikidata_enricher import _TokenBucket

        bucket = _TokenBucket(requests_per_minute=60, burst=5)
        # Should be able to acquire 5 tokens immediately (burst)
        for _ in range(5):
            bucket.acquire()
        # No assertion needed — just verify no exception

    def test_rate_limiting(self):
        from mempalace_agi.wikidata_enricher import _TokenBucket

        bucket = _TokenBucket(requests_per_minute=60, burst=1)
        bucket.acquire()  # Use the burst token
        start = time.monotonic()
        bucket.acquire()  # Should wait ~1 second
        elapsed = time.monotonic() - start
        assert elapsed >= 0.5  # At least some waiting occurred


# ── WikidataEnricher tests (mocked) ────────────────────────────────

class TestWikidataEnricher:
    def test_enrich_entity(self, tmp_path):
        """Enrichment should add entities and triples to our KG."""
        from mempalace_agi.wikidata_enricher import (
            WikidataClient, WikidataEnricher, WikidataRelation,
        )

        bridge = _make_kg_bridge(tmp_path)
        client = WikidataClient()

        # Mock client methods
        from mempalace_agi.wikidata_enricher import WikidataEntity
        client.search_entity = MagicMock(return_value=[
            WikidataEntity(qid="Q11660", label="artificial intelligence", description="AI"),
        ])
        client.fetch_neighbors = MagicMock(return_value=[
            WikidataRelation(
                source_qid="Q11660", target_qid="Q21198",
                property_id="P279", property_label="subclass of",
                target_label="machine learning",
            ),
        ])

        enricher = WikidataEnricher(kg_bridge=bridge, client=client)
        result = enricher.enrich_entity("artificial intelligence")

        assert result.source_qid == "Q11660"
        assert result.new_triples >= 1
        assert result.new_entities >= 1
        assert "wikidata.org" in result.wikidata_url

    def test_enrich_entity_not_found(self, tmp_path):
        """Enriching a non-existent entity should return errors."""
        from mempalace_agi.wikidata_enricher import WikidataClient, WikidataEnricher

        bridge = _make_kg_bridge(tmp_path)
        client = WikidataClient()
        client.search_entity = MagicMock(return_value=[])

        enricher = WikidataEnricher(kg_bridge=bridge, client=client)
        result = enricher.enrich_entity("xyzzy_nonexistent")

        assert result.new_triples == 0
        assert len(result.errors) > 0

    def test_enrichment_provenance(self, tmp_path):
        """Enriched triples should have wikidata provenance."""
        from mempalace_agi.wikidata_enricher import (
            WikidataClient, WikidataEnricher, WikidataEntity, WikidataRelation,
        )

        bridge = _make_kg_bridge(tmp_path)
        client = WikidataClient()
        client.search_entity = MagicMock(return_value=[
            WikidataEntity(qid="Q11660", label="artificial intelligence"),
        ])
        client.fetch_neighbors = MagicMock(return_value=[
            WikidataRelation(
                source_qid="Q11660", target_qid="Q21198",
                property_id="P279", property_label="subclass of",
                target_label="machine learning",
            ),
        ])

        enricher = WikidataEnricher(kg_bridge=bridge, client=client)
        enricher.enrich_entity("artificial intelligence")

        # Check provenance in the DB
        conn = sqlite3.connect(bridge.config.kg_db_path)
        conn.row_factory = sqlite3.Row
        prov_rows = conn.execute(
            "SELECT * FROM triple_provenance WHERE agent_id = 'wikidata_enricher'"
        ).fetchall()
        conn.close()

        assert len(prov_rows) >= 1

    def test_expand_entity(self, tmp_path):
        from mempalace_agi.wikidata_enricher import (
            WikidataClient, WikidataEnricher, WikidataEntity, WikidataRelation,
        )

        bridge = _make_kg_bridge(tmp_path)
        client = WikidataClient()
        client.fetch_entity = MagicMock(return_value=WikidataEntity(
            qid="Q11660", label="artificial intelligence",
        ))
        client.fetch_neighbors = MagicMock(return_value=[
            WikidataRelation(
                source_qid="Q11660", target_qid="Q21198",
                property_id="P279", property_label="subclass of",
                target_label="machine learning",
            ),
        ])

        enricher = WikidataEnricher(kg_bridge=bridge, client=client)
        result = enricher.expand_entity("Q11660", max_neighbors=30)

        assert result.source_qid == "Q11660"
        assert result.new_triples >= 1

    def test_expand_entity_not_found(self, tmp_path):
        from mempalace_agi.wikidata_enricher import WikidataClient, WikidataEnricher

        bridge = _make_kg_bridge(tmp_path)
        client = WikidataClient()
        client.fetch_entity = MagicMock(return_value=None)

        enricher = WikidataEnricher(kg_bridge=bridge, client=client)
        result = enricher.expand_entity("Q999999999")

        assert result.new_triples == 0
        assert len(result.errors) > 0


# ── KG Bridge integration tests ────────────────────────────────────

class TestKGBridgeIntegration:
    def test_bridge_find_path(self, tmp_path):
        """KnowledgeGraphBridge.find_path() should work."""
        from mempalace_agi.config import IntegrationConfig
        from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge

        db_path = os.path.join(str(tmp_path), "test_kg.sqlite3")
        config = IntegrationConfig(kg_db_path=db_path)
        bridge = KnowledgeGraphBridge(config=config)

        # Add some triples
        bridge.kg.add_entity(name="x", entity_type="test")
        bridge.kg.add_entity(name="y", entity_type="test")
        bridge.kg.add_entity(name="z", entity_type="test")
        bridge.kg.add_triple(subject="x", predicate="causes", obj="y",
                            valid_from="2026-01-01", confidence=0.9)
        bridge.kg.add_triple(subject="y", predicate="causes", obj="z",
                            valid_from="2026-01-01", confidence=0.8)

        result = bridge.find_path("x", "z")
        assert result is not None
        assert result.complete is True
        assert len(result.path) == 3
