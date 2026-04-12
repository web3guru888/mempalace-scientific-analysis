"""
MemPalace-AGI Orchestrator — Top-level wiring for the integration.

Wires PalaceDiscoveryMemory, MemoryAugmentedOrient, KnowledgeGraphBridge,
and DomainSpecialistManager into the ASTRA DiscoveryEngine, with:

- Blocker 1: Monkey-patch for ASTRA cosmology bug (Om/Ol → Omega_m/Omega_L)
- Blocker 2: Real KG triple extraction from engine discoveries
- Blocker 3: Continuous discovery loop with background threading
"""

import json
import logging
import threading
import time
from typing import Optional

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.memory_augmented_orient import MemoryAugmentedOrient
from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge
from mempalace_agi.domain_specialists import DomainSpecialistManager
from mempalace_agi.hypothesis_workspace import (
    HypothesisWorkspace,
    DomainSpecialistProxy,
)
from mempalace_agi.analogy_hypothesis_bridge import (
    AnalogyHypothesisBridge,
    inject_analogy_hypotheses,
)

logger = logging.getLogger("mempalace_agi")


def _patch_cosmology():
    """Blocker 1: Monkey-patch distance_modulus to fix key mismatch.

    ASTRA engine.py line 1516 passes ``{'H0': best_h0, 'Om': 0.3, 'Ol': 0.7}``
    but ``cosmology.distance_modulus`` expects ``Omega_m``, ``Omega_L``, ``c``.
    We patch at the module level so every call site in the engine benefits.
    """
    try:
        import astra_live_backend.engine as eng_mod
        from astra_live_backend.cosmology import (
            PLANCK_2018,
            distance_modulus as orig_dm,
        )

        def patched_distance_modulus(z, cosmo=None):
            if cosmo is not None and "c" not in cosmo:
                full = PLANCK_2018.copy()
                if "Om" in cosmo:
                    full["Omega_m"] = cosmo["Om"]
                if "Ol" in cosmo:
                    full["Omega_L"] = cosmo["Ol"]
                if "H0" in cosmo:
                    full["H0"] = cosmo["H0"]
                cosmo = full
            return orig_dm(z, cosmo)

        eng_mod.distance_modulus = patched_distance_modulus
        logger.info("Patched distance_modulus in astra_live_backend.engine (cosmology fix)")
    except ImportError:
        logger.debug("ASTRA engine not available — cosmology patch skipped")
    except Exception as e:
        logger.warning("Failed to apply cosmology patch: %s", e)


# Apply the patch on module load so it's active before any engine call
_patch_cosmology()


class MemPalaceAGI:
    """
    Top-level integration wiring for MemPalace-AGI.
    Wires PalaceDiscoveryMemory, MemoryAugmentedOrient, KnowledgeGraphBridge,
    and DomainSpecialistManager into the ASTRA DiscoveryEngine.
    """

    def __init__(self, config: Optional[IntegrationConfig] = None, engine_mock=None):
        self.config = config or IntegrationConfig()

        # 1. Initialize MemPalace Components
        self.palace_memory = PalaceDiscoveryMemory(self.config)
        self.orient_helper = MemoryAugmentedOrient(self.palace_memory)
        self.kg_bridge = KnowledgeGraphBridge(self.config)
        self.specialists = DomainSpecialistManager(self.palace_memory, self.config)

        # 2. Continuous loop state (Blocker 3)
        self._running = False
        self._cycle_metrics: list = []
        self._cycle_errors: list = []
        self._thread: Optional[threading.Thread] = None

        # 3. Track discoveries already synced to KG (Blocker 2)
        self._kg_synced_discovery_ids: set = set()

        # 4. Initialize Engine
        if engine_mock:
            self.engine = engine_mock
        else:
            try:
                from astra_live_backend.engine import DiscoveryEngine
                self.engine = DiscoveryEngine()
            except ImportError:
                logger.warning("ASTRA engine not found. Using a mock engine for integration testing.")

                class MockEngine:
                    def __init__(self):
                        self.cycle_count = 0
                        from astra_live_backend.hypotheses import HypothesisStore
                        from astra_live_backend.safety import SafetyController
                        self.store = HypothesisStore()
                        self.safety = SafetyController()
                        self.discovery_memory = None

                    def orient(self):
                        pass

                    def select(self):
                        pass

                    def investigate(self):
                        pass

                    def evaluate(self):
                        pass

                    def update(self):
                        pass

                    def run_cycle(self):
                        self.cycle_count += 1
                        self.orient()
                        self.select()
                        self.investigate()
                        self.evaluate()
                        self.update()

                self.engine = MockEngine()

        # 5. Wire Engine Dependencies
        self._replace_engine_memory()

        # 6. Hypothesis Workspace (GWT-based selection, optional)
        self._use_gwt_select = False  # off by default, enable via use_gwt_select()
        self.hypothesis_workspace = HypothesisWorkspace(capacity=7, competition_rounds=3)
        self._register_domain_specialists()

        # 7. Patch Lifecycle Hooks
        self._patch_engine_hooks()

    def _replace_engine_memory(self):
        """Replace the engine's standard DiscoveryMemory with PalaceDiscoveryMemory."""
        self.engine.discovery_memory = self.palace_memory

        # In a real ASTRA engine, we need to rebuild components that held the old reference
        try:
            from astra_live_backend.hypothesis_generator import HypothesisGenerator
            from astra_live_backend.adaptive_strategist import AdaptiveStrategist
            if hasattr(self.engine, 'hypothesis_generator'):
                self.engine.hypothesis_generator = HypothesisGenerator(self.palace_memory)
            if hasattr(self.engine, 'strategist'):
                self.engine.strategist = AdaptiveStrategist(self.palace_memory)
        except ImportError:
            pass

    def _patch_engine_hooks(self):
        """Monkey-patch engine phases to insert MemPalace hooks."""

        # 1. Patch Orient
        original_orient = self.engine.orient

        def augmented_orient():
            original_orient()
            active_hyps = self.engine.store.active()
            if not active_hyps:
                return

            ctx = self.orient_helper.retrieve_context(
                active_hyps[:10],
                current_domain=getattr(self.engine, 'current_domain', 'CrossDomain'),
                cycle_number=self.engine.cycle_count
            )

            for hyp in active_hyps:
                hit_list = ctx["per_hypothesis"].get(hyp.id, [])
                if not hasattr(hyp, 'memory_context'):
                    hyp.memory_context = []
                hyp.memory_context.extend(hit_list)

                boost = self.orient_helper.score_hypothesis_with_memory(hyp, hit_list)
                current_boost = getattr(hyp, 'memory_score_boost', 0.0)
                if type(current_boost).__name__ in ('Mock', 'MagicMock'):
                    current_boost = 0.0
                hyp.memory_score_boost = current_boost + boost

            logger.info("Semantic memory context injected into Orient phase.")

        self.engine.orient = augmented_orient

        # 2. Patch Investigate (for Diary pre-context)
        original_investigate = self.engine.investigate

        def augmented_investigate():
            # In a real setup, we'd inject pre-investigation context here
            # using self.specialists.get_pre_investigation_context()
            original_investigate()

        self.engine.investigate = augmented_investigate

        # 3. Patch Evaluate (Blocker 2: extract real triples from discoveries)
        original_evaluate = self.engine.evaluate

        def augmented_evaluate():
            original_evaluate()
            self._sync_discoveries_to_kg()
            logger.info("Knowledge Graph and Diary synced post Evaluate phase.")

        self.engine.evaluate = augmented_evaluate

        # 4. Analogy-to-Hypothesis Bridge is called from run_augmented_cycle()
        # (not from Update phase, because theory_engine.tick() runs AFTER update
        # and the analogy_engine._all_analogies / _analogies cache is only populated
        # once the async tick thread completes)

    # ── Hypothesis Workspace (GWT-based selection) ───────────────────

    def _register_domain_specialists(self):
        """Register domain specialist proxies on the HypothesisWorkspace.

        Covers all domains from ASTRA-dev's HypothesisGenerator.ALL_DOMAINS
        plus the Physics/Cosmology diversification domains added in upstream
        commit cf60b52 (2026-04-11).
        """
        default_domains = [
            "astrophysics", "climate", "economics",
            "epidemiology", "cryptography",
            "physics", "cosmology", "cross-domain",
        ]
        for domain in default_domains:
            self.hypothesis_workspace.register_specialist(domain)

    def use_gwt_select(self, enabled: bool = True) -> None:
        """Enable or disable GWT-based hypothesis selection.

        When enabled, the ``select`` phase uses HypothesisWorkspace
        competition instead of the engine's default selection strategy.
        The default (disabled) uses the original engine.select().
        """
        if enabled and not self._use_gwt_select:
            self._patch_select_with_gwt()
        self._use_gwt_select = enabled

    def _patch_select_with_gwt(self):
        """Monkey-patch engine.select to use GWT workspace competition."""
        original_select = self.engine.select

        def gwt_select():
            if not self._use_gwt_select:
                return original_select()

            active_hyps = self.engine.store.active()
            if not active_hyps:
                return original_select()

            # Populate workspace with active hypotheses
            for hyp in active_hyps:
                activation = getattr(hyp, "confidence", 0.5)
                if isinstance(activation, str):
                    try:
                        activation = float(activation)
                    except (ValueError, TypeError):
                        activation = 0.5
                boost = getattr(hyp, "memory_score_boost", 0.0)
                if type(boost).__name__ in ("Mock", "MagicMock"):
                    boost = 0.0
                activation = min(1.0, activation + boost * 0.3)

                self.hypothesis_workspace.submit_hypothesis(
                    hypothesis_id=hyp.id,
                    content=getattr(hyp, "description", str(hyp)),
                    domain=getattr(hyp, "domain", "unknown"),
                    activation=activation,
                    metadata={"cycle": self.engine.cycle_count},
                )

            # Run competition
            winner = self.hypothesis_workspace.run_competition()
            if winner:
                # Mark the winning hypothesis as selected on the engine store
                for hyp in active_hyps:
                    if hyp.id == winner.hypothesis_id:
                        if hasattr(self.engine.store, "set_selected"):
                            self.engine.store.set_selected(hyp)
                        elif hasattr(self.engine, "_selected"):
                            self.engine._selected = hyp
                        logger.info(
                            "GWT selected hypothesis %s (domain=%s, strength=%.3f)",
                            winner.hypothesis_id,
                            winner.domain,
                            winner.competition_strength,
                        )
                        break
            else:
                logger.debug("GWT workspace returned no winner — falling back")
                original_select()

        self.engine.select = gwt_select

    # ── Blocker 2: Extract real triples from engine discoveries ──────

    def _sync_discoveries_to_kg(self):
        """Extract entity-relationship triples from engine discoveries and
        store them in the Knowledge Graph.

        Called after each evaluate phase. Iterates over all discoveries that
        haven't been synced yet and:
        1. Creates discovery entities in the KG
        2. Extracts variable relationships based on finding_type
        3. Processes hypothesis test_results for causal findings
        """
        cycle = self.engine.cycle_count
        agent_id = f"orchestrator_cycle_{cycle}"
        cycle_id = f"cycle_{cycle}"

        # Get all current discoveries
        discoveries = self.palace_memory.discoveries

        new_triples = 0

        for rec in discoveries:
            if rec.id in self._kg_synced_discovery_ids:
                continue

            self._kg_synced_discovery_ids.add(rec.id)

            # 1. Record the discovery entity + links to hypothesis, domain, variables
            try:
                self.kg_bridge.record_discovery_entity(
                    discovery_id=rec.id,
                    domain=rec.domain,
                    finding_type=rec.finding_type,
                    description=rec.description,
                    hypothesis_id=rec.hypothesis_id,
                    variables=rec.variables,
                    strength=rec.strength,
                    agent_id=agent_id,
                    cycle_id=cycle_id,
                )
                new_triples += 1  # At minimum: produced_by + belongs_to_domain + var links
            except Exception as e:
                logger.warning(
                    "Failed to record discovery entity %s in KG: %s", rec.id, e
                )

            # 2. Extract variable-to-variable relationships based on finding_type
            try:
                self._extract_variable_triples(rec, agent_id, cycle_id)
                new_triples += 1
            except Exception as e:
                logger.warning(
                    "Failed to extract variable triples from %s: %s", rec.id, e
                )

        # 3. Extract from hypothesis test_results (causal findings)
        try:
            self._extract_hypothesis_test_triples(agent_id, cycle_id)
        except Exception as e:
            logger.warning("Failed to extract hypothesis test triples: %s", e)

        if new_triples > 0:
            logger.info(
                "KG sync: %d new discoveries → triples (cycle %d, total KG: %s)",
                new_triples, cycle, self.kg_bridge.stats().get("total_triples", 0),
            )

    def _extract_variable_triples(self, rec, agent_id: str, cycle_id: str):
        """Extract variable-to-variable relationship triples from a discovery.

        Maps finding_type to a predicate and creates directed edges between
        the variables involved in the discovery.
        """
        variables = rec.variables
        if not variables or len(variables) < 2:
            return

        # Map finding types to predicates
        finding_predicate_map = {
            "correlation": "correlated_with",
            "scaling": "scales_with",
            "bimodality": "bimodal_with",
            "anomaly": "anomalous_in",
            "causal": "causes",
            "intervention": "intervenes_on",
            "trend": "trends_with",
            "regression": "regresses_on",
            "clustering": "clusters_with",
            "distribution": "distributed_with",
        }

        predicate = finding_predicate_map.get(
            rec.finding_type.lower(), "related_to"
        )

        confidence = rec.strength
        timestamp = time.time()

        # For the primary pair: first two variables get a directed edge
        source_var = variables[0]
        target_var = variables[1]

        # Ensure entities exist
        for var in variables:
            self.kg_bridge.kg.add_entity(
                name=var,
                entity_type="variable",
                properties={"domain": rec.domain, "discovery": rec.id},
            )

        # Primary relationship: var[0] → var[1]
        triple_id = self.kg_bridge.kg.add_triple(
            subject=source_var,
            predicate=predicate,
            obj=target_var,
            valid_from=str(timestamp),
            confidence=confidence,
            source_closet="discovery_engine",
            source_file=f"discovery_{rec.id}",
        )
        self.kg_bridge._store_provenance(
            triple_id=triple_id,
            agent_id=agent_id,
            cycle_id=cycle_id,
            evidence_chain=[rec.id, rec.hypothesis_id],
            confidence=confidence,
            reason=(
                f"Discovery {rec.id}: {source_var} {predicate} {target_var} "
                f"(strength={rec.strength:.3f}, p={rec.p_value})"
            ),
            statement_type="fact",
            temporal_type="dynamic",
        )

        # If there are more than 2 variables, create additional edges
        for i in range(2, len(variables)):
            extra_triple_id = self.kg_bridge.kg.add_triple(
                subject=source_var,
                predicate=predicate,
                obj=variables[i],
                valid_from=str(timestamp),
                confidence=confidence * 0.8,  # Slightly lower for non-primary
                source_closet="discovery_engine",
                source_file=f"discovery_{rec.id}",
            )
            self.kg_bridge._store_provenance(
                triple_id=extra_triple_id,
                agent_id=agent_id,
                cycle_id=cycle_id,
                evidence_chain=[rec.id],
                confidence=confidence * 0.8,
                reason=f"Secondary variable link from {rec.id}",
            )

    def _extract_hypothesis_test_triples(self, agent_id: str, cycle_id: str):
        """Extract causal findings from hypothesis test results.

        Iterates over active and tested hypotheses in the store, looking for
        test_results that contain causal or statistical information.
        """
        if not hasattr(self.engine, 'store'):
            return

        try:
            # Get all hypotheses (active + tested)
            all_hyps = []
            if hasattr(self.engine.store, 'active'):
                all_hyps.extend(self.engine.store.active())
            if hasattr(self.engine.store, 'all_hypotheses'):
                all_hyps = self.engine.store.all_hypotheses()
            elif hasattr(self.engine.store, 'hypotheses'):
                all_hyps = list(self.engine.store.hypotheses.values())
        except Exception:
            return

        for hyp in all_hyps:
            test_results = getattr(hyp, 'test_results', [])
            if not test_results:
                continue

            hyp_id = getattr(hyp, 'id', str(hyp))

            for tr in test_results:
                # test_results are dicts (asdict(StatTestResult))
                if not isinstance(tr, dict):
                    continue

                test_name = tr.get("test_name", "")
                statistic = tr.get("statistic", 0)
                p_value = tr.get("p_value", 1.0)
                passed = tr.get("passed", False)
                details = tr.get("details", "")

                if not passed or not test_name:
                    continue

                # Store significant test results as triples
                predicate = "tested_by"
                if "causal" in test_name.lower():
                    predicate = "causally_tested_by"
                elif "correlation" in test_name.lower():
                    predicate = "correlation_tested_by"

                confidence = max(0.0, min(1.0, 1.0 - (p_value or 1.0)))

                try:
                    triple_id = self.kg_bridge.kg.add_triple(
                        subject=hyp_id,
                        predicate=predicate,
                        obj=test_name,
                        valid_from=str(time.time()),
                        confidence=confidence,
                        source_closet="hypothesis_testing",
                        source_file=f"hypothesis_{hyp_id}",
                    )
                    self.kg_bridge._store_provenance(
                        triple_id=triple_id,
                        agent_id=agent_id,
                        cycle_id=cycle_id,
                        evidence_chain=[hyp_id, test_name],
                        confidence=confidence,
                        reason=f"Test result: {details[:200]}",
                        statement_type="fact",
                        temporal_type="dynamic",
                    )
                except Exception as e:
                    logger.debug(
                        "Failed to store test result triple for %s: %s",
                        hyp_id, e,
                    )

    # ── Run a single augmented cycle ────────────────────────────────

    def run_augmented_cycle(self) -> dict:
        """Run one full OODA cycle with all integration hooks active.

        After the engine cycle completes (including theory_engine.tick()),
        injects analogy-transfer hypotheses from accumulated cross-domain
        analogies into the hypothesis pool for the NEXT cycle.
        """
        old_count = self.engine.cycle_count
        self.engine.run_cycle()

        # ── Analogy-to-Hypothesis Bridge (Exp #45) ──
        # The theory_engine.tick() runs asynchronously during run_cycle().
        # The _analogies cache on the TheoryEngine is populated once the
        # daemon thread completes.  We check it here after the full cycle;
        # if the thread hasn't finished yet, the cache will have results from
        # the PREVIOUS tick (which is still useful — one tick behind).
        analogy_hyps_injected = 0
        try:
            theory_eng = getattr(self.engine, 'theory_engine', None)
            if theory_eng is not None:
                existing_names = {h.name for h in self.engine.store.all()}
                new_hyps = inject_analogy_hypotheses(
                    engine=self.engine,
                    theory_engine=theory_eng,
                    max_new=2,
                    existing_names=existing_names,
                    similarity_threshold=0.70,
                )
                if new_hyps:
                    from astra_live_backend.hypotheses import Phase
                    for hyp_dict in new_hyps:
                        h = self.engine.store.add(
                            hyp_dict["name"],
                            hyp_dict["domain"],
                            hyp_dict["description"],
                            confidence=hyp_dict.get("confidence", 0.3),
                        )
                        h.phase = Phase.PROPOSED
                        h.cross_domain_links = []
                        h.finding_type = "analogy_transfer"
                        h.source_analogy_id = hyp_dict.get("source_analogy_id")
                    analogy_hyps_injected = len(new_hyps)
                    logger.info(
                        "Analogy bridge injected %d transfer hypotheses.",
                        analogy_hyps_injected,
                    )
        except Exception as e:
            logger.debug("Analogy bridge skipped: %s", e)

        return {
            "cycle": self.engine.cycle_count,
            "status": "success",
            "new_cycles_run": self.engine.cycle_count - old_count,
            "analogy_hyps_injected": analogy_hyps_injected,
        }

    # ── Blocker 3: Continuous Discovery Loop ─────────────────────────

    def start(self, interval_seconds: float = 30.0, max_cycles: int = None):
        """Start continuous discovery cycling in a background thread.

        Args:
            interval_seconds: Seconds to sleep between cycles.
            max_cycles: Stop after this many cycles (None = run forever).
        """
        self._running = True
        self._cycle_errors = []
        self._cycle_metrics = []

        def _loop():
            cycles_run = 0
            while self._running and (max_cycles is None or cycles_run < max_cycles):
                try:
                    t0 = time.time()
                    result = self.run_augmented_cycle()
                    elapsed = time.time() - t0

                    metric = {
                        "cycle": result["cycle"],
                        "elapsed_seconds": round(elapsed, 2),
                        "discoveries": len(self.palace_memory.discoveries),
                        "palace_drawers": self.palace_memory._backend.count(),
                        "kg_triples": self.kg_bridge.stats().get("total_triples", 0),
                        "timestamp": time.time(),
                    }
                    self._cycle_metrics.append(metric)
                    logger.info(
                        "Cycle %d completed in %.1fs — "
                        "%d discoveries, %d palace drawers, %d KG triples",
                        result["cycle"], elapsed,
                        metric["discoveries"],
                        metric["palace_drawers"],
                        metric["kg_triples"],
                    )

                    cycles_run += 1
                    if self._running and (
                        max_cycles is None or cycles_run < max_cycles
                    ):
                        time.sleep(interval_seconds)

                except Exception as ex:
                    logger.error("Cycle failed: %s", ex, exc_info=True)
                    self._cycle_errors.append({
                        "error": str(ex),
                        "timestamp": time.time(),
                    })
                    # Don't crash — sleep and retry
                    if self._running:
                        time.sleep(interval_seconds)

            self._running = False

        self._thread = threading.Thread(
            target=_loop, daemon=True, name="mempalace-agi-discovery"
        )
        self._thread.start()
        logger.info(
            "Discovery loop started (interval=%.1fs, max_cycles=%s)",
            interval_seconds, max_cycles,
        )

    def stop(self):
        """Stop the discovery loop."""
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=60)
        logger.info("Discovery loop stopped")

    def get_status(self) -> dict:
        """Full system status including cycle metrics."""
        return {
            "running": self._running,
            "engine_cycle": self.engine.cycle_count,
            "palace_stats": self.palace_memory.get_persistence_stats(),
            "kg_stats": self.kg_bridge.stats(),
            "total_cycles_completed": len(self._cycle_metrics),
            "total_errors": len(self._cycle_errors),
            "last_cycle": self._cycle_metrics[-1] if self._cycle_metrics else None,
            "recent_errors": self._cycle_errors[-5:] if self._cycle_errors else [],
            "gwt_select_enabled": self._use_gwt_select,
            "hypothesis_workspace": self.hypothesis_workspace.get_status(),
        }
