#!/usr/bin/env python3
"""
Phase 20 Validation Experiment — Causal Chain Orient Integration
================================================================

Tests that the KG pathfinder → orient pipeline works end-to-end:
  1. Chain Discovery: orient finds A* paths linking cross-domain discoveries
  2. Boost Verification: KG_PATH_BOOST (1.2×) applied correctly, capped at 1.0
  3. Graceful Degradation: no crash on empty KG, missing file, disconnected domains
  4. Pheromone Learning: repeated traversals → lower path cost → faster convergence
  5. Production-like: 5-domain corpus, multiple hypotheses, quality metrics

Usage:
    PYTHONPATH=/shared/ASTRA-dev:/shared/mempalace-agi/src python3 scripts/causal_chain_experiment.py
"""

import json
import logging
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path setup ──────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.memory_augmented_orient import MemoryAugmentedOrient, KG_PATH_BOOST
from mempalace_agi.retrieval_profiles import (
    RetrievalProfile, ORIENT_BREADTH, EVALUATE_PRECISION, DECIDE_RECENCY, compose,
)
from mempalace_agi.kg_pheromones import PheromoneManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("causal_chain_experiment")


# ── Data types ──────────────────────────────────────────────────────

@dataclass
class MockHypothesis:
    id: str
    description: str
    domain: str
    name: str = ""
    variables: list = None

    def __post_init__(self):
        if self.variables is None:
            self.variables = []


# ── KG Corpus Builder ──────────────────────────────────────────────

def create_rich_kg(db_path: str, include_astro_epi_bridge: bool = False) -> int:
    """Create a multi-domain KG with cross-domain causal chains.

    Graph structure:
        Climate ←→ Economics:
            co2 →(causes)→ temperature →(causes)→ gdp_change
            climate →(involves)→ co2, temperature
            economics →(involves)→ gdp, gdp_change

        Economics ←→ Epidemiology:
            population →(correlated_with)→ gdp →(causes)→ life_expectancy
            gdp →(causes)→ healthcare_spending →(causes)→ life_expectancy
            economics →(involves)→ gdp, population
            epidemiology →(involves)→ life_expectancy, healthcare_spending

        Climate ←→ Epidemiology:
            temperature →(causes)→ disease_spread
            climate →(involves)→ temperature
            epidemiology →(involves)→ disease_spread

        Astrophysics (isolated by default):
            stellar_mass →(causes)→ luminosity →(causes)→ habitable_zone
            astrophysics →(involves)→ stellar_mass, luminosity, habitable_zone

        Optional Astrophysics ←→ Epidemiology bridge:
            radiation →(causes)→ cancer_rate
            astrophysics →(involves)→ radiation
            epidemiology →(involves)→ cancer_rate

        Cryptography (isolated):
            key_length →(causes)→ encryption_strength
            cryptography →(involves)→ key_length, encryption_strength

    Returns number of triples inserted.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS triples (
        id INTEGER PRIMARY KEY,
        subject TEXT,
        predicate TEXT,
        object TEXT,
        confidence REAL DEFAULT 0.8,
        source TEXT DEFAULT 'experiment',
        valid_from TEXT DEFAULT '',
        valid_to TEXT DEFAULT ''
    )""")

    triples = [
        # Climate → Economics chain
        ("co2", "causes", "temperature", 0.92),
        ("temperature", "causes", "gdp_change", 0.73),
        ("climate", "involves_variable", "co2", 0.95),
        ("climate", "involves_variable", "temperature", 0.95),
        ("economics", "involves_variable", "gdp", 0.90),
        ("economics", "involves_variable", "gdp_change", 0.88),

        # Economics → Epidemiology chain
        ("population", "correlated_with", "gdp", 0.82),
        ("gdp", "causes", "life_expectancy", 0.78),
        ("gdp", "causes", "healthcare_spending", 0.85),
        ("healthcare_spending", "causes", "life_expectancy", 0.80),
        ("economics", "involves_variable", "population", 0.85),
        ("epidemiology", "involves_variable", "life_expectancy", 0.92),
        ("epidemiology", "involves_variable", "healthcare_spending", 0.88),

        # Climate → Epidemiology chain
        ("temperature", "causes", "disease_spread", 0.65),
        ("epidemiology", "involves_variable", "disease_spread", 0.90),

        # Astrophysics (isolated subgraph)
        ("stellar_mass", "causes", "luminosity", 0.95),
        ("luminosity", "causes", "habitable_zone", 0.80),
        ("astrophysics", "involves_variable", "stellar_mass", 0.92),
        ("astrophysics", "involves_variable", "luminosity", 0.90),
        ("astrophysics", "involves_variable", "habitable_zone", 0.85),

        # Cryptography (isolated subgraph)
        ("key_length", "causes", "encryption_strength", 0.95),
        ("cryptography", "involves_variable", "key_length", 0.90),
        ("cryptography", "involves_variable", "encryption_strength", 0.90),
    ]

    if include_astro_epi_bridge:
        triples.extend([
            ("radiation", "causes", "cancer_rate", 0.70),
            ("astrophysics", "involves_variable", "radiation", 0.85),
            ("epidemiology", "involves_variable", "cancer_rate", 0.88),
        ])

    for s, p, o, c in triples:
        conn.execute(
            "INSERT INTO triples (subject, predicate, object, confidence) "
            "VALUES (?, ?, ?, ?)",
            (s, p, o, c),
        )
    conn.commit()
    conn.close()
    return len(triples)


def create_empty_kg(db_path: str):
    """Create KG with schema but no triples."""
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS triples (
        id INTEGER PRIMARY KEY,
        subject TEXT, predicate TEXT, object TEXT,
        confidence REAL DEFAULT 0.8,
        source TEXT DEFAULT 'experiment',
        valid_from TEXT DEFAULT '', valid_to TEXT DEFAULT ''
    )""")
    conn.commit()
    conn.close()


# ── Discovery Corpus Builder ──────────────────────────────────────

DISCOVERY_CORPUS = [
    # Climate
    dict(hypothesis_id="H001", domain="Climate", finding_type="anomaly",
         variables=["temperature", "co2"],
         statistic=6.2, p_value=0.00001,
         description="Global temperature anomaly closely tracks atmospheric CO2 concentration over 146 years",
         data_source="gistemp"),
    dict(hypothesis_id="H002", domain="Climate", finding_type="trend",
         variables=["co2", "sea_level"],
         statistic=4.8, p_value=0.0005,
         description="Rising CO2 levels correlate with accelerating sea level rise",
         data_source="noaa"),
    dict(hypothesis_id="H003", domain="Climate", finding_type="correlation",
         variables=["temperature", "disease_spread"],
         statistic=3.1, p_value=0.008,
         description="Higher temperatures linked to faster spread of vector-borne diseases",
         data_source="gistemp"),

    # Economics
    dict(hypothesis_id="H004", domain="Economics", finding_type="correlation",
         variables=["gdp_change", "temperature"],
         statistic=3.5, p_value=0.005,
         description="GDP change in developing nations correlates with temperature fluctuations",
         data_source="worldbank"),
    dict(hypothesis_id="H005", domain="Economics", finding_type="scaling",
         variables=["gdp", "population"],
         statistic=5.1, p_value=0.0001,
         description="GDP scales super-linearly with urban population size",
         data_source="worldbank"),
    dict(hypothesis_id="H006", domain="Economics", finding_type="trend",
         variables=["healthcare_spending", "gdp"],
         statistic=4.0, p_value=0.001,
         description="Healthcare spending as GDP fraction increases with national income",
         data_source="worldbank"),

    # Epidemiology
    dict(hypothesis_id="H007", domain="Epidemiology", finding_type="scaling",
         variables=["life_expectancy", "gdp"],
         statistic=4.2, p_value=0.001,
         description="Life expectancy scales logarithmically with GDP per capita",
         data_source="who"),
    dict(hypothesis_id="H008", domain="Epidemiology", finding_type="correlation",
         variables=["disease_spread", "temperature"],
         statistic=3.3, p_value=0.006,
         description="Malaria incidence increases with mean annual temperature",
         data_source="who"),
    dict(hypothesis_id="H009", domain="Epidemiology", finding_type="trend",
         variables=["healthcare_spending", "life_expectancy"],
         statistic=3.8, p_value=0.003,
         description="Per-capita healthcare spending strongly predicts life expectancy gains",
         data_source="who"),

    # Astrophysics (isolated)
    dict(hypothesis_id="H010", domain="Astrophysics", finding_type="scaling",
         variables=["stellar_mass", "luminosity"],
         statistic=8.5, p_value=0.00001,
         description="Mass-luminosity relation follows power law L ∝ M^3.5 for main-sequence stars",
         data_source="exoplanets"),
    dict(hypothesis_id="H011", domain="Astrophysics", finding_type="correlation",
         variables=["luminosity", "habitable_zone"],
         statistic=6.0, p_value=0.0002,
         description="Habitable zone radius scales with stellar luminosity",
         data_source="exoplanets"),

    # Cryptography (isolated)
    dict(hypothesis_id="H012", domain="Cryptography", finding_type="scaling",
         variables=["key_length", "encryption_strength"],
         statistic=9.0, p_value=0.000001,
         description="Encryption strength grows exponentially with key length in symmetric ciphers",
         data_source="nist"),
]


def populate_memory(memory: PalaceDiscoveryMemory, subset: str = "all") -> int:
    """Populate memory with discovery corpus.

    Args:
        subset: "all", "connected" (Climate+Econ+Epi), "climate_only"
    """
    corpus = DISCOVERY_CORPUS
    if subset == "connected":
        corpus = [d for d in corpus if d["domain"] in ("Climate", "Economics", "Epidemiology")]
    elif subset == "climate_only":
        corpus = [d for d in corpus if d["domain"] == "Climate"]

    for d in corpus:
        memory.record_discovery(**d)
    return len(corpus)


# ── Test Infrastructure ───────────────────────────────────────────

class ExperimentResult:
    """Accumulates results from all tests."""

    def __init__(self):
        self.tests: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def record(self, name: str, passed: bool, details: Dict[str, Any],
               latency_ms: float = 0.0):
        self.tests.append({
            "name": name,
            "passed": passed,
            "latency_ms": round(latency_ms, 2),
            "details": details,
        })
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {name} ({latency_ms:.1f}ms)")
        if not passed:
            logger.warning(f"  Details: {json.dumps(details, indent=2, default=str)[:500]}")

    def summary(self) -> Dict[str, Any]:
        total = len(self.tests)
        passed = sum(1 for t in self.tests if t["passed"])
        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total else 0,
            "total_time_s": round(time.time() - self.start_time, 2),
            "tests": self.tests,
        }


def fresh_env(tmp_root: str, include_bridge: bool = False):
    """Create a fresh PalaceDiscoveryMemory + KG database pair."""
    subdir = tempfile.mkdtemp(dir=tmp_root)
    config = IntegrationConfig(
        palace_path=os.path.join(subdir, "palace"),
        kg_db_path=os.path.join(subdir, "kg.sqlite3"),
        discovery_db_path=os.path.join(subdir, "disc.db"),
    )
    memory = PalaceDiscoveryMemory(config=config, max_records=200)
    kg_path = os.path.join(subdir, "kg.sqlite3")
    n_triples = create_rich_kg(kg_path, include_astro_epi_bridge=include_bridge)
    return memory, kg_path, config, n_triples


# ═══════════════════════════════════════════════════════════════════
#  TEST 1: Chain Discovery
# ═══════════════════════════════════════════════════════════════════

def test_chain_discovery(results: ExperimentResult, tmp_root: str):
    """Verify orient finds causal chains between connected domains."""
    memory, kg_path, config, n_triples = fresh_env(tmp_root)
    n_disc = populate_memory(memory, "all")

    orient = MemoryAugmentedOrient(
        palace_memory=memory,
        kg_db_path=kg_path,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )

    # Test 1a: Climate → should find chains to Economics and/or Epidemiology
    t0 = time.time()
    ctx_climate = orient.retrieve_context(
        hypotheses=[MockHypothesis(
            id="H_TEST_1A",
            description="CO2 atmospheric concentration drives temperature anomalies globally",
            domain="Climate",
            variables=["co2", "temperature"],
        )],
        current_domain="Climate",
        phase="orient",
    )
    latency_1a = (time.time() - t0) * 1000

    chains_climate = ctx_climate["causal_chains"]
    cross_climate = ctx_climate["cross_domain"]
    chain_domains = set()
    for c in chains_climate:
        chain_domains.add(c["goal"])

    results.record(
        "1a_climate_chain_discovery",
        passed=len(chains_climate) >= 1,
        details={
            "n_chains": len(chains_climate),
            "chain_domains": list(chain_domains),
            "n_cross_domain_hits": len(cross_climate),
            "n_discoveries": n_disc,
            "n_triples": n_triples,
            "chains": chains_climate,
        },
        latency_ms=latency_1a,
    )

    # Test 1b: Validate chain structure
    all_valid = True
    required_keys = {"start", "goal", "path", "cost", "hops", "discovery_id"}
    for chain in chains_climate:
        if not required_keys.issubset(chain.keys()):
            all_valid = False
        if chain["hops"] < 1:
            all_valid = False
        if len(chain["path"]) < 2:
            all_valid = False
        if chain["cost"] <= 0:
            all_valid = False

    results.record(
        "1b_chain_structure_valid",
        passed=all_valid and len(chains_climate) >= 1,
        details={
            "n_chains_validated": len(chains_climate),
            "required_keys": list(required_keys),
            "sample_chain": chains_climate[0] if chains_climate else None,
        },
        latency_ms=0,
    )

    # Test 1c: Economics → should find chains to Climate and/or Epidemiology
    t0 = time.time()
    ctx_econ = orient.retrieve_context(
        hypotheses=[MockHypothesis(
            id="H_TEST_1C",
            description="GDP growth correlates with population dynamics and economic output",
            domain="Economics",
            variables=["gdp", "population"],
        )],
        current_domain="Economics",
        phase="orient",
    )
    latency_1c = (time.time() - t0) * 1000
    chains_econ = ctx_econ["causal_chains"]

    results.record(
        "1c_economics_chain_discovery",
        passed=len(chains_econ) >= 1,
        details={
            "n_chains": len(chains_econ),
            "chain_goals": [c["goal"] for c in chains_econ],
            "n_cross_domain": len(ctx_econ["cross_domain"]),
        },
        latency_ms=latency_1c,
    )

    # Test 1d: Cross-domain hits with kg_path metadata
    hits_with_kgpath = [h for h in ctx_climate["cross_domain"] if "kg_path" in h]
    results.record(
        "1d_kg_path_metadata_present",
        passed=len(hits_with_kgpath) >= 1,
        details={
            "n_hits_with_kg_path": len(hits_with_kgpath),
            "n_total_cross_domain": len(cross_climate),
            "sample_kg_path": hits_with_kgpath[0]["kg_path"] if hits_with_kgpath else None,
        },
        latency_ms=0,
    )

    # Test 1e: kg_path metadata structure
    all_meta_valid = True
    for h in hits_with_kgpath:
        kp = h["kg_path"]
        if "path" not in kp or "cost" not in kp or "hops" not in kp:
            all_meta_valid = False
        if kp["hops"] < 1 or not isinstance(kp["path"], list):
            all_meta_valid = False

    results.record(
        "1e_kg_path_metadata_structure",
        passed=all_meta_valid and len(hits_with_kgpath) >= 1,
        details={
            "n_validated": len(hits_with_kgpath),
            "sample": hits_with_kgpath[0] if hits_with_kgpath else None,
        },
        latency_ms=0,
    )


# ═══════════════════════════════════════════════════════════════════
#  TEST 2: Boost Verification
# ═══════════════════════════════════════════════════════════════════

def test_boost_verification(results: ExperimentResult, tmp_root: str):
    """Compare similarity scores with and without KG path boost."""
    memory, kg_path, config, _ = fresh_env(tmp_root)
    populate_memory(memory, "all")

    hyp = MockHypothesis(
        id="H_TEST_2",
        description="CO2 atmospheric concentration temperature anomaly global warming",
        domain="Climate",
        variables=["co2", "temperature"],
    )

    # Without KG
    orient_no_kg = MemoryAugmentedOrient(
        palace_memory=memory,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    t0 = time.time()
    ctx_no_kg = orient_no_kg.retrieve_context(
        hypotheses=[hyp], current_domain="Climate", phase="orient",
    )
    lat_no_kg = (time.time() - t0) * 1000

    sims_no_kg = {h["discovery_id"]: h["similarity"] for h in ctx_no_kg["cross_domain"]}

    # With KG
    orient_with_kg = MemoryAugmentedOrient(
        palace_memory=memory,
        kg_db_path=kg_path,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    t0 = time.time()
    ctx_with_kg = orient_with_kg.retrieve_context(
        hypotheses=[hyp], current_domain="Climate", phase="orient",
    )
    lat_with_kg = (time.time() - t0) * 1000

    # Test 2a: Boosted hits should have higher similarity
    boosted_hits = []
    unboosted_hits = []
    boost_violations = []
    for hit in ctx_with_kg["cross_domain"]:
        did = hit["discovery_id"]
        if "kg_path" in hit and did in sims_no_kg:
            original = sims_no_kg[did]
            boosted = hit["similarity"]
            boosted_hits.append({
                "discovery_id": did,
                "original_sim": round(original, 6),
                "boosted_sim": round(boosted, 6),
                "boost_factor": round(boosted / original, 4) if original > 0 else float("inf"),
            })
            if boosted < original:
                boost_violations.append(did)
        elif did in sims_no_kg:
            unboosted_hits.append({
                "discovery_id": did,
                "similarity": round(hit["similarity"], 6),
                "original_sim": round(sims_no_kg[did], 6),
            })

    results.record(
        "2a_boost_increases_similarity",
        passed=len(boosted_hits) >= 1 and len(boost_violations) == 0,
        details={
            "n_boosted": len(boosted_hits),
            "n_unboosted": len(unboosted_hits),
            "n_violations": len(boost_violations),
            "violations": boost_violations,
            "boosted_hits": boosted_hits,
            "latency_no_kg_ms": round(lat_no_kg, 1),
            "latency_with_kg_ms": round(lat_with_kg, 1),
            "latency_overhead_ms": round(lat_with_kg - lat_no_kg, 1),
        },
        latency_ms=lat_with_kg,
    )

    # Test 2b: Boost factor should be exactly KG_PATH_BOOST (1.2) or capped at 1.0
    correct_factors = 0
    for bh in boosted_hits:
        if bh["original_sim"] * KG_PATH_BOOST > 1.0:
            # Should be capped at 1.0
            if bh["boosted_sim"] == 1.0:
                correct_factors += 1
        else:
            # Should be exactly original * 1.2
            expected = round(bh["original_sim"] * KG_PATH_BOOST, 6)
            if abs(bh["boosted_sim"] - expected) < 0.0001:
                correct_factors += 1

    results.record(
        "2b_boost_factor_correct",
        passed=correct_factors == len(boosted_hits) and len(boosted_hits) >= 1,
        details={
            "correct_factors": correct_factors,
            "total_boosted": len(boosted_hits),
            "expected_boost": KG_PATH_BOOST,
            "boosted_hits": boosted_hits,
        },
        latency_ms=0,
    )

    # Test 2c: All similarities capped at 1.0
    over_1 = [h for h in ctx_with_kg["cross_domain"] if h["similarity"] > 1.0]
    results.record(
        "2c_similarity_capped_at_1",
        passed=len(over_1) == 0,
        details={
            "n_over_1": len(over_1),
            "violations": over_1,
            "max_sim": max(h["similarity"] for h in ctx_with_kg["cross_domain"]) if ctx_with_kg["cross_domain"] else 0,
        },
        latency_ms=0,
    )

    # Test 2d: Evaluate phase should NOT boost even with kg_db_path set
    orient_eval = MemoryAugmentedOrient(
        palace_memory=memory,
        kg_db_path=kg_path,
        evaluate_profile=compose(EVALUATE_PRECISION, min_similarity=0.0),
        cross_domain_results=16,
    )
    ctx_eval = orient_eval.retrieve_context(
        hypotheses=[hyp], current_domain="Climate", phase="evaluate",
    )
    results.record(
        "2d_evaluate_phase_no_boost",
        passed=ctx_eval["causal_chains"] == [],
        details={
            "causal_chains": ctx_eval["causal_chains"],
            "profile_used": ctx_eval["profile_used"],
        },
        latency_ms=0,
    )

    # Test 2e: use_kg_paths=False explicitly disables boost
    orient_no_flag = MemoryAugmentedOrient(
        palace_memory=memory,
        kg_db_path=kg_path,
        orient_profile=compose(ORIENT_BREADTH, use_kg_paths=False, min_similarity=0.0),
        cross_domain_results=16,
    )
    ctx_no_flag = orient_no_flag.retrieve_context(
        hypotheses=[hyp], current_domain="Climate", phase="orient",
    )
    any_kg_path = any("kg_path" in h for h in ctx_no_flag["cross_domain"])
    results.record(
        "2e_use_kg_paths_false_disables",
        passed=(ctx_no_flag["causal_chains"] == [] and not any_kg_path),
        details={
            "causal_chains": ctx_no_flag["causal_chains"],
            "any_hit_has_kg_path": any_kg_path,
            "profile_used": ctx_no_flag["profile_used"],
        },
        latency_ms=0,
    )


# ═══════════════════════════════════════════════════════════════════
#  TEST 3: Graceful Degradation
# ═══════════════════════════════════════════════════════════════════

def test_graceful_degradation(results: ExperimentResult, tmp_root: str):
    """Verify no crashes with empty KG, missing file, disconnected domains."""
    hyp = MockHypothesis(
        id="H_TEST_3",
        description="Temperature anomaly and CO2 concentration",
        domain="Climate",
        variables=["temperature", "co2"],
    )

    # Test 3a: Empty KG (schema but no triples)
    memory_3a, _, config_3a, _ = fresh_env(tmp_root)
    populate_memory(memory_3a, "all")
    empty_kg = os.path.join(tmp_root, "empty_kg.sqlite3")
    create_empty_kg(empty_kg)

    orient_empty = MemoryAugmentedOrient(
        palace_memory=memory_3a,
        kg_db_path=empty_kg,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    t0 = time.time()
    try:
        ctx_empty = orient_empty.retrieve_context(
            hypotheses=[hyp], current_domain="Climate", phase="orient",
        )
        no_crash_empty = True
        chains_empty = ctx_empty["causal_chains"]
    except Exception as e:
        no_crash_empty = False
        chains_empty = str(e)
    lat_empty = (time.time() - t0) * 1000

    results.record(
        "3a_empty_kg_no_crash",
        passed=no_crash_empty and chains_empty == [],
        details={
            "no_crash": no_crash_empty,
            "causal_chains": chains_empty,
            "cross_domain_count": len(ctx_empty["cross_domain"]) if no_crash_empty else -1,
        },
        latency_ms=lat_empty,
    )

    # Test 3b: Non-existent KG file
    memory_3b, _, config_3b, _ = fresh_env(tmp_root)
    populate_memory(memory_3b, "all")
    fake_path = os.path.join(tmp_root, "nonexistent_kg.sqlite3")

    orient_fake = MemoryAugmentedOrient(
        palace_memory=memory_3b,
        kg_db_path=fake_path,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    t0 = time.time()
    try:
        ctx_fake = orient_fake.retrieve_context(
            hypotheses=[hyp], current_domain="Climate", phase="orient",
        )
        no_crash_fake = True
        key_present = "causal_chains" in ctx_fake
    except Exception as e:
        no_crash_fake = False
        key_present = False
    lat_fake = (time.time() - t0) * 1000

    results.record(
        "3b_nonexistent_kg_no_crash",
        passed=no_crash_fake and key_present,
        details={
            "no_crash": no_crash_fake,
            "causal_chains_key_present": key_present,
        },
        latency_ms=lat_fake,
    )

    # Test 3c: Only one domain — no cross-domain hits possible
    memory_3c, kg_path_3c, config_3c, _ = fresh_env(tmp_root)
    populate_memory(memory_3c, "climate_only")

    orient_single = MemoryAugmentedOrient(
        palace_memory=memory_3c,
        kg_db_path=kg_path_3c,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    ctx_single = orient_single.retrieve_context(
        hypotheses=[hyp], current_domain="Climate", phase="orient",
    )
    results.record(
        "3c_single_domain_no_chains",
        passed=ctx_single["causal_chains"] == [],
        details={
            "causal_chains": ctx_single["causal_chains"],
            "cross_domain_count": len(ctx_single["cross_domain"]),
        },
        latency_ms=0,
    )

    # Test 3d: Astrophysics query — isolated subgraph, no chain to Climate/Economics
    memory_3d, kg_path_3d, config_3d, _ = fresh_env(tmp_root)
    populate_memory(memory_3d, "all")

    orient_astro = MemoryAugmentedOrient(
        palace_memory=memory_3d,
        kg_db_path=kg_path_3d,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    ctx_astro = orient_astro.retrieve_context(
        hypotheses=[MockHypothesis(
            id="H_TEST_3D",
            description="Stellar mass luminosity habitable zone relationship",
            domain="Astrophysics",
            variables=["stellar_mass", "luminosity"],
        )],
        current_domain="Astrophysics",
        phase="orient",
    )
    # Chains from Astrophysics to other domains should be 0 (isolated subgraph)
    astro_chains = ctx_astro["causal_chains"]
    results.record(
        "3d_isolated_domain_no_chains",
        passed=len(astro_chains) == 0,
        details={
            "n_chains": len(astro_chains),
            "chains": astro_chains,
            "n_cross_domain": len(ctx_astro["cross_domain"]),
            "cross_domain_domains": list(set(h.get("domain", "") for h in ctx_astro["cross_domain"])),
        },
        latency_ms=0,
    )

    # Test 3e: kg_db_path=None (no KG configured)
    memory_3e, _, config_3e, _ = fresh_env(tmp_root)
    populate_memory(memory_3e, "all")
    orient_none = MemoryAugmentedOrient(
        palace_memory=memory_3e,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    ctx_none = orient_none.retrieve_context(
        hypotheses=[hyp], current_domain="Climate", phase="orient",
    )
    results.record(
        "3e_no_kg_configured",
        passed=(ctx_none["causal_chains"] == [] and "causal_chains" in ctx_none),
        details={
            "causal_chains": ctx_none["causal_chains"],
            "cross_domain_count": len(ctx_none["cross_domain"]),
        },
        latency_ms=0,
    )

    # Test 3f: causal_chains key present in ALL phases
    memory_3f, kg_path_3f, config_3f, _ = fresh_env(tmp_root)
    populate_memory(memory_3f, "all")
    orient_3f = MemoryAugmentedOrient(palace_memory=memory_3f, kg_db_path=kg_path_3f)
    key_present_all_phases = True
    for phase in ("orient", "evaluate", "decide"):
        ctx = orient_3f.retrieve_context(
            hypotheses=[hyp], current_domain="Climate", phase=phase,
        )
        if "causal_chains" not in ctx:
            key_present_all_phases = False

    results.record(
        "3f_causal_chains_key_all_phases",
        passed=key_present_all_phases,
        details={"tested_phases": ["orient", "evaluate", "decide"]},
        latency_ms=0,
    )


# ═══════════════════════════════════════════════════════════════════
#  TEST 4: Pheromone Learning
# ═══════════════════════════════════════════════════════════════════

def test_pheromone_learning(results: ExperimentResult, tmp_root: str):
    """Verify pheromone deposits make repeated chains cheaper over time."""
    memory, kg_path, config, _ = fresh_env(tmp_root)
    populate_memory(memory, "all")

    # Initialize pheromone manager
    pheromone_mgr = PheromoneManager(db_path=kg_path)

    # Get baseline stats
    stats_before = pheromone_mgr.get_stats()

    # Test 4a: Orient WITHOUT pheromones — get baseline costs
    orient_no_pher = MemoryAugmentedOrient(
        palace_memory=memory,
        kg_db_path=kg_path,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    ctx_baseline = orient_no_pher.retrieve_context(
        hypotheses=[MockHypothesis(
            id="H_TEST_4A",
            description="CO2 temperature atmospheric global warming",
            domain="Climate",
            variables=["co2", "temperature"],
        )],
        current_domain="Climate",
        phase="orient",
    )
    baseline_chains = ctx_baseline["causal_chains"]
    baseline_costs = {c["discovery_id"]: c["cost"] for c in baseline_chains}

    results.record(
        "4a_baseline_without_pheromones",
        passed=len(baseline_chains) >= 1,
        details={
            "n_chains": len(baseline_chains),
            "costs": baseline_costs,
            "pheromone_stats_before": stats_before,
        },
        latency_ms=0,
    )

    # Deposit pheromones on paths found — simulate multiple traversals
    # Get triple IDs along the causal chains
    from mempalace_agi.kg_pathfinder import GraphAdapter

    adapter = GraphAdapter(db_path=kg_path)
    deposited_triples = set()
    for chain in baseline_chains:
        path = chain["path"]
        for i in range(len(path) - 1):
            edge_info = adapter.get_edge_info(path[i], path[i + 1])
            if edge_info:
                triple_id = edge_info["triple_id"]
                deposited_triples.add(triple_id)
                # Deposit multiple times to simulate learning
                for _ in range(5):
                    pheromone_mgr.deposit_traversal(triple_id, amount=0.2)
                    pheromone_mgr.deposit_success(triple_id, amount=0.3)

    stats_after_deposit = pheromone_mgr.get_stats()

    # Test 4b: Pheromone levels increased
    results.record(
        "4b_pheromones_deposited",
        passed=(stats_after_deposit["success"]["nonzero"] > stats_before["success"]["nonzero"]),
        details={
            "before_nonzero_success": stats_before["success"]["nonzero"],
            "after_nonzero_success": stats_after_deposit["success"]["nonzero"],
            "deposited_on_triples": len(deposited_triples),
            "stats_after": stats_after_deposit,
        },
        latency_ms=0,
    )

    # Test 4c: Orient WITH pheromones — costs should be lower
    orient_with_pher = MemoryAugmentedOrient(
        palace_memory=memory,
        kg_db_path=kg_path,
        pheromone_manager=pheromone_mgr,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    t0 = time.time()
    ctx_with_pher = orient_with_pher.retrieve_context(
        hypotheses=[MockHypothesis(
            id="H_TEST_4C",
            description="CO2 temperature atmospheric global warming",
            domain="Climate",
            variables=["co2", "temperature"],
        )],
        current_domain="Climate",
        phase="orient",
    )
    lat_pher = (time.time() - t0) * 1000
    pher_chains = ctx_with_pher["causal_chains"]
    pher_costs = {c["discovery_id"]: c["cost"] for c in pher_chains}

    # Compare costs: pheromone paths should be cheaper
    cost_reductions = {}
    for did, baseline_cost in baseline_costs.items():
        if did in pher_costs:
            reduction = (baseline_cost - pher_costs[did]) / baseline_cost * 100
            cost_reductions[did] = {
                "baseline_cost": round(baseline_cost, 6),
                "pheromone_cost": round(pher_costs[did], 6),
                "reduction_pct": round(reduction, 2),
            }

    any_reduction = any(r["reduction_pct"] > 0 for r in cost_reductions.values())
    results.record(
        "4c_pheromone_reduces_cost",
        passed=any_reduction and len(cost_reductions) >= 1,
        details={
            "cost_reductions": cost_reductions,
            "n_chains_baseline": len(baseline_chains),
            "n_chains_pheromone": len(pher_chains),
        },
        latency_ms=lat_pher,
    )

    # Test 4d: Verify pheromone modifier math
    # For each deposited triple, check that get_pheromone_modifier < 1.0
    modifiers = {}
    for tid in deposited_triples:
        mod = pheromone_mgr.get_pheromone_modifier(tid)
        modifiers[tid] = mod

    all_reduced = all(m < 1.0 for m in modifiers.values())
    results.record(
        "4d_pheromone_modifier_reduces_cost",
        passed=all_reduced and len(modifiers) >= 1,
        details={
            "modifiers": {k: round(v, 6) for k, v in modifiers.items()},
            "all_below_1": all_reduced,
            "min_modifier": round(min(modifiers.values()), 6) if modifiers else None,
            "max_modifier": round(max(modifiers.values()), 6) if modifiers else None,
        },
        latency_ms=0,
    )

    # Test 4e: Multi-cycle pheromone convergence (10 cycles)
    # IMPORTANT: Use a FRESH environment so pheromones start at zero.
    # The previous tests saturated pheromones above the cap (1.0) in the
    # modifier formula, so incremental deposits had zero marginal effect.
    # Here we start clean and deposit small amounts each cycle to observe
    # the cost converging downward.
    memory_4e, kg_path_4e, _, _ = fresh_env(tmp_root)
    populate_memory(memory_4e, "all")
    pheromone_mgr_4e = PheromoneManager(db_path=kg_path_4e)
    adapter_4e = GraphAdapter(db_path=kg_path_4e)

    # First: get baseline cost with zero pheromones
    orient_base_4e = MemoryAugmentedOrient(
        palace_memory=memory_4e,
        kg_db_path=kg_path_4e,
        pheromone_manager=pheromone_mgr_4e,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )
    ctx_base_4e = orient_base_4e.retrieve_context(
        hypotheses=[MockHypothesis(
            id="H_TEST_4E_BASE",
            description="CO2 temperature atmospheric global warming",
            domain="Climate",
            variables=["co2", "temperature"],
        )],
        current_domain="Climate",
        phase="orient",
    )
    base_chains_4e = ctx_base_4e["causal_chains"]

    cycle_costs = []
    for cycle in range(10):
        # Deposit small incremental pheromones on path triples
        for chain in base_chains_4e:
            path = chain["path"]
            for i in range(len(path) - 1):
                edge_info = adapter_4e.get_edge_info(path[i], path[i + 1])
                if edge_info:
                    # Small deposits: 0.05 traversal + 0.05 success per cycle
                    # After 10 cycles: max 0.5 each — still under the 1.0 cap
                    pheromone_mgr_4e.deposit_traversal(edge_info["triple_id"], amount=0.05)
                    pheromone_mgr_4e.deposit_success(edge_info["triple_id"], amount=0.05)

        # Re-query with the same pheromone manager
        orient_cycle = MemoryAugmentedOrient(
            palace_memory=memory_4e,
            kg_db_path=kg_path_4e,
            pheromone_manager=pheromone_mgr_4e,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
            cross_domain_results=16,
        )
        ctx_cycle = orient_cycle.retrieve_context(
            hypotheses=[MockHypothesis(
                id=f"H_TEST_4E_{cycle}",
                description="CO2 temperature atmospheric global warming",
                domain="Climate",
                variables=["co2", "temperature"],
            )],
            current_domain="Climate",
            phase="orient",
        )
        total_cost = sum(c["cost"] for c in ctx_cycle["causal_chains"])
        cycle_costs.append(round(total_cost, 6))

    # Costs should generally decrease (monotonic is ideal, but noise is OK)
    if len(cycle_costs) >= 2 and cycle_costs[0] > 0:
        overall_reduction = (cycle_costs[0] - cycle_costs[-1]) / cycle_costs[0] * 100
    else:
        overall_reduction = 0

    results.record(
        "4e_multi_cycle_convergence",
        passed=overall_reduction > 0,
        details={
            "cycle_costs": cycle_costs,
            "overall_reduction_pct": round(overall_reduction, 2),
            "first_cost": cycle_costs[0] if cycle_costs else None,
            "last_cost": cycle_costs[-1] if cycle_costs else None,
            "monotonic": all(cycle_costs[i] >= cycle_costs[i+1] for i in range(len(cycle_costs)-1)),
        },
        latency_ms=0,
    )

    # Test 4f: Decay reduces pheromones
    stats_pre_decay = pheromone_mgr.get_stats()
    n_decayed = pheromone_mgr.decay_all()
    stats_post_decay = pheromone_mgr.get_stats()

    decay_worked = (
        stats_post_decay["success"]["avg"] < stats_pre_decay["success"]["avg"]
        or stats_pre_decay["success"]["avg"] == 0
    )
    results.record(
        "4f_decay_reduces_pheromones",
        passed=decay_worked and n_decayed > 0,
        details={
            "n_decayed": n_decayed,
            "success_avg_before": stats_pre_decay["success"]["avg"],
            "success_avg_after": stats_post_decay["success"]["avg"],
            "traversal_avg_before": stats_pre_decay["traversal"]["avg"],
            "traversal_avg_after": stats_post_decay["traversal"]["avg"],
        },
        latency_ms=0,
    )


# ═══════════════════════════════════════════════════════════════════
#  TEST 5: Production-like Scenario
# ═══════════════════════════════════════════════════════════════════

def test_production_scenario(results: ExperimentResult, tmp_root: str):
    """Full 5-domain corpus, multiple hypotheses, quality metrics."""
    # Use the bridge to connect Astrophysics ↔ Epidemiology
    memory, kg_path, config, n_triples = fresh_env(tmp_root, include_bridge=True)
    n_disc = populate_memory(memory, "all")

    pheromone_mgr = PheromoneManager(db_path=kg_path)

    orient = MemoryAugmentedOrient(
        palace_memory=memory,
        kg_db_path=kg_path,
        pheromone_manager=pheromone_mgr,
        orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        cross_domain_results=16,
    )

    # Test 5a: Multi-hypothesis orient
    hypotheses = [
        MockHypothesis(
            id="H_PROD_1",
            description="CO2 concentration drives global temperature anomalies and economic impacts",
            domain="Climate",
            variables=["co2", "temperature", "gdp_change"],
        ),
        MockHypothesis(
            id="H_PROD_2",
            description="Temperature increase accelerates disease spread patterns",
            domain="Climate",
            variables=["temperature", "disease_spread"],
        ),
    ]

    t0 = time.time()
    ctx_multi = orient.retrieve_context(
        hypotheses=hypotheses,
        current_domain="Climate",
        phase="orient",
    )
    lat_multi = (time.time() - t0) * 1000

    results.record(
        "5a_multi_hypothesis_orient",
        passed=(len(ctx_multi["causal_chains"]) >= 1 and len(ctx_multi["cross_domain"]) >= 1),
        details={
            "n_hypotheses": len(hypotheses),
            "n_chains": len(ctx_multi["causal_chains"]),
            "n_cross_domain": len(ctx_multi["cross_domain"]),
            "chain_goals": [c["goal"] for c in ctx_multi["causal_chains"]],
            "per_hypothesis_counts": {
                k: len(v) for k, v in ctx_multi["per_hypothesis"].items()
            },
            "profile_used": ctx_multi["profile_used"],
        },
        latency_ms=lat_multi,
    )

    # Test 5b: All 5 domains queried — measure chain discovery rates
    all_domains = ["Climate", "Economics", "Epidemiology", "Astrophysics", "Cryptography"]
    domain_results = {}
    total_chains = 0
    total_latency = 0

    for domain in all_domains:
        hyp = MockHypothesis(
            id=f"H_PROD_{domain}",
            description=f"Research hypothesis about {domain.lower()} phenomena and cross-domain effects",
            domain=domain,
            variables=[],
        )
        t0 = time.time()
        ctx = orient.retrieve_context(
            hypotheses=[hyp], current_domain=domain, phase="orient",
        )
        lat = (time.time() - t0) * 1000
        total_latency += lat

        domain_results[domain] = {
            "n_chains": len(ctx["causal_chains"]),
            "n_cross_domain": len(ctx["cross_domain"]),
            "chain_goals": [c["goal"] for c in ctx["causal_chains"]],
            "boosted_hits": len([h for h in ctx["cross_domain"] if "kg_path" in h]),
            "latency_ms": round(lat, 1),
        }
        total_chains += len(ctx["causal_chains"])

    # Connected domains should have chains, isolated should not
    connected_have_chains = all(
        domain_results[d]["n_chains"] >= 1
        for d in ["Climate", "Economics", "Epidemiology"]
    )
    # Cryptography is truly isolated (no bridge)
    crypto_isolated = domain_results["Cryptography"]["n_chains"] == 0
    # Astrophysics should NOW have chains (we included the bridge)
    astro_has_chains = domain_results["Astrophysics"]["n_chains"] >= 1

    results.record(
        "5b_all_domains_chain_rates",
        passed=connected_have_chains and crypto_isolated,
        details={
            "domain_results": domain_results,
            "total_chains": total_chains,
            "avg_latency_ms": round(total_latency / len(all_domains), 1),
            "connected_domains_have_chains": connected_have_chains,
            "crypto_isolated": crypto_isolated,
            "astro_has_chains_with_bridge": astro_has_chains,
        },
        latency_ms=round(total_latency, 1),
    )

    # Test 5c: Astrophysics bridge test (radiation → cancer_rate)
    results.record(
        "5c_astro_epi_bridge_works",
        passed=astro_has_chains,
        details={
            "astro_chains": domain_results["Astrophysics"]["n_chains"],
            "astro_chain_goals": domain_results["Astrophysics"]["chain_goals"],
            "note": "Bridge: radiation →(causes)→ cancer_rate connects Astrophysics to Epidemiology",
        },
        latency_ms=0,
    )

    # Test 5d: Latency budget (<2000ms per orient call)
    max_latency = max(d["latency_ms"] for d in domain_results.values())
    avg_latency = total_latency / len(all_domains)
    results.record(
        "5d_latency_within_budget",
        passed=max_latency < 2000,
        details={
            "max_latency_ms": round(max_latency, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "budget_ms": 2000,
            "per_domain_latency": {d: domain_results[d]["latency_ms"] for d in all_domains},
        },
        latency_ms=0,
    )

    # Test 5e: Quality — boosted hits should have higher mean similarity than unboosted
    all_hits = []
    for domain in all_domains:
        hyp = MockHypothesis(
            id=f"H_QUAL_{domain}",
            description=f"Research about {domain.lower()} cross-domain connections",
            domain=domain,
        )
        ctx = orient.retrieve_context(
            hypotheses=[hyp], current_domain=domain, phase="orient",
        )
        for h in ctx["cross_domain"]:
            all_hits.append({
                "query_domain": domain,
                "hit_domain": h.get("domain", ""),
                "similarity": h["similarity"],
                "has_kg_path": "kg_path" in h,
            })

    boosted = [h["similarity"] for h in all_hits if h["has_kg_path"]]
    unboosted = [h["similarity"] for h in all_hits if not h["has_kg_path"]]

    mean_boosted = sum(boosted) / len(boosted) if boosted else 0
    mean_unboosted = sum(unboosted) / len(unboosted) if unboosted else 0

    # Statistical test: if both groups have data
    p_value = None
    if len(boosted) >= 2 and len(unboosted) >= 2:
        try:
            from scipy.stats import mannwhitneyu
            stat, p_value = mannwhitneyu(boosted, unboosted, alternative="greater")
            p_value = round(p_value, 6)
        except ImportError:
            p_value = "scipy not available"

    results.record(
        "5e_boosted_vs_unboosted_quality",
        passed=mean_boosted > mean_unboosted if (boosted and unboosted) else len(boosted) >= 1,
        details={
            "n_boosted": len(boosted),
            "n_unboosted": len(unboosted),
            "mean_boosted_sim": round(mean_boosted, 6),
            "mean_unboosted_sim": round(mean_unboosted, 6),
            "difference": round(mean_boosted - mean_unboosted, 6),
            "mann_whitney_p": p_value,
            "total_hits": len(all_hits),
        },
        latency_ms=0,
    )


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    logger.info("=" * 70)
    logger.info("Phase 20 Causal Chain Orient Experiment")
    logger.info("=" * 70)
    logger.info(f"KG_PATH_BOOST = {KG_PATH_BOOST}")
    logger.info(f"ORIENT_BREADTH.use_kg_paths = {ORIENT_BREADTH.use_kg_paths}")
    logger.info(f"EVALUATE_PRECISION.use_kg_paths = {EVALUATE_PRECISION.use_kg_paths}")

    tmp_root = tempfile.mkdtemp(prefix="causal_chain_exp_")
    logger.info(f"Temp root: {tmp_root}")

    results = ExperimentResult()

    try:
        logger.info("\n" + "=" * 50)
        logger.info("TEST 1: Chain Discovery")
        logger.info("=" * 50)
        test_chain_discovery(results, tmp_root)

        logger.info("\n" + "=" * 50)
        logger.info("TEST 2: Boost Verification")
        logger.info("=" * 50)
        test_boost_verification(results, tmp_root)

        logger.info("\n" + "=" * 50)
        logger.info("TEST 3: Graceful Degradation")
        logger.info("=" * 50)
        test_graceful_degradation(results, tmp_root)

        logger.info("\n" + "=" * 50)
        logger.info("TEST 4: Pheromone Learning")
        logger.info("=" * 50)
        test_pheromone_learning(results, tmp_root)

        logger.info("\n" + "=" * 50)
        logger.info("TEST 5: Production Scenario")
        logger.info("=" * 50)
        test_production_scenario(results, tmp_root)

    except Exception as e:
        logger.error(f"EXPERIMENT ABORTED: {e}", exc_info=True)
        results.record("ABORT", passed=False, details={"error": str(e)})

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    # Summary
    summary = results.summary()
    logger.info("\n" + "=" * 70)
    logger.info(f"RESULTS: {summary['passed']}/{summary['total_tests']} passed "
                f"({summary['pass_rate']}%) in {summary['total_time_s']}s")
    logger.info("=" * 70)

    for t in summary["tests"]:
        status = "✅" if t["passed"] else "❌"
        logger.info(f"  {status} {t['name']} ({t['latency_ms']:.0f}ms)")

    # Save raw results
    out_dir = "/workspace/experiments/2026-04-10-causal-chains"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "results.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"\nRaw results saved to: {out_path}")

    return summary


if __name__ == "__main__":
    main()
