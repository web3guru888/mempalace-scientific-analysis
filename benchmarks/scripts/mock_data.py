import json
import numpy as np
from collections import defaultdict
from typing import Dict, Any, Optional

try:
    from astra_live_backend.data_registry import DataResult # Or however ASTRA-dev imports it
except ImportError:
    try:
        from astra_live_backend.data_fetcher import DataResult
    except ImportError:
        # Define a mock if we can't import
        from dataclasses import dataclass, field
        @dataclass
        class DataResult:
            source: str
            query: str
            data: np.ndarray
            metadata: Dict[str, Any] = field(default_factory=dict)
            row_count: int = 0
            fetch_time: float = 0.0
            schema: Optional[Any] = None
        
            def __post_init__(self):
                self.row_count = len(self.data) if self.data is not None else 0

class MockDataFetcher:
    """Deterministic data fetcher for benchmarking."""
    
    def __init__(self, mock_data_path: str, seed: int = 42):
        try:
            with open(mock_data_path, "r") as f:
                self.responses = json.load(f)
        except (FileVersionError, FileNotFoundError):
            self.responses = {}
        self.rng = np.random.RandomState(seed)
        self.call_counts = defaultdict(int)
    
    def fetch(self, source_id: str, query: str = "", **kwargs) -> DataResult:
        key = f"{source_id}_{self.call_counts[source_id]}"
        self.call_counts[source_id] += 1
        
        if key in self.responses:
            data_dict = self.responses[key]
            # Convert python lists back to numpy for ASTRA
            arr = np.array(data_dict.get("data", []))
            return DataResult(
                source=source_id, 
                query=query, 
                data=arr, 
                metadata=data_dict.get("metadata", {})
            )
            
        # Wrap around with noise
        base_key = f"{source_id}_0"
        if base_key not in self.responses:
            # Fallback for completely missing sources
            return self._generate_fallback(source_id, query)
            
        base = self.responses[base_key]
        noisy_arr = self._add_noise(base, self.rng)
        return DataResult(
            source=source_id, 
            query=query, 
            data=noisy_arr, 
            metadata=base.get("metadata", {})
        )
        
    def _add_noise(self, base_response: Dict[str, Any], rng: np.random.RandomState) -> np.ndarray:
        base_data = np.array(base_response.get("data", []))
        if len(base_data) == 0:
            return base_data
            
        # Add 5% noise if it's numeric
        if np.issubdtype(base_data.dtype, np.number):
            noise = rng.normal(1.0, 0.05, base_data.shape)
            return base_data * noise
        return base_data
        
    def _generate_fallback(self, source_id: str, query: str) -> DataResult:
        """Generate generic fallback data if not in mock dataset."""
        n_points = 100
        n_cols = 5
        data = self.rng.normal(0, 1, (n_points, n_cols))
        return DataResult(
            source=source_id,
            query=query,
            data=data,
            metadata={"n_points": n_points, "synthetic": True}
        )

# Simple generator for creating mock data
def generate_mock_data_file(path: str):
    rng = np.random.RandomState(42)
    mock = {}
    sources = ["gaia_dr3", "sdss_dr18", "exoplanets", "pantheon", "world_bank", "fed_data"]
    
    for source in sources:
        for i in range(50):
            n_points = rng.randint(50, 500)
            n_cols = rng.randint(2, 5)
            # Create semi-realistic correlated data sometimes
            base_col = rng.normal(0, 1, n_points)
            arr = np.zeros((n_points, n_cols))
            arr[:, 0] = base_col
            for c in range(1, n_cols):
                correlation = rng.uniform(0.1, 0.9)
                arr[:, c] = correlation * base_col + np.sqrt(1 - correlation**2) * rng.normal(0, 1, n_points)
                
            mock[f"{source}_{i}"] = {
                "source": source,
                "data": arr.tolist(),
                "metadata": {"generated": True, "cols": n_cols}
            }
            
    with open(path, "w") as f:
        json.dump(mock, f)
    return mock
