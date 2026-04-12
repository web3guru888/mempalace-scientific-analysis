# MemPalace-AGI: Codebase Analysis Report
**Date**: 2026-04-08  
**Author**: MemPalace-AGI Engineer  
**Purpose**: Foundation analysis for integrating MemPalace + ASTRA-dev

---

## Executive Summary

This report provides a comprehensive analysis of two open-source codebases — **MemPalace** (AI memory system with spatial organization) and **ASTRA-dev** (autonomous scientific discovery framework) — for the purpose of integrating them into a unified autonomous research system with perfect memory.

**Key findings:**
- MemPalace provides a lightweight (2 core deps), well-structured hierarchical memory system using ChromaDB with 19 MCP tools
- ASTRA-dev provides a sophisticated discovery engine with OODA cycles, Bayesian hypothesis management, and 89+ API endpoints
- The primary integration point is ASTRA-dev's `DiscoveryMemory` class (677 LOC, 13 public methods) which can be augmented with MemPalace's palace architecture
- No dependency conflicts between the two projects
- Python version: target 3.10+ (ASTRA uses `match` statements and `X | Y` type hints)

---

## Part 1: MemPalace Analysis

### 1.1 Project Overview
- **Repository**: github.com/milla-jovovich/mempalace
- **Version**: 3.0.0
- **License**: MIT
- **Python**: ≥3.9
- **Total LOC**: ~8,580 (main package)
- **Core purpose**: Give AI systems persistent, searchable memory with spatial organization

### 1.2 Directory Structure

```
/shared/mempalace/
├── .github/workflows/ci.yml     — CI pipeline
├── benchmarks/                   — LongMemEval, LoCoMo, ConvoMem, MemBench
├── examples/                     — Setup guides, basic usage
├── hooks/                        — Git hooks for save/precompact
├── mempalace/                    — Main package
│   ├── __init__.py / __main__.py — Entry points
│   ├── cli.py                    — 483 LOC — CLI commands
│   ├── config.py                 — 149 LOC — Configuration management
│   ├── convo_miner.py            — 404 LOC — Conversation ingestion
│   ├── dialect.py                — 1075 LOC — AAAK dialect compression
│   ├── entity_detector.py        — 853 LOC — Auto entity detection
│   ├── entity_registry.py        — 639 LOC — Persistent entity store
│   ├── general_extractor.py      — 521 LOC — 5-type memory extraction
│   ├── knowledge_graph.py        — 387 LOC — Temporal entity-relationship graph
│   ├── layers.py                 — 515 LOC — 4-layer memory stack
│   ├── mcp_server.py             — 784 LOC — MCP server (19 tools)
│   ├── miner.py                  — 672 LOC — Project file mining
│   ├── normalize.py              — 328 LOC — Chat format normalization
│   ├── onboarding.py             — 489 LOC — First-run setup
│   ├── palace_graph.py           — 227 LOC — Graph traversal (BFS)
│   ├── searcher.py               — 152 LOC — Semantic search
│   ├── room_detector_local.py    — 310 LOC — Room auto-detection
│   ├── spellcheck.py             — 269 LOC — User message spellcheck
│   └── split_mega_files.py       — 309 LOC — Mega file splitter
├── tests/                        — 11 test files
├── pyproject.toml                — Build configuration
└── uv.lock                       — Dependency lock file
```

### 1.3 Palace Architecture — Hierarchical Memory Model

**Conceptual Hierarchy**: Wings → Rooms → (Halls) → Drawers

Physical storage is **flat in ChromaDB** (`mempalace_drawers` collection), with metadata providing the logical hierarchy:

| Level | Purpose | Example | Stored As |
|-------|---------|---------|-----------|
| **Wing** | Top-level domain/project | `wing_code`, `wing_user`, `emotions` | ChromaDB metadata `wing` |
| **Room** | Topic within wing | `backend`, `diary`, `planning` | ChromaDB metadata `room` |
| **Hall** | Optional corridor | `hall_diary`, `hall_facts` | ChromaDB metadata `hall` |
| **Drawer** | Atomic memory unit | Verbatim text chunk | ChromaDB document + embedding |

**Note**: Despite README mentioning "closets", there is **no explicit closet layer in the code**. The hierarchy is: Wings → Rooms → Drawers. The `source_closet` field exists only in the knowledge graph schema as a reference marker.

**Drawer Metadata Schema**:
```python
{
    "wing": str,           # e.g., "project", "wing_atlas"
    "room": str,           # e.g., "backend", "diary", "general"
    "hall": str,           # Optional: "hall_diary"
    "source_file": str,    # Original file path
    "chunk_index": int,    # Position in chunked file
    "added_by": str,       # Agent name: "mempalace", "mcp"
    "filed_at": str,       # ISO timestamp
    "type": str,           # Optional: "diary_entry"
    "agent": str,          # Optional: for diary entries
    "topic": str,          # Optional: diary topic
    "date": str,           # Optional: "YYYY-MM-DD"
    "importance": float,   # Optional: for Layer 1 scoring
    "emotional_weight": float,
}
```

### 1.4 ChromaDB Integration

- **Collection**: `"mempalace_drawers"` (primary), `"mempalace_compressed"` (AAAK compressed, optional)
- **Client**: `chromadb.PersistentClient(path=palace_path)`
- **Default path**: `~/.mempalace/palace`
- **Embedding**: ChromaDB default (Sentence Transformers / all-MiniLM-L6-v2)
- **Storage**: `col.add(documents=[text], ids=[drawer_id], metadatas=[meta])`
- **Semantic query**: `col.query(query_texts=[q], n_results=N, where=filter)`
- **Metadata query**: `col.get(where={"wing": wing}, limit=N)`

### 1.5 Knowledge Graph — SQLite

**File**: `mempalace/knowledge_graph.py` (387 LOC)  
**DB path**: `~/.mempalace/knowledge_graph.sqlite3`

**Schema**:
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,          -- lowercase normalized
    name TEXT NOT NULL,           -- display name
    type TEXT DEFAULT 'unknown',  -- "person", "project", etc.
    properties TEXT DEFAULT '{}', -- JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE triples (
    id TEXT PRIMARY KEY,          -- "t_{sub}_{pred}_{obj}_{hash8}"
    subject TEXT NOT NULL,        -- FK → entities.id
    predicate TEXT NOT NULL,      -- "parent_of", "does", "loves"
    object TEXT NOT NULL,         -- FK → entities.id
    valid_from TEXT,              -- temporal start
    valid_to TEXT,                -- temporal end (NULL = current)
    confidence REAL DEFAULT 1.0,
    source_closet TEXT,
    source_file TEXT,
    extracted_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Key methods** of `KnowledgeGraph` class:
- `add_entity(name, entity_type, properties) → str`
- `add_triple(subject, predicate, obj, valid_from, valid_to, confidence, source_closet, source_file) → str`
- `invalidate(subject, predicate, obj, ended)`
- `query_entity(name, as_of, direction) → list[dict]`
- `query_relationship(predicate, as_of) → list[dict]`
- `timeline(entity_name) → list[dict]`
- `stats() → dict`

Features: temporal queries (valid_from/valid_to), deduplication, entity ID normalization.

### 1.6 MCP Server — 19 Tools

**Protocol**: JSON-RPC 2.0, MCP protocol `2024-11-05`, stdin/stdout transport.

| # | Tool | Category | Key Parameters |
|---|------|----------|----------------|
| 1 | `mempalace_status` | Read | — |
| 2 | `mempalace_list_wings` | Read | — |
| 3 | `mempalace_list_rooms` | Read | `wing?` |
| 4 | `mempalace_get_taxonomy` | Read | — |
| 5 | `mempalace_get_aaak_spec` | Read | — |
| 6 | `mempalace_kg_query` | KG | `entity`, `as_of?`, `direction?` |
| 7 | `mempalace_kg_add` | KG | `subject`, `predicate`, `object`, `valid_from?` |
| 8 | `mempalace_kg_invalidate` | KG | `subject`, `predicate`, `object`, `ended?` |
| 9 | `mempalace_kg_timeline` | KG | `entity?` |
| 10 | `mempalace_kg_stats` | KG | — |
| 11 | `mempalace_traverse` | Graph | `start_room`, `max_hops?` |
| 12 | `mempalace_find_tunnels` | Graph | `wing_a?`, `wing_b?` |
| 13 | `mempalace_graph_stats` | Graph | — |
| 14 | `mempalace_search` | Search | `query`, `limit?`, `wing?`, `room?` |
| 15 | `mempalace_check_duplicate` | Search | `content`, `threshold?` |
| 16 | `mempalace_add_drawer` | Write | `wing`, `room`, `content`, `source_file?` |
| 17 | `mempalace_delete_drawer` | Write | `drawer_id` |
| 18 | `mempalace_diary_write` | Diary | `agent_name`, `entry`, `topic?` |
| 19 | `mempalace_diary_read` | Diary | `agent_name`, `last_n?` |

### 1.7 Specialist Agents & Diary System

- Each agent gets a wing: `wing_{agent_name}` with room `diary`, hall `hall_diary`
- Not hardcoded agent classes — agents are an **application pattern**
- Diary metadata: `{type: "diary_entry", agent: name, topic: topic, date: "YYYY-MM-DD"}`
- AAAK dialect available for token-efficient diary compression

### 1.8 4-Layer Memory Stack

| Layer | Tokens | Trigger | Function |
|-------|--------|---------|----------|
| L0 | ~100 | Always | Identity text from `~/.mempalace/identity.txt` |
| L1 | ~500-800 | Always | Top 15 drawers by importance, grouped by room |
| L2 | ~200-500 | On-demand | Wing/room filtered retrieval |
| L3 | Unlimited | On-demand | Full ChromaDB semantic search |

**Critical for integration**: `Layer3.search_raw(query, wing, room, n_results)` returns raw dicts: `{text, wing, room, source_file, similarity, metadata}`.

### 1.9 Dependencies

```
chromadb>=0.5.0,<0.7
pyyaml>=6.0
```
Only 2 runtime dependencies. Extremely lightweight.

### 1.10 Storage/Retrieval API Summary

**Write paths**:
1. `tool_add_drawer(wing, room, content)` — MCP/programmatic drawer creation
2. `tool_diary_write(agent_name, entry, topic)` — Agent diary entries
3. `mine(project_dir, palace_path)` — Batch project mining
4. `mine_convos(convo_dir, palace_path)` — Conversation mining
5. `kg.add_entity()` / `kg.add_triple()` — Knowledge graph writes

**Read paths**:
1. `search_memories(query, palace_path, wing, room)` — Semantic search (returns dict)
2. `Layer3.search_raw(query, wing, room)` — Raw semantic search results
3. `kg.query_entity()` / `kg.query_relationship()` — Knowledge graph queries
4. `traverse(start_room, col, max_hops)` — BFS graph traversal
5. `col.get(where=filter)` — Direct ChromaDB metadata query

---

## Part 2: ASTRA-dev Analysis

### 2.1 Project Overview
- **Repository**: github.com/Tilanthi/ASTRA-dev
- **Python**: 3.10+ (uses `match` statements, `X | Y` type hints)
- **License**: Not specified (README)
- **Core module**: `astra_live_backend/` (~15,000+ LOC)
- **Core purpose**: Autonomous scientific discovery with OODA cycles

### 2.2 Directory Structure

```
/shared/ASTRA-dev/
├── astra_live_backend/          ★ CORE — discovery engine
│   ├── engine.py               — 3384 LOC — OODA cycle engine
│   ├── server.py               — 2537 LOC — FastAPI (89+ endpoints)
│   ├── hypotheses.py           — 314 LOC — Hypothesis state machine
│   ├── discovery_memory.py     — 677 LOC ★★★ KEY INTEGRATION POINT
│   ├── knowledge_graph.py      — 996 LOC — Dynamic knowledge graph
│   ├── hypothesis_generator.py — 368 LOC — Memory-driven generation
│   ├── adaptive_strategist.py  — 239 LOC — Method selection
│   ├── bayesian.py             — 342 LOC — Bayesian model comparison
│   ├── causal.py               — 350 LOC — PC/FCI algorithms
│   ├── data_fetcher.py         — 578 LOC — Data source clients
│   ├── data_registry.py        — 973 LOC — 9+ source registry
│   ├── novelty.py              — Novelty detection
│   ├── anomaly.py              — Anomaly detection
│   ├── alignment.py            — 6-dim alignment checker
│   ├── degradation.py          — Performance monitoring
│   ├── state_persistence.py    — 160 LOC — JSON state save/load
│   ├── provenance.py           — Discovery provenance
│   ├── exporter.py             — JSON/CSV/LaTeX export
│   ├── safety/                 — Safety subsystem (12 files)
│   │   ├── controller.py       — 5-state safety machine
│   │   ├── arbiter.py          — GO/NO_GO/ABORT decisions
│   │   ├── circuit_breakers.py — Circuit breaker checks
│   │   ├── phased_autonomy.py  — 4-level autonomy framework
│   │   └── [8 more files]
│   ├── multi_agent/            — Swarm collaboration
│   ├── autonomous_agenda/      — Self-generated goals
│   └── [advanced modules]
├── astra_core/                  — Research/AGI modules
│   ├── memory/                  — Kernel memory, graph memory, Milvus
│   ├── causal/                  — Advanced causal inference
│   └── domains/                 — 60+ astrophysics modules
├── astra-live/index.html        — Dashboard frontend
└── requirements.txt             — Dependencies
```

### 2.3 Discovery Engine — OODA Cycle

**File**: `astra_live_backend/engine.py` — `class DiscoveryEngine`

**Cycle flow** (`run_cycle()`):
```
safety.can_run_cycle() → orient() → select() → investigate() → evaluate()
→ update() → degradation_check → theory_engine.tick() → discovery_memory.compact()
→ _manage_hypothesis_lifecycle() → compute_state_vector()
→ anomaly_detector.check() → arbiter.evaluate_cycle()
```

**Orient** — Scans data feeds (no semantic search — key gap for MemPalace integration)
**Select** — Ranks hypotheses: `score = info_gain * 0.4 + novelty * 0.3 + testability * 0.3`
**Investigate** — Dispatches to domain handlers (up to 8 targets/cycle):
  - Astrophysics: hubble, galaxy, exoplanets, stellar, star_formation, gw_events, cmb, transients, time_domain
  - Multi-domain: economics, climate, epidemiology, cryptography, crossdomain, crosslink
**Evaluate** — Statistical battery, FDR correction, discovery recording
**Update** — Bayesian updates, hypothesis generation from memory, pruning

### 2.4 Hypothesis Lifecycle

**Phases**: PROPOSED → SCREENING → TESTING → VALIDATED → PUBLISHED / ARCHIVED

**Transitions**: Based on confidence thresholds:
- PROPOSED → SCREENING: conf ≥ 0.3
- SCREENING → TESTING: score > 0.55
- TESTING → VALIDATED: conf ≥ 0.6
- VALIDATED → PUBLISHED: requires human approval
- → ARCHIVED: conf < 0.2 after 3+ tests

**Bayesian updates**: Likelihood ratios based on p-values, clamped to [0.01, 0.99]

### 2.5 Discovery Memory — THE KEY INTEGRATION POINT ★★★

**File**: `astra_live_backend/discovery_memory.py` — `class DiscoveryMemory` (677 LOC)

**Data structures**:
```python
@dataclass
class DiscoveryRecord:
    id: str              # "D0001"
    timestamp: float
    cycle: int
    hypothesis_id: str
    domain: str          # "Astrophysics", "Economics", etc.
    finding_type: str    # "scaling", "correlation", "bimodality", "anomaly", "causal"
    variables: list
    statistic: float
    p_value: float
    description: str
    data_source: str
    strength: float      # 0-1 composite
    follow_ups_generated: int = 0
    verified: bool = False
    effect_size: float = None
    metadata: dict = None

@dataclass
class MethodOutcome:
    method_name: str
    hypothesis_id: str
    domain: str
    timestamp: float
    cycle: int
    data_points: int
    tests_run: int
    significant_results: int
    novelty_signals: int
    confidence_delta: float
    success: bool

@dataclass
class ExplorationState:
    data_source: str
    variable_pairs_tested: dict
    last_explored: float
    total_explorations: int
    novelty_rate: float
```

**SQLite schema**: 3 tables — `discoveries`, `method_outcomes`, `generated_hypotheses`

**Complete public interface** (13 methods):
```python
class DiscoveryMemory:
    # Recording
    record_discovery(hypothesis_id, domain, finding_type, variables,
                     statistic, p_value, description, data_source,
                     sample_size=0, effect_size=None, metadata=None) → DiscoveryRecord
    record_method_outcome(method_name, hypothesis_id, domain, cycle,
                          data_points, tests_run, significant_results,
                          novelty_signals, confidence_delta, success)
    record_generated_hypothesis(source_discovery_id, hypothesis_text, domain)

    # Querying
    get_strong_discoveries(min_strength=0.5, max_age_cycles=50, current_cycle=0) → List[DiscoveryRecord]
    get_unexplored_variable_pairs(data_source) → List[Tuple[str, str]]
    get_best_methods(domain=None) → List[Tuple[str, float]]
    get_hot_domains(top_n=3) → List[Tuple[str, float]]
    get_discovery_graph() → Dict

    # Maintenance
    compact_if_needed()
    get_persistence_stats() → Dict
    compute_improvement_metrics() → Dict
    to_dict() → dict
```

**Where it's consumed**:
1. `DiscoveryEngine.__init__()` — creates instance
2. `investigate()` — records method outcomes
3. `evaluate()` — records discoveries
4. `_generate_discovery_guided_hypotheses()` — queries strong discoveries
5. `_propose_from_unexplored_pairs()` — queries exploration state
6. `run_cycle()` — calls compact_if_needed()
7. `HypothesisGenerator` — takes DiscoveryMemory as constructor param
8. `AdaptiveStrategist` — takes DiscoveryMemory as constructor param
9. `DegradationDetector.check_after_cycle()` — takes DiscoveryMemory

### 2.6 Knowledge Graph

**File**: `astra_live_backend/knowledge_graph.py` — `class DynamicKnowledgeGraph` (996 LOC)

Uses **networkx MultiDiGraph** + **SQLite** for persistence. Much more complex than MemPalace's:
- Typed entities (`EntityType` enum: 10 types)
- Typed relations (`RelationType` enum: 16 types)
- Belief propagation across the graph
- Knowledge gap detection
- Cross-domain analogy discovery
- Contradiction detection

### 2.7 Causal Inference

**File**: `astra_live_backend/causal.py`
- `pc_algorithm()` — Phase 1: conditional independence, Phase 2: v-structures, Phase 3: Meek rules
- `fci_algorithm()` — Handles latent confounders
- `test_intervention()` — do-calculus inspired, bootstrap CI
- Returns `CausalGraph` with `CausalEdge` objects

### 2.8 Safety Architecture

5-state machine: NOMINAL → PAUSED → SAFE_MODE → STOPPED → LOCKDOWN
- Arbiter: 6 weighted signals → GO/NO_GO/ABORT
- Circuit breakers: anomaly, alignment, failure detection
- Phased autonomy: SHADOW → SUPERVISED → SEMI_AUTONOMOUS → AUTONOMOUS

### 2.9 FastAPI Endpoints (89+)

Organized into: Engine, Hypotheses, Discovery Memory, Science, Knowledge Graph, Safety, Data Sources, Verification, Export, Literature, Multi-Agent, Agenda, Cognitive, Stigmergy

### 2.10 Dashboard

Single-page HTML app using Chart.js + D3.js with dark space theme. Hypothesis funnel, domain distribution, confidence radar, activity log, causal graphs.

### 2.11 Dependencies

```
fastapi, uvicorn, numpy, scipy, scikit-learn, pandas, matplotlib,
requests, beautifulsoup4, aiohttp, psutil, pytest
```
Plus implicit: networkx, threading, sqlite3

---

## Part 3: Integration Point Analysis

### 3.1 Primary Integration: DiscoveryMemory → Palace

**What needs to happen**: Augment ASTRA-dev's `DiscoveryMemory` with MemPalace's palace storage and semantic search while maintaining backward compatibility.

**Palace mapping**:
| ASTRA Concept | Palace Equivalent |
|--------------|-------------------|
| domain ("Astrophysics", "Economics") | Wing (`wing_astrophysics`, `wing_economics`) |
| hypothesis_id ("H001") | Room (`room_H001`) |
| finding_type ("scaling", "causal") | Metadata tag |
| DiscoveryRecord | Drawer (text = description, metadata = all fields) |
| MethodOutcome | Drawer in methods room |

### 3.2 Knowledge Graph Bridge

**Challenge**: Two different knowledge graph implementations:
- MemPalace: Simple SQLite triples (subject, predicate, object) with temporal bounds
- ASTRA: Typed entities, typed relations, networkx graph, belief propagation

**Strategy**: Use MemPalace's KG as the persistent store, bridge ASTRA's richer type system via predicate naming conventions and entity properties.

### 3.3 Semantic Search Gap

**The orient() method has NO semantic search** — it only scans cached data and stigmergy signals. Injecting MemPalace's `search_memories()` during Orient would:
- Surface relevant past discoveries before hypothesis scoring
- Enable cross-domain discovery via semantic similarity
- Dramatically improve hypothesis generation quality

### 3.4 Dependency Compatibility

| Concern | Status |
|---------|--------|
| Python version | Use 3.10+ (ASTRA-dev requirement) |
| chromadb | MemPalace only — no conflict |
| numpy/scipy/pandas | ASTRA only — chromadb transitively brings numpy |
| fastapi | ASTRA only — no conflict |
| sqlite3 | Both use it — stdlib, no conflict |
| networkx | ASTRA only — no conflict |

**Verdict**: Zero conflicts. All dependencies can coexist.

### 3.5 Consumers Requiring Adapter

These ASTRA components take `DiscoveryMemory` and must work with the augmented version:
1. `DiscoveryEngine` — direct attribute `self.discovery_memory`
2. `HypothesisGenerator.__init__(discovery_memory: DiscoveryMemory)`
3. `AdaptiveStrategist.__init__(discovery_memory: DiscoveryMemory)`
4. `DegradationDetector.check_after_cycle(discovery_memory)`

All access through the 13-method public interface → **adapter must implement exactly these 13 methods**.

---

## Part 4: Key Observations & Risks

### 4.1 Architecture Observations
- MemPalace is elegantly simple (2 deps, flat ChromaDB storage)
- ASTRA-dev is complex and monolithic (3384-line engine.py)
- MemPalace's "closet" level doesn't exist in code — we can introduce it if needed
- ASTRA's `DynamicKnowledgeGraph` is far more sophisticated than MemPalace's — we need a bridge, not a replacement
- ASTRA's in-memory deques (`deque(maxlen=500)`) are a performance bottleneck — palace storage + semantic search should improve recall

### 4.2 Risks
1. **ChromaDB cold-start latency**: First query triggers model download (~500MB). Must handle in production.
2. **Embedding model mismatch**: MemPalace uses all-MiniLM-L6-v2 default. Scientific text may benefit from a domain-specific model.
3. **ASTRA engine.py coupling**: Heavy use of `self.discovery_memory` attribute access throughout 3384 lines. Must be a drop-in replacement.
4. **Knowledge graph impedance mismatch**: MemPalace's simple (s,p,o) triples vs ASTRA's typed entity/relation model with belief propagation.
