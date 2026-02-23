#!/usr/bin/env python3
"""
Test script for CADQuery render engine only.
Bypasses FreeCAD-dependent parts for quick testing.
"""
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from render.engines.cadquery_engine import CADQueryEngine
from core.layout_engine import LayoutEngine, SheetSize
from core.view_candidates import ViewCandidate, ViewCandidateGenerator
from core.drawing_plan import DrawingPlan

def test_cadquery_engine(step_path: str):
    """Test CADQuery engine with a STEP file."""
    
    # Check if CADQuery is available
    engine = CADQueryEngine()
    if not engine.is_available():
        print("ERROR: CADQuery is not installed.")
        print("Install with: pip install cadquery")
        return False
    
    print("✓ CADQuery engine is available")
    
    # Create minimal test data
    view_candidate = ViewCandidate(
        name="front",
        direction=(0, 0, 1),
        type="orthographic",
        description="Front view"
    )
    
    from core.layout_engine import ViewPlacement
    view_placement = ViewPlacement(
        view=view_candidate,
        position=(50.0, 200.0),  # mm from bottom-left
        scale=1.0,
        width_mm=100.0,
        height_mm=100.0
    )
    
    # Create minimal drawing plan
    drawing_plan = {
        "assembly_id": "test_asm",
        "sheet_size": "A4",
        "scale": 1.0
    }
    
    # Create output directory
    output_dir = Path("output") / "test_cadquery" / "drawing"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Test render
    print(f"\nTesting render with: {step_path}")
    print(f"Output directory: {output_dir}")
    
    result = engine.render(
        plan=drawing_plan,
        input_step_path=step_path,
        output_dir=output_dir,
        view_placements=[view_placement],
        bom_table=None,
        balloons=None,
        metadata={
            "assembly_id": "test_asm",
            "assembly_name": os.path.basename(step_path),
            "sheet_size": "A4",
            "scale": 1.0,
            "date": "2025-01-29",
            "part_id_mapping": {}
        }
    )
    
    if result.get("pdf_path"):
        print(f"\n✓ SUCCESS: PDF generated at {result['pdf_path']}")
        print(f"  Rendered views: {result.get('rendered_views', 0)}")
        if result.get("errors"):
            print(f"  Warnings: {result['errors']}")
        return True
    else:
        print(f"\n✗ FAILED: No PDF generated")
        if result.get("errors"):
            print(f"  Errors: {result['errors']}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_cadquery_only.py <step_file>")
        print("\nExample:")
        print("  python test_cadquery_only.py ../web/uploads/eb9f276cc74e4e4ba6fff36e05b3cc62_strut.step")
        sys.exit(1)
    
    step_path = sys.argv[1]
    if not os.path.exists(step_path):
        print(f"ERROR: File not found: {step_path}")
        sys.exit(1)
    
    success = test_cadquery_engine(step_path)
    sys.exit(0 if success else 1)
