"""
MemPalace-AGI: Autonomous research with perfect memory.

Integrates MemPalace's spatial memory architecture with ASTRA-dev's
autonomous scientific discovery engine.
"""

import logging

# ChromaDB 0.6.x ships a Posthog telemetry client whose capture() signature is
# incompatible with the bundled posthog library, producing noisy stderr warnings
# on every client operation.  Silence just that logger.  (Matches upstream
# MemPalace fix from PR #236.)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

__version__ = "0.1.0"

from .config import IntegrationConfig
from .palace_discovery_memory import PalaceDiscoveryMemory, RecordResult, ConsolidationState
from .memory_augmented_orient import MemoryAugmentedOrient, WorkingMemoryBuffer, WorkingMemoryItem
from .safety_constraints import HypothesisSafetyChecker, SafetyConstraint
from .knowledge_graph_bridge import KnowledgeGraphBridge
from .domain_specialists import DomainSpecialistManager
from .unified_mcp_server import UnifiedMCPServer
from .orchestrator import MemPalaceAGI
from .palace_handles import PalaceHandleManager, MemoryHandle, HeatMetrics
from .kg_pheromones import PheromoneManager
from .kg_pathfinder import (
    GraphAdapter,
    SemanticAStarPathfinder,
    PathResult,
    find_knowledge_path,
)
from .wikidata_enricher import (
    WikidataClient,
    WikidataEnricher,
    WikidataEntity as WDEntity,
    WikidataRelation,
    EnrichmentResult,
)

__all__ = [
    "IntegrationConfig",
    "PalaceDiscoveryMemory",
    "RecordResult",
    "ConsolidationState",
    "MemoryAugmentedOrient",
    "WorkingMemoryBuffer",
    "WorkingMemoryItem",
    "HypothesisSafetyChecker",
    "SafetyConstraint",
    "KnowledgeGraphBridge",
    "DomainSpecialistManager",
    "UnifiedMCPServer",
    "MemPalaceAGI",
    # RLM Handle Protocol
    "PalaceHandleManager",
    "MemoryHandle",
    "HeatMetrics",
    # Phase 18: STAN_X v8 ports
    "PheromoneManager",
    "GraphAdapter",
    "SemanticAStarPathfinder",
    "PathResult",
    "find_knowledge_path",
    "WikidataClient",
    "WikidataEnricher",
    "WDEntity",
    "WikidataRelation",
    "EnrichmentResult",
]
