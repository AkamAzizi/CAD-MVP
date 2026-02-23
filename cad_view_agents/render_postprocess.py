#!/usr/bin/env python3
"""
Post-processing script to render drawings using CADQuery after FreeCAD processing.
This runs in regular Python (not FreeCAD's Python) so CADQuery is available.
"""
import sys
import os
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from render.engines.cadquery_engine import CADQueryEngine
from core.drawing_plan import DrawingPlan
from core.layout_engine import ViewPlacement
from core.view_candidates import ViewCandidate
from core.bom_generator import BOMTable, PartMetadata


def load_drawing_plan(plan_path: str) -> dict:
    """Load drawing plan from JSON file."""
    with open(plan_path, 'r') as f:
        return json.load(f)


def reconstruct_view_placements(plan_data: dict) -> list:
    """Reconstruct ViewPlacement objects from plan data."""
    # This is a simplified version - in production, we'd need to store full ViewPlacement data
    placements = []
    # For now, return empty list - will be populated from plan
    return placements


def reconstruct_bom_table(plan_data: dict) -> BOMTable:
    """Reconstruct BOMTable from plan data."""
    bom_data = plan_data.get("bom_table", {})
    parts = []
    for row in bom_data.get("rows", []):
        parts.append(PartMetadata(
            part_id=row.get("part_number", ""),
            item_number=row.get("item", 0),
            name=row.get("description", ""),
            quantity=row.get("quantity", 1),
            material=row.get("material", "N/A")
        ))
    return BOMTable(parts=parts)


def main():
    if len(sys.argv) < 3:
        print("Usage: python render_postprocess.py <drawing_plan.json> <step_file> [assembly_id]")
        sys.exit(1)
    
    plan_path = sys.argv[1]
    step_path = sys.argv[2]
    assembly_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    if not os.path.exists(plan_path):
        print(f"Error: Drawing plan not found: {plan_path}")
        sys.exit(1)
    
    if not os.path.exists(step_path):
        print(f"Error: STEP file not found: {step_path}")
        sys.exit(1)
    
    # Load drawing plan
    plan_data = load_drawing_plan(plan_path)
    
    if not assembly_id:
        assembly_id = plan_data.get("assembly_id", "unknown")
    
    # Check if CADQuery is available
    engine = CADQueryEngine()
    if not engine.is_available():
        print("ERROR: CADQuery is not available in this Python environment.")
        print("Install with: pip install cadquery")
        sys.exit(1)
    
    print(f"Rendering drawing for assembly: {assembly_id}")
    print(f"Using STEP file: {step_path}")
    
    # Reconstruct objects from plan data
    # Note: This is simplified - full implementation would reconstruct ViewPlacements properly
    bom_table = reconstruct_bom_table(plan_data)
    
    # Create output directory
    output_dir = Path("output") / assembly_id / "drawing"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Prepare metadata
    metadata = {
        "assembly_id": assembly_id,
        "assembly_name": os.path.basename(step_path),
        "sheet_size": plan_data.get("sheet_size", "A4"),
        "scale": plan_data.get("scale", 1.0),
        "date": plan_data.get("date", ""),
        "part_id_mapping": {}  # Will be populated from snapshot if available
    }
    
    # For MVP, create minimal view placements
    # In production, these would be loaded from the plan
    view_placements = []  # Will be populated from plan_data
    
    # Render
    result = engine.render(
        plan=plan_data,
        input_step_path=step_path,
        output_dir=output_dir,
        view_placements=view_placements,
        bom_table=bom_table,
        balloons=None,
        metadata=metadata
    )
    
    if result.get("pdf_path"):
        print(f"\n✓ SUCCESS: PDF generated at {result['pdf_path']}")
        print(f"  Rendered views: {result.get('rendered_views', 0)}")
        if result.get("errors"):
            print(f"  Warnings: {result['errors']}")
        sys.exit(0)
    else:
        print(f"\n✗ FAILED: No PDF generated")
        if result.get("errors"):
            print(f"  Errors: {result['errors']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
