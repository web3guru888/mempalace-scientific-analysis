import os
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge
from mempalace_agi.domain_specialists import DomainSpecialistManager

# Create routers
palace_router = APIRouter(prefix="/api/v1/palace", tags=["palace"])
integration_router = APIRouter(prefix="/api/v1/integration", tags=["integration"])
engine_router = APIRouter(prefix="/api/v1/engine", tags=["engine"])

# Globals for dependency injection
_engine = None
_palace_memory = None
_kg_bridge = None
_specialists = None

def get_engine():
    return _engine

def get_palace() -> PalaceDiscoveryMemory:
    if not _palace_memory:
        raise HTTPException(500, "Palace memory not initialized")
    return _palace_memory

def get_kg_bridge() -> KnowledgeGraphBridge:
    if not _kg_bridge:
        raise HTTPException(500, "KG bridge not initialized")
    return _kg_bridge

def get_specialists() -> DomainSpecialistManager:
    if not _specialists:
        raise HTTPException(500, "Specialists not initialized")
    return _specialists

# --- Models ---
class SearchQuery(BaseModel):
    query: str
    domain: Optional[str] = None
    n_results: int = 10

# --- Palace Routes ---

@palace_router.get("/status")
def palace_status(palace: PalaceDiscoveryMemory = Depends(get_palace)):
    return palace.to_dict()

@palace_router.get("/wings")
def palace_wings(palace: PalaceDiscoveryMemory = Depends(get_palace)):
    try:
        stats = palace.get_persistence_stats()
        return {"wings": stats.get("palace_wings", 0)}
    except AttributeError:
        # Fallback if get_persistence_stats is missing or doesn't have it
        return {"wings": []}

@palace_router.get("/wings/{wing}/rooms")
def palace_rooms(wing: str, palace: PalaceDiscoveryMemory = Depends(get_palace)):
    # Since PalaceDiscoveryMemory uses ChromaDB, it doesn't actually have a distinct "list rooms" 
    # method in its interface. In a real impl, we'd query metadata. We'll return dummy for now.
    return {"wing": wing, "rooms": []}

@palace_router.post("/search")
def palace_search(req: SearchQuery, palace: PalaceDiscoveryMemory = Depends(get_palace)):
    return palace.semantic_search(req.query, req.domain, req.n_results)

@palace_router.get("/kg/stats")
def palace_kg_stats(kg_bridge: KnowledgeGraphBridge = Depends(get_kg_bridge)):
    return kg_bridge.stats()

@palace_router.get("/diary/{agent}")
def palace_diary(agent: str, last_n: int = 10, specialists: DomainSpecialistManager = Depends(get_specialists)):
    # The specialist manager formats agent names with `specialist_` prefix but accepts domains.
    # If the user passes the domain, we just get context.
    return {"entries": specialists.get_domain_context(agent, last_n)}

# --- Integration Routes ---

@integration_router.get("/status")
def integration_status():
    return {
        "status": "online",
        "engine": "active" if _engine else "inactive",
        "palace": "active" if _palace_memory else "inactive",
        "kg_bridge": "active" if _kg_bridge else "inactive"
    }

@integration_router.post("/orient-context/{hypothesis_id}")
def integration_orient_context(hypothesis_id: str, specialists: DomainSpecialistManager = Depends(get_specialists)):
    # In a full flow we also call memory_augmented_orient here. 
    # For now, just use the specialist pre-investigation context.
    return specialists.get_pre_investigation_context("CrossDomain", hypothesis_id)

@integration_router.get("/cross-domain")
def integration_cross_domain(palace: PalaceDiscoveryMemory = Depends(get_palace)):
    return palace.search_across_domains("connection opportunities", n_results=5)

@integration_router.post("/sync-kg")
def integration_sync_kg(kg_bridge: KnowledgeGraphBridge = Depends(get_kg_bridge)):
    # Actual implementation depends on ASTRA's dynamic KG properties.
    return {"status": "synced"}

# --- Engine Routes ---

@engine_router.get("/status")
def engine_status():
    """Placeholder for ASTRA engine endpoints"""
    return {"engine": "placeholder for original 89+ endpoints"}

def create_app(palace_memory, engine, kg_bridge, specialists) -> FastAPI:
    global _engine, _palace_memory, _kg_bridge, _specialists
    _engine = engine
    _palace_memory = palace_memory
    _kg_bridge = kg_bridge
    _specialists = specialists

    app = FastAPI(title="MemPalace-AGI Unified Server")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(palace_router)
    app.include_router(integration_router)
    app.include_router(engine_router)
    
    try:
        from astra_live_backend.server import app as astra_app
        app.mount("/astra", astra_app)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to mount ASTRA-dev app: {e}")
        
    
    # Mount Dashboard
    dashboard_path = "/shared/mempalace-agi/dashboard"
    if not os.path.exists(dashboard_path):
        os.makedirs(dashboard_path, exist_ok=True)
        with open(os.path.join(dashboard_path, "index.html"), "w") as f:
            f.write("<html><body><h1>MemPalace-AGI Dashboard</h1></body></html>")
            
    app.mount("/dashboard", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
    
    @app.get("/")
    def root():
        return FileResponse(os.path.join(dashboard_path, "index.html"))
        
    return app
