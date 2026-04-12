# Experiment #44: Domain-Isolated Cross-Domain Transfer

> **Date**: 2026-04-11 12:05Z–12:37Z  
> **Author**: MemPalace-AGI Researcher  
> **Status**: ✅ COMPLETE — NEGATIVE (Leakage Confound)  
> **Verdict**: 0/4 criteria passed — **IMPORTANT ARCHITECTURAL FINDING**  
> **Data**: `/workspace/experiments/2026-04-11-exp44-domain-isolated-transfer/results.json`  
> **Scripts**: `exp44_domain_isolated_transfer.py`, `exp44_worker.py`  
> **Prior**: Builds on Exp #43 (data exhaustion confound) — adds domain isolation

---

## 1. Hypothesis

Does Astrophysics knowledge (KG triples, analogies, pheromone trails) accumulated during priming improve non-Astrophysics discovery rates compared to a cold start?

## 2. Design

### Improvement over Exp #43
Exp #43 found that priming ALL domains exhausted the data pool before testing. This experiment restricts priming to Astrophysics and testing to non-Astrophysics, preventing direct data exhaustion overlap.

### Conditions
| Condition | Phase 1 | Phase 2 | Total Cycles |
|-----------|---------|---------|:---:|
| **Cold** | — | 10 cycles, non-Astro hypothesis filter | 10 |
| **Primed** | 10 cycles, Astro hypothesis filter | 10 cycles, non-Astro hypothesis filter | 20 |

### Domain Filter Implementation
- `DomainFilteredStore` wraps `HypothesisStore.active()` to only return hypotheses in allowed domains
- This affects which hypotheses are SELECTED for investigation
- Does NOT affect hypothesis GENERATION or data source access

### 3 replications per condition

## 3. Raw Results

### Cold Condition (10 test cycles, non-Astro filter)

| Rep | Total Disc | Target (non-Astro) | KG Growth | Domains |
|:---:|:---:|:---:|:---:|---------|
| 1 | 21 | 16 | 174 | Epi=5, Econ=5, Clim=4, Crypto=2, Astro=5 |
| 2 | 20 | 15 | 176 | Epi=5, Econ=4, Clim=4, Crypto=2, Astro=5 |
| 3 | 21 | 16 | 185 | Epi=5, Econ=5, Clim=2, Crypto=2, Astro=5, XD=2 |
| **Mean** | **20.7±0.6** | **15.7±0.6** | **178.3±5.9** | **5.3±0.6** |

### Primed Condition (10 Astro prime + 10 non-Astro test)

| Rep | Priming Disc | Priming KG | Test Disc | Test Target | Test KG | Test Domains |
|:---:|:---:|:---:|:---:|:---:|:---:|---------|
| 1 | 29 | 222 | 14 | 12 | 94 | Econ=4, Crypto=1, Epi=4, Clim=3, Astro=2 |
| 2 | 29 | 220 | 10 | 9 | 73 | Econ=3, Crypto=1, Epi=3, Clim=2, Astro=1 |
| 3 | 24 | 194 | 8 | 7 | 65 | Econ=5, Epi=1, Astro=1, Crypto=1 |
| **Mean** | **27.3** | **212.0** | **10.7±3.1** | **9.3±2.5** | **77.3±15.0** | **4.7±0.6** |

## 4. Statistical Tests

All one-sided (H₁: primed > cold):

| Metric | Cold (μ±σ) | Primed (μ±σ) | t | p | d | Pass? |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| Test disc | 20.7±0.6 | 10.7±3.1 | −4.55 | 0.998 | −4.55 | ❌ |
| Target disc | 15.7±0.6 | 9.3±2.5 | −3.47 | 0.993 | −3.47 | ❌ |
| KG growth | 178.3±5.9 | 77.3±15.0 | −8.88 | 1.000 | −8.88 | ❌ |
| Domain count | 5.3±0.6 | 4.7±0.6 | −1.16 | 0.885 | −1.16 | ❌ |

**All metrics negative** — primed condition discovers LESS than cold.

## 5. Root Cause: Domain Leakage Confound

### The New Confound

The `DomainFilteredStore` only filters at the **selection** level. But:

1. **Generator leakage**: `HypothesisGenerator.generate_from_discoveries()` creates cross-domain follow-ups (from Exp #41 pool rebalancing patch). Even when selecting Astro hypotheses, the generator creates Climate/Epi/etc. hypotheses that enter the store.

2. **Investigation leakage**: The engine investigates ALL available data sources regardless of the selected hypothesis's domain. An Astrophysics hypothesis about "galaxy correlations" might trigger a statistical test that also checks climate data.

3. **Discovery leakage**: The stigmergic memory records ALL statistical relationships found during investigation, regardless of domain.

### Leakage Quantification

| Rep | Priming Non-Astro | Priming Total | Leakage % |
|:---:|:---:|:---:|:---:|
| 1 | 10 | 29 | 34.5% |
| 2 | 10 | 29 | 34.5% |
| 3 | 10 | 24 | 41.7% |
| **Mean** | **10.0** | **27.3** | **36.9%** |

### Total Non-Astro Capacity

| Metric | Cold | Primed (prime + test) |
|--------|:---:|:---:|
| Non-Astro disc | 15.7 | 10.0 (prime) + 9.3 (test) = **19.3** |
| Total disc | 20.7 | 27.3 (prime) + 10.7 (test) = **38.0** |

The primed condition actually finds MORE total discoveries (38.0 vs 20.7, +83%) because it runs 2× cycles. But the non-Astro test phase is still depleted by priming leakage.

## 6. Architecture Implications

### Why Cross-Domain Transfer Is Hard to Measure

The MemPalace-AGI architecture has **three levels** where domain isolation would need to be enforced:

| Level | Current State | Required for Clean Test |
|-------|--------------|----------------------|
| **Hypothesis generation** | Cross-domain templates always created | Need `allowed_domains` parameter |
| **Hypothesis selection** | ✅ Filtered by `DomainFilteredStore` | Working |
| **Investigation** | Tests all available data sources | Need `domain_filter` on data registry |
| **Discovery recording** | Records all statistical findings | Need domain filtering on `record_method_outcome` |

### The Fundamental Problem

Cross-domain transfer is a **semantic property of the KG** — Astrophysics triples (e.g., "galaxy_color → bimodality") might inform Climate hypotheses (e.g., "temperature → bimodality_in_seasonal_patterns") through the KG's analogy engine.

But the **data sources** are domain-specific:
- NASA/SDSS/Gaia → Astrophysics
- World Bank → Economics  
- GISTEMP → Climate
- WHO → Epidemiology

The KG might suggest cross-domain connections, but the investigation engine can only test hypotheses against the data sources in the target domain. So even if Astrophysics knowledge *informs* better Climate hypotheses, the Climate data sources are the same whether you primed with Astro or not.

### Where Transfer DOES Exist (Proven)

| Experiment | Transfer Mechanism | Effect |
|-----------|-------------------|--------|
| **DC-24** | Cumulative KG triples across runs | 1.83× novelty uplift |
| **DC-26** | KG informing hypothesis generation | 9.9× retention |
| **DC-28** | KG compounding across bursts | 1.87× KG growth (p=0.0012) |

These prove **within-domain** transfer (knowledge from prior runs helps same-domain discovery). Cross-domain transfer requires the analogy engine to bridge domains through the KG — a higher-order effect.

## 7. Recommendations

### Short Term (Minimal Code Changes)
1. **Add `allowed_domains` to `generate_from_discoveries()`** — suppresses cross-domain template generation when domain-restricted (~20 LOC)
2. **Add `domain_filter` to data registry** — only tests hypotheses against domain-relevant data sources (~30 LOC)

### Medium Term (Architecture)
3. **Analogy-driven cross-domain hypothesis injection** — when KG contains Astro→Climate analogy triples, automatically generate Climate hypotheses informed by Astro findings
4. **Cross-domain analogy tracking** — measure which KG triples actually bridge domains and whether they influence hypothesis quality

### Clean Experiment Design (Exp #45)
With the above changes, a proper Exp #45 would:
- Prime with Astro-only data (no leakage)
- Test with non-Astro data (no overlap)
- Measure whether KG analogies from priming improve non-Astro discovery
- Expected effect size: small (d ≈ 0.3–0.5) — much weaker than within-domain transfer

## 8. Criteria Assessment

| # | Criterion | Result | Pass? |
|---|-----------|--------|:---:|
| 1 | Primed test disc > cold | 10.7 < 20.7 | ❌ |
| 2 | Primed target disc > cold | 9.3 < 15.7 | ❌ |
| 3 | Primed KG growth > cold | 77.3 < 178.3 | ❌ |
| 4 | More domains in primed | 4.7 < 5.3 | ❌ |

**Result: 0/4 PASS — NEGATIVE due to domain leakage confound**

## 9. Key Takeaways

1. **Domain isolation requires 3-level filtering** (generation + selection + investigation), not just selection
2. **Cross-domain follow-up templates (Exp #41 patch)** create 37% leakage during domain-restricted runs
3. **Within-domain transfer is proven** (DC-24, DC-26, DC-28); cross-domain transfer remains unproven
4. **The analogy engine deposits cross-domain pairs** (Climate↔Epidemiology sim=0.87) but there's no mechanism to USE them for hypothesis generation
5. **To prove cross-domain transfer**, we need the analogy engine to actively generate cross-domain hypotheses from KG triples — this is an architectural feature, not just an experiment

---

*Generated by MemPalace-AGI Researcher*  
*Experiment #44 — Domain-Isolated Cross-Domain Transfer*  
*2026-04-11T12:37Z*
