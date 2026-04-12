import sys
import uvicorn
import logging
from mempalace_agi.config import IntegrationConfig
from mempalace_agi.orchestrator import MemPalaceAGI
from mempalace_agi.unified_api import create_app

logging.basicConfig(level=logging.INFO)

def main():
    print("=" * 60)
    print("  MemPalace-AGI Unified System")
    print("=" * 60)
    
    config = IntegrationConfig()
    
    # Needs to be dynamically imported and injected, but maybe handled inside MemPalaceAGI already
    # Let's check how orchestrator brings up the engine. It creates a new DiscoveryEngine if none provided.
    
    import threading
    orchestrator = MemPalaceAGI(config)
    
    # The ASTRA engine has its own cycle loop which runs automatically?
    # Actually wait. DiscoveryEngine.start(interval=...) uses an internal timer.
    # MemPalaceAGI patch replaces the engine.run_cycle with the patched cycle.
    # We should let the engine start if we want autonomous mode.
    # But for now, we just boot the combined server, engine should be ready.
    
    app = create_app(
        orchestrator.palace_memory,
        orchestrator.engine,
        orchestrator.kg_bridge,
        orchestrator.specialists
    )
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()
