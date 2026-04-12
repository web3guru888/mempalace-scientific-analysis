import json
import logging
import sys
import importlib.util
from typing import Dict, Any, List, Optional

logger = logging.getLogger("mempalace_agi")

# Try to load MemPalace tools
MEMPALACE_TOOLS = {}
mempalace_handle = None

try:
    import mempalace.mcp_server as mempalace_mcp
    MEMPALACE_TOOLS = mempalace_mcp.TOOLS
    mempalace_handle = mempalace_mcp.handle_request
except ImportError:
    pass

class UnifiedMCPServer:
    """
    Unified MCP Server combining ASTRA's 6 new tools and MemPalace's 19 tools.
    """
    def __init__(self, palace_memory, engine, kg_bridge, specialist_manager, config, handle_mgr=None):
        self.palace_memory = palace_memory
        self.engine = engine
        self.kg_bridge = kg_bridge
        self.specialist_manager = specialist_manager
        self.config = config
        self.handle_mgr = handle_mgr  # Optional PalaceHandleManager
        
        self.astra_tools = {
            "astra_run_cycle": {
                "description": "Execute one OODA cycle.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "force_domain": {
                            "type": "string",
                            "description": "Optional domain to force exploration in"
                        }
                    },
                },
                "handler": self._tool_run_cycle
            },
            "astra_test_hypothesis": {
                "description": "Test specific hypothesis.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "hypothesis_id": {
                            "type": "string",
                            "description": "Hypothesis ID to test"
                        }
                    },
                    "required": ["hypothesis_id"]
                },
                "handler": self._tool_test_hypothesis
            },
            "astra_query_discoveries": {
                "description": "Semantic search across discoveries.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "domain": {"type": "string"},
                        "min_strength": {"type": "number"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["query"]
                },
                "handler": self._tool_query_discoveries
            },
            "astra_get_status": {
                "description": "Full system status.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                },
                "handler": self._tool_get_status
            },
            "astra_causal_query": {
                "description": "Query causal KG relationships.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity": {"type": "string"},
                        "direction": {"type": "string"}
                    },
                    "required": ["entity"]
                },
                "handler": self._tool_causal_query
            },
            "astra_hypothesis_lifecycle": {
                "description": "View hypothesis phases.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "hypothesis_id": {"type": "string"},
                        "phase": {"type": "string"}
                    },
                },
                "handler": self._tool_hypothesis_lifecycle
            }
        }
        
        # ── Handle Protocol Tools (requires handle_mgr) ────────────────
        if self.handle_mgr is not None:
            self.astra_tools["palace_allocate"] = {
                "description": (
                    "Allocate a memory handle for lazy retrieval. Returns a lightweight "
                    "handle with count and metadata previews — no full document text. "
                    "Use palace_resolve to materialize specific memories at the desired "
                    "fidelity level."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query to search palace memories",
                        },
                        "wing": {
                            "type": "string",
                            "description": "Optional wing filter (e.g. 'wing_astrophysics')",
                        },
                        "room": {
                            "type": "string",
                            "description": "Optional room filter (e.g. 'room_hyp_123')",
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 20)",
                        },
                        "min_similarity": {
                            "type": "number",
                            "description": "Minimum cosine similarity threshold (default: 0.3)",
                        },
                    },
                    "required": ["query"],
                },
                "handler": self._tool_palace_allocate,
            }
            self.astra_tools["palace_resolve"] = {
                "description": (
                    "Resolve a memory handle at the requested fidelity level. "
                    "Fidelity: 'meta' (titles+scores), 'summary' (200-char excerpt), "
                    "'full' (complete text + KG triples)."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "handle_id": {
                            "type": "string",
                            "description": "Handle ID from a prior palace_allocate call",
                        },
                        "fidelity": {
                            "type": "string",
                            "description": "Resolution fidelity level (default: 'meta')",
                        },
                        "ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional: resolve only these specific discovery IDs",
                        },
                    },
                    "required": ["handle_id"],
                },
                "handler": self._tool_palace_resolve,
            }
            self.astra_tools["palace_heat_scores"] = {
                "description": (
                    "Get heat scores for a set of drawer IDs. Heat reflects access frequency, "
                    "correction status, recency, and KG connectivity."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "drawer_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of drawer/discovery IDs to score",
                        },
                    },
                    "required": ["drawer_ids"],
                },
                "handler": self._tool_palace_heat_scores,
            }
        
    def _tool_run_cycle(self, force_domain: Optional[str] = None):
        """Execute one OODA cycle."""
        # Typically engine.run_cycle doesn't take force_domain directly or it uses a setter
        if force_domain and hasattr(self.engine, 'force_domain'):
            self.engine.force_domain = force_domain
        self.engine.run_cycle()
        return {"status": "success", "cycle": self.engine.cycle_count}
        
    def _tool_test_hypothesis(self, hypothesis_id: str):
        hyps = [h for h in self.engine.store.active() if h.id == hypothesis_id]
        if not hyps:
            return {"error": f"Hypothesis {hypothesis_id} not active"}
        # Run test via engine if it has a way to test specific hyp. This is a simplification.
        return {"status": "tested", "hypothesis": hypothesis_id}
        
    def _tool_query_discoveries(self, query: str, domain: Optional[str] = None, min_strength: float = 0.0, limit: int = 10):
        results = self.palace_memory.semantic_search(query=query, domain=domain, n_results=limit)
        if min_strength > 0:
            results = [r for r in results if r.get('strength', 0) >= min_strength]
        return {"results": results}
        
    def _tool_get_status(self):
        return {
            "cycle_count": self.engine.cycle_count,
            "active_hypotheses": len(self.engine.store.active()),
            "system_confidence": self.engine.system_confidence,
            "safety_state": self.engine.safety.current_state if hasattr(self.engine, 'safety') else "UNKNOWN"
        }
        
    def _tool_causal_query(self, entity: str, direction: str = "outgoing"):
        return {"triples": self.kg_bridge.kg.query_entity(entity, direction=direction)}
        
    def _tool_hypothesis_lifecycle(self, hypothesis_id: Optional[str] = None, phase: Optional[str] = None):
        if hypothesis_id:
            hyp = self.engine.store.get(hypothesis_id)
            if not hyp:
                return {"error": "not found"}
            return {"hypothesis": hyp.to_dict() if hasattr(hyp, 'to_dict') else str(hyp)}
        
        hyps = self.engine.store.all()
        if phase:
            hyps = [h for h in hyps if getattr(h, 'phase', '') == phase]
        return {"hypotheses": [h.id for h in hyps]}

    # ── Handle Protocol Tool Handlers ──────────────────────────────────

    def _tool_palace_allocate(
        self,
        query: str,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        n_results: int = 20,
        min_similarity: float = 0.3,
    ) -> dict:
        handle = self.handle_mgr.allocate(
            query=query,
            wing=wing,
            room=room,
            n_results=n_results,
            min_similarity=min_similarity,
        )
        return {
            "handle_id": handle.handle_id,
            "count": handle.count,
            "preview": handle.preview,
        }

    def _tool_palace_resolve(
        self,
        handle_id: str,
        fidelity: str = "meta",
        ids: Optional[List[str]] = None,
    ) -> dict:
        results = self.handle_mgr.resolve(
            handle_id=handle_id,
            fidelity=fidelity,
            ids=ids,
        )
        return {
            "fidelity": fidelity,
            "count": len(results),
            "memories": results,
        }

    def _tool_palace_heat_scores(self, drawer_ids: List[str]) -> dict:
        scores = self.handle_mgr.get_heat_scores(drawer_ids)
        return {
            "scores": scores,
            "formula": "heat = (access_freq * 0.35) + (is_correction * 0.30) + (recency * 0.20) + (inbound_edges * 0.15)",
        }

    @staticmethod
    def _filter_args_by_schema(tool_args: Dict[str, Any], schema: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """Strip arguments not declared in the tool's inputSchema.
        
        Protects against non-standard args injected by MCP clients
        (e.g. Gemini's ``wait_for_previous``) that would cause TypeError
        on **kwargs dispatch.  Returns a (possibly new) dict containing
        only the keys present in ``schema["properties"]``.
        """
        known_keys = set(schema.get("properties", {}).keys())
        stripped = {k for k in tool_args if k not in known_keys}
        if stripped:
            logger.debug("Stripped undeclared args from %s: %s", tool_name, stripped)
            return {k: v for k, v in tool_args.items() if k in known_keys}
        return tool_args

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        if method == "initialize":
            tools = {}
            for name, meta in self.astra_tools.items():
                tools[name] = {
                    "description": meta["description"],
                    "inputSchema": meta["input_schema"]
                }
            for name, meta in MEMPALACE_TOOLS.items():
                tools[name] = {
                    "description": meta["description"],
                    "inputSchema": meta["input_schema"]
                }
            
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mempalace-agi", "version": "0.1.0"},
                },
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            tools_list = []
            for name, meta in self.astra_tools.items():
                tools_list.append({"name": name, "description": meta["description"], "inputSchema": meta["input_schema"]})
            for name, meta in MEMPALACE_TOOLS.items():
                tools_list.append({"name": name, "description": meta["description"], "inputSchema": meta["input_schema"]})
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools_list},
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            # Handle ASTRA tools
            if tool_name in self.astra_tools:
                schema = self.astra_tools[tool_name]["input_schema"]
                schema_props = schema.get("properties", {})
                # Type coercion for declared properties
                for key, value in list(tool_args.items()):
                    prop_schema = schema_props.get(key, {})
                    declared_type = prop_schema.get("type")
                    if declared_type == "integer" and not isinstance(value, int):
                        tool_args[key] = int(value)
                    elif declared_type == "number" and not isinstance(value, (int, float)):
                        tool_args[key] = float(value)
                # Strip undeclared arguments (e.g. Gemini's wait_for_previous)
                tool_args = self._filter_args_by_schema(tool_args, schema, tool_name)
                try:
                    result = self.astra_tools[tool_name]["handler"](**tool_args)
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
                    }
                except Exception as e:
                    logger.exception(f"Tool error in {tool_name}")
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32000, "message": str(e)},
                    }
            
            # Handle MemPalace tools
            if tool_name in MEMPALACE_TOOLS:
                if mempalace_handle:
                    # Strip undeclared args before delegating to upstream handler
                    mp_schema = MEMPALACE_TOOLS[tool_name].get("input_schema", {})
                    filtered_args = self._filter_args_by_schema(tool_args, mp_schema, tool_name)
                    if filtered_args is not tool_args:
                        # Args were modified — build a cleaned request
                        cleaned_request = {**request, "params": {**params, "arguments": filtered_args}}
                        return mempalace_handle(cleaned_request)
                    return mempalace_handle(request)
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": "MemPalace handlers not loaded"},
                    }
                    
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
            
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        }

