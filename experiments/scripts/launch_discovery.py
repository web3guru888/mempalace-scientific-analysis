#!/usr/bin/env python3
"""
MemPalace-AGI — Full Autonomous Discovery Mode
================================================
Launches the integrated system for sustained discovery cycles with real data.
Every cycle: ORIENT (semantic memory search) → SELECT → INVESTIGATE (real APIs) → 
EVALUATE (statistical tests) → UPDATE (palace storage + KG triples).

Discoveries flow from NASA, Pantheon, Gaia, SDSS, World Bank, GISTEMP, WHO
into the MemPalace architecture (wings/rooms/closets/drawers) with ChromaDB
semantic search and a temporal knowledge graph.

Usage:
    python scripts/launch_discovery.py [--cycles N] [--interval SECS] [--palace-dir DIR]
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

# ─── Path setup ───────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))

# ─── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("discovery_launch")

# Reduce noisy loggers
for noisy in ["chromadb", "httpx", "urllib3", "onnxruntime", "sentence_transformers"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)


def run_discovery(cycles: int, interval: float, palace_dir: str, run_dir: str):
    """Run N discovery cycles and collect results."""
    
    from mempalace_agi.orchestrator import MemPalaceAGI
    from mempalace_agi.config import IntegrationConfig

    config = IntegrationConfig()
    config.palace_path = palace_dir

    logger.info("=" * 70)
    logger.info("  MemPalace-AGI — AUTONOMOUS DISCOVERY MODE")
    logger.info("=" * 70)
    logger.info(f"  Palace directory: {palace_dir}")
    logger.info(f"  Cycles planned: {cycles}")
    logger.info(f"  Interval: {interval}s between cycles")
    logger.info(f"  Run output: {run_dir}")
    logger.info("=" * 70)

    # Initialize
    t0 = time.time()
    agi = MemPalaceAGI(config=config)
    init_time = time.time() - t0
    logger.info(f"System initialized in {init_time:.1f}s")
    logger.info(f"Engine has {len(agi.engine.store.all())} hypotheses loaded")
    logger.info(f"Palace starts with {agi.palace_memory._collection.count()} drawers")

    # Track cumulative metrics per cycle
    cycle_log = []
    start_discoveries = len(agi.palace_memory.discoveries)
    start_drawers = agi.palace_memory._collection.count()

    for i in range(1, cycles + 1):
        logger.info(f"\n{'─' * 50}")
        logger.info(f"  CYCLE {i}/{cycles}")
        logger.info(f"{'─' * 50}")

        cycle_start = time.time()
        try:
            result = agi.run_augmented_cycle()
            elapsed = time.time() - cycle_start

            # Collect metrics
            n_discoveries = len(agi.palace_memory.discoveries)
            n_drawers = agi.palace_memory._collection.count()
            kg = agi.kg_bridge.stats()
            
            # Count discoveries by domain
            domain_counts = {}
            for d in agi.palace_memory.discoveries:
                dom = getattr(d, 'domain', 'unknown')
                domain_counts[dom] = domain_counts.get(dom, 0) + 1

            # Get the latest discoveries from this cycle
            prev_total = start_discoveries
            for prev in reversed(cycle_log):
                if "total_discoveries" in prev:
                    prev_total = prev["total_discoveries"]
                    break
            new_this_cycle = n_discoveries - prev_total
            
            metric = {
                "cycle": i,
                "engine_cycle": result.get("cycle", "?"),
                "elapsed_seconds": round(elapsed, 1),
                "total_discoveries": n_discoveries,
                "new_discoveries": new_this_cycle,
                "palace_drawers": n_drawers,
                "kg_triples": kg.get("total_triples", kg.get("triples", 0)),
                "kg_entities": kg.get("total_entities", kg.get("entities", 0)),
                "domains": domain_counts,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success",
            }
            cycle_log.append(metric)

            logger.info(f"  ✅ Cycle {i} completed in {elapsed:.1f}s")
            logger.info(f"     New discoveries: +{new_this_cycle} (total: {n_discoveries})")
            logger.info(f"     Palace drawers: {n_drawers}")
            logger.info(f"     KG: {metric['kg_triples']} triples, {metric['kg_entities']} entities")
            logger.info(f"     Domains: {domain_counts}")

            # Show the latest discoveries
            if new_this_cycle > 0:
                all_disc = agi.palace_memory.discoveries
                show_count = min(new_this_cycle, 5)
                for idx in range(max(0, len(all_disc) - show_count), len(all_disc)):
                    d = all_disc[idx]
                    logger.info(f"     📍 [{d.domain}] {d.finding_type}: {d.variables} "
                              f"(strength={d.strength:.3f}, p={d.p_value:.4f})")

        except Exception as ex:
            elapsed = time.time() - cycle_start
            logger.error(f"  ❌ Cycle {i} FAILED in {elapsed:.1f}s: {ex}")
            cycle_log.append({
                "cycle": i,
                "elapsed_seconds": round(elapsed, 1),
                "status": "error",
                "error": str(ex),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Save progress after each cycle
        progress_file = os.path.join(run_dir, "cycle_log.json")
        with open(progress_file, "w") as f:
            json.dump(cycle_log, f, indent=2)

        # Wait between cycles (except after last)
        if i < cycles:
            logger.info(f"  ⏱️  Waiting {interval}s before next cycle...")
            time.sleep(interval)

    # ─── Final Summary ────────────────────────────────────────────
    total_elapsed = time.time() - t0
    successful = [c for c in cycle_log if c["status"] == "success"]
    failed = [c for c in cycle_log if c["status"] == "error"]

    logger.info(f"\n{'=' * 70}")
    logger.info(f"  DISCOVERY RUN COMPLETE")
    logger.info(f"{'=' * 70}")
    logger.info(f"  Total time: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    logger.info(f"  Cycles: {len(successful)} succeeded, {len(failed)} failed")
    
    if successful:
        final = successful[-1]
        logger.info(f"  Total discoveries: {final['total_discoveries']} (+{final['total_discoveries'] - start_discoveries} new)")
        logger.info(f"  Palace drawers: {final['palace_drawers']} (+{final['palace_drawers'] - start_drawers} new)")
        logger.info(f"  KG triples: {final['kg_triples']}")
        logger.info(f"  KG entities: {final['kg_entities']}")
        logger.info(f"  Domains: {final['domains']}")
    
    if failed:
        logger.info(f"  Errors:")
        for f_ in failed:
            logger.info(f"    Cycle {f_['cycle']}: {f_.get('error', 'unknown')}")

    # Save final summary
    summary = {
        "run_id": os.path.basename(run_dir),
        "start_time": datetime.fromtimestamp(t0, tz=timezone.utc).isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "total_seconds": round(total_elapsed, 1),
        "cycles_planned": cycles,
        "cycles_succeeded": len(successful),
        "cycles_failed": len(failed),
        "palace_dir": palace_dir,
        "final_discoveries": successful[-1]["total_discoveries"] if successful else 0,
        "final_drawers": successful[-1]["palace_drawers"] if successful else 0,
        "final_kg_triples": successful[-1]["kg_triples"] if successful else 0,
        "final_kg_entities": successful[-1]["kg_entities"] if successful else 0,
        "final_domains": successful[-1]["domains"] if successful else {},
        "cycle_log": cycle_log,
    }

    summary_file = os.path.join(run_dir, "summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"\n  Summary saved: {summary_file}")
    logger.info(f"  Cycle log: {progress_file}")

    # Also produce a human-readable report
    report_lines = [
        f"# MemPalace-AGI Discovery Run — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        f"**Duration**: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)",
        f"**Cycles**: {len(successful)} succeeded, {len(failed)} failed out of {cycles} planned",
        "",
        "## Results",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Discoveries | {summary['final_discoveries']} |",
        f"| Palace Drawers | {summary['final_drawers']} |",
        f"| KG Triples | {summary['final_kg_triples']} |",
        f"| KG Entities | {summary['final_kg_entities']} |",
        "",
        "## Per-Cycle Breakdown",
        "",
        "| Cycle | Time | New Disc | Total | Drawers | KG Triples | Status |",
        "|-------|------|----------|-------|---------|------------|--------|",
    ]
    for c in cycle_log:
        report_lines.append(
            f"| {c['cycle']} | {c['elapsed_seconds']}s | "
            f"{c.get('new_discoveries', '?')} | {c.get('total_discoveries', '?')} | "
            f"{c.get('palace_drawers', '?')} | {c.get('kg_triples', '?')} | "
            f"{'✅' if c['status'] == 'success' else '❌ ' + c.get('error', '')[:40]} |"
        )
    
    if successful:
        report_lines.extend([
            "",
            "## Domain Distribution",
            "",
            "| Domain | Discoveries |",
            "|--------|-------------|",
        ])
        for dom, cnt in sorted(summary["final_domains"].items(), key=lambda x: -x[1]):
            report_lines.append(f"| {dom} | {cnt} |")

    report_file = os.path.join(run_dir, "report.md")
    with open(report_file, "w") as f:
        f.write("\n".join(report_lines))

    # Copy report to shared KB
    import shutil
    kb_report = f"/shared/kb/mempalace-agi-reports/discovery-run-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M')}.md"
    shutil.copy2(report_file, kb_report)
    logger.info(f"  Report copied to: {kb_report}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MemPalace-AGI Autonomous Discovery")
    parser.add_argument("--cycles", type=int, default=10, help="Number of discovery cycles")
    parser.add_argument("--interval", type=float, default=10.0, help="Seconds between cycles")
    parser.add_argument("--palace-dir", type=str, default=None, help="Palace storage directory (default: auto)")
    args = parser.parse_args()

    # Create run directory
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = f"/shared/mempalace-agi/discovery_runs/run-{run_id}"
    os.makedirs(run_dir, exist_ok=True)

    # Palace directory
    palace_dir = args.palace_dir or os.path.join(run_dir, "palace")
    os.makedirs(palace_dir, exist_ok=True)

    summary = run_discovery(
        cycles=args.cycles,
        interval=args.interval,
        palace_dir=palace_dir,
        run_dir=run_dir,
    )

    sys.exit(0 if summary["cycles_failed"] == 0 else 1)
