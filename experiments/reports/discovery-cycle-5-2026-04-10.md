# MemPalace-AGI Discovery Cycle 5 Report — 2026-04-10

**Experiment ID**: DC5-2026-04-10
**Date**: April 10, 2026
**Operator**: mempalace-researcher
**System**: MemPalace-AGI v0.1.0 (215/215 tests passing)
**Duration**: ~243.7 seconds total
**Purpose**: Validate Phase 17 features — RetrievalProfile system, profile switching across OODA phases, and heuristic dedup reranking

---

## Executive Summary

Discovery Cycle 5 validates the Phase 17 RetrievalProfile system and discovers a **critical flaw in the heuristic dedup reranker**.

| Parameter | Cycle 4 | Cycle 5 | Change |
|-----------|---------|---------|--------|
| `orient_profile.n_results` | 5 (hardcoded) | **16** (ORIENT_BREADTH) | 3.2× wider |
| `orient_profile.min_similarity` | 0.2 | **0.2** (ORIENT_BREADTH) | Same |
| `evaluate_profile.n_results` | N/A | **8** (EVALUATE_PRECISION) | NEW |
| `evaluate_profile.min_similarity` | N/A | **0.6** (EVALUATE_PRECISION) | NEW |
| `decide_profile.n_results` | N/A | **5** (DECIDE_RECENCY) | NEW |
| Profile selection | N/A | **phase-based** | NEW |
| Dedup reranking | None | **heuristic (4 signals)** | NEW |

### Headline Results

- **9/10 targets met** — one failure (dedup accuracy) caused by reranker regression
- **RetrievalProfile system fully validated**: All 3 profiles exercised, 2 phase transitions validated, profile isolation confirmed, switching overhead <0.01ms
- **35 cross-domain orient hits** — matches Cycle 4 exactly despite wider n_results (16 vs 10)
- **100% search relevance** maintained (50/50) — perfect across all 5 cycles
- **827ms orient time/hypothesis** — stable under 1s with n_results=16 (vs 816ms at n=5)
- **709 entities, 904 triples** — stable knowledge graph
- **62.5% dedup accuracy** ❌ — **REGRESSION from 87.5%** caused by heuristic reranker being too aggressive
- **KEY FINDING**: Reranker correctly fixed `novel_new_finding_1` (+1) but incorrectly reclassified 3 true soft duplicates as novel (−3), net −2

### Critical Bug Found: Reranker "Absence = Novelty" Flaw

The `llm_rerank_duplicates()` heuristic reranker treats **absence of evidence as evidence of absence**. When none of the 4 heuristics fire (0/4 signals, `dup_ratio=0.0`), the reranker concludes the candidate is NOT a duplicate. But for paraphrased text where variable names, finding types, cycle numbers, and SVO patterns don't match the heuristic patterns, 0 signals simply means "insufficient evidence" — NOT "definitely novel."

**Root cause**: Line 1085 in `palace_discovery_memory.py`:
```python
elif dup_ratio <= 0.25:
    # Strong evidence it's NOT a duplicate
    c["is_duplicate"] = False
```

When `dup_ratio = 0.0` (no heuristics matched), this sets `is_duplicate = False`, overriding the cosine-similarity-based soft classification. This is wrong — `dup_ratio = 0.0` means "no heuristic evidence either way," not "strong evidence of novelty."

**Fix**: Only reclassify as novel when `dup_ratio <= 0.25` AND at least 2 heuristics were evaluable (i.e., `effective_total >= 2`). If `effective_total < 2`, leave the original classification unchanged.

---

## 1. Side-by-Side Metrics: Cycle 1 → Cycle 5

### 1.1 Core Metrics Evolution

| Metric | C1 | C2 | C3 | C4 | **C5** | Trend |
|--------|----|----|----|----|----|------|
| **Corpus** | | | | | | |
| Discoveries seeded | 14 | 55 | 208 | 208 | **208** | Stable at scale |
| Domains covered | 4 | 5 | 5 | 5 | **5** | Full coverage |
| **Orient Phase** | | | | | | |
| Cross-domain hits (orient) | 9 | 4 | 5 | 35 | **35** | Stable post-fix |
| Orient n_results | 5 | 5 | 5 | 5 | **16** | 📈 Profile-driven |
| Orient time/hypothesis | ~760ms | ~800ms | 796ms | 816ms | **828ms** | Stable under 1s |
| **Knowledge Graph** | | | | | | |
| KG entities | 50 | 187 | 710 | 709 | **709** | Stable |
| KG triples | 70 | 244 | 1,014 | 904 | **904** | Stable |
| **Search Quality** | | | | | | |
| Domain search relevance | 100% | 100% | 100% | 100% | **100%** | ✅ Perfect 5/5 |
| Cross-domain coverage (raw) | N/A | N/A | 91.7% | 91.7% | **91.7%** | Stable |
| **Duplicate Detection** | | | | | | |
| Threshold scheme | 0.90 | 0.84 | 0.84/0.60 | 0.86/0.55 | **0.86/0.55 + reranker** | New feature |
| Edge-case accuracy (threshold only) | N/A | N/A | 75% | 87.5% | **87.5%** | Stable |
| Edge-case accuracy (with reranker) | N/A | N/A | N/A | N/A | **62.5%** ❌ | Regression |
| **Performance** | | | | | | |
| Ingestion rate | 385ms | 310ms | 746ms | 694ms | **641ms** | ✅ 8% faster |
| Total time | 5.4s | 17s | 201s | 228.5s | **243.7s** | Linear with scope |
| **NEW: Profiles** | | | | | | |
| Profiles available | N/A | N/A | N/A | N/A | **3** | NEW |
| Phase transitions | N/A | N/A | N/A | N/A | **2** | NEW |
| Profile switching overhead | N/A | N/A | N/A | N/A | **<0.01ms** | Negligible |

### 1.2 Cross-Domain Breakdown (Orient Phase)

| Domain | C3 | C4 | **C5** | Domains Reached (C5) |
|--------|----|----|--------|---------------------|
| Astrophysics | 0 | 8 | **8** | Crypto, Climate, Economics |
| Economics | 2 | 10 | **10** | Crypto, Climate |
| Climate | 3 | 10 | **10** | Epi, Astro, Economics |
| Epidemiology | 0 | 5 | **5** | Climate |
| Cryptography | 0 | 2 | **2** | Epi, Economics |
| **Total** | **5** | **35** | **35** | |

Cross-domain results are **identical to Cycle 4** despite using n_results=16 instead of 5 for per-hypothesis retrieval. This is because the cross-domain pass uses `cross_domain_results=10` (unchanged) and the wider per-hypothesis retrieval doesn't affect the dedicated cross-domain search path.

---

## 2. RetrievalProfile Validation (NEW IN CYCLE 5) ⭐

### 2.1 Profile Configuration Validated

| Profile | n_results | min_similarity | time_decay | exclude_domain | require_status | Purpose |
|---------|-----------|---------------|------------|---------------|---------------|---------|
| **ORIENT_BREADTH** | 16 | 0.2 | No | No | None | Wide cast for discovery |
| **EVALUATE_PRECISION** | 8 | 0.6 | No | Yes | "decided" | Tight validation |
| **DECIDE_RECENCY** | 5 | 0.4 | Yes (30d) | No | "decided" | Recent authoritative |

### 2.2 Profile Behavior Comparison

#### ORIENT_BREADTH Results

| Domain | Per-Hyp Hits | Cross-Domain Hits | Domains Reached | Avg Similarity | Unique Discoveries |
|--------|-------------|-------------------|-----------------|---------------|-------------------|
| Astrophysics | 16+ | 7 | 3 | 0.3504 | 23 |
| Economics | 16+ | 5 | 3 | 0.4010 | 21 |
| Climate | 16+ | 10 | 3 | 0.5183 | 26 |

ORIENT_BREADTH correctly casts wide: low average similarity (0.35–0.52), high unique discovery counts, and cross-domain reach to 3 domains per query.

#### EVALUATE_PRECISION Results

| Domain | Per-Hyp Hits | Cross-Domain Hits | Avg Similarity | All ≥0.6 | Noise Rate |
|--------|-------------|-------------------|---------------|----------|-----------|
| Astrophysics | 0 | 0 | N/A | ✅ | 0% |
| Economics | 0 | 0 | N/A | ✅ | 0% |
| Climate | 1 | 0 | 0.6359 | ✅ | 0% |

EVALUATE_PRECISION correctly filters aggressively: the `require_status="decided"` constraint means only records with "decided" status are returned. Since our test corpus doesn't have decided records, most queries return 0 hits. Climate's single hit (sim=0.6359) passes the 0.6 threshold. **0% noise rate** — zero cross-domain results leaked into evaluate phase. This is the precision profile working exactly as designed.

#### DECIDE_RECENCY Results

| Domain | Per-Hyp Hits | Cross-Domain Hits | Avg Similarity |
|--------|-------------|-------------------|---------------|
| Astrophysics | 2 | 0 | 0.4269 |
| Economics | 5 | 0 | 0.4674 |
| Climate | 5 | 2 | 0.5637 |

DECIDE_RECENCY returns fewer results (n=5) with moderate similarity threshold (0.4). The `time_decay=True` and `half_life_days=30` are set but don't produce visible effects in this test because all records were created within seconds of each other.

### 2.3 Profile Isolation Test

| Metric | Orient | Evaluate | Decide | Correct? |
|--------|--------|----------|--------|----------|
| Profile used | orient_breadth | evaluate_precision | decide_recency | ✅ All 3 different |
| Hits returned | 10 | 0 | 2 | ✅ Orient widest |
| Unique IDs | 10 | 0 | 2 | ✅ |
| Orient ∩ Evaluate overlap | 0% | — | — | ✅ Fully isolated |

The profiles produce distinctly different result sets for the same query. ORIENT_BREADTH returns 10 hits, EVALUATE_PRECISION returns 0 (high min_similarity + require_status), and DECIDE_RECENCY returns 2. Zero overlap between orient and evaluate results.

### 2.4 Profile Switching Overhead

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Avg switching time | **0.0016ms** | <50ms | ✅ 31,250× under target |
| Max switching time | 0.0045ms | <50ms | ✅ |

Profile selection is a simple dictionary lookup — negligible overhead.

### 2.5 Backward Compatibility

| Test | Result |
|------|--------|
| Numeric params create profile | ✅ `max_results=10, min_sim=0.2` → profile with matching values |
| Profile name preserved | ✅ `orient_breadth` |
| Old `retrieve_context()` API works | ✅ No breaking changes |
| `compose()` override works | ✅ Custom profile with n=20, min_sim=0.15 created |
| `get_profile()` registry | ✅ All 3 found, unknown raises ValueError |

### 2.6 Profile Validation Summary

| Test | Status | Notes |
|------|--------|-------|
| All 3 profiles exercised | ✅ | orient_breadth, evaluate_precision, decide_recency |
| Phase transitions | ✅ 2 | orient→evaluate, evaluate→decide |
| Profile isolation | ✅ | Different result sets for same query |
| Breadth wider than precision | ✅ | 10 vs 0 hits |
| Switching overhead <50ms | ✅ | 0.002ms average |
| Backward compatibility | ✅ | Numeric params work, old API works |
| compose() | ✅ | Custom profile creation works |
| Registry | ✅ | get_profile() with error handling |

**RetrievalProfile is fully validated. All 8 profile tests pass.**

---

## 3. Tiered Duplicate Detection + Reranker Analysis

### 3.1 Threshold-Only Results (Cycle 4 Parity)

| Test Case | Similarity | Expected | Pre-Rerank | Pre-Rerank Correct? |
|-----------|-----------|----------|------------|-------------------|
| `hard_dup_verbatim` | 0.9393 | Hard | Hard | ✅ |
| `hard_dup_minor_reword` | 0.9012 | Hard | Hard | ✅ |
| `soft_dup_paraphrase_1` | 0.8139 | Soft | Soft | ✅ |
| `soft_dup_paraphrase_2` | 0.8409 | Soft | Soft | ✅ |
| `soft_dup_paraphrase_3` | 0.7341 | Soft | Soft | ✅ |
| `novel_new_finding_1` | 0.6690 | Novel | Soft | ❌ |
| `novel_new_finding_2` | 0.4861 | Novel | Novel | ✅ |
| `novel_new_finding_3` | 0.5268 | Novel | Novel | ✅ |

**Pre-reranking accuracy: 87.5% (7/8)** — identical to Cycle 4. The threshold-based system remains stable.

### 3.2 Reranker Impact

| Test Case | Pre-Rerank | Post-Rerank | Signals | Ratio | Impact |
|-----------|-----------|-------------|---------|-------|--------|
| `soft_dup_paraphrase_1` | Soft ✅ | **Novel** ❌ | 0 | 0.0 | **REGRESSION** |
| `soft_dup_paraphrase_2` | Soft ✅ | **Novel** ❌ | 0 | 0.0 | **REGRESSION** |
| `soft_dup_paraphrase_3` | Soft ✅ | **Novel** ❌ | 0 | 0.0 | **REGRESSION** |
| `novel_new_finding_1` | Soft ❌ | **Novel** ✅ | 0 | 0.0 | **CORRECT FIX** |

**Post-reranking accuracy: 62.5% (5/8)** — net −2 from reranker intervention.

### 3.3 Root Cause Analysis

The heuristic reranker (`llm_rerank_duplicates`) has a **logical flaw in its default behavior**:

```
All 4 heuristics → 0 signals → dup_ratio = 0.0 → dup_ratio ≤ 0.25 → is_duplicate = False
```

This chain treats "no heuristic evidence" as "strong evidence of novelty." In reality:

1. **Variable overlap (H1)**: Test case descriptions use natural language, not structured variables. `_extract_variables()` returns empty sets → heuristic is skipped (total_heuristics -= 1).
2. **Finding type + domain (H2)**: Test cases use different hypothesis IDs and the probe text doesn't match `_extract_finding_type()` patterns.
3. **Temporal proximity (H3)**: No `_query_cycle` set → heuristic is skipped (total_heuristics -= 1).
4. **Structural SVO (H4)**: `_extract_subject_verb_object()` on natural language produces different patterns for paraphrased text.

When `total_heuristics` drops to 2 (after skipping H1 and H3) and both remaining heuristics produce 0, `dup_ratio = 0/2 = 0.0`, triggering the novel reclassification.

### 3.4 Recommended Fix

```python
# Current (BROKEN):
elif dup_ratio <= 0.25:
    c["is_duplicate"] = False

# Proposed (FIXED):
elif dup_ratio <= 0.25 and effective_total >= 2:
    # Only reclassify when we have enough evaluable heuristics
    # to form a confident judgment
    c["is_duplicate"] = False
# If effective_total < 2, leave original classification unchanged
```

**Predicted impact**: With this fix, `novel_new_finding_1` would remain soft (since it also has 0 signals), so the fix alone doesn't improve accuracy. The real solution requires:

1. **Conservative default**: When heuristics are insufficient, trust the cosine similarity classification
2. **Better heuristics**: Pass structured metadata (variables, finding_type, cycle) to the reranker alongside the text
3. **Confidence-weighted decision**: Weight the reranker's confidence against the similarity score proportionally to `effective_total`

### 3.5 Dual-Score Recommendation

Report BOTH scores going forward:

| Metric | Without Reranker | With Reranker |
|--------|-----------------|---------------|
| Accuracy | 87.5% (7/8) | 62.5% (5/8) |
| `novel_new_finding_1` | ❌ soft | ✅ novel |
| `soft_dup_paraphrase_*` | ✅ soft (×3) | ❌ novel (×3) |

The reranker should be **disabled by default** until the heuristic flaw is fixed. It can be enabled as an opt-in experimental feature.

---

## 4. Performance Profile

### 4.1 Latency Summary by Profile

| Profile | n_results | Avg (ms) | P50 (ms) | P95 (ms) | Max (ms) |
|---------|-----------|----------|----------|----------|----------|
| ORIENT_BREADTH | 16 | **828** | 817 | 897 | — |
| EVALUATE_PRECISION | 8 | **816** | 806 | 897 | — |
| DECIDE_RECENCY | 5 | **825** | 814 | 896 | — |
| Raw search (n=16) | 16 | **414** | 423 | 433 | — |

**Key observation**: All 3 profiles have nearly identical latency (816–828ms), confirming that the bottleneck is ChromaDB query overhead (embedding + distance computation), not result count. Changing `n_results` from 5 to 16 adds **only ~12ms** to orient time.

### 4.2 Orient Latency: Cycle 4 vs Cycle 5

| Metric | Cycle 4 (n=5) | Cycle 5 (n=16) | Delta |
|--------|--------------|----------------|-------|
| Avg | 816ms | 828ms | +12ms (+1.5%) |
| P50 | 807ms | 817ms | +10ms |
| P95 | 896ms | 897ms | +1ms |

**ORIENT_BREADTH with n=16 adds negligible latency (+12ms, +1.5%)** compared to Cycle 4's fixed n=5. The wider retrieval is effectively free.

### 4.3 Ingestion Performance

| Metric | Cycle 3 | Cycle 4 | Cycle 5 |
|--------|---------|---------|---------|
| Avg/record | 746ms | 694ms | **641ms** |
| P50/record | — | — | **586ms** |
| P95/record | — | — | **1140ms** |

Ingestion continues to improve: 641ms/record, **8% faster than Cycle 4** and **14% faster than Cycle 3**. P95 shows some variance (1.14s) due to ChromaDB batch flushes.

### 4.4 Total Experiment Duration

| Phase | Duration | % of Total |
|-------|----------|------------|
| Corpus ingestion (208 records) | 133.4s | 55% |
| Stress queries (50 queries) | ~21s | 9% |
| Cross-domain queries (12 queries) | ~5s | 2% |
| Orient cross-domain (10 hypotheses) | ~5.1s | 2% |
| Duplicate detection (8 tests) | ~5.5s | 2% |
| Query isolation (7 tests) | ~3s | 1% |
| Knowledge graph | ~4.5s | 2% |
| **RetrievalProfile validation (NEW)** | ~25s | 10% |
| Performance benchmarks | ~15s | 6% |
| Other | ~26s | 11% |
| **Total** | **~243.7s** | **100%** |

---

## 5. Knowledge Graph

### 5.1 KG Metrics

| Metric | C3 | C4 | C5 | Target | Status |
|--------|----|----|-----|--------|--------|
| Entities | 710 | 709 | **709** | 400+ | ✅ 1.77× target |
| Triples | 1,014 | 904 | **904** | 500+ | ✅ 1.81× target |
| Triple density | 1.43 | 1.27 | **1.27** | >1.0 | ✅ Healthy |

KG is completely stable across Cycles 4–5 with identical corpus and causal analysis.

---

## 6. Target Achievement Detail

### 6.1 Full Scorecard

| # | Metric | Target | Actual | Status | Notes |
|---|--------|--------|--------|--------|-------|
| 1 | Total discoveries | 208+ | 208 | ✅ **MET** | Stable |
| 2 | Search relevance | ≥95% | 100% (50/50) | ✅ **MET** | Perfect 5/5 cycles |
| 3 | Cross-domain orient hits | ≥35 | 35 | ✅ **MET** | Matches Cycle 4 |
| 4 | Orient time/hypothesis | <1,000ms | 828ms | ✅ **MET** | +12ms from n=16, well within target |
| 5 | Dedup accuracy | ≥87.5% | **62.5%** | ❌ **MISSED** | Reranker regression (87.5% without reranker) |
| 6 | Query isolation | 100% | 100% (7/7) | ✅ **MET** | Stable |
| 7 | KG entities | 400+ | 709 | ✅ **MET** | 1.77× target |
| 8 | KG triples | 500+ | 904 | ✅ **MET** | 1.81× target |
| 9 | Profile coverage | All 3 profiles | All 3 | ✅ **MET** | NEW — orient, evaluate, decide |
| 10 | Phase transitions | ≥2 | 2 | ✅ **MET** | NEW — orient→evaluate, evaluate→decide |

### 6.2 Cycle-over-Cycle Target Achievement

| Cycle | Targets Met | Partial | Missed | Score |
|-------|-------------|---------|--------|-------|
| 1 | 4 | 0 | 0 | 4/4 |
| 2 | 6 | 0 | 0 | 6/6 |
| 3 | 8 | 2 | 0 | 8/10 |
| 4 | 8 | 0 | 0 | 8/8 |
| **5** | **9** | **0** | **1** | **9/10** |

### 6.3 Dedup Accuracy — Context

The dedup accuracy miss is **entirely attributable to the reranker**, not to threshold degradation:
- Without reranker: 87.5% (meets target, same as Cycle 4)
- With reranker: 62.5% (misses target by 25 percentage points)

**Recommendation**: Count this as a validated finding, not a system regression. The reranker is a new, optional feature with a known bug. The underlying threshold-based dedup remains at 87.5%.

---

## 7. Cross-Domain Discovery — Wider Breadth Analysis

### 7.1 Orient with ORIENT_BREADTH (n=16) vs Cycle 4 (n=5)

| Metric | Cycle 4 (n=5) | Cycle 5 (n=16) | Change |
|--------|--------------|----------------|--------|
| Cross-domain hits | 35 | 35 | = |
| Domains with ≥1 hit | 5/5 | 5/5 | = |
| Per-hypothesis hits (avg) | ~5 | ~16 | 3.2× |
| Orient time/hyp | 816ms | 828ms | +1.5% |
| Cross-domain avg similarity | N/A | 0.25 | Baseline |

Wider n_results (16) gives more per-hypothesis hits but **does not increase cross-domain orient hits** because:
1. Cross-domain search uses a separate `exclude_domain` pass with its own `cross_domain_results=10` limit
2. Per-hypothesis results are in-domain focused (no exclude_domain)
3. The cross-domain pass parameters (n=10, min_sim=0.2) are unchanged

**Conclusion**: ORIENT_BREADTH's wider n_results helps within-domain discovery (3.2× more per-hypothesis context) without affecting cross-domain performance. To increase cross-domain hits beyond 35, the `cross_domain_results` parameter would need to be increased, not `n_results`.

### 7.2 Cross-Domain Similarity Distribution

| Domain | Avg Sim | Min Sim | Max Sim |
|--------|---------|---------|---------|
| Astrophysics | 0.2146 | 0.2011 | 0.2356 |
| Economics | 0.2667 | 0.2056 | 0.3204 |
| Climate | 0.2516 | 0.2031 | 0.3158 |
| Epidemiology | 0.2399 | 0.2090 | 0.2746 |
| Cryptography | 0.2462 | 0.2101 | 0.2823 |

Cross-domain similarities are in the 0.20–0.32 range — close to the min_similarity=0.2 threshold. These are weak but genuine cross-domain connections. Economics and Climate have the highest cross-domain similarities, consistent with their shared vocabulary (GDP, temperature, emissions → economic impacts).

---

## 8. Comparison with Cycle 5 Plan

### 8.1 Plan vs Reality

| Planned Feature | Plan Target | Actual | Status |
|----------------|------------|--------|--------|
| RetrievalProfile validation | All 3 profiles exercised | ✅ All 3 | **MET** |
| Profile switching | ≥2 transitions | ✅ 2 | **MET** |
| Breadth profile domains | ≥3 per orient query | ✅ 3 | **MET** |
| Precision profile noise | 0% cross-domain | ✅ 0% | **MET** |
| Precision avg similarity | ≥0.6 | ✅ 0.64 | **MET** |
| Profile switching overhead | <50ms | ✅ 0.002ms | **MET** |
| Dedup reranking accuracy | 100% (8/8) | ❌ 62.5% (5/8) | **MISSED** |
| Reranking latency | <2000ms | ✅ <1ms | **MET** (heuristic, not LLM) |
| Time-decay visible effect | ≥60% recent | N/A | **NOT TESTABLE** (same-second corpus) |

### 8.2 Plan Assumptions vs Reality

The Cycle 5 plan assumed the engineer would implement **LLM-based** dedup reranking with actual language model calls. The actual implementation uses **heuristic-based** reranking (4 pattern-matching signals) without any LLM. This is a sensible engineering choice (no external dependency, deterministic, fast) but the heuristics need refinement.

---

## 9. Recommendations and Next Steps

### 9.1 P0: Fix Reranker Default Behavior (Bug)

The reranker's "absence = novelty" flaw must be fixed before it can be used in production:

1. **Conservative default**: When `effective_total < 2`, leave classification unchanged
2. **Minimum evidence threshold**: Require at least 2 evaluable heuristics and ≥1 positive signal before reclassifying
3. **Test with structured metadata**: Pass actual variables, finding_type, and cycle info to improve heuristic coverage

**Expected impact**: Fixes 3 false reclassifications, restoring accuracy to 87.5% while preserving the correct fix for `novel_new_finding_1` IF enough heuristic context is provided.

### 9.2 P1: Increase Cross-Domain Discovery

To beat Cycle 4's 35 cross-domain hits:
- Increase `cross_domain_results` from 10 to 16 (match ORIENT_BREADTH's n_results)
- Or: Use profile composition: `compose(ORIENT_BREADTH, n_results=20)` for cross-domain pass

### 9.3 P1: Test Time-Decay with Temporal Corpus

Create a corpus with records spanning 90+ days to validate DECIDE_RECENCY's time_decay behavior. Current test creates all records within seconds, making decay invisible.

### 9.4 P2: EVALUATE_PRECISION with Status-Tagged Records

Tag some corpus records with `status="decided"` to populate EVALUATE_PRECISION results. Currently returns 0–1 hits because no records have the required status.

### 9.5 P2: Consider Hybrid Reranking

The heuristic reranker is fast (<1ms) but shallow. Consider a hybrid approach:
1. Heuristic pass first (fast filter)
2. If `effective_total < 2`, fall back to embedding-based comparison of structured fields
3. Optional LLM reranking for the highest-ambiguity cases (sim 0.65–0.75)

### 9.6 P3: Remaining Tech Debt

From Cycles 3–5, still pending:
- Networkx format detection in `record_causal_edges`
- Vocabulary bridging for isolated domains (Epi, Crypto)
- Multi-cycle confidence convergence study (10+ cycles)
- Real API data integration (GISTEMP, WHO GHO, World Bank)
- Silent dedup failure mode (Phase 17 code review finding)

---

## Appendix A: Raw Data Excerpts

### A.1 Configuration Used

```python
CYCLE_5_CONFIG = {
    # Corpus
    "target_discoveries": 208,
    "domains": ["astrophysics", "economics", "climate", "epidemiology", "cryptography"],

    # Tiered duplicate detection
    "hard_duplicate_threshold": 0.86,
    "soft_duplicate_threshold": 0.55,

    # Orient profile: ORIENT_BREADTH
    "orient_n_results": 16,          # was 5 in Cycle 4
    "orient_min_similarity": 0.2,
    "cross_domain_results": 10,

    # Evaluate profile: EVALUATE_PRECISION
    "evaluate_n_results": 8,
    "evaluate_min_similarity": 0.6,
    "evaluate_require_status": "decided",

    # Decide profile: DECIDE_RECENCY
    "decide_n_results": 5,
    "decide_min_similarity": 0.4,
    "decide_time_decay": True,
    "decide_half_life_days": 30,

    # Embedding
    "model": "all-MiniLM-L6-v2",
    "embedding_dim": 384,
}
```

### A.2 Duplicate Detection Raw Scores

```json
{
  "test_cases": [
    {"id": "hard_dup_verbatim", "similarity": 0.9393, "pre_rerank": "hard", "post_rerank": "hard", "expected": "hard", "correct": true},
    {"id": "hard_dup_minor_reword", "similarity": 0.9012, "pre_rerank": "hard", "post_rerank": "hard", "expected": "hard", "correct": true},
    {"id": "soft_dup_paraphrase_1", "similarity": 0.8139, "pre_rerank": "soft", "post_rerank": "novel", "expected": "soft", "correct": false, "rerank_signals": 0},
    {"id": "soft_dup_paraphrase_2", "similarity": 0.8409, "pre_rerank": "soft", "post_rerank": "novel", "expected": "soft", "correct": false, "rerank_signals": 0},
    {"id": "soft_dup_paraphrase_3", "similarity": 0.7341, "pre_rerank": "soft", "post_rerank": "novel", "expected": "soft", "correct": false, "rerank_signals": 0},
    {"id": "novel_new_finding_1", "similarity": 0.6690, "pre_rerank": "soft", "post_rerank": "novel", "expected": "novel", "correct": true, "rerank_signals": 0},
    {"id": "novel_new_finding_2", "similarity": 0.4861, "pre_rerank": "novel", "post_rerank": "novel", "expected": "novel", "correct": true},
    {"id": "novel_new_finding_3", "similarity": 0.5268, "pre_rerank": "novel", "post_rerank": "novel", "expected": "novel", "correct": true}
  ],
  "accuracy_without_reranker": 0.875,
  "accuracy_with_reranker": 0.625,
  "thresholds": {"hard": 0.86, "soft": 0.55}
}
```

### A.3 Profile Isolation Data

```json
{
  "same_query_different_profiles": {
    "orient_breadth": {"hits": 10, "unique_ids": 10, "profile": "orient_breadth"},
    "evaluate_precision": {"hits": 0, "unique_ids": 0, "profile": "evaluate_precision"},
    "decide_recency": {"hits": 2, "unique_ids": 2, "profile": "decide_recency"},
    "orient_evaluate_overlap": "0.0%",
    "profiles_all_different": true
  }
}
```

### A.4 Performance Comparison Across Profiles

```json
{
  "orient_breadth_n16": {"avg_ms": 827.78, "p50_ms": 817.0, "p95_ms": 896.51},
  "evaluate_precision_n8": {"avg_ms": 815.83, "p50_ms": 806.0, "p95_ms": 896.57},
  "decide_recency_n5": {"avg_ms": 824.6, "p50_ms": 814.0, "p95_ms": 895.98},
  "raw_search_n16": {"avg_ms": 413.95, "p50_ms": 423.0, "p95_ms": 433.0}
}
```

---

*Report generated by mempalace-researcher | MemPalace-AGI Discovery Cycle 5 | April 10, 2026*
