"""
ReportBuilder: Builds engineering reports from assembly snapshots.
"""
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from .models import (
    Report, ReportMeta, ReportOverview, BOMItem, Insight, ManufacturingHint,
    HealthCheck, BBoxMM, RepetitionData, ReferenceGeometryItem
)
from .complexity import compute_complexity_score
from .rules import generate_insights
from .config import REPORT_VERSION, REFERENCE_GEOMETRY_KEYWORDS, MAX_REALISTIC_VOLUME_MM3
import math


class ReportBuilder:
    """Builds engineering reports from assembly snapshots."""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize ReportBuilder.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
    
    def build_from_snapshot(self, snapshot_path: str) -> Report:
        """
        Build report from snapshot JSON file.
        
        Args:
            snapshot_path: Path to snapshot JSON file
            
        Returns:
            Report object
        """
        if not os.path.exists(snapshot_path):
            raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")
        
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        
        return self.build_from_dict(snapshot, snapshot_path)
    
    def build_from_dict(self, snapshot: Dict[str, Any], snapshot_path: Optional[str] = None) -> Report:
        """
        Build report from snapshot dictionary.
        
        Args:
            snapshot: Snapshot dictionary
            snapshot_path: Optional path to snapshot file (for metadata)
            
        Returns:
            Report object
        """
        # Extract metadata
        assembly_id = snapshot.get("assembly_id", "unknown")
        source_file = snapshot.get("source_file", "")
        file_name = os.path.basename(source_file) if source_file else None
        
        # Detect and separate reference geometry
        reference_geometry = self._detect_reference_geometry(snapshot)
        # Create sets for matching (use lowercase names and part IDs)
        ref_geom_names = set()
        ref_geom_ids = set()
        for item in reference_geometry:
            if item.part_name:
                ref_geom_names.add(item.part_name.lower())
            if item.part_id:
                ref_geom_ids.add(item.part_id)
        
        # Build report sections (excluding reference geometry)
        overview = self._compute_overview(snapshot, ref_geom_names, ref_geom_ids)
        bom = self._build_bom(snapshot, ref_geom_names, ref_geom_ids)
        largest_parts = self._compute_largest_parts(snapshot, top_n=5, ref_geom_names=ref_geom_names, ref_geom_ids=ref_geom_ids)
        repetition = self._compute_repetition(snapshot, ref_geom_names)
        
        # Create temporary report for insights generation
        temp_report = Report(
            meta=ReportMeta(
                assembly_id=assembly_id,
                file_name=file_name,
                generated_at_iso=datetime.now().isoformat(),
                version=REPORT_VERSION,
                source_snapshot_path=snapshot_path or "",
            ),
            overview=overview,
            bom=bom,
            largest_parts=largest_parts,
            repetition=repetition,
            insights=[],
            manufacturing_hints=[],
            health_check=HealthCheck(score_0_100=0, warnings=[]),
            next_steps=[],
            reference_geometry=reference_geometry,
        )
        
        # Generate insights
        insights = generate_insights(temp_report)
        
        # Generate manufacturing hints (rules-based, excluding reference geometry)
        manufacturing_hints = self._generate_manufacturing_hints(snapshot, bom, largest_parts)
        
        # Compute health check
        health_check = self._compute_health_check(snapshot, insights)
        
        # Generate next steps (template-based, deterministic)
        next_steps = self._generate_next_steps(overview, insights, health_check)
        
        # Build final report
        report = Report(
            meta=ReportMeta(
                assembly_id=assembly_id,
                file_name=file_name,
                generated_at_iso=datetime.now().isoformat(),
                version=REPORT_VERSION,
                source_snapshot_path=snapshot_path or "",
            ),
            overview=overview,
            bom=bom,
            largest_parts=largest_parts,
            repetition=repetition,
            insights=insights,
            manufacturing_hints=manufacturing_hints,
            health_check=health_check,
            next_steps=next_steps,
            reference_geometry=reference_geometry,
        )
        
        return report
    
    def _detect_reference_geometry(self, snapshot: Dict[str, Any]) -> List[ReferenceGeometryItem]:
        """
        Detect reference geometry parts that should be excluded from manufacturing analysis.
        
        A part is considered reference geometry if:
        - Name contains reference geometry keywords
        - Volume is null, infinite, or extremely large
        """
        reference_items = []
        parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
        bom_preview = snapshot.get("bom_preview", [])
        
        # Create mapping from part_id to BOM data
        bom_map = {item.get("part_number"): item for item in bom_preview}
        
        for part in parts_tree:
            part_name = part.get("name", "").lower()
            part_id = part.get("id", "")
            volume = part.get("volume_mm3")
            
            reasons = []
            
            # Check name for reference geometry keywords
            if any(keyword in part_name for keyword in REFERENCE_GEOMETRY_KEYWORDS):
                reasons.append("name contains reference geometry keyword")
            
            # Check for null or invalid volume
            if volume is None:
                reasons.append("no volume data")
            elif math.isinf(volume) or math.isnan(volume):
                reasons.append("invalid volume (infinite or NaN)")
            elif volume > MAX_REALISTIC_VOLUME_MM3:
                reasons.append(f"extremely large volume ({volume:.2e} mm³)")
            
            if reasons:
                bom_item = bom_map.get(part_id, {})
                display_name = bom_item.get("description", part.get("name", "Unknown"))
                reference_items.append(ReferenceGeometryItem(
                    part_name=display_name,
                    part_id=part_id if part_id else None,
                    reason="; ".join(reasons)
                ))
        
        return reference_items
    
    def _compute_overview(self, snapshot: Dict[str, Any], ref_geom_names: set = None, ref_geom_ids: set = None) -> ReportOverview:
        """Compute overview metrics, excluding reference geometry."""
        if ref_geom_names is None:
            ref_geom_names = set()
        if ref_geom_ids is None:
            ref_geom_ids = set()
        
        overview_data = snapshot.get("overview", {})
        
        # Count parts excluding reference geometry
        bom_preview = snapshot.get("bom_preview", [])
        total_parts = 0
        unique_parts_set = set()
        
        for item in bom_preview:
            part_name = item.get("description", "")
            part_id = item.get("part_number", "")
            qty = item.get("quantity", 1)
            
            # Skip reference geometry
            if part_name.lower() in ref_geom_names or part_id in ref_geom_ids:
                continue
            
            total_parts += qty
            unique_parts_set.add(part_id)
        
        unique_parts = len(unique_parts_set)
        repeated_parts = total_parts - unique_parts
        
        # Extract bbox
        bbox_data = overview_data.get("bbox_mm")
        bbox = None
        if bbox_data and isinstance(bbox_data, dict):
            bbox = BBoxMM(
                x=bbox_data.get("x", 0.0),
                y=bbox_data.get("y", 0.0),
                z=bbox_data.get("z", 0.0),
            )
        
        # Count fasteners from BOM (excluding reference geometry)
        fastener_count = 0
        for item in bom_preview:
            part_name = item.get("description", "")
            part_id = item.get("part_number", "")
            
            # Skip reference geometry
            if part_name.lower() in ref_geom_names or part_id in ref_geom_ids:
                continue
            
            part_name_lower = part_name.lower()
            if any(kw in part_name_lower for kw in ["bolt", "screw", "washer", "nut", "fastener", "rivet", "pin"]):
                fastener_count += item.get("quantity", 0)
        
        # Compute complexity score
        complexity_score = compute_complexity_score(
            total_parts=total_parts,
            unique_parts=unique_parts,
            fastener_count=fastener_count,
            tree_depth=None  # Not available in snapshot
        )
        
        return ReportOverview(
            total_parts=total_parts,
            unique_parts=unique_parts,
            repeated_parts=repeated_parts,
            bbox_mm=bbox,
            complexity_score_0_100=complexity_score,
        )
    
    def _build_bom(self, snapshot: Dict[str, Any], ref_geom_names: set = None, ref_geom_ids: set = None) -> List[BOMItem]:
        """Build BOM from snapshot, excluding reference geometry."""
        if ref_geom_names is None:
            ref_geom_names = set()
        if ref_geom_ids is None:
            ref_geom_ids = set()
        
        bom_items = []
        
        # Get BOM preview and parts tree
        bom_preview = snapshot.get("bom_preview", [])
        parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
        
        # Create mapping from part_id to part data
        parts_map = {p.get("id"): p for p in parts_tree}
        
        for item in bom_preview:
            part_name = item.get("description", "")
            part_id = item.get("part_number", "")
            
            # Skip reference geometry
            if part_name.lower() in ref_geom_names or part_id in ref_geom_ids:
                continue
            part_id = item.get("part_number", "")
            part_data = parts_map.get(part_id, {})
            
            # Extract bbox
            bbox_data = part_data.get("bbox_mm")
            bbox = None
            if bbox_data and isinstance(bbox_data, dict):
                bbox = BBoxMM(
                    x=bbox_data.get("x", 0.0),
                    y=bbox_data.get("y", 0.0),
                    z=bbox_data.get("z", 0.0),
                )
            
            # Determine category (simple heuristic)
            category = None
            part_name = item.get("description", "").lower()
            if any(kw in part_name for kw in ["bolt", "screw", "washer", "nut", "fastener"]):
                category = "fastener"
            
            bom_item = BOMItem(
                item_no=item.get("item", 0),
                part_name=item.get("description", "Unknown"),
                qty=item.get("quantity", 1),
                material=item.get("material") if item.get("material") != "N/A" else None,
                volume_mm3=part_data.get("volume_mm3"),
                bbox_mm=bbox,
                category=category,
            )
            bom_items.append(bom_item)
        
        return bom_items
    
    def _compute_largest_parts(self, snapshot: Dict[str, Any], top_n: int = 5, ref_geom_names: set = None, ref_geom_ids: set = None) -> List[Dict[str, Any]]:
        """Find top N largest parts by volume, excluding reference geometry."""
        if ref_geom_names is None:
            ref_geom_names = set()
        if ref_geom_ids is None:
            ref_geom_ids = set()
        
        parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
        bom_preview = snapshot.get("bom_preview", [])
        
        # Create mapping from part_id to BOM data
        bom_map = {item.get("part_number"): item for item in bom_preview}
        
        # Get parts with volume data (excluding reference geometry)
        parts_with_volume = []
        for part in parts_tree:
            part_name = part.get("name", "").lower()
            part_id = part.get("id", "")
            
            # Skip reference geometry
            if part_name in ref_geom_names or part_id in ref_geom_ids:
                continue
            
            volume = part.get("volume_mm3")
            # Only include parts with valid, realistic volumes
            if volume is not None and volume > 0 and volume <= MAX_REALISTIC_VOLUME_MM3:
                part_id = part.get("id", "")
                bom_item = bom_map.get(part_id, {})
                parts_with_volume.append({
                    "part_name": part.get("name", "Unknown"),
                    "volume_mm3": volume,
                    "bbox_mm": part.get("bbox_mm"),
                    "qty": bom_item.get("quantity", part.get("instances", 1)),
                })
        
        # Sort by volume descending
        parts_with_volume.sort(key=lambda p: p.get("volume_mm3", 0), reverse=True)
        
        return parts_with_volume[:top_n]
    
    def _compute_repetition(self, snapshot: Dict[str, Any], ref_geom_names: set = None) -> RepetitionData:
        """Compute repetition metrics, excluding reference geometry."""
        if ref_geom_names is None:
            ref_geom_names = set()
        
        bom_preview = snapshot.get("bom_preview", [])
        
        if not bom_preview:
            return RepetitionData(top_repeated=[], repeated_share_pct=0.0)
        
        # Group by part name and sum quantities (excluding reference geometry)
        part_counts = {}
        total_parts = 0
        
        for item in bom_preview:
            part_name = item.get("description", "Unknown")
            
            # Skip reference geometry
            if part_name.lower() in ref_geom_names:
                continue
            
            qty = item.get("quantity", 1)
            part_counts[part_name] = part_counts.get(part_name, 0) + qty
            total_parts += qty
        
        # Find repeated parts (qty > 1)
        repeated = [(name, qty) for name, qty in part_counts.items() if qty > 1]
        repeated.sort(key=lambda x: x[1], reverse=True)
        
        # Calculate repeated share
        repeated_total = sum(qty for _, qty in repeated)
        repeated_share_pct = (repeated_total / total_parts * 100) if total_parts > 0 else 0.0
        
        # Format top repeated
        top_repeated = [
            {"part_name": name, "qty": qty}
            for name, qty in repeated[:10]  # Top 10
        ]
        
        return RepetitionData(
            top_repeated=top_repeated,
            repeated_share_pct=repeated_share_pct,
        )
    
    def _generate_manufacturing_hints(self, snapshot: Dict[str, Any], bom: List[BOMItem], largest_parts: List[Dict]) -> List[ManufacturingHint]:
        """Generate manufacturing hints (rules-based)."""
        hints = []
        
        # Check for high repetition
        repetition = self._compute_repetition(snapshot)
        if repetition.repeated_share_pct > 50:
            hints.append(ManufacturingHint(
                title="High Part Repetition",
                details=f"{repetition.repeated_share_pct:.1f}% of parts are repeated. Consider batch manufacturing or modular tooling.",
                evidence={"repeated_share_pct": repetition.repeated_share_pct},
            ))
        
        # Check for large parts
        if largest_parts:
            largest = largest_parts[0]
            if largest.get("volume_mm3", 0) > 1000000:  # > 1M mm³
                hints.append(ManufacturingHint(
                    title="Large Part Detected",
                    details=f"Largest part '{largest.get('part_name')}' has volume {largest.get('volume_mm3', 0):.0f} mm³. Consider manufacturing method and material selection.",
                    evidence={"largest_part": largest},
                ))
        
        # Check for material diversity
        materials = set()
        for item in bom:
            if item.material and item.material != "N/A":
                materials.add(item.material)
        
        if len(materials) > 5:
            hints.append(ManufacturingHint(
                title="Material Diversity",
                details=f"Assembly uses {len(materials)} different materials. Consider material consolidation to reduce costs and simplify supply chain.",
                evidence={"material_count": len(materials), "materials": sorted(list(materials))[:10]},
            ))
        
        return hints
    
    def _compute_health_check(self, snapshot: Dict[str, Any], insights: List[Insight]) -> HealthCheck:
        """Compute health check score and warnings."""
        warnings = []
        score = 100  # Start at 100, deduct for issues
        
        # Deduct for insights
        for insight in insights:
            if insight.severity == "risk":
                score -= 20
                warnings.append(insight.title)
            elif insight.severity == "warn":
                score -= 10
                warnings.append(insight.title)
            elif insight.severity == "info":
                score -= 5
        
        # Check for validation errors
        validation_errors = snapshot.get("validation_errors", [])
        if validation_errors:
            score -= 15
            warnings.append(f"{len(validation_errors)} validation error(s)")
        
        # Ensure score is in valid range
        score = max(0, min(100, score))
        
        return HealthCheck(
            score_0_100=score,
            warnings=warnings,
        )
    
    def _generate_next_steps(self, overview: ReportOverview, insights: List[Insight], health_check: HealthCheck) -> List[str]:
        """Generate next steps (template-based, deterministic)."""
        next_steps = []
        
        # Always include basic steps
        next_steps.append("Review assembly snapshot and BOM for accuracy")
        next_steps.append("Verify part quantities match design intent")
        
        # Add steps based on insights
        if any(i.severity == "risk" for i in insights):
            next_steps.append("Address high-priority risks identified in insights")
        
        if health_check.score_0_100 < 70:
            next_steps.append("Review health check warnings and improve assembly design")
        
        if overview.complexity_score_0_100 > 70:
            next_steps.append("Consider design simplification to reduce complexity")
        
        # Add manufacturing steps if applicable
        if overview.repeated_parts > 0:
            next_steps.append("Evaluate manufacturing strategy for repeated parts")
        
        return next_steps
