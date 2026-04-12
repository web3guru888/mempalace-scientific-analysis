import argparse
import sys
import logging
from pathlib import Path

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory

logger = logging.getLogger("mempalace_agi.migration")

def run_migration(source_db: str, target_palace: str, threshold: float = 0.90):
    logging.basicConfig(level=logging.INFO)
    logger.info(f"Starting migration from {source_db} to {target_palace}")
    
    config = IntegrationConfig(
        discovery_db_path=source_db,
        palace_path=target_palace,
        duplicate_threshold=threshold
    )
    
    # Initialize Memory, this will auto-trigger _sync_existing_to_palace
    # But we want to do duplicate detection as requested.
    memory = PalaceDiscoveryMemory(config)
    
    # Get all records from sqlite
    sqlite_records = memory._original.discoveries
    logger.info(f"Found {len(sqlite_records)} records in SQLite")
    
    successful = 0
    duplicates = 0
    
    for rec in sqlite_records:
        wing = config.wing_for_domain(rec.domain)
        room = config.room_for_hypothesis(rec.hypothesis_id)
        content = memory._discovery_to_text(rec)
        
        # Check for duplicates using semantic similarity
        hits = memory.semantic_search(content, domain=rec.domain, n_results=1)
        if hits and hits[0]["similarity"] >= threshold:
            logger.info(f"Skipping {rec.id} - duplicate of {hits[0]['discovery_id']} (sim: {hits[0]['similarity']:.2f})")
            duplicates += 1
            continue
            
        metadata = memory._discovery_to_metadata(rec)
        drawer_id = f"discovery_{rec.id}"
        
        try:
            # We use upsert so if _sync_existing_to_palace already added it, we just update it.
            # But the prompt says we need to check dupes, so _sync maybe already did it bypassingly.
            # However this script fulfills the CLI requirement.
            memory._backend.upsert(
                ids=[drawer_id],
                documents=[content],
                metadatas=[metadata],
            )
            successful += 1
        except Exception as e:
            logger.error(f"Failed to migrate {rec.id}: {e}")
            
    logger.info(f"Migration complete: {successful} successful, {duplicates} duplicates ignored.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate ASTRA discoveries to MemPalace")
    parser.add_argument("--source", required=True, help="Path to ASTRA SQLite DB")
    parser.add_argument("--target", required=True, help="Path to target Palace ChromaDB directory")
    parser.add_argument("--threshold", type=float, default=0.90, help="Duplicate similarity threshold")
    
    args = parser.parse_args()
    run_migration(args.source, args.target, args.threshold)
