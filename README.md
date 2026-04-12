# Spatial Metaphors for LLM Memory: A Critical Analysis of the MemPalace Architecture

[![Paper](https://img.shields.io/badge/Paper-Markdown-blue)](paper/mempalace-scientific-analysis.md)
[![License](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey)](LICENSE)
[![Data](https://img.shields.io/badge/Data-Open-green)](#repository-structure)

**Authors:** MEMPALACE-AGI Research Group  
**Date:** April 12, 2026  
**Affiliation:** Taurus Autonomous Research Platform  

---

## Abstract

MemPalace is an open-source AI memory system that applies the ancient *method of loci* (memory palace) spatial metaphor to organize long-term memory for large language models. Launched in April 2026, the project has attracted over 42,000 GitHub stars and claims state-of-the-art retrieval performance on the LongMemEval benchmark (96.6% Recall@5) without requiring any LLM inference at write time.

We present a comprehensive technical analysis of the MemPalace architecture, examining the mapping between its cognitive-science-inspired hierarchical structure (Wings→Rooms→Closets→Drawers) and its actual implementation in code. Through independent codebase analysis, benchmark replication, and comparison with competing systems, we find that:

1. **MemPalace's headline retrieval performance** is attributable primarily to its verbatim storage philosophy combined with ChromaDB's default embedding model (all-MiniLM-L6-v2), rather than to its spatial organizational metaphor per se
2. **The palace hierarchy** operates as standard vector database metadata filtering — an effective but well-established technique
3. **Genuinely novel contributions** include: a contrarian verbatim-first storage philosophy, extremely low wake-up cost (~170 tokens), a fully deterministic zero-LLM write path, and the first systematic application of spatial memory metaphors to AI memory systems

Our analysis concludes that MemPalace represents significant *architectural insight* wrapped in *overstated claims* — a pattern common in rapidly adopted open-source projects where marketing velocity exceeds scientific rigor.

**Keywords:** AI memory systems, method of loci, spatial memory, vector databases, LLM memory, retrieval-augmented generation, MCP protocol, ChromaDB

---

## 📄 Paper

The full paper is available at:

- **[`paper/mempalace-scientific-analysis.md`](paper/mempalace-scientific-analysis.md)** — Complete analysis (630 lines, ~60KB)

### Paper Sections

| Section | Topic |
|---------|-------|
| §1 | Introduction and contributions |
| §2 | Background: AI memory problem, method of loci neuroscience, hierarchical memory, vector DBs, MCP |
| §3 | System architecture: palace hierarchy, ingestion, search, knowledge graph, AAAK, MCP server |
| §4 | Evaluation: LongMemEval results, benchmark controversy, honest assessment, competitive comparison |
| §5 | Discussion: what's novel vs. not, marketing-science gap, cognitive science verdict, scalability |
| §6 | Related systems: Supermemory ASMR, Mem0, Zep/Graphiti, Mastra, Hindsight |
| §7 | Framework for evaluating AI memory systems |
| §8 | Conclusion and recommendations |
| App A | Code statistics |
| App B | Benchmark reproduction notes |
| App C | Glossary |

---

## 🔬 Supporting Materials for Peer Review

This repository contains **all data, code, and experiment reports** needed to independently verify our claims.

### Repository Structure

```
├── paper/
│   └── mempalace-scientific-analysis.md    # The full paper
│
├── benchmarks/
│   ├── scripts/                            # Benchmark runner code
│   │   ├── runner.py                       # Main benchmark runner (391 lines)
│   │   ├── metrics.py                      # Metric computation (53 lines)
│   │   ├── config.py                       # Benchmark configuration
│   │   ├── mock_data.py                    # Mock data generators
│   │   └── __main__.py                     # Entry point
│   ├── results/
│   │   ├── raw/                            # Raw JSON results (25 benchmark runs)
│   │   └── aggregated/
│   │       └── summary.json                # Aggregated statistics with effect sizes
│   └── analysis/
│       ├── S1_S2_results.md                # Cold start / warm start analysis
│       └── phase7-benchmark-summary.md     # Phase 7 benchmark summary
│
├── experiments/
│   ├── experiment-registry-2026-04-10.md   # Master registry of all experiments
│   ├── scripts/
│   │   ├── causal_chain_experiment.py      # Causal chain Orient experiment (1,314 lines)
│   │   ├── cycle6_experiment.py            # Cycle 6 retrieval profiles (1,229 lines)
│   │   ├── cycle7_experiment.py            # Cycle 7 embedding dedup (1,205 lines)
│   │   └── launch_discovery.py             # Discovery cycle launcher (280 lines)
│   └── reports/                            # 33 experiment reports (Markdown)
│       ├── discovery-cycle-{2..28}-*.md    # Individual cycle reports
│       ├── causal-chain-experiment-*.md    # Causal chain experiment
│       ├── real-data-experiment-*.md       # Real data source experiment
│       ├── bridge-ab-experiment-*.md       # A/B comparison experiment
│       ├── cross-domain-transfer-*.md      # Cross-domain transfer experiment
│       ├── domain-diversity-*.md           # Domain diversity experiment
│       └── pool-rebalance-*.md             # Pool rebalance experiment
│
├── integration-code/
│   ├── src/mempalace_agi/                  # Full MemPalace-AGI integration source
│   │   ├── palace_discovery_memory.py      # Core: Palace-backed discovery memory
│   │   ├── memory_augmented_orient.py      # OODA Orient with semantic search
│   │   ├── knowledge_graph.py              # Temporal knowledge graph
│   │   ├── knowledge_graph_bridge.py       # KG ↔ ASTRA bridge
│   │   ├── hypothesis_workspace.py         # Hypothesis lifecycle management
│   │   ├── retrieval_profiles.py           # 5 retrieval profile system
│   │   ├── kg_pathfinder.py                # Knowledge graph pathfinding
│   │   ├── kg_pheromones.py                # Stigmergic pheromone trails
│   │   ├── kg_communities.py               # KG community detection
│   │   ├── domain_specialists.py           # Domain specialist agents
│   │   ├── discovery_synergy.py            # Cross-domain synergy detection
│   │   ├── orchestrator.py                 # OODA cycle orchestrator
│   │   ├── unified_api.py                  # Unified REST API
│   │   ├── mcp_server.py                   # MCP server (19+ tools)
│   │   ├── backends/                       # Pluggable storage backends
│   │   │   ├── vector_backend.py           # Abstract vector backend
│   │   │   ├── chromadb_backend.py         # ChromaDB implementation
│   │   │   ├── kg_backend.py               # KG backend interface
│   │   │   └── sqlite_kg_backend.py        # SQLite KG backend
│   │   └── ...                             # Additional modules
│   └── tests/                              # 30 test files
│       ├── test_palace_discovery_memory.py
│       ├── test_memory_augmented_orient.py
│       ├── test_retrieval_profiles.py
│       ├── test_kg_bridge.py
│       └── ...                             # Additional test files
│
├── data/
│   └── discovery-runs/                     # Raw cycle logs from 18 discovery runs
│       ├── run-20260410-*/cycle_log.json
│       ├── run-20260411-*/cycle_log.json
│       └── run-20260412-*/cycle_log.json
│
├── references/
│   ├── astra-rasti-v6.0.pdf               # ASTRA paper (White, 2026)
│   └── astra-paper-text.md                # ASTRA paper text extraction
│
├── CITATION.cff                            # Citation metadata
├── LICENSE                                 # CC BY 4.0
└── README.md                               # This file
```

---

## 🔑 Key Claims and Where to Verify Them

| Claim in Paper | Evidence Location |
|----------------|-------------------|
| 96.6% is Recall@5, not end-to-end QA | `paper/` §4.2, `benchmarks/analysis/S1_S2_results.md` |
| Honest QA score is ~67.2% | `paper/` §4.3 |
| Palace hierarchy = metadata filtering | `integration-code/src/mempalace_agi/palace_discovery_memory.py` |
| Verbatim storage is the key differentiator | `paper/` §5.1, `benchmarks/results/` |
| A/B: MemPalace vs baseline (null on single-run) | `experiments/reports/bridge-ab-experiment-2026-04-11.md` |
| Cross-domain transfer shows compounding | `experiments/reports/cross-domain-transfer-experiment-2026-04-11.md` |
| KG enrichment: 4,500+ triples per run | `experiments/reports/discovery-cycle-22-optimized-2026-04-10.md` |
| Burst mode: 88% discovery yield | `experiments/reports/discovery-cycle-22-optimized-2026-04-10.md` |
| Causal chain Orient improves hypothesis quality | `experiments/reports/causal-chain-experiment-2026-04-10.md` |
| 5 retrieval profiles system | `integration-code/src/mempalace_agi/retrieval_profiles.py` |

---

## 🏃 Reproducing Results

### Prerequisites

```bash
# Python 3.10+
pip install chromadb pyyaml scipy numpy
```

### Running Benchmarks

```bash
cd benchmarks/scripts
python -m __main__
```

The benchmark runner (`runner.py`) executes treatment vs. baseline comparisons across multiple scenarios (cold start, warm start, cross-domain, scaling, deduplication). Raw results are written to `results/raw/` as JSON.

### Running Experiments

Each experiment script in `experiments/scripts/` is self-contained:

```bash
cd experiments/scripts
python causal_chain_experiment.py   # Causal chain Orient experiment
python cycle6_experiment.py         # Retrieval profiles experiment
python cycle7_experiment.py         # Embedding dedup experiment
python launch_discovery.py          # Full OODA discovery cycle
```

**Note:** Experiments require the full MemPalace-AGI integration and ASTRA-dev framework. The integration code is provided in `integration-code/` for inspection. To run experiments end-to-end, you also need:

- [MemPalace](https://github.com/milla-jovovich/mempalace) (MIT License)
- [ASTRA-dev](https://github.com/Tilanthi/ASTRA-dev) (License TBD — see §8.2 of the paper)

---

## 📊 Data Description

### Benchmark Results (`benchmarks/results/raw/`)

25 JSON files containing per-run metrics:
- **Scenarios:** cold_start (25/50 cycles), warm_start (25/50 cycles), cross_domain (100 cycles), scaling (500 cycles), duplicates (30 cycles), specialist with/without diaries (100 cycles)
- **Conditions:** baseline (SQLite DiscoveryMemory) vs. treatment (PalaceDiscoveryMemory)
- **Metrics:** M6 confirmation rate, M7 time-to-confirm, M15 AUC confidence, M17 domain balance, M13 storage overhead

### Discovery Run Logs (`data/discovery-runs/`)

18 complete discovery run cycle logs containing:
- Per-cycle hypothesis generation, testing, and evaluation data
- Knowledge graph triple counts
- Drawer creation and deduplication statistics
- Domain distribution metrics

### Experiment Reports (`experiments/reports/`)

33 detailed Markdown reports from the full experimental campaign (April 9–11, 2026), documenting:
- Discovery cycles 2–28 with incremental improvements
- A/B comparisons (MemPalace vs. baseline)
- Cross-domain transfer experiments
- Causal chain integration experiments
- Domain diversity and pool rebalance studies

---

## ⚖️ Ethical Considerations

This paper presents a critical but fair analysis of an open-source project. We:
- Acknowledge MemPalace's genuine contributions alongside its overstated claims
- Use only publicly available code and data
- Disclose that the MEMPALACE-AGI Research Group previously contributed to the MemPalace project
- Note that ASTRA-dev currently lacks a formal license, which affects reproducibility (§8.2)

---

## 📝 Citation

```bibtex
@article{mempalace-agi-2026-analysis,
  title={Spatial Metaphors for LLM Memory: A Critical Analysis of the MemPalace Architecture},
  author={{MEMPALACE-AGI Research Group}},
  year={2026},
  month={April},
  url={https://github.com/web3guru888/mempalace-scientific-analysis}
}
```

---

## 📜 License

- **Paper and documentation:** [CC BY 4.0](LICENSE)
- **Code (benchmarks, experiments, integration):** [MIT License](LICENSE-CODE)
- **Referenced projects:** MemPalace (MIT), ASTRA-dev (License TBD)
