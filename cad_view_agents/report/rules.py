"""
Rules engine for deterministic insights generation.
All insights are rules-based, not LLM-generated.
"""
from typing import List, Optional, Dict, Any
from .models import Insight, BOMItem, Report
from .config import (
    FASTENER_KEYWORDS,
    FASTENER_COUNT_WARNING_THRESHOLD,
    FASTENER_VARIETY_WARNING_THRESHOLD,
    COMPLEXITY_HIGH_THRESHOLD,
    REPETITION_MIN_QTY,
    VOLUME_DOMINANCE_THRESHOLD,
    MIN_VOLUME_THRESHOLD_MM3,
)


def _is_fastener(part_name: str, category: Optional[str] = None) -> bool:
    """Check if a part is a fastener based on name or category."""
    name_lower = part_name.lower()
    if category and category.lower() == "fastener":
        return True
    return any(keyword in name_lower for keyword in FASTENER_KEYWORDS)


def check_high_fastener_count(bom: List[BOMItem], threshold: int = FASTENER_COUNT_WARNING_THRESHOLD) -> Optional[Insight]:
    """
    Check for high fastener count.
    
    Detects parts with names containing fastener keywords or category="fastener".
    Returns warning if total fastener count > threshold.
    """
    fastener_count = 0
    fastener_parts = []
    
    for item in bom:
        if _is_fastener(item.part_name, item.category):
            fastener_count += item.qty
            fastener_parts.append(f"{item.part_name} (x{item.qty})")
    
    if fastener_count > threshold:
        return Insight(
            severity="warn",
            title="High Fastener Count",
            details=f"Assembly contains {fastener_count} fasteners, which may indicate high assembly complexity or potential for simplification.",
            evidence={
                "fastener_count": fastener_count,
                "threshold": threshold,
                "fastener_parts": fastener_parts[:10],  # Limit to first 10
            }
        )
    return None


def check_fastener_variety(bom: List[BOMItem], threshold: int = FASTENER_VARIETY_WARNING_THRESHOLD) -> Optional[Insight]:
    """
    Check for high fastener variety.
    
    Counts unique fastener types.
    Returns warning if unique fasteners > threshold.
    """
    unique_fasteners = set()
    
    for item in bom:
        if _is_fastener(item.part_name, item.category):
            unique_fasteners.add(item.part_name)
    
    if len(unique_fasteners) > threshold:
        return Insight(
            severity="warn",
            title="High Fastener Variety",
            details=f"Assembly uses {len(unique_fasteners)} different fastener types. Consider standardizing to reduce inventory and assembly complexity.",
            evidence={
                "unique_fastener_count": len(unique_fasteners),
                "threshold": threshold,
                "fastener_types": sorted(list(unique_fasteners))[:10],  # Limit to first 10
            }
        )
    return None


def check_complexity(complexity_score: int, threshold: int = COMPLEXITY_HIGH_THRESHOLD) -> Optional[Insight]:
    """
    Check for over-complex assembly.
    
    Returns risk if complexity_score > threshold.
    """
    if complexity_score > threshold:
        return Insight(
            severity="risk",
            title="High Assembly Complexity",
            details=f"Assembly complexity score is {complexity_score}/100, indicating a highly complex assembly. Consider design simplification or modularization.",
            evidence={
                "complexity_score": complexity_score,
                "threshold": threshold,
            }
        )
    elif complexity_score > threshold - 20:  # Medium complexity
        return Insight(
            severity="info",
            title="Moderate Assembly Complexity",
            details=f"Assembly complexity score is {complexity_score}/100. Monitor for potential simplification opportunities.",
            evidence={
                "complexity_score": complexity_score,
            }
        )
    return None


def check_repetition_opportunity(repetition: Dict[str, Any], min_qty: int = REPETITION_MIN_QTY) -> Optional[Insight]:
    """
    Check for repetition opportunities.
    
    Suggests standardization for top repeated parts.
    """
    top_repeated = repetition.get("top_repeated", [])
    if not top_repeated:
        return None
    
    # Find parts with significant repetition
    significant_repeats = [p for p in top_repeated if p.get("qty", 0) >= min_qty]
    
    if significant_repeats:
        top_part = significant_repeats[0]
        return Insight(
            severity="info",
            title="Repetition Opportunity",
            details=f"Part '{top_part.get('part_name', 'Unknown')}' appears {top_part.get('qty', 0)} times. Consider standardizing similar parts or using modular design.",
            evidence={
                "top_repeated": significant_repeats[:5],  # Top 5
                "repeated_share_pct": repetition.get("repeated_share_pct", 0.0),
            }
        )
    return None


def check_size_extremes(parts: List[Dict[str, Any]], volume_threshold_ratio: float = VOLUME_DOMINANCE_THRESHOLD) -> Optional[Insight]:
    """
    Check for size extremes.
    
    Detects if largest part dominates volume or very small parts present.
    """
    if not parts:
        return None
    
    # Calculate total volume
    total_volume = sum(p.get("volume_mm3", 0) or 0 for p in parts)
    if total_volume == 0:
        return None
    
    # Find largest part
    parts_with_volume = [p for p in parts if p.get("volume_mm3")]
    if not parts_with_volume:
        return None
    
    largest = max(parts_with_volume, key=lambda p: p.get("volume_mm3", 0))
    largest_volume = largest.get("volume_mm3", 0)
    largest_ratio = largest_volume / total_volume if total_volume > 0 else 0
    
    # Check for volume dominance
    if largest_ratio > volume_threshold_ratio:
        return Insight(
            severity="info",
            title="Size Dominance",
            details=f"Largest part '{largest.get('part_name', 'Unknown')}' accounts for {largest_ratio:.1%} of total volume. Consider if this is intentional or if the part could be split.",
            evidence={
                "largest_part": largest.get("part_name"),
                "largest_volume_mm3": largest_volume,
                "total_volume_mm3": total_volume,
                "ratio": largest_ratio,
            }
        )
    
    # Check for very small parts
    small_parts = [p for p in parts_with_volume if (p.get("volume_mm3", 0) or 0) < MIN_VOLUME_THRESHOLD_MM3]
    if small_parts:
        return Insight(
            severity="warn",
            title="Very Small Parts Detected",
            details=f"Found {len(small_parts)} part(s) with volume < {MIN_VOLUME_THRESHOLD_MM3} mm³. Verify these are intentional design elements.",
            evidence={
                "small_part_count": len(small_parts),
                "small_parts": [p.get("part_name") for p in small_parts[:5]],
            }
        )
    
    return None


def generate_insights(report: Report) -> List[Insight]:
    """
    Generate all insights by running all rules.
    
    Args:
        report: Report object with computed metrics
        
    Returns:
        List of Insight objects
    """
    insights = []
    
    # Run all rule checks
    fastener_count_insight = check_high_fastener_count(report.bom)
    if fastener_count_insight:
        insights.append(fastener_count_insight)
    
    fastener_variety_insight = check_fastener_variety(report.bom)
    if fastener_variety_insight:
        insights.append(fastener_variety_insight)
    
    complexity_insight = check_complexity(report.overview.complexity_score_0_100)
    if complexity_insight:
        insights.append(complexity_insight)
    
    repetition_insight = check_repetition_opportunity(report.repetition.dict())
    if repetition_insight:
        insights.append(repetition_insight)
    
    # Build parts list for size extremes check
    parts_list = []
    for item in report.bom:
        parts_list.append({
            "part_name": item.part_name,
            "volume_mm3": item.volume_mm3,
        })
    size_extremes_insight = check_size_extremes(parts_list)
    if size_extremes_insight:
        insights.append(size_extremes_insight)
    
    return insights
