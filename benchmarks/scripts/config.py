from dataclasses import dataclass

@dataclass
class BenchmarkConfig:
    system: str  # "baseline" or "treatment"
    scenario: str  # e.g., "cold_start_50", "warm_start_100"
    seed: int  # RNG seed for reproducibility
    n_cycles: int  # Number of OODA cycles to run
    n_runs: int  # Number of independent runs (different seeds)
    mock_data_path: str  # Path to deterministic mock data
    output_dir: str  # Where to write logs and metrics
    
    # Treatment-only parameters
    palace_path: str = ""  # ChromaDB storage path
    kg_db_path: str = ""  # KG SQLite path
    semantic_search_k: int = 5  # Top-K for semantic retrieval
    cross_domain_k: int = 3  # Top-K for cross-domain search
    min_similarity: float = 0.3  # Minimum similarity threshold
