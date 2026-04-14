# Spatial Metaphors for LLM Memory: A Critical Analysis of the MemPalace Architecture

[![arXiv](https://img.shields.io/badge/arXiv-cs.AI-b31b1b.svg)](https://arxiv.org/search/?searchtype=all&query=mempalace+spatial+metaphors)
[![Paper PDF](https://img.shields.io/badge/Paper-PDF-blue)](paper/mempalace-paper.pdf)
[![LaTeX Source](https://img.shields.io/badge/LaTeX-Source-orange)](paper/mempalace-paper.tex)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![Code License: MIT](https://img.shields.io/badge/Code%20License-MIT-green.svg)](LICENSE-CODE)

**Author:** Robin Dey (robin@vbrl.ai)  
**Affiliation:** VBRL Holdings, Thailand  
**Date:** April 2026  
**Branch:** `submission-draft` — arXiv-ready LaTeX version

> 📄 **[Read the PDF →](paper/mempalace-paper.pdf)**  
> 📝 **[LaTeX source →](paper/mempalace-paper.tex)**  
> 🗂 **[arXiv submission guide →](paper/arxiv-submission/README.md)**

---

## Abstract

MemPalace is an open-source AI memory system that applies the ancient *method of loci* (memory palace) spatial metaphor to organize long-term memory for large language models. Launched in April 2026, the project accumulated over 42,000 GitHub stars and claims state-of-the-art retrieval performance on the LongMemEval benchmark (96.6% Recall@5) without requiring any LLM inference at write time.

We present a comprehensive technical analysis of the MemPalace architecture, examining the mapping between its cognitive-science-inspired hierarchical structure (Wings→Rooms→Drawers) and its actual implementation in code. Through independent codebase analysis, benchmark replication, and comparison with competing systems, we find that MemPalace's headline retrieval performance is attributable primarily to its **verbatim storage philosophy** combined with ChromaDB's default embedding model (all-MiniLM-L6-v2), rather than to its spatial organizational metaphor per se.

Our analysis concludes that MemPalace represents **significant architectural insight wrapped in overstated claims** — a pattern common in rapidly adopted open-source projects where marketing velocity exceeds scientific rigor.

**Keywords:** AI memory systems · method of loci · spatial memory · vector databases · LLM memory · retrieval-augmented generation · MCP protocol · ChromaDB · LongMemEval

---

## Key Findings

| Finding | Result |
|---------|--------|
| LongMemEval Recall@5 (raw, no LLM) | **96.6%** |
| Benchmark attributable to palace structure? | ❌ (it's ChromaDB + verbatim text) |
| Benchmark attributable to verbatim storage? | ✅ |
| Wake-up cost (L0+L1) | **~170 tokens** |
| Write-time LLM calls required | **0** |
| Runtime dependencies | **2** (chromadb, pyyaml) |
| Mem0 comparison (extraction-based) | ~49% Recall@5 |
| "+34% from palace" claim valid? | ⚠️ Standard metadata filtering |
| AAAK "lossless" claim valid? | ❌ 12.4pp recall drop |

---

## Paper Structure

| Section | Topic |
|---------|-------|
| §1 | Introduction and contributions |
| §2 | Background: AI memory, method of loci neuroscience, hierarchical memory, vector DBs, MCP |
| §3 | System architecture: palace hierarchy, ingestion, search, knowledge graph, AAAK, MCP |
| §4 | Evaluation: LongMemEval, benchmark controversy, honest assessment, competitive comparison |
| §5 | Discussion: novelty, marketing-science gap, cognitive science verdict, verbatim insight |
| §6 | Related systems: Supermemory ASMR, Mem0, Zep/Graphiti, Mastra, Hindsight |
| §7 | Framework for evaluating AI memory systems |
| §8 | Conclusion and recommendations |
| App A | Code statistics |
| App B | Benchmark reproduction notes |
| App C | Glossary |

---

## How to Cite

```bibtex
@unpublished{dey2026mempalace,
  author = {Dey, Robin},
  title  = {Spatial Metaphors for {LLM} Memory: A Critical Analysis of the {MemPalace} Architecture},
  year   = {2026},
  url    = {https://github.com/web3guru888/mempalace-scientific-analysis},
  note   = {Preprint}
}
```

Or see [`CITATION.cff`](CITATION.cff) for the Citation File Format version.

---

## Reproduce Our Results

All benchmark scripts, experiment code, and raw data are included in this repository.

### Requirements

```bash
pip install chromadb pyyaml numpy pandas
```

### Run Benchmarks

```bash
cd benchmarks/
python -m scripts --config scripts/config.py
# Results written to results/aggregated/summary.json
```

### Key Experiments

| Script | Description |
|--------|-------------|
| `benchmarks/scripts/runner.py` | Main benchmark runner (LongMemEval reproduction) |
| `experiments/scripts/causal_chain_experiment.py` | Causal chain orient experiment |
| `experiments/scripts/cycle6_experiment.py` | Retrieval profiles (Cycle 6) |
| `experiments/scripts/cycle7_experiment.py` | Embedding deduplication (Cycle 7) |

### Build the Paper PDF

```bash
cd paper/
make pdf
# → mempalace-paper.pdf (18 pages)
```

Requires: `pdflatex`, `bibtex` (standard TeX Live installation).

---

## Repository Structure

```
mempalace-scientific-analysis/
│
├── paper/
│   ├── mempalace-paper.tex              ← LaTeX source (JMLR preprint style)
│   ├── mempalace-paper.bib              ← BibTeX bibliography (25 references)
│   ├── mempalace-paper.pdf              ← Pre-built PDF (18 pages)
│   ├── jmlr2e.sty                       ← JMLR style file
│   ├── Makefile                         ← Reproducible PDF build
│   ├── mempalace-scientific-analysis.md ← Original Markdown paper
│   └── arxiv-submission/
│       ├── README.md                    ← arXiv upload instructions
│       └── jmlr2e.sty                   ← Style file for arXiv bundle
│
├── benchmarks/
│   ├── scripts/                         ← Benchmark runner code
│   │   ├── runner.py                    ← Main runner (391 lines)
│   │   ├── metrics.py                   ← Metric computation
│   │   ├── config.py                    ← Configuration
│   │   ├── mock_data.py                 ← Mock data generators
│   │   └── __main__.py                  ← Entry point
│   ├── results/raw/                     ← Raw JSON results (25 runs)
│   └── results/aggregated/summary.json  ← Aggregated statistics
│
├── experiments/
│   ├── experiment-registry-2026-04-10.md ← Master registry
│   ├── scripts/                          ← Experiment scripts (4 files)
│   └── reports/                          ← 33 experiment reports (Markdown)
│
├── integration-code/
│   └── src/mempalace_agi/               ← Full integration source (6 modules)
│
├── data/discovery-runs/                 ← Experiment data
├── references/                          ← Reference documents
│
├── CITATION.cff                         ← Citation metadata
├── LICENSE                              ← CC BY 4.0 (paper)
└── LICENSE-CODE                         ← MIT (code/benchmarks)
```

---

## License

- **Paper** (`.tex`, `.pdf`, `.md`): [CC BY 4.0](LICENSE) — cite us and use freely
- **Code** (benchmarks, experiments, integration): [MIT](LICENSE-CODE) — use freely

---

## Contact

Robin Dey — robin@vbrl.ai  
VBRL Holdings, Thailand  
GitHub: [web3guru888](https://github.com/web3guru888)
