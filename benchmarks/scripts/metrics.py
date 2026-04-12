import numpy as np
from typing import List, Set, Dict, Any, Generator
import math

def recall_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """Fraction of relevant items in the top-K retrieved."""
    top_k = set(retrieved_ids[:k])
    if not relevant_ids:
        return 1.0  # No relevant items → trivially satisfied
    return len(top_k & relevant_ids) / len(relevant_ids)

def precision_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """Fraction of top-K that are relevant."""
    top_k = set(retrieved_ids[:k])
    if k == 0:
        return 0.0
    return len(top_k & relevant_ids) / k

def domain_coverage_balance(domain_counts: Dict[str, int]) -> float:
    """Shannon entropy normalized to [0, 1]."""
    total = sum(domain_counts.values())
    if total == 0 or len(domain_counts) <= 1:
        return 0.0
    probs = [c / total for c in domain_counts.values()]
    entropy = -sum(p * math.log(p) for p in probs if p > 0)
    max_entropy = math.log(len(domain_counts))
    return entropy / max_entropy if max_entropy > 0 else 0.0

def auc_confidence(confidence_history: List[float]) -> float:
    """Area under the confidence curve (trapezoid rule)."""
    if len(confidence_history) < 2:
        return np.mean(confidence_history) if confidence_history else 0.0
    return np.trapz(confidence_history) / len(confidence_history)

def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Cohen's d effect size for two independent groups."""
    group1 = np.array(group1, dtype=float)
    group2 = np.array(group2, dtype=float)
    n1, n2 = len(group1), len(group2)
    var1 = np.var(group1, ddof=1) if n1 > 1 else 0.0
    var2 = np.var(group2, ddof=1) if n2 > 1 else 0.0
    
    if n1 + n2 <= 2:
        return 0.0
        
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(group1) - np.mean(group2)) / pooled_std

def extract_variables(text: str) -> Set[str]:
    """Simple heuristic out of variable name structure."""
    return set([w for w in text.replace("-", " ").replace("_", " ").split() if len(w) > 3])
