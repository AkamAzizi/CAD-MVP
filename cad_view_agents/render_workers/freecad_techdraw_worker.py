#!/usr/bin/env python3
"""
FreeCAD TechDraw worker for generating 2D drawings.
Uses FreeCAD GUI (TechDraw module) to create technical drawings.
"""
import sys
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# Prevent FreeCAD from auto-opening files passed as arguments
# Clear sys.argv to prevent FreeCAD from processing command-line files
_original_argv = sys.argv[:]
sys.argv = [sys.argv[0]]  # Keep only script name

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import FreeCAD
    # Prevent FreeCAD from opening files automatically
    # Note: Console.SetStatus may not be available in all FreeCAD versions
    
    import FreeCADGui
    import TechDraw
    import Draft
    FREECAD_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: FreeCAD not available: {e}", file=sys.stderr)
    sys.exit(1)


def load_drawing_plan(plan_path: str) -> Dict[str, Any]:
    """Load drawing plan from JSON file."""
    with open(plan_path, 'r') as f:
        return json.load(f)


def import_step_file(step_path: str, doc: Any) -> Any:
    """Import STEP file into FreeCAD document."""
    try:
        # Use Import module
        import Import
        Import.insert(step_path, doc.Name)
        
        # Find the imported object
        imported_objects = [obj for obj in doc.Objects if hasattr(obj, 'Shape')]
        if imported_objects:
            return imported_objects[-1]  # Return the last imported object
        else:
            raise RuntimeError("No objects imported from STEP file")
    except Exception as e:
        raise RuntimeError(f"Failed to import STEP file: {e}") from e


def create_techdraw_page(doc: Any, sheet_size: str, template_path: Optional[str] = None) -> Any:
    """Create a TechDraw page with template."""
    try:
        import TechDraw
        
        # Create page
        page = doc.addObject('TechDraw::DrawPage', 'Page')
        
        # Template property expects a DocumentObject, not a string path
        # If template_path is provided, we would need to load it as a DocumentObject first
        # For now, create page without template (TechDraw will use defaults)
        # page.Template = None  # None is the default
        
        # Set page size based on sheet_size (if supported)
        # TechDraw pages have standard sizes, but we'll let it use defaults
        
        doc.recompute()
        return page
    except Exception as e:
        raise RuntimeError(f"Failed to create TechDraw page: {e}") from e


def create_view(page: Any, obj: Any, view_direction: tuple, view_name: str, 
                position: tuple, scale: float) -> Any:
    """Create a TechDraw view on the page."""
    try:
        # Create view in the document, then add to page
        doc = page.Document
        view = doc.addObject('TechDraw::DrawViewPart', view_name)
        view.Source = [obj]
        
        # Set view direction (FreeCAD uses (X, Y, Z) tuple)
        view.Direction = FreeCAD.Vector(view_direction[0], view_direction[1], view_direction[2])
        
        # Set position (in page coordinates, in mm)
        view.X = position[0]
        view.Y = position[1]
        
        # Set scale
        view.Scale = scale
        
        # Note: ProjectionType is not a standard TechDraw property
        # Views are orthographic by default
        
        # Add view to page
        page.addView(view)
        
        doc.recompute()
        return view
    except Exception as e:
        print(f"WARN: Failed to create view {view_name}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return None


def add_bom_table(page: Any, bom_rows: List[Dict[str, Any]], position: tuple) -> None:
    """Add BOM table to TechDraw page."""
    try:
        # Create a simple text annotation for BOM
        # TechDraw doesn't have built-in BOM table, so we'll use annotations
        bom_text = "BOM:\n"
        bom_text += "Item | Part | Qty\n"
        bom_text += "----|------|----\n"
        
        for row in bom_rows[:10]:  # Limit to top 10
            item_no = row.get('item_number', '')
            part_id = row.get('part_id', '')
            qty = row.get('quantity', 1)
            bom_text += f"{item_no} | {part_id[:20]} | {qty}\n"
        
        # Create annotation in document, then add to page
        doc = page.Document
        annotation = doc.addObject('TechDraw::DrawViewAnnotation', 'BOM')
        annotation.Text = bom_text
        annotation.X = position[0]
        annotation.Y = position[1]
        
        # Add annotation to page
        page.addView(annotation)
        
        doc.recompute()
    except Exception as e:
        print(f"WARN: Failed to add BOM table: {e}", file=sys.stderr)


def add_balloons(page: Any, balloons: List[Dict[str, Any]]) -> None:
    """Add balloons to TechDraw page."""
    try:
        # TechDraw has balloon support via DrawViewBalloon
        for balloon in balloons:
            try:
                item_number = balloon.get('item_number', 0)
                anchor_point = balloon.get('anchor_point', (0, 0))
                
                # Create balloon in document, then add to page
                doc = page.Document
                balloon_obj = doc.addObject('TechDraw::DrawViewBalloon', f'Balloon_{item_number}')
                balloon_obj.Text = str(item_number)
                balloon_obj.X = anchor_point[0]
                balloon_obj.Y = anchor_point[1]
                
                # Link to view if available
                if 'view_name' in balloon:
                    # Find the view in the page's views
                    for view in page.Views:
                        if hasattr(view, 'Label') and view.Label == balloon['view_name']:
                            balloon_obj.SourceView = view
                            break
                
                # Add balloon to page
                page.addView(balloon_obj)
                
                doc.recompute()
            except Exception as e:
                print(f"WARN: Failed to add balloon {item_number}: {e}", file=sys.stderr)
                continue
    except Exception as e:
        print(f"WARN: Failed to add balloons: {e}", file=sys.stderr)


def export_pdf(page: Any, output_path: str) -> None:
    """Export TechDraw page to PDF."""
    try:
        # In console mode, TechDraw can't export PDF directly
        # Use SVG export then convert to PDF
        import tempfile
        
        # Export to SVG first
        svg_path = output_path.replace('.pdf', '.svg')
        doc = page.Document
        
        # TechDraw pages need to export via template
        # Try using the page's export method
        if hasattr(page, 'exportPageAsSvg'):
            page.exportPageAsSvg(svg_path)
        elif hasattr(page, 'Template'):
            # If page has a template, we can export
            # For now, create a simple SVG manually
            # This is a workaround - ideally we'd use TechDraw's export
            raise RuntimeError("SVG export requires page template or GUI mode")
        else:
            # No template, can't export SVG in console mode
            raise RuntimeError("TechDraw page needs template for SVG export in console mode")
        
        # Convert SVG to PDF using reportlab
        try:
            from reportlab.lib.pagesizes import A4, A3, A2, A1, A0
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm
            
            # Try to import svglib for SVG rendering
            try:
                from svglib.svglib import svg2rlg
                from reportlab.graphics import renderPDF
                
                # Convert SVG to PDF
                drawing = svg2rlg(svg_path)
                if drawing:
                    renderPDF.drawToFile(drawing, output_path)
                    # Clean up SVG
                    try:
                        os.unlink(svg_path)
                    except Exception:
                        pass
                    return
            except ImportError:
                # svglib not available, create a simple PDF with text
                print("  [WARN] svglib not available, creating placeholder PDF")
                c = canvas.Canvas(output_path, pagesize=A4)
                c.drawString(50 * mm, 200 * mm, "TechDraw page exported as SVG")
                c.drawString(50 * mm, 180 * mm, f"SVG file: {svg_path}")
                c.save()
                return
        except Exception as e:
            raise RuntimeError(f"Failed to convert SVG to PDF: {e}") from e
            
    except Exception as e:
        raise RuntimeError(f"Failed to export PDF: {e}") from e


def main():
    """Main worker function."""
    # Restore original argv for argument parsing
    sys.argv = _original_argv
    
    parser = argparse.ArgumentParser(description='FreeCAD TechDraw worker for 2D drawing generation')
    parser.add_argument('drawing_plan', type=str, help='Path to drawing_plan.json')
    parser.add_argument('step_file', type=str, help='Path to STEP file')
    parser.add_argument('output_dir', type=str, help='Output directory')
    parser.add_argument('--template', type=str, help='Path to TechDraw template (optional)')
    
    args = parser.parse_args()
    
    # Clear any documents that FreeCAD might have auto-opened
    if FreeCAD.listDocuments():
        for doc_name in list(FreeCAD.listDocuments().keys()):
            try:
                FreeCAD.closeDocument(doc_name)
            except Exception:
                pass
    
    try:
        # Load drawing plan
        plan = load_drawing_plan(args.drawing_plan)
        
        # Create new FreeCAD document
        doc = FreeCAD.newDocument('Drawing')
        
        # Import STEP file
        print(f"Importing STEP file: {args.step_file}")
        print(f"  [DEBUG] FreeCAD document objects before import: {len(doc.Objects)}")
        imported_obj = import_step_file(args.step_file, doc)
        doc.recompute()
        print(f"  [DEBUG] FreeCAD document objects after import: {len(doc.Objects)}")
        print(f"  [DEBUG] Imported object: {imported_obj.Label if hasattr(imported_obj, 'Label') else 'N/A'}")
        
        # Get sheet size from plan
        sheet_size = plan.get('sheet_size', 'A4')
        
        # Create TechDraw page
        template_path = args.template
        if not template_path:
            # Look for template in render_workers directory
            template_path = os.path.join(os.path.dirname(__file__), 'techdraw_template.svg')
        
        print(f"Creating TechDraw page (sheet: {sheet_size})")
        page = create_techdraw_page(doc, sheet_size, template_path)
        
        # Create views from drawing plan
        views = plan.get('views', [])
        view_placements = plan.get('view_placements', [])
        
        print(f"Creating {len(views)} views")
        created_views = []
        for i, view_info in enumerate(views):
            view_name = view_info.get('name', f'View_{i}')
            view_direction = tuple(view_info.get('direction', [0, 0, 1]))
            
            # Get placement info
            if i < len(view_placements):
                placement = view_placements[i]
                position = tuple(placement.get('position', [50 + i * 100, 50]))
                scale = placement.get('scale', 1.0)
            else:
                position = (50 + i * 100, 50)
                scale = 1.0
            
            view = create_view(page, imported_obj, view_direction, view_name, position, scale)
            if view:
                created_views.append(view)
        
        # Add BOM table
        bom_rows = plan.get('bom', {}).get('rows', [])
        if bom_rows:
            print(f"Adding BOM table with {len(bom_rows)} rows")
            bom_position = (50, 50)  # Bottom-left
            add_bom_table(page, bom_rows, bom_position)
        
        # Add balloons
        balloons = plan.get('balloons', [])
        if balloons:
            print(f"Adding {len(balloons)} balloons")
            add_balloons(page, balloons)
        
        # Export PDF
        output_path = os.path.join(args.output_dir, 'drawing.pdf')
        print(f"Exporting PDF to: {output_path}")
        export_pdf(page, output_path)
        
        print(f"SUCCESS: PDF exported to {output_path}")
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: Worker failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
