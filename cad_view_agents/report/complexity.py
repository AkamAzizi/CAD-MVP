"""
Complexity score calculation for assemblies.
"""
import math
from typing import Optional


def compute_complexity_score(
    total_parts: int,
    unique_parts: int,
    fastener_count: int = 0,
    tree_depth: Optional[int] = None
) -> int:
    """
    Compute complexity score 0-100.
    
    Formula:
    - Base: log(total_parts + 1) * 20 (max ~60 for very large assemblies)
    - Unique ratio: (unique_parts / total_parts) * 20 (max 20, higher = more complex)
    - Fastener penalty: min(fastener_count / 10, 20) (max 20, more fasteners = more complex)
    - Tree depth bonus: min(tree_depth or 0, 10) (max 10, deeper = more complex)
    - Normalize to 0-100
    
    Args:
        total_parts: Total number of parts in assembly
        unique_parts: Number of unique parts
        fastener_count: Number of fasteners (bolts, screws, etc.)
        tree_depth: Depth of assembly tree (optional)
        
    Returns:
        Complexity score 0-100 (higher = more complex)
    """
    if total_parts == 0:
        return 0
    
    # Base complexity from part count (logarithmic scale)
    base_score = math.log(total_parts + 1) * 20
    base_score = min(base_score, 60)  # Cap at 60
    
    # Unique parts ratio (more unique parts = more complex)
    unique_ratio = unique_parts / total_parts if total_parts > 0 else 0
    unique_score = unique_ratio * 20
    unique_score = min(unique_score, 20)  # Cap at 20
    
    # Fastener penalty (more fasteners = more assembly complexity)
    fastener_score = min(fastener_count / 10, 20)  # Cap at 20
    
    # Tree depth (deeper hierarchy = more complex)
    depth_score = min(tree_depth or 0, 10)  # Cap at 10
    
    # Sum all components
    raw_score = base_score + unique_score + fastener_score + depth_score
    
    # Normalize to 0-100
    score = min(int(raw_score), 100)
    
    return max(0, score)  # Ensure non-negative
