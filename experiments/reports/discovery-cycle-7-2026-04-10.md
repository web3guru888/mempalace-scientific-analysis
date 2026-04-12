# MemPalace-AGI Discovery Cycle 7 Report — 2026-04-10

**Experiment ID**: DC7-2026-04-10
**Date**: April 10, 2026
**Operator**: MEMPALACE-AGI (automated)
**System**: MemPalace-AGI v0.1.0 (Phase 20 — Embedding Dedup + Causal Chain Orient)
**Duration**: 479.1s
**Purpose**: Validate Phase 20 new features — 5th dedup heuristic (embedding-based) and causal chain enrichment in Orient

---

## Executive Summary

Discovery Cycle 7 validates Phase 20's two new features:
1. **Embedding-based dedup heuristic**: The 5th dedup heuristic uses the embedding model's own cosine similarity to compare query and candidate texts, providing the most reliable signal for duplicate detection. Weight: 1.5× (highest among all heuristics).
2. **Causal chain enrichment**: During ORIENT_BREADTH, cross-domain hits are enriched with KG A* paths connecting the current domain to the hit's domain, with a 1.2× similarity boost for KG-backed hits.

**11/12 targets met**

---

## Results Table

| # | Target | Metric | Value | Status |
|---|--------|--------|-------|--------|
| 1 | Store ≥208 discoveries | total_discoveries | 208 | ✅ |
| 2 | Cross-domain ≥20 hits | cross_domain_hits | 24 | ✅ |
| 3 | Dedup accuracy ≥87.5% | dedup_accuracy_pct | 100.0% | ✅ |
| 4 | 8-case battery: 100% | dedup_battery_perfect | True | ✅ |
| 5 | Embedding heuristic fires | emb_heuristic_fired | True | ✅ |
| 6 | Causal chain enrichment | causal_chain_enrichment | True | ✅ |
| 7 | KG path boost applied | kg_path_boost | True | ✅ |
| 8 | Time-decay rank change ≥30% | time_decay_rank_change_pct | 100.0% | ✅ |
| 9 | Status filter precision ≥90% | status_filter_precision_pct | 100.0% | ✅ |
| 10 | KG Pathfinder ≥3 hops | pathfinder_hops_gte3 | True | ✅ |
| 11 | Pheromone modifier ≤0.9 | pheromone_modifier_lte09 | True | ✅ |
| 12 | Orient time <2000ms | orient_time_ms | 11947.0ms | ❌ |

## Cross-Cycle Comparison

| Metric | C4 | C5 | C6 | **C7** |
|--------|----|----|----|----|
| Discoveries | 208 | 208 | 208 | **208** |
| Cross-domain | 35 | 35 | 24 | **24** |
| Dedup accuracy | 87.5% | 62.5% | 62.5% | **100.0%** |
| Orient time | 816ms | 828ms | 639ms | **11947.0ms** |
| Time decay | N/A | N/A | 100% | **100.0%** |
| Status filter | N/A | N/A | 100% | **100.0%** |
| Embedding dedup | N/A | N/A | N/A | **✅** |
| Causal chains | N/A | N/A | N/A | **✅** |
| KG path boost | N/A | N/A | N/A | **✅** |

## Phase 20 Feature Details

### Embedding-Based Dedup Heuristic (5th heuristic)
- **Weight**: 1.5× (highest among 5 heuristics)
- **Mechanism**: Computes fresh cosine similarity between query and candidate embeddings using the collection's embedding function
- **Thresholds**: >0.85 → full weight (1.5), ≥0.6 → half weight (0.75), <0.6 → no signal
- **Impact**: Closes the gap between threshold-only accuracy (87.5%) and reranker accuracy (was 62.5%, now 100.0%)
- **Battery result**: ✅ (8/8)

### Causal Chain Enrichment in Orient
- **Trigger**: ORIENT_BREADTH profile with `use_kg_paths=True`
- **Mechanism**: For each cross-domain hit, finds A* paths from current domain entities to hit domain entities in the KG
- **Boost**: KG_PATH_BOOST = 1.2× similarity multiplier for hits with KG-backed paths
- **Chains found**: 24
- **Result**: ✅

## Phase Timings

| Phase | Time |
|-------|------|
| 1. Corpus Ingestion (208 discoveries) | 275.3s |
| 2. Dedup Battery (8 cases) + Embedding Heuristic | 6.6s |
| 3. Orient + Causal Chain Enrichment | 69.3s |
| 4. Status Filter (EVALUATE_PRECISION / require_status) | 96.6s |
| 5. Time Decay (DECIDE_RECENCY) | 21.9s |
| 6. KG Pathfinder + Pheromones | 5.5s |
| 7. Query Isolation | 3.6s |
| **Total** | **479.1s** |

## Errors

None.

---

*Generated automatically by Cycle 7 experiment script at 2026-04-10T09:35:10.003372Z*
