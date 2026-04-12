# Discovery Cycle 23 — Multi-Run Knowledge Transfer A/B Test (INCOMPLETE)

**Date**: 2026-04-10 ~16:45–17:30 UTC  
**Cycle**: DC-23  
**Type**: A/B comparison — knowledge transfer across runs  
**Status**: ⚠️ INCOMPLETE — worker timeout + critical design confound  
**Score**: 2/6 targets PASS  

> **⚠️ CRITICAL CONFOUND**: The "fresh" condition's palace was reset (empty ChromaDB) but ASTRA's `astra_knowledge.db` persists in the shared workdir. Both conditions inherited identical KG state in Run 2, making the A/B comparison meaningless. See [Confound Analysis](#confound-astras-astra_knowledgedb-leak).

## Executive Summary

DC-23 attempted to measure whether **cumulative palace state** (carrying ChromaDB + KG across runs) produces better discovery than **fresh restarts** (new palace per run). Two conditions × two reps × two sequential runs were launched as subprocess-isolated workers. **Rep 1** completed Run 1 (8 cycles, 481 discoveries, 5,957 KG triples — **perfectly identical** across conditions) and reached cycle 4 of Run 2 before SIGTERM. **Rep 2** was killed immediately (exit -9, likely OOM cascade). A critical confound was discovered: ASTRA's `astra_knowledge.db` lives in the workdir, not the palace directory, so the "fresh" condition actually inherited all KG state from Run 1. The only thing truly fresh was the ChromaDB vector collection (dedup). The experiment is **inconclusive** but yields important engineering insights.

## Experimental Design

### Hypothesis
**H₀**: Fresh and cumulative palace conditions produce equal discovery counts in Run 2.  
**H₁**: Cumulative palace (carrying prior discoveries + KG) enables more discoveries in Run 2 than a fresh start.

### Configuration
| Parameter | Value |
|-----------|-------|
| Cycles per run | 15 (max) |
| max_dry_cycles | 5 |
| Runs per rep | 2 (Run 1 → Run 2) |
| Reps per condition | 2 (intended) |
| Workers | Subprocess isolation (separate Python processes) |
| Conditions | `fresh` (new palace for Run 2), `cumulative` (copy Run 1 palace to Run 2) |

### Condition Definitions
- **Cumulative**: Run 1 palace directory copied to Run 2's palace path → Run 2 starts with all discoveries, embeddings, and (intended) KG from Run 1.
- **Fresh**: Run 2 gets a new empty palace directory → Run 2 starts with no prior discovery vectors. Should re-discover from scratch.

## Raw Results

### Run 1: Seeding Phase (Identical Across Conditions)

Both conditions ran Run 1 in the same workdir with the same configuration. Results were **perfectly identical** — validating subprocess isolation and deterministic discovery.

| Cycle | Disc (cumul.) | Δ Disc | KG Triples | Notes |
|-------|--------------|--------|------------|-------|
| C1 | 496 | +496 | 5,777 | Seeding (template load) |
| C2 | 450 | −46 | 5,777 | Dedup purge (removed stale) |
| C3 | 459 | +9 | 5,813 | Productive |
| C4 | 465 | +6 | 5,837 | Productive |
| C5 | 472 | +7 | 5,874 | Productive |
| C6 | 475 | +3 | 5,906 | Productive |
| C7 | 481 | +6 | 5,957 | Productive |
| C8 | 481 | +0 | 5,957 | Dry → max_dry_cycles hit, stop |

**Run 1 summary**: 481 discoveries, 5,957 KG triples. 7 productive cycles + 1 dry cycle. **0 difference** between conditions on 7 of 8 cycles.

### Run 2: Transfer Test (Partial — 4/15 Cycles Before Kill)

| Cycle | Cumul. Disc | Cumul. Δ | Fresh Disc | Fresh Δ | Diff |
|-------|------------|----------|-----------|---------|------|
| C1 | 490 | +7 | 491 | +8 | −1 |
| C2 | 495 | +5 | 496 | +5 | 0 |
| C3 | 450 | −45 (purge) | 450 | −46 (purge) | 0 |
| C4 | 456 | +6 | 456 | +6 | 0 |

Both conditions started Run 2 at **483 discoveries, 5,957 KG triples** — already revealing the confound.

### Timing Data (Run 2)

| Metric | Cumulative | Fresh | Ratio |
|--------|-----------|-------|-------|
| C1 time | 108.8s | 59.2s | 1.84× |
| Total (4 cycles) | 252.4s | 189.5s | 1.33× |
| Avg cycle time | 63.1s | 47.4s | 1.33× |

Cumulative condition was **33.2% slower** in Run 2 — the larger ChromaDB collection (from Run 1) increases semantic search latency in every Orient call.

### Dedup Rejections
Both conditions: **73 hard duplicate rejections** total (identical).

### Rep 2: Immediate Kill
Both Rep 2 workers were terminated within **5.5 seconds** (exit code -9 → SIGKILL). Likely OOM from running 4 concurrent discovery processes, or cascading kill from the scheduler. **Zero usable data from Rep 2.**

## Confound: ASTRA's `astra_knowledge.db` Leak

### The Problem
The "fresh" condition was designed to test what happens when Run 2 starts without prior knowledge. The implementation:
- ✅ Created a new empty palace directory (fresh ChromaDB, no discovery vectors)
- ❌ Reused the same workdir for Run 2

ASTRA's discovery engine uses `os.chdir(args.workdir)` and creates `astra_knowledge.db` (SQLite) in that directory. This database contains:
- All hypotheses from Run 1
- All investigation results
- Entity-relationship triples
- Confidence scores and status tracking

Since Run 2 reused the same workdir, **both conditions inherited the full `astra_knowledge.db` from Run 1**. The only difference was whether ChromaDB had the discovery embedding vectors — but the actual knowledge (hypotheses, KG, scores) was identical.

### Impact
This makes the A/B comparison **meaningless for testing knowledge transfer**:
- Both conditions had identical KG state at Run 2 start → identical discovery trajectories
- The ±1 discovery difference in C1 is within noise
- ChromaDB dedup vectors alone don't drive discovery — the KG does

### Fix Required
For a valid knowledge transfer test:
1. **Separate workdirs** for Run 1 and Run 2
2. For `fresh`: new workdir with NO `.db` files
3. For `cumulative`: copy BOTH palace dir AND `astra_*.db` files to Run 2 workdir
4. Explicit KG isolation at the file level

## Target Evaluation

| # | Target | Result | Evidence |
|---|--------|--------|----------|
| T1 | Run 1 identical across conditions | ✅ **PASS** | 0 disc difference on 7/8 cycles; 481 disc, 5,957 KG in both |
| T2 | Run 2 completes (15 cycles) | ❌ **FAIL** | Killed at cycle 4 of 15 (SIGTERM) |
| T3 | Fresh ≠ Cumulative in Run 2 | ❌ **FAIL** | Confound — both inherited identical KG; ±1 disc difference |
| T4 | Statistical significance (p<0.05) | ❌ **FAIL** | No meaningful difference to test; 1 rep only |
| T5 | Timing data collected | ✅ **PASS** | Cumulative 33.2% slower in Run 2 (larger ChromaDB overhead) |
| T6 | 2 reps per condition complete | ❌ **FAIL** | Only 1 rep completed Run 1; Rep 2 killed at startup |

**Score: 2/6 PASS**

## Key Findings

### F1: Run 1 Is Perfectly Reproducible
Discovery counts across conditions were **identical** (0 difference on 7 of 8 cycles). This is the strongest validation yet of subprocess isolation — same code, same data, same results.

### F2: `astra_knowledge.db` Is NOT Palace-Scoped
The ASTRA engine's knowledge database lives in the workdir, independent of the palace directory. Any A/B test that only swaps the palace directory is testing ChromaDB dedup only, not knowledge transfer. **This is the #1 engineering fix needed for a valid transfer experiment.**

### F3: Cumulative ChromaDB Adds ~33% Overhead
The larger ChromaDB collection (from Run 1) increases Run 2 cycle times by 33%. This is the cost of semantic search over a larger embedding space. The overhead is concentrated in C1 (1.84× slower) and diminishes slightly in later cycles as the query patterns stabilize.

### F4: Worker Concurrency Limits
Running 4 simultaneous discovery workers (2 conditions × 2 reps) exceeds resource limits. Rep 2 was killed immediately (exit -9). **Max safe concurrency: 2 workers** (or 1 with longer timeout).

### F5: Dedup Purge Persists in Run 2
Both conditions experienced a dedup purge in Run 2 C3 (−45/−46 discoveries), identical to Run 1 C2 behavior. This is expected — the ASTRA engine re-validates all discoveries each cycle and removes stale entries.

## Recommendations for DC-24

### Design Fixes
1. **Separate workdirs for each run**: `workdir_run1/` and `workdir_run2/` — eliminates `astra_knowledge.db` leak
2. **For fresh condition**: New workdir with zero `.db` files, zero palace state
3. **For cumulative condition**: Copy BOTH `palace/` directory AND `astra_*.db` files from Run 1 workdir to Run 2 workdir
4. **Increase worker timeout**: 30+ minutes per worker (current ~10 min insufficient for 15 cycles)
5. **Reduce concurrency**: 1 rep at a time (sequential), or max 2 workers simultaneously

### Statistical Improvements
6. **Run 1 rep only, ensure full completion** — better 1 complete rep than 2 partial
7. **15 cycles minimum per run** to capture the full saturation curve
8. **Pre-register targets** based on DC-23's timing data (expected ~5 min/cycle × 15 cycles = 75 min/run)

## Appendix: Worker Exit Codes

| Worker | Run 1 | Run 2 | Exit Code |
|--------|-------|-------|-----------|
| Rep 1 Cumulative | ✅ 8 cycles | ⚠️ 4 cycles | SIGTERM |
| Rep 1 Fresh | ✅ 8 cycles | ⚠️ 4 cycles | SIGTERM |
| Rep 2 Cumulative | ❌ 0 cycles | — | -9 (SIGKILL) |
| Rep 2 Fresh | ❌ 0 cycles | — | -9 (SIGKILL) |

---

*Report generated: 2026-04-10 ~17:33 UTC*  
*Experiment: DC-23 Multi-Run Knowledge Transfer A/B*  
*Status: INCOMPLETE — confound invalidates comparison, partial data only*  
*Next: DC-24 with workdir isolation and extended timeouts*
