# Experiment #45: Analogy-to-Hypothesis Bridge A/B Test

**Date**: 2026-04-11T18:00Z  
**Status**: COMPLETE — 3/5 hypotheses PASS  
**Overall Verdict**: PARTIAL PASS — Bridge mechanism WORKS (p < 0.001) but downstream impact limited by data saturation  
**Experiment Duration**: ~60 minutes (6 replicates × ~10 min each)

## Executive Summary

The analogy-to-hypothesis bridge injects **34 ± 2 transfer hypotheses per run** (d = 24.0, p = 4×10⁻⁶), generates **201K+ structural analogies**, and produces **+24 KG triples** and **+12 KG entities** compared to the control. However, the injected hypotheses do not translate into additional *discoveries* or increased domain diversity within 20 cycles, because:

1. **Data saturation**: All 466 discoveries appear in cycle 1 and never grow — the existing data sources are fully explored before the bridge even activates (cycle 5+).
2. **Hypothesis → Discovery gap**: The 34 AT hypotheses are added to the hypothesis store but the OODA select/investigate/evaluate phases rarely pick them (they compete against ~466+ existing high-confidence hypotheses).
3. **Deterministic data**: Both arms see identical data sources, producing identical discovery sets (Jaccard overlap = 1.0).

**Key Result**: The bridge is a correctly functioning *hypothesis generation* mechanism that needs either (a) richer data sources or (b) preferential AT-hypothesis selection to produce measurable *discovery* differences.

## Experimental Design

### Conditions
| Condition | Description | Bridge Status |
|-----------|-------------|---------------|
| **Control (A)** | 20 OODA cycles via `engine.run_cycle()` | **OFF** — NullAnalogyEngine + _analogies cleared |
| **Bridge (B)** | 20 OODA cycles via `run_augmented_cycle()` | **ON** — Full analogy bridge pipeline |

### Isolation Protocol
- **CWD isolation**: Each subprocess runs from a unique temp directory, preventing ASTRA's relative-path DB files (astra_discoveries.db, astra_knowledge.db, astra_metacognition.db, astra_agent_expertise.db, astra_state/) from leaking between runs.
- **Palace isolation**: Unique palace directory and KG DB path per replicate via IntegrationConfig.
- **Process isolation**: Each replicate runs as a subprocess (no shared memory state).
- **Sequential execution**: All replicates run sequentially to avoid resource contention.

### Parameters
- **Cycles per run**: 20
- **Replicates per condition**: 3 (total: 6 runs)
- **Timeout**: 40 minutes per replicate
- **Bridge config**: `max_new=2`, `similarity_threshold=0.70`

## Results

### Primary Metric: Analogy-Transfer Hypothesis Injection

| Metric | Control (mean ± SD) | Bridge (mean ± SD) | t-test p | U-test p | Cohen's d | Verdict |
|--------|-------------------|-------------------|----------|----------|-----------|---------|
| **AT hyps injected** | **0.0 ± 0.0** | **34.0 ± 2.0** | **4×10⁻⁶** | **0.032** | **24.0** | ✅ **PASS** |
| AT discoveries | 0.0 ± 0.0 | 0.0 ± 0.0 | N/A | 1.0 | 0.0 | ❌ FAIL |

The bridge injects exactly **2 AT hypotheses per cycle** from cycle 5 onward (32-36 total across 20 cycles). The injected hypotheses span **47 unique transfer directions** across all 3 bridge replicates, covering all 5 domains plus Cross-Domain:

**Example AT hypotheses injected:**
- Analogy Transfer: Astrophysics bimodal → Economics  
- Analogy Transfer: Epidemiology periodic → Climate  
- Analogy Transfer: Cryptography bimodal → Astrophysics  
- Analogy Transfer: Climate unknown → Cross-Domain  
- Analogy Transfer: Economics periodic → Cryptography  

### Secondary Metrics

| Metric | Control (mean ± SD) | Bridge (mean ± SD) | t-test p | Cohen's d | Verdict |
|--------|-------------------|-------------------|----------|-----------|---------|
| Total discoveries | 466.0 ± 0.0 | 466.0 ± 0.0 | N/A | 0.0 | Tied |
| Palace drawers | 466.0 ± 0.0 | 466.0 ± 0.0 | N/A | 0.0 | Tied |
| Shannon entropy | 2.284 ± 0.0 | 2.284 ± 0.0 | N/A | 0.0 | Tied |
| Non-Astro discoveries | 345.0 ± 0.0 | 345.0 ± 0.0 | N/A | 0.0 | Tied |
| Domains | 5.0 ± 0.0 | 5.0 ± 0.0 | N/A | 0.0 | Tied |
| **KG triples** | **2503.7 ± 2.5** | **2527.7 ± 2.5** | **3.1×10⁻⁴** | **9.5** | ✅ |
| **KG entities** | **589.0 ± 1.0** | **601.3 ± 1.2** | **1.5×10⁻⁴** | **11.4** | ✅ |
| **Total analogies** | **0.0 ± 0.0** | **201,626 ± 6,491** | **~0** | **43.9** | ✅ |
| **Novel analogies** | **0.0 ± 0.0** | **122,741 ± 4,547** | **1×10⁻⁶** | **38.2** | ✅ |

### Hypothesis Verdicts

| ID | Hypothesis | Verdict | Evidence |
|----|-----------|---------|----------|
| **H1** | Bridge injects AT hypotheses (> 0) | ✅ **PASS** | 34.0 ± 2.0 vs 0, p = 4×10⁻⁶, d = 24.0 |
| **H2** | Higher domain diversity (entropy) | ❌ **FAIL** | Identical: 2.284 vs 2.284 |
| **H3** | Cross-domain discoveries produced | ❌ **FAIL** | 0 AT discoveries in both arms |
| **H4** | Comparable/higher total discoveries | ✅ **PASS** | Identical: 466 vs 466, ratio = 1.0 |
| **H5** | Higher KG triples | ✅ **PASS** | +24.0 triples, p = 3.1×10⁻⁴, d = 9.5 |

**Score: 3/5 PASS**

### Domain Distribution (Identical Across Arms)

| Domain | Count per Run | Percentage |
|--------|--------------|------------|
| Astrophysics | 121 | 26.0% |
| Climate | 105 | 22.5% |
| Epidemiology | 103 | 22.1% |
| Cryptography | 69 | 14.8% |
| Economics | 68 | 14.6% |

**Note**: The pool rebalancing fix (Exp #41) is working — Astrophysics is no longer 99% of the pool.

### Bridge Activation Timeline (Representative Run)

```
Cycle  Discoveries  KG Triples  AT Injected  AT Cumulative  Analogies
  C1      466         2,457        0              0              0
  C2      466         2,463        0              0              0
  C3      466         2,468        0              0              0
  C4      466         2,477        0              0              0
  C5      466         2,481        2              2         23,660  ← Theory tick #1 completes
  C6      466         2,485        2              4         23,660
  C7      466         2,490        2              6         23,660
  C8      466         2,493        2              8         23,660
  C9      466         2,496        2             10         23,660
 C10      466         2,500        2             12         64,205  ← Theory tick #2 completes
 C11      466         2,503        2             14         64,205
  ...     ...         ...         ...           ...           ...
 C15      466         2,512        2             22        124,605  ← Theory tick #3
 C20      466         2,528        2             32        203,773  ← Theory tick #4
```

**Key observations:**
- Theory engine ticks complete every ~5 cycles, accumulating analogies in batches
- Analogies grow from 23K → 64K → 125K → 204K (each tick processes ~40-80K new analogies)
- Bridge consistently injects 2 AT hypotheses per cycle (max_new=2 setting)
- Discoveries are fully saturated at C1 — all 466 discoveries are found in the first cycle

### Fingerprint Analysis

- **Control unique fingerprints**: 0
- **Bridge unique fingerprints**: 0
- **Overlap**: 38 (Jaccard = 1.0)

The discovery sets are **completely identical** across both arms. This confirms that the bridge does not yet produce differential *discoveries* — only differential *hypotheses*.

## Analysis: Why AT Hypotheses Don't Become Discoveries

The experiment reveals a **hypothesis-to-discovery conversion bottleneck**:

### 1. Data Saturation (Primary Cause)
All 466 discoveries are generated from the 9 real data sources in cycle 1. The OODA cycle finds everything that can be found statistically from the available data immediately. Adding 34 more hypotheses doesn't help because:
- The data sources have already been exhaustively analyzed
- AT hypotheses propose testing patterns from domain_a in domain_b, but the same data points have already been tested

### 2. Selection Competition
The AT hypotheses compete with ~466 existing validated hypotheses. The OODA select phase picks hypotheses based on confidence and information value — AT hypotheses start with low confidence (similarity × 0.4 ≈ 0.29) and may never get selected.

### 3. Investigation Overlap  
Even when an AT hypothesis IS investigated, it likely produces findings already captured by the standard analysis pipeline. For example, "Analogy Transfer: Astrophysics bimodal → Economics" proposes testing bimodal distributions in economic data — but bimodal analysis is already in the standard hypothesis set.

## KG Enrichment Effect

Despite zero AT discoveries, the bridge arm produces:
- **+24 KG triples** (2,528 vs 2,504) — 0.96% increase
- **+12.3 KG entities** (601 vs 589) — 2.1% increase

This comes from the AT hypotheses themselves being processed through the KG extraction pipeline during the evaluate phase. Even hypotheses that don't become discoveries can enrich the knowledge graph with entity relationships.

**Statistical significance**: t-test p = 3.1×10⁻⁴ for triples, p = 1.5×10⁻⁴ for entities. The effect is real but small.

## Comparison with Previous Experiments

| Experiment | Cross-Domain Signal | Root Cause of Failure |
|-----------|-------------------|---------------------|
| **#43** Cross-domain transfer | 0/5 metrics pass, d = -13.6 | Data exhaustion + no bridge |
| **#44** Domain-isolated transfer | 0/4 metrics pass, d = -3.47 | Domain leakage + no bridge |
| **#45** Bridge A/B test | **3/5 pass**, d = 24.0 (AT hyps) | Data saturation (bridge works!) |

**Progress**: Exp #45 proves the bridge *mechanism* works. The failure mode shifted from "no cross-domain hypothesis generation" (#43/#44) to "insufficient data diversity for AT hypothesis *investigation*."

## Recommendations

### Short-Term (Address Data Saturation)
1. **AT-priority selection**: Add a selection boost for `finding_type="analogy_transfer"` hypotheses so they are investigated preferentially
2. **Novel data sources**: Add time-series or multi-resolution data that isn't fully explored in cycle 1
3. **Longer runs**: Run 50-100 cycles to give AT hypotheses more chances to be selected

### Medium-Term (Improve Bridge Impact)
4. **AT-specific investigation methods**: Create investigation strategies tailored for analogy transfer (e.g., test the *specific* mathematical form from domain_a in domain_b data)
5. **Multi-hop transfer**: Chain analogies (A→B, B→C) for deeper transfer
6. **Confidence decay**: Decay confidence of stale hypotheses so AT hypotheses eventually outcompete them

### Long-Term (Systemic)  
7. **Real-time data**: Stream data sources so the system can discover new patterns as data arrives
8. **Active learning**: Let the bridge request specific data points needed to test AT hypotheses

## Technical Details

### Files
- **Experiment script**: `/workspace/experiments/2026-04-11-exp45-bridge-ab/experiment.py`
- **Worker script**: `/workspace/experiments/2026-04-11-exp45-bridge-ab/worker.py`
- **Results JSON**: `/workspace/experiments/2026-04-11-exp45-bridge-ab/results.json`
- **Run log**: `/workspace/experiments/2026-04-11-exp45-bridge-ab/run.log`
- **Bridge module**: `/shared/mempalace-agi/src/mempalace_agi/analogy_hypothesis_bridge.py`
- **Orchestrator**: `/shared/mempalace-agi/src/mempalace_agi/orchestrator.py`

### Software Versions
- Python 3.10
- ASTRA-dev (latest, pool rebalancing applied)
- MemPalace-AGI (KGBackend migrated, bridge wired)
- ChromaDB (VectorBackend abstraction)
- scipy/numpy for statistical tests

### Reproducibility Notes
- Discovery count (466) is deterministic across all 6 runs (zero variance)
- KG triples have minor variance (2,501-2,530) due to timing of KG extraction during evaluate
- AT hypothesis injection count varies slightly (32-36) due to theory engine tick timing
- CWD isolation eliminates the astra_knowledge.db leak from Exp #23
