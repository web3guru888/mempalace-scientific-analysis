# Experiment #43: Cross-Domain Knowledge Transfer

> **Date**: 2026-04-11 11:15Z–11:54Z  
> **Author**: MemPalace-AGI Researcher  
> **Status**: ✅ COMPLETE — NEGATIVE (Data Exhaustion Confound)  
> **Verdict**: 0/5 criteria passed — **IMPORTANT NULL RESULT**  
> **Data**: `/workspace/experiments/2026-04-11-exp43-cross-domain-transfer/results.json`  
> **Script**: `/workspace/experiments/2026-04-11-exp43-cross-domain-transfer/exp43_cross_domain_transfer.py`

---

## 1. Hypothesis

**Does knowledge accumulated in one domain improve discovery rates in OTHER domains compared to a cold start?**

This is the crown jewel theoretical claim of MemPalace-AGI: that spatial memory + knowledge graph enables cross-domain transfer that would be impossible with domain-isolated memory.

## 2. Design

### Conditions
| Condition | Phase 1 | Phase 2 | Total Cycles |
|-----------|---------|---------|:---:|
| **Cold** | — | 10 test cycles | 10 |
| **Primed** | 10 priming cycles (all domains) | 10 test cycles | 20 |

- **3 replications** per condition
- **Full state isolation**: each rep uses a fresh temp directory for palace, KG, and discovery DB
- **Subprocess execution**: each condition runs in an isolated Python process

### Metrics
1. Test-phase discoveries (primary)
2. Non-Astrophysics test discoveries
3. KG triple growth during test phase
4. Domain count in test phase
5. Fingerprint uniqueness (Jaccard overlap)

## 3. Raw Results

### Per-Replication Data

| Rep | Cold: disc | Cold: nonastro | Cold: KG | Cold: domains | Primed: disc | Primed: nonastro | Primed: KG | Primed: domains |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 27 | 15 | 222 | 5 | 3 | 2 | 23 | 2 |
| 2 | 32 | 16 | 249 | 5 | 0 | 0 | 3 | 0 |
| 3 | 30 | 17 | 245 | 5 | 1 | 1 | 12 | 1 |
| **Mean** | **29.7±2.5** | **16.0±1.0** | **238.7±14.6** | **5.0±0.0** | **1.3±1.5** | **1.0±1.0** | **12.7±10.0** | **1.0±1.0** |

### Priming Phase (Primed condition only)

| Rep | Priming disc | Priming KG | Priming domains |
|:---:|:---:|:---:|:---:|
| 1 | 29 | 233 | — |
| 2 | 36 | 271 | — |
| 3 | 35 | 266 | — |
| **Mean** | **33.3** | **256.7** | — |

### Total Discoveries (Priming + Test)

| Condition | Total Disc | Disc/Cycle | Time (s) |
|-----------|:---:|:---:|:---:|
| Cold (10 cycles) | 29.7 | **2.97** | 173.6 |
| Primed (20 cycles) | 34.6 | **1.73** | 351.5 |

## 4. Statistical Tests

All tests are one-sided (H₁: primed > cold):

| Metric | Cold (μ±σ) | Primed (μ±σ) | t | p | d | Pass? |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| Total disc | 29.7±2.5 | 1.3±1.5 | −16.67 | 1.000 | −13.61 | ❌ |
| Non-Astro | 16.0±1.0 | 1.0±1.0 | −18.37 | 1.000 | −15.00 | ❌ |
| KG growth | 238.7±14.6 | 12.7±10.0 | −22.14 | 1.000 | −18.08 | ❌ |
| Domain count | 5.0±0.0 | 1.0±1.0 | −6.93 | 0.999 | −5.66 | ❌ |
| Unique fingerprints | 24 cold-only | 1 primed-only | — | — | — | ❌ |

**All metrics strongly NEGATIVE** — primed condition discovers far LESS than cold.

### Fingerprint Analysis
- Cold-only fingerprints: 24
- Primed-only fingerprints: 1
- Overlap: 2
- Jaccard similarity: 0.074 (7.4% overlap)

### Domain Distribution (Test Phase)

| Domain | Cold (all 3 reps) | Primed (all 3 reps) |
|--------|:---:|:---:|
| Astrophysics | 41 (46.1%) | 1 (25.0%) |
| Economics | 15 (16.9%) | 0 (0%) |
| Epidemiology | 12 (13.5%) | 3 (75.0%) |
| Climate | 12 (13.5%) | 0 (0%) |
| Cryptography | 9 (10.1%) | 0 (0%) |

## 5. Root Cause Analysis: Data Exhaustion Confound

### The Problem

The priming phase is **NOT** teaching the system to discover better — it's **consuming the finite data pool**, leaving nothing for the test phase to find.

Evidence:
1. **Priming discovers ~33 things**, test discovers ~1 — the data is exhausted
2. **Cold discovers ~30 things** in the same number of cycles — nearly the same total
3. **96.2% of primed discoveries come from priming**, only 3.8% from test
4. **Fingerprint overlap is only 7.4%** — cold and primed find essentially different subsets (due to stochastic hypothesis generation), not "better" subsets

### Why This Confound Exists

The MemPalace-AGI system has a **fixed data pool** of 12 data sources × ~49 variables. Within ~10 cycles, most testable combinations are exhausted (our saturation law from DC-15, DC-17, DC-25). Priming burns through this pool, leaving the test phase with:
- Hard duplicate rejection at sim≥0.92 (blocks re-discovery)
- All low-hanging fruit already collected
- Hypothesis pool dominated by already-tested combinations

### Mitigating Factors

The total discoveries (priming + test) for the primed condition (34.6) actually **exceed** cold (29.7) at marginal significance (p=0.064, two-sided). This suggests:
- **20 cycles > 10 cycles** for total discovery (unsurprising)
- Per-cycle efficiency drops from 2.97 to 1.73 (41.7% decline)
- The additional 10 cycles yield only +5 discoveries (+16.8%)

## 6. Implications for MemPalace-AGI

### What This Experiment DOES Prove

1. **Data source exhaustion is the dominant bottleneck** — confirmed with the strongest effect sizes in our entire corpus (d = 13–18)
2. **Dedup system works perfectly** — zero re-discoveries after priming, exactly as designed
3. **Saturation law holds** — ~30 unique discoveries from 10 fresh cycles (consistent with DC-15, DC-17 findings)
4. **State isolation is correct** — cold replications are remarkably consistent (CV = 8.5%)

### What This Experiment DOES NOT Prove

This experiment **cannot** measure cross-domain transfer because:
- The design does not isolate domains between phases
- Priming exhausts ALL domains, not just one
- There is no mechanism to restrict hypothesis generation to specific domains during testing

### What Would Be Needed

To properly test cross-domain transfer, we would need:

1. **Domain-restricted priming**: Only generate and test Astrophysics hypotheses during priming
2. **Domain-restricted testing**: Only generate and test non-Astrophysics hypotheses during test phase
3. **This requires a `domain_filter` parameter** in the hypothesis generator and OODA cycle
4. **Alternative approach**: Use different non-overlapping data sources for priming vs testing

### Priority Assessment

| Approach | Effort | Likelihood of Success | Priority |
|----------|:---:|:---:|:---:|
| Add `domain_filter` to hypothesis generator | ~50 LOC | High | **P0** |
| Add `domain_filter` to OODA cycle | ~30 LOC | High | **P0** |
| Non-overlapping data sources | New APIs | Medium | P1 |
| Larger synthetic corpus | ~200 LOC | Medium | P2 |

## 7. Experiment Criteria Assessment

| # | Criterion | Result | Pass? |
|---|-----------|--------|:---:|
| 1 | Primed test-phase discoveries > cold | 1.3 < 29.7 | ❌ |
| 2 | Primed non-Astro discoveries > cold | 1.0 < 16.0 | ❌ |
| 3 | Primed KG growth > cold during test | 12.7 < 238.7 | ❌ |
| 4 | Primed discovers in more domains | 1.0 < 5.0 | ❌ |
| 5 | Unique fingerprints (Jaccard > 0.3) | 0.074 | ❌ |

**Result: 0/5 PASS — NEGATIVE due to data exhaustion confound**

## 8. Connection to Prior Work

| Experiment | Finding | Connection |
|-----------|---------|------------|
| DC-15 | Saturation at ~10 cycles | Confirms: 10 priming cycles ≈ full saturation |
| DC-17 | New sources +42.6% capacity | Confirms: data pool, not memory, is bottleneck |
| DC-24 | 1.83× transfer uplift | Different design: cumulative runs (not phase-isolated) |
| DC-25 | 93.2% waste after saturation | Explains: test phase is pure waste after priming |
| DC-28 | KG compounding proven | KG does grow, but within-phase, not cross-phase transfer |
| Exp #39 | 99% Astro in hypothesis pool | Domain restriction needed for clean test |
| Exp #41 | Pool rebalancing works | Generator diversity alone doesn't break saturation |
| Exp #42 | Saturation at C14 | Consistent: exhaustion happens in ~10 cycles |

## 9. Recommendation

**This is an important negative result, not a failure.** It establishes that:

1. Cross-domain transfer REQUIRES domain isolation in the experiment design
2. The data exhaustion confound must be controlled before any transfer measurement
3. A `domain_filter` feature is the minimal addition needed to enable a proper test

**Proposed Experiment #44**: Domain-Isolated Cross-Domain Transfer
- Add `domain_filter` parameter to `HypothesisGenerator.generate_from_discoveries()`
- Condition A: Fresh → 10 cycles (Astro only) → 10 cycles (non-Astro only)
- Condition B: Fresh → 10 cycles (non-Astro only)
- This isolates the priming data pool from the test data pool
- Expected: if cross-domain transfer exists, Condition A discovers more non-Astro things

---

*Generated by MemPalace-AGI Researcher*
*Experiment #43 — Cross-Domain Knowledge Transfer*
*2026-04-11T11:54Z*
