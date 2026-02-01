"""
TechDraw Agent for generating technical drawings from CAD assemblies.
Integrates with FreeCAD TechDraw module for 2D projection generation.
"""
import os
import FreeCAD
from typing import List, Optional, Dict, Any, Tuple
from core.layout_engine import ViewPlacement, SheetSize
from core.view_candidates import ViewCandidate
from config.drawing_standards import DrawingStandards, ProjectionStandard
from config.sheet_templates import SheetTemplate, TEMPLATES
from utils.freecad_utils import is_techdraw_available


class TechDrawAgent:
    """Generates technical drawings using FreeCAD TechDraw module."""
    
    def __init__(self, projection_standard: ProjectionStandard = None):
        """
        Initialize TechDraw agent.
        
        Args:
            projection_standard: Projection standard (THIRD_ANGLE or FIRST_ANGLE)
        """
        self.projection_standard = projection_standard or DrawingStandards.DEFAULT_PROJECTION
        self.techdraw_available = is_techdraw_available()
        
        # Check if GUI is available (needed for safe SVG export)
        # In headless mode (freecadcmd), GUI modules may import but not work correctly
        self.gui_available = False
        try:
            import FreeCADGui
            # Try to access a GUI-specific method to verify GUI is actually working
            # If this fails, we're in headless mode even if import succeeded
            if hasattr(FreeCADGui, 'getDocument'):
                # Additional check: try to verify we're not in freecadcmd
                import sys
                if 'freecadcmd' not in sys.argv[0].lower():
                    self.gui_available = True
        except (ImportError, AttributeError, Exception):
            self.gui_available = False
        
        if not self.techdraw_available:
            print("Warning: TechDraw module not available. Fallback exporters will be used.")
    
    def create_page(self, sheet_size: SheetSize, template_name: str = "standard") -> Any:
        """
        Create a TechDraw page for the technical drawing.
        
        Args:
            sheet_size: SheetSize object with dimensions
            template_name: Template name (default: "standard")
            
        Returns:
            TechDraw page object or None if TechDraw unavailable
        """
        if not self.techdraw_available:
            return None
        
        try:
            import TechDraw
            
            # Get the active document (assumed to be created by import_agent)
            doc = FreeCAD.ActiveDocument
            if doc is None:
                raise ValueError("No active FreeCAD document found")
            
            # Create TechDraw page
            page = doc.addObject("TechDraw::DrawPage", "TechDrawPage")
            
            # TechDraw requires a template to add views
            # Try to find or create a default template
            template = self._get_or_create_template(doc, sheet_size)
            if template:
                page.Template = template
            else:
                # If no template available, we can't use TechDraw views
                # The page will be created but views will fail
                print("  [WARN] No TechDraw template available - views will not be created")
                page.Template = None
            
            # Store sheet size info in page metadata
            page.Label = f"Drawing_{sheet_size.name}"
            
            # Recompute to initialize the page (only page, not document to avoid loops)
            page.recompute()
            
            # Try to show the page (may not work in headless mode)
            try:
                if hasattr(page, 'ViewObject') and page.ViewObject:
                    page.ViewObject.show()
            except:
                pass  # Ignore if ViewObject not available in headless mode
            
            # Set page dimensions (TechDraw uses templates, but we can customize)
            # Note: TechDraw page size is typically controlled by template
            # For MVP, we'll use default template and rely on view scaling
            
            return page
            
        except Exception as e:
            print(f"Error creating TechDraw page: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_or_create_template(self, doc: Any, sheet_size: Any) -> Optional[Any]:
        """
        Try to get an existing template or create a simple one.
        
        Args:
            doc: FreeCAD document
            sheet_size: SheetSize object
            
        Returns:
            Template object or None
        """
        try:
            import TechDraw
            
            # Try to find an existing template in the document
            for obj in doc.Objects:
                if hasattr(obj, 'TypeId') and 'TechDraw::DrawTemplate' in str(obj.TypeId):
                    return obj
            
            # Try to load a default template from FreeCAD's template directory
            # FreeCAD templates are typically in Resources/Mod/TechDraw/Templates
            try:
                import os
                import FreeCAD as App
                
                # Get FreeCAD's resource directory
                resource_dir = App.getResourceDir()
                template_dir = os.path.join(resource_dir, "Mod", "TechDraw", "Templates")
                
                # Try common template files - prioritize landscape A4
                template_files = [
                    "A4_Landscape_blank.svg",
                    "Default_Template_A4_Landscape.svg",
                    "A4_Landscape_ISO5457_minimal.svg",
                    "A4_Landscape.svg",
                    "A4_Portrait.svg"
                ]
                
                for template_file in template_files:
                    template_path = os.path.join(template_dir, template_file)
                    if os.path.exists(template_path):
                        # Load template
                        template = doc.addObject("TechDraw::DrawSVGTemplate", "Template")
                        template.Template = template_path
                        # Only recompute the template, not the whole document
                        template.recompute()
                        return template
            except Exception as e:
                # Template loading failed, continue
                pass
            
            # If no template found, return None (will use fallback exporters)
            return None
            
        except Exception as e:
            return None
    
    def create_view(self, page: Any, placement: ViewPlacement, doc: Any, 
                   base_object: Any = None) -> Optional[Any]:
        """
        Create a TechDraw view from a view placement.
        
        Args:
            page: TechDraw page object
            placement: ViewPlacement with view candidate and position
            doc: FreeCAD document
            base_object: Base object to project (if None, projects entire document)
            
        Returns:
            TechDraw view object or None if failed
        """
        if not self.techdraw_available or page is None:
            return None
        
        try:
            import TechDraw
            
            # Determine view type
            view_candidate = placement.view
            
            # For orthographic views, create ProjectionGroup or individual views
            # For isometric views, create a ProjectionGroup with isometric projection
            
            if view_candidate.type == "orthographic":
                view = self._create_orthographic_view(page, placement, doc, base_object)
            elif view_candidate.type == "isometric":
                view = self._create_isometric_view(page, placement, doc, base_object)
            else:
                # Default to orthographic
                view = self._create_orthographic_view(page, placement, doc, base_object)
            
            if view:
                # Check if page has a template (required to add views)
                if page.Template is None:
                    print(f"  [WARN] Cannot add view '{view_candidate.name}': page has no template")
                    return None
                
                # Set view position on page
                view.X = placement.position[0]  # X position in mm
                view.Y = placement.position[1]  # Y position in mm
                view.Scale = placement.scale
                
                # Configure view appearance
                view.CoarseView = True  # Faster rendering
                view.SmoothVisible = True
                view.SmoothHidden = True
                view.SeamVisible = True
                view.SeamHidden = True
                view.IsoVisible = True
                view.IsoHidden = True
                view.HardHidden = True
                
                # Recompute view before adding (only recompute the view, not the whole document)
                # Use try-except to handle projection errors gracefully
                try:
                    view.recompute()
                except Exception as e:
                    # TechDraw projection can fail on complex geometry
                    error_msg = str(e)
                    if "OCC error" in error_msg or "projectShape" in error_msg:
                        print(f"  [WARN] TechDraw projection failed for view '{view_candidate.name}': {error_msg[:100]}")
                        print(f"  [INFO] This is common with complex assemblies. View will be skipped.")
                    else:
                        print(f"  [WARN] View recompute failed: {e}")
                    return None
                
                # Add view to page
                try:
                    page.addView(view)
                    # Only recompute the page, not the whole document to avoid recomputation loops
                    page.recompute()
                except Exception as e:
                    print(f"  [WARN] Failed to add view to page: {e}")
                    return None
            
            return view
            
        except Exception as e:
            print(f"Error creating TechDraw view: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _create_orthographic_view(self, page: Any, placement: ViewPlacement, 
                                  doc: Any, base_object: Any) -> Optional[Any]:
        """Create an orthographic projection view."""
        import TechDraw
        
        # Get all objects to project
        if base_object is None:
            objects_to_project = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape is not None]
        else:
            objects_to_project = [base_object]
        
        if not objects_to_project:
            return None
        
        # Create a compound shape from all objects for projection
        import Part
        if len(objects_to_project) == 1:
            compound = objects_to_project[0].Shape
        else:
            compound = Part.makeCompound([obj.Shape for obj in objects_to_project])
        
        # Create a temporary object to hold the compound
        temp_obj = doc.addObject("Part::Feature", "TempProjection")
        temp_obj.Shape = compound
        
        # Create TechDraw view
        view = doc.addObject("TechDraw::DrawViewPart", placement.view.name)
        view.Source = [temp_obj]
        
        # Set projection direction based on view candidate
        direction = placement.view.direction
        view.Direction = direction
        
        # Set rotation for standard views
        self._set_view_rotation(view, placement.view)
        
        # Recompute view before returning (don't recompute document to avoid loops)
        # Wrap in try-except to handle projection errors
        try:
            view.recompute()
        except Exception as e:
            # TechDraw projection can fail on complex geometry - return None to skip this view
            error_msg = str(e)
            if "OCC error" in error_msg or "projectShape" in error_msg:
                print(f"  [WARN] TechDraw projection failed: {error_msg[:100]}")
            return None
        
        return view
    
    def _create_isometric_view(self, page: Any, placement: ViewPlacement, 
                              doc: Any, base_object: Any) -> Optional[Any]:
        """Create an isometric projection view."""
        import TechDraw
        import Part
        
        # Get all objects to project
        if base_object is None:
            objects_to_project = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape is not None]
        else:
            objects_to_project = [base_object]
        
        if not objects_to_project:
            return None
        
        # Create compound
        if len(objects_to_project) == 1:
            compound = objects_to_project[0].Shape
        else:
            compound = Part.makeCompound([obj.Shape for obj in objects_to_project])
        
        temp_obj = doc.addObject("Part::Feature", "TempIsoProjection")
        temp_obj.Shape = compound
        
        # Create TechDraw view with isometric direction
        view = doc.addObject("TechDraw::DrawViewPart", placement.view.name)
        view.Source = [temp_obj]
        
        # Set isometric direction
        direction = placement.view.direction
        view.Direction = direction
        view.Rotation = 0  # Isometric views don't need rotation
        
        return view
    
    def _set_view_rotation(self, view: Any, view_candidate: ViewCandidate):
        """Set rotation for standard orthographic views."""
        # Standard view rotations for TechDraw
        # This is a simplified implementation - full implementation would handle
        # all view orientations properly
        
        if view_candidate.name == "front":
            view.Rotation = 0
        elif view_candidate.name == "top":
            view.Rotation = 0
        elif view_candidate.name == "right":
            view.Rotation = 0
        elif view_candidate.name == "left":
            view.Rotation = 180
        elif view_candidate.name == "back":
            view.Rotation = 180
        elif view_candidate.name == "bottom":
            view.Rotation = 180
        else:
            view.Rotation = 0
    
    def apply_hidden_lines(self, views: List[Any], style: str = "Dashed") -> None:
        """
        Apply hidden line style to views.
        
        Args:
            views: List of TechDraw view objects
            style: Line style for hidden lines ("Dashed", "DashDot", etc.)
        """
        if not self.techdraw_available:
            return
        
        try:
            for view in views:
                if view is None:
                    continue
                
                # TechDraw handles hidden lines automatically based on view settings
                # We can configure the appearance here
                view.HardHidden = True  # Show hidden lines
                view.SmoothHidden = True
                view.IsoHidden = True
                view.SeamHidden = True
                
                # Line style is typically controlled at the page or template level
                # For MVP, we rely on TechDraw defaults
                
        except Exception as e:
            print(f"Error applying hidden lines: {e}")
    
    def add_balloons(self, page: Any, balloons: List[Any]) -> None:
        """
        Add balloons to the TechDraw page.
        
        Args:
            page: TechDraw page object
            balloons: List of Balloon objects from balloon_engine
        """
        if not self.techdraw_available or page is None:
            return
        
        if not balloons:
            return
        
        try:
            import TechDraw
            from core.balloon_engine import Balloon
            
            doc = page.Document if hasattr(page, "Document") else FreeCAD.ActiveDocument
            
            for balloon in balloons:
                if not isinstance(balloon, Balloon):
                    continue
                
                # Create balloon annotation (circle with number)
                # TechDraw uses RichTextAnnotation or custom drawing elements
                # For MVP, we'll create a simple annotation
                
                # Create a balloon annotation object
                # Note: TechDraw may not have direct balloon support, so we'll use
                # a combination of drawing elements or annotations
                
                # Create leader line
                leader = balloon.leader
                if leader:
                    # Create leader line as a drawing element
                    # TechDraw uses DrawViewDimension or custom geometry
                    # For MVP, we'll store balloon data for export
                    pass
                
                # Store balloon data in document properties instead of Meta
                # Use document properties for persistent storage
                if not hasattr(doc, 'Balloons'):
                    doc.addProperty('App::PropertyStringList', 'Balloons')
                    doc.Balloons = []
                
                balloon_data = {
                    "item_number": balloon.item_number,
                    "part_id": balloon.part_id,
                    "position": balloon.position,
                    "leader_start": leader.start_point if leader else None,
                    "leader_end": leader.end_point if leader else None,
                    "radius": balloon.style.circle_radius
                }
                
                # Convert to string for storage in StringList property
                import json
                balloon_json = json.dumps(balloon_data)
                current_balloons = list(doc.Balloons) if doc.Balloons else []
                current_balloons.append(balloon_json)
                doc.Balloons = current_balloons
            
            # Recompute page (avoid document recompute to prevent loops)
            page.recompute()
            
        except Exception as e:
            print(f"Error adding balloons: {e}")
            import traceback
            traceback.print_exc()
    
    def add_bom_table(self, page: Any, bom_table: Any, position: tuple) -> None:
        """
        Add BOM table to the TechDraw page.
        
        Args:
            page: TechDraw page object
            bom_table: BOMTable object from bom_generator
            position: (x, y) position on page
        """
        if not self.techdraw_available or page is None:
            return
        
        if bom_table is None:
            return
        
        try:
            from core.bom_generator import BOMTable
            
            if not isinstance(bom_table, BOMTable):
                return
            
            # Store BOM data in document properties
            doc = page.Document if hasattr(page, "Document") else FreeCAD.ActiveDocument
            
            if not hasattr(doc, 'BOMTable'):
                doc.addProperty('App::PropertyStringList', 'BOMTable')
                doc.BOMTable = []
            
            bom_data = {
                "columns": bom_table.columns,
                "rows": [
                    {
                        "item": part.item_number,
                        "part_number": part.part_id,
                        "description": part.name,
                        "quantity": part.quantity,
                        "material": part.material
                    }
                    for part in bom_table.parts
                ],
                "position": position
            }
            
            # Convert to string for storage
            import json
            bom_json = json.dumps(bom_data)
            doc.BOMTable = [bom_json]
            
            # Recompute page (avoid document recompute to prevent loops)
            page.recompute()
            
        except Exception as e:
            print(f"Error adding BOM table: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_page_as_svg(self, doc: Any, page: Any, svg_path: str) -> None:
        """
        Export TechDraw page to SVG file.
        Works in both GUI and headless mode (with risk of segfaults in headless).
        
        In headless mode, this is called but may cause segmentation faults with complex assemblies.
        We accept this risk since the conversion to PDF happens outside FreeCAD process.
        
        Args:
            doc: FreeCAD document
            page: TechDraw page object
            svg_path: Output SVG file path
            
        Raises:
            RuntimeError: If all SVG export methods fail
        """
        os.makedirs(os.path.dirname(svg_path) if os.path.dirname(svg_path) else ".", exist_ok=True)
        
        # Method 1: Try TechDrawGui.exportPageAsSvg (works in GUI mode)
        try:
            import TechDrawGui
            TechDrawGui.exportPageAsSvg(page, svg_path)
            
            # Verify SVG was created
            if os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                return
            
            raise RuntimeError("TechDrawGui.exportPageAsSvg created empty SVG file")
            
        except ImportError:
            pass  # TechDrawGui not available in headless
        except AttributeError:
            pass  # Method doesn't exist in this FreeCAD version
        except Exception as e:
            error_msg = str(e)
            if "TechDrawGui" not in error_msg:
                # Real error, not just import failure
                raise RuntimeError(f"TechDrawGui SVG export failed: {e}") from e
            pass
        
        # Method 2: Try ImportGui.export (alternative GUI method)
        try:
            import ImportGui
            ImportGui.export([page], svg_path)
            
            if os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                return
            
            raise RuntimeError("ImportGui.export created empty SVG file")
            
        except ImportError:
            pass  # ImportGui not available in headless
        except AttributeError:
            pass  # Method doesn't exist
        except Exception as e:
            error_msg = str(e)
            if "ImportGui" not in error_msg:
                raise RuntimeError(f"ImportGui SVG export failed: {e}") from e
            pass
        
        # Method 3: Try TechDraw module export functions (if available)
        try:
            import TechDraw
            
            # Check if TechDraw has export function
            if hasattr(TechDraw, 'exportPageAsSvg'):
                TechDraw.exportPageAsSvg(page, svg_path)
                
                if os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                    return
            
            # Try exporting individual views as SVG
            # WARNING: This can cause segmentation faults in headless mode with complex assemblies
            # Only attempt if GUI is available
            if self.gui_available and hasattr(page, 'Views') and page.Views:
                svg_parts = []
                for view in page.Views:
                    try:
                        if hasattr(TechDraw, 'viewPartAsSvg'):
                            svg_content = TechDraw.viewPartAsSvg(view)
                            if svg_content:
                                svg_parts.append(svg_content)
                    except Exception as e:
                        # Skip individual view export if it fails (can cause segfault)
                        error_msg = str(e)
                        if "OCC error" in error_msg or "segmentation" in error_msg.lower():
                            # Likely segfault risk, skip this view
                            continue
                        raise
                
                if svg_parts:
                    # Combine SVG parts into a single SVG file
                    # Basic SVG wrapper
                    svg_header = '<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg">\n'
                    svg_footer = '</svg>\n'
                    
                    with open(svg_path, 'w') as f:
                        f.write(svg_header)
                        for part in svg_parts:
                            f.write(part)
                        f.write(svg_footer)
                    
                    if os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                        return
            
        except Exception as e:
            pass  # TechDraw export methods not available
        
        # If all methods failed
        raise RuntimeError(
            "All SVG export methods failed. TechDraw page cannot be exported as SVG in headless mode. "
            "This may require GUI mode or additional FreeCAD plugins."
        )
    
    def _project_shape_for_view(self, doc: Any, source_obj: Any, view_name: str) -> Any:
        """
        Create 2D projection of source document object for a given view using Draft.makeShape2DView.
        
        Args:
            doc: FreeCAD document
            source_obj: App.DocumentObject to project (must be a document object, not a Shape)
            view_name: View name ("front", "top", "right", "iso")
            
        Returns:
            Draft Shape2DView object with 2D projection
            
        Raises:
            RuntimeError: If Draft module is not available
        """
        try:
            import Draft
        except ImportError as e:
            raise RuntimeError("Draft module not available for Shape2DView projection") from e
        
        # Define view directions (normal vectors for projection)
        dirs = {
            "front": FreeCAD.Vector(0, 1, 0),  # Front view: look along +Y
            "top":   FreeCAD.Vector(0, 0, 1),  # Top view: look along +Z
            "right": FreeCAD.Vector(1, 0, 0),  # Right view: look along +X
            "iso":   FreeCAD.Vector(1, 1, 1),  # Isometric: diagonal
        }
        
        # Get direction vector for this view
        v = dirs.get(view_name, FreeCAD.Vector(0, 1, 0))
        
        # Normalize vector (required by makeShape2DView)
        try:
            v.normalize()
        except Exception:
            # If normalization fails (zero vector), use default
            v = FreeCAD.Vector(0, 1, 0)
        
        # Create 2D projection using Draft.makeShape2DView (requires DocumentObject, not Shape)
        obj = Draft.makeShape2DView(source_obj, v)
        obj.Label = f"Shape2D_{view_name}"
        
        # Recompute to ensure projection is calculated
        try:
            doc.recompute()
        except Exception:
            pass  # Don't fail if recompute has issues
        
        return obj
    
    def _get_shape_objects_for_projection(self, doc: Any, max_objects: int = 50) -> List[Any]:
        """
        Select 'safe' shape objects for projection by excluding TechDraw objects and selecting largest parts.
        
        Args:
            doc: FreeCAD document
            max_objects: Maximum number of objects to return (default: 50)
            
        Returns:
            List of DocumentObjects sorted by size (largest first), excluding TechDraw objects
        """
        shape_objects = []
        
        # Collect valid shape objects, excluding TechDraw objects and temporary Shape2D objects
        for obj in doc.Objects:
            # Skip TechDraw objects, templates, and Shape2D objects
            obj_type = obj.TypeId if hasattr(obj, 'TypeId') else ""
            if "TechDraw" in obj_type or "Shape2D" in obj.Label or "TmpSource" in obj.Label:
                continue
            
            # Only include objects with valid shapes
            if hasattr(obj, 'Shape') and obj.Shape is not None:
                try:
                    # Check if shape has a valid bounding box
                    bbox = obj.Shape.BoundBox
                    if bbox.isValid():
                        shape_objects.append(obj)
                except Exception:
                    # Skip objects with invalid bounding boxes
                    continue
        
        if not shape_objects:
            return []
        
        # Sort by approximate size (using diagonal length of bounding box)
        # Larger parts are more important for assembly representation
        def get_size(obj):
            try:
                bbox = obj.Shape.BoundBox
                if bbox.isValid():
                    return bbox.DiagonalLength
                return 0.0
            except Exception:
                return 0.0
        
        shape_objects.sort(key=get_size, reverse=True)
        
        # Return top N objects
        return shape_objects[:max_objects]
    
    def _export_view_as_svg(self, doc: Any, view_obj: Any, view_name: str, svg_path: str) -> bool:
        """
        Export a TechDraw view as SVG by creating 2D projection and exporting it.
        
        Args:
            doc: FreeCAD document
            view_obj: TechDraw view object (to get source shape from)
            view_name: View name ("front", "top", "right", "iso")
            svg_path: Output SVG file path
            
        Returns:
            True if SVG export succeeded, False otherwise
        """
        try:
            import TechDraw
            import Part
            
            # Get source shape from view
            source_obj = None
            source_shape = None
            temp_src = None  # Temporary object to hold Shape if needed
            
            # Try to get source from view.Source
            if hasattr(view_obj, 'Source') and view_obj.Source:
                source_obj = view_obj.Source[0] if isinstance(view_obj.Source, list) else view_obj.Source
                if hasattr(source_obj, 'Shape'):
                    source_shape = source_obj.Shape
            
            # If no source from view, create compound from all shapes in document
            if source_shape is None:
                shapes = [obj.Shape for obj in doc.Objects if hasattr(obj, "Shape") and obj.Shape is not None]
                if not shapes:
                    print(f"  [WARN] No shapes found for view '{view_name}' projection")
                    return False
                
                if len(shapes) == 1:
                    source_shape = shapes[0]
                else:
                    source_shape = Part.makeCompound(shapes)
                source_obj = None  # Will create temp object below
            
            # Wrap source_shape in a temporary DocumentObject if source_obj is None
            # Draft.makeShape2DView() requires App.DocumentObject, not Part.Shape
            temp_src = None
            temp_src_subset = None
            shape2d_obj = None
            
            # ATTEMPT A: Try full projection first
            projection_success = False
            try:
                if source_obj is None:
                    # Create temporary Part::Feature to hold the shape
                    temp_src = doc.addObject("Part::Feature", f"TmpSource_{view_name}")
                    temp_src.Shape = source_shape
                    doc.recompute()
                    source_obj = temp_src
                
                # Create 2D projection using Draft.makeShape2DView (requires DocumentObject)
                try:
                    shape2d_obj = self._project_shape_for_view(doc, source_obj, view_name)
                    print(f"  [OK] Tier2: Projected source shape for view '{view_name}' via Draft.makeShape2DView")
                    projection_success = True
                except (RuntimeError, Exception) as e:
                    error_msg = str(e)
                    # Check for OCC/projection errors
                    if "OCC error" in error_msg or "projectShape" in error_msg or "projection" in error_msg.lower():
                        print(f"  [WARN] Tier2: Projection attempt A failed (OCC error: {error_msg[:80]}), falling back to subset projection")
                    else:
                        print(f"  [WARN] Tier2: Projection attempt A failed for view '{view_name}': {error_msg[:80]}, falling back to subset projection")
                    projection_success = False
                    
                    # Cleanup shape2d_obj if it was partially created
                    try:
                        if shape2d_obj:
                            doc.removeObject(shape2d_obj.Name)
                            shape2d_obj = None
                    except Exception:
                        pass
            
            except Exception as e:
                error_msg = str(e)
                if "OCC error" in error_msg or "projectShape" in error_msg:
                    print(f"  [WARN] Tier2: Projection attempt A failed (OCC error: {error_msg[:80]}), falling back to subset projection")
                else:
                    print(f"  [WARN] Tier2: Projection attempt A failed for view '{view_name}': {error_msg[:80]}, falling back to subset projection")
                projection_success = False
            
            # ATTEMPT B: If full projection failed, try subset projection with biggest parts
            if not projection_success:
                try:
                    # Get safe shape objects (biggest parts, excluding TechDraw objects)
                    safe_objects = self._get_shape_objects_for_projection(doc, max_objects=30)
                    
                    if not safe_objects:
                        print(f"  [WARN] No safe shape objects found for subset projection of view '{view_name}'")
                        # Cleanup temp_src if created
                        try:
                            if temp_src:
                                doc.removeObject(temp_src.Name)
                        except Exception:
                            pass
                        return False
                    
                    # Build compound from subset of shapes
                    subset_shapes = [obj.Shape for obj in safe_objects]
                    if len(subset_shapes) == 1:
                        subset_shape = subset_shapes[0]
                    else:
                        subset_shape = Part.makeCompound(subset_shapes)
                    
                    # Create temporary Part::Feature for subset
                    temp_src_subset = doc.addObject("Part::Feature", f"TmpSourceSubset_{view_name}")
                    temp_src_subset.Shape = subset_shape
                    doc.recompute()
                    
                    print(f"  [INFO] Tier2: Subset projection using top {len(safe_objects)} shapes for view '{view_name}'")
                    
                    # Try projection with subset
                    try:
                        shape2d_obj = self._project_shape_for_view(doc, temp_src_subset, view_name)
                        projection_success = True
                        print(f"  [OK] Tier2: Projected subset shape for view '{view_name}' via Draft.makeShape2DView")
                    except (RuntimeError, Exception) as e:
                        error_msg = str(e)
                        print(f"  [WARN] Tier2: Subset projection also failed for view '{view_name}': {error_msg[:80]}")
                        projection_success = False
                        # Cleanup
                        try:
                            if shape2d_obj:
                                doc.removeObject(shape2d_obj.Name)
                                shape2d_obj = None
                        except Exception:
                            pass
                        try:
                            if temp_src_subset:
                                doc.removeObject(temp_src_subset.Name)
                        except Exception:
                            pass
                        try:
                            if temp_src:
                                doc.removeObject(temp_src.Name)
                        except Exception:
                            pass
                        return False
                        
                except Exception as e:
                    error_msg = str(e)
                    print(f"  [WARN] Tier2: Subset projection setup failed for view '{view_name}': {error_msg[:80]}")
                    # Cleanup
                    try:
                        if temp_src_subset:
                            doc.removeObject(temp_src_subset.Name)
                    except Exception:
                        pass
                    try:
                        if temp_src:
                            doc.removeObject(temp_src.Name)
                    except Exception:
                        pass
                    return False
            
            # Export 2D shape to SVG (works for both Attempt A and Attempt B)
            if not projection_success or shape2d_obj is None:
                # Cleanup
                try:
                    if shape2d_obj:
                        doc.removeObject(shape2d_obj.Name)
                except Exception:
                    pass
                try:
                    if temp_src_subset:
                        doc.removeObject(temp_src_subset.Name)
                except Exception:
                    pass
                try:
                    if temp_src:
                        doc.removeObject(temp_src.Name)
                except Exception:
                    pass
                return False
            
            try:
                # Export 2D shape to SVG using TechDraw.exportSVGEdges
                if not hasattr(shape2d_obj, 'Shape') or shape2d_obj.Shape is None:
                    print(f"  [WARN] Shape2D object for view '{view_name}' has no Shape")
                    # Cleanup on error
                    try:
                        if shape2d_obj:
                            doc.removeObject(shape2d_obj.Name)
                    except Exception:
                        pass
                    try:
                        if temp_src_subset:
                            doc.removeObject(temp_src_subset.Name)
                    except Exception:
                        pass
                    try:
                        if temp_src:
                            doc.removeObject(temp_src.Name)
                    except Exception:
                        pass
                    return False
                
                # TechDraw.exportSVGEdges takes Part.Shape (not DrawViewPart) and returns SVG string
                svg_content = TechDraw.exportSVGEdges(shape2d_obj.Shape)
                
                # Write SVG content to file
                if svg_content:
                    if isinstance(svg_content, bytes):
                        with open(svg_path, 'wb') as f:
                            f.write(svg_content)
                    else:
                        with open(svg_path, 'w', encoding='utf-8') as f:
                            f.write(str(svg_content))
                    
                    # Verify SVG was created
                    if os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                        print(f"  [OK] Tier2: Exported SVG for view '{view_name}' to {os.path.basename(svg_path)}")
                        
                        # Cleanup: remove temporary objects
                        try:
                            if shape2d_obj:
                                doc.removeObject(shape2d_obj.Name)
                        except Exception:
                            pass
                        try:
                            if temp_src_subset:
                                doc.removeObject(temp_src_subset.Name)
                        except Exception:
                            pass
                        try:
                            if temp_src:
                                doc.removeObject(temp_src.Name)
                        except Exception:
                            pass
                        try:
                            doc.recompute()
                        except Exception:
                            pass
                        
                        return True
                    else:
                        print(f"  [WARN] SVG export for view '{view_name}' created empty file")
                        # Cleanup on error
                        try:
                            if shape2d_obj:
                                doc.removeObject(shape2d_obj.Name)
                        except Exception:
                            pass
                        try:
                            if temp_src_subset:
                                doc.removeObject(temp_src_subset.Name)
                        except Exception:
                            pass
                        try:
                            if temp_src:
                                doc.removeObject(temp_src.Name)
                        except Exception:
                            pass
                        return False
                else:
                    print(f"  [WARN] TechDraw.exportSVGEdges returned no content for view '{view_name}'")
                    # Cleanup on error
                    try:
                        if shape2d_obj:
                            doc.removeObject(shape2d_obj.Name)
                    except Exception:
                        pass
                    try:
                        if temp_src_subset:
                            doc.removeObject(temp_src_subset.Name)
                    except Exception:
                        pass
                    try:
                        if temp_src:
                            doc.removeObject(temp_src.Name)
                    except Exception:
                        pass
                    return False
                    
            except Exception as e:
                error_msg = str(e)
                print(f"  [WARN] Failed to export SVG for view '{view_name}': {error_msg[:100]}")
                # Cleanup on error (ensure all objects are removed)
                try:
                    if shape2d_obj:
                        doc.removeObject(shape2d_obj.Name)
                except Exception:
                    pass
                try:
                    if temp_src_subset:
                        doc.removeObject(temp_src_subset.Name)
                except Exception:
                    pass
                try:
                    if temp_src:
                        doc.removeObject(temp_src.Name)
                except Exception:
                    pass
                try:
                    doc.recompute()
                except Exception:
                    pass
                return False
                
        except Exception as e:
            print(f"  [WARN] Error in _export_view_as_svg for view '{view_name}': {e}")
            return False
    
    def _export_views_as_svgs(self, doc: Any, page: Any, view_objects: List[Any], 
                              view_placements: List[Any], out_dir: str) -> List[Tuple[str, dict]]:
        """
        Export each TechDraw view as a separate SVG file using TechDraw.exportSVGEdges.
        This works in headless mode when page→SVG export fails.
        
        Args:
            doc: FreeCAD document
            page: TechDraw page object
            view_objects: List of TechDraw view objects to export
            view_placements: List of ViewPlacement objects for position/size information
            out_dir: Output directory for SVG files
            
        Returns:
            List of tuples: (svg_path, view_info) where view_info contains:
                {x, y, w, h, name} - position and size in mm, and view name
                If svg_path is None, the view export failed and placeholder should be used
        """
        if not self.techdraw_available:
            return []
        
        os.makedirs(out_dir, exist_ok=True)
        
        view_svgs = []
        
        # Build lookup: view object -> ViewPlacement (by matching view names/labels)
        placement_map = {}
        for placement in view_placements or []:
            view_name = placement.view.name if hasattr(placement, 'view') and hasattr(placement.view, 'name') else "Unknown"
            placement_map[view_name] = placement
        
        # Try to match view objects to placements by Label or Name
        for idx, view_obj in enumerate(view_objects):
            if view_obj is None:
                continue
            
            try:
                import TechDraw
                
                # Get view name/label for matching
                view_name = "Unknown"
                if hasattr(view_obj, 'Label'):
                    view_name = view_obj.Label
                elif hasattr(view_obj, 'Name'):
                    view_name = view_obj.Name
                
                # Find matching placement
                placement = None
                for pl in view_placements or []:
                    pl_view_name = pl.view.name if hasattr(pl, 'view') and hasattr(pl.view, 'name') else None
                    if pl_view_name == view_name or view_name in str(pl_view_name):
                        placement = pl
                        break
                
                # If no exact match, use placement by index
                if placement is None and view_placements and idx < len(view_placements):
                    placement = view_placements[idx]
                
                # Get position and size from placement
                if placement:
                    x, y = placement.position if hasattr(placement, 'position') else (0, 0)
                    w = placement.width_mm if hasattr(placement, 'width_mm') else 100.0
                    h = placement.height_mm if hasattr(placement, 'height_mm') else 100.0
                    pl_view_name = placement.view.name if hasattr(placement, 'view') and hasattr(placement.view, 'name') else view_name
                else:
                    x, y, w, h = 0, 0, 100.0, 100.0
                    pl_view_name = view_name
                
                # Export view as SVG using Draft.makeShape2DView + TechDraw.exportSVGEdges
                # This works in headless mode by projecting the source shape to 2D
                svg_path = os.path.join(out_dir, f"view_{idx}_{pl_view_name}.svg")
                
                # Use new method that projects shape and exports SVG
                success = self._export_view_as_svg(doc, view_obj, pl_view_name, svg_path)
                
                if success and os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                    # SVG export succeeded
                    view_info = {
                        "x": float(x),
                        "y": float(y),
                        "w": float(w),
                        "h": float(h),
                        "name": pl_view_name
                    }
                    view_svgs.append((svg_path, view_info))
                else:
                    # SVG export failed - create placeholder entry
                    view_info = {
                        "x": float(x),
                        "y": float(y),
                        "w": float(w),
                        "h": float(h),
                        "name": pl_view_name,
                        "error": "SVG export failed via Draft.makeShape2DView"
                    }
                    view_svgs.append((None, view_info))
                    
            except Exception as e:
                print(f"  [WARN] Error processing view object: {e}")
                continue
        
        return view_svgs
    
    def export_pdf(self, page: Any, output_path: str, 
                  view_placements: Optional[List[Any]] = None,
                  balloons: Optional[List[Any]] = None,
                  bom_table: Optional[Any] = None,
                  metadata: Optional[dict] = None,
                  view_objects: Optional[List[Any]] = None) -> str:
        """
        Export TechDraw page to PDF using 3-tier approach:
        
        Tier 1 (GUI): TechDrawGui.exportPageAsPdf() if GUI available
        Tier 2 (Headless): Export page as SVG -> convert SVG to PDF
        Tier 3 (Fallback): Generate placeholder PDF with reportlab
        
        Args:
            page: TechDraw page object
            output_path: Output file path
            view_placements: List of ViewPlacement objects (for fallback)
            balloons: List of Balloon objects (for fallback)
            bom_table: BOMTable object (for fallback)
            metadata: Drawing metadata (for fallback)
            
        Returns:
            Path to exported PDF file
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        # Early return if TechDraw not available
        if not self.techdraw_available or page is None:
            print("  [INFO] PDF export Tier3: TechDraw not available, using placeholder PDF")
            result = self._export_pdf_tier3(page, output_path, view_placements, balloons, bom_table, metadata)
            return result.get("pdf_path", output_path) if isinstance(result, dict) else result
        
        doc = page.Document if hasattr(page, 'Document') else FreeCAD.ActiveDocument
        if doc is None:
            print("  [INFO] PDF export Tier3: No document available, using placeholder PDF")
            result = self._export_pdf_tier3(page, output_path, view_placements, balloons, bom_table, metadata)
            return result.get("pdf_path", output_path) if isinstance(result, dict) else result
        
        # Tier 1: Try TechDrawGui.exportPageAsPdf() (requires GUI)
        try:
            import TechDrawGui
            TechDrawGui.exportPageAsPdf(page, output_path)
            
            # Verify PDF was created
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"  [OK] PDF export Tier1: TechDrawGui native export successful")
                return output_path
            
            raise RuntimeError("TechDrawGui created empty PDF file")
            
        except ImportError:
            print("  [INFO] PDF export Tier1: TechDrawGui not available (headless mode), trying Tier2")
        except AttributeError:
            print("  [INFO] PDF export Tier1: exportPageAsPdf method not found, trying Tier2")
        except Exception as e:
            print(f"  [INFO] PDF export Tier1: Failed ({str(e)[:100]}), trying Tier2")
        
        # Tier 2: Export individual views as SVG, then embed in PDF with reportlab+svglib
        # This works in headless mode when page→SVG export fails
        if view_objects and view_placements:
            try:
                # Export each view as SVG using TechDraw.exportSVGEdges
                out_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else "."
                view_svgs = self._export_views_as_svgs(doc, page, view_objects, view_placements, out_dir)
                
                # If we got at least some view SVGs, use Tier2 with embedded SVGs
                successful_svgs = [v for v in view_svgs if v[0] is not None]
                if successful_svgs:
                    svg_count = len(successful_svgs)
                    print(f"  [INFO] PDF export Tier2: Exported {svg_count} view(s) as SVG, embedding in PDF...")
                    # Call Tier3 PDF exporter with view_svgs to render real geometry
                    # Note: _export_pdf_tier3 now returns a dict with stats, not just a path
                    result = self._export_pdf_tier3(page, output_path, view_placements, balloons, bom_table, metadata, view_svgs=view_svgs)
                    
                    # Extract result (may be dict or string for backward compatibility)
                    if isinstance(result, dict):
                        result_path = result.get("pdf_path", output_path)
                        rendered_count = result.get("rendered", 0)
                        total_views = result.get("total", svg_count)
                    else:
                        # Backward compatibility: if string returned, assume all rendered
                        result_path = result
                        rendered_count = svg_count
                        total_views = svg_count
                    
                    # Verify PDF was created and check if any views were actually rendered
                    if result_path and os.path.exists(result_path) and os.path.getsize(result_path) > 0:
                        if rendered_count > 0:
                            # Tier2 succeeded - at least one SVG was rendered into PDF
                            print(f"  [OK] PDF export Tier2: Successfully generated PDF with geometry (rendered {rendered_count}/{total_views} views)")
                            return result_path
                        else:
                            # PDF was created but no SVGs were rendered (all placeholders)
                            print(f"  [WARN] PDF export Tier2: 0/{total_views} SVG views rendered, falling back to Tier3 placeholder")
                            # Continue to Tier3 fallback below
                    else:
                        print(f"  [WARN] PDF export Tier2: PDF generation failed, falling back to Tier3 placeholder")
                        # Continue to Tier3 fallback below
                else:
                    print(f"  [WARN] PDF export Tier2: No views exported as SVG, falling back to Tier3")
            except Exception as e:
                error_msg = str(e)
                print(f"  [WARN] PDF export Tier2: Per-view SVG export failed ({error_msg[:100]}), falling back to Tier3")
        else:
            # Try old page→SVG method as fallback (often fails in headless)
            try:
                # Skip recompute if risky - it can cause segfaults
                try:
                    page.recompute()
                except:
                    pass  # Don't fail if recompute causes issues
                
                # Export page as SVG (this part is safe even in headless)
                svg_path = output_path.rsplit('.', 1)[0] + '.svg'
                
                try:
                    self._export_page_as_svg(doc, page, svg_path)
                    
                    # Verify SVG was created
                    if os.path.exists(svg_path) and os.path.getsize(svg_path) > 0:
                        # SVG export successful - mark for external conversion
                        # Don't convert to PDF here (can cause segfaults in FreeCAD process)
                        # Conversion will be done by run_pipeline.sh using system python3
                        print(f"  [OK] PDF export Tier2: Page SVG exported to {svg_path} (conversion will be done outside FreeCAD)")
                        
                        # Create placeholder PDF for now (Tier3 will create proper one if SVG conversion fails)
                        # The SVG will be converted to PDF by run_pipeline.sh after FreeCAD exits
                        # Store SVG path in metadata for run_pipeline.sh to find
                        if not hasattr(doc, 'SVGExportPath'):
                            doc.addProperty('App::PropertyString', 'SVGExportPath')
                        doc.SVGExportPath = svg_path
                        
                        # Still generate Tier3 placeholder PDF as fallback
                        # If SVG->PDF conversion succeeds, it will overwrite this
                        print("  [INFO] Generating fallback placeholder PDF (will be replaced if SVG conversion succeeds)...")
                        # Continue to Tier3 to create placeholder PDF as backup
                    else:
                        raise RuntimeError("SVG export created empty file")
                        
                except RuntimeError as e:
                    # SVG export failed (e.g., headless mode detection)
                    error_msg = str(e)
                    print(f"  [INFO] PDF export Tier2: Page SVG export failed ({error_msg[:100]}), trying Tier3")
            except Exception as e:
                error_msg = str(e)
                print(f"  [WARN] PDF export Tier2: Failed ({error_msg[:100]}), falling back to Tier3")
        
        # Tier 3: Fallback to placeholder PDF with reportlab
        result = self._export_pdf_tier3(page, output_path, view_placements, balloons, bom_table, metadata)
        # Return path string for backward compatibility
        return result.get("pdf_path", output_path) if isinstance(result, dict) else result
    
    def _export_pdf_tier3(self, page: Any, output_path: str,
                          view_placements: Optional[List[Any]],
                          balloons: Optional[List[Any]],
                          bom_table: Optional[Any],
                          metadata: Optional[dict],
                          view_svgs: Optional[List[Tuple[Optional[str], dict]]] = None) -> Any:
        """
        Tier 3 PDF export: Generate PDF using reportlab (with SVG embedding if view_svgs provided).
        
        Args:
            page: TechDraw page object (may be None)
            output_path: Output file path
            view_placements: List of ViewPlacement objects
            balloons: List of Balloon objects
            bom_table: BOMTable object
            metadata: Drawing metadata
            view_svgs: Optional list of (svg_path, view_info) tuples for Tier2 SVG embedding
            
        Returns:
            If view_svgs provided: dict with {"pdf_path": str, "rendered": int, "total": int, "placeholders": int}
            Otherwise: str path to exported PDF file (backward compatibility)
        """
        from exporters.pdf_exporter import PDFExporter
        
        exporter = PDFExporter()
        
        # Extract sheet size from page or metadata
        sheet_size_name = "A4"
        if page and hasattr(page, 'Label'):
            label_parts = page.Label.split('_')
            if len(label_parts) > 1:
                sheet_size_name = label_parts[-1]
        elif metadata and 'sheet_size' in metadata:
            sheet_size_name = metadata['sheet_size']
        
        # Try to get balloons and BOM from document properties if not provided
        doc = page.Document if (page and hasattr(page, 'Document')) else FreeCAD.ActiveDocument
        if doc:
            if not balloons and hasattr(doc, 'Balloons') and doc.Balloons:
                try:
                    import json
                    balloons = [json.loads(b) for b in doc.Balloons]
                except:
                    pass
            if not bom_table and hasattr(doc, 'BOMTable') and doc.BOMTable:
                try:
                    import json
                    bom_table = json.loads(doc.BOMTable[0]) if doc.BOMTable else None
                except:
                    pass
        
        # Prepare view data for exporter
        view_data = None
        if view_placements:
            view_data = [
                {
                    "name": vp.view.name if hasattr(vp, 'view') else str(vp),
                    "position": vp.position if hasattr(vp, 'position') else (0, 0),
                    "scale": vp.scale if hasattr(vp, 'scale') else 1.0,
                    "width": vp.width_mm if hasattr(vp, 'width_mm') else 100,
                    "height": vp.height_mm if hasattr(vp, 'height_mm') else 100
                }
                for vp in view_placements
            ]
        
        result = exporter.export(None, output_path, sheet_size_name, view_data, 
                                balloons, bom_table, metadata, view_svgs=view_svgs)
        
        # Handle new return format (dict with stats) vs old format (string path)
        if isinstance(result, dict):
            result_path = result.get("pdf_path", output_path)
            rendered_count = result.get("rendered", 0)
            total_views = result.get("total", 0)
            
            if view_svgs and rendered_count > 0:
                # Tier2 mode: SVG views were embedded
                # Don't log Tier3 message - this is Tier2 success
                pass  # Logging already done by exporter
            else:
                # Tier3 mode: placeholder PDF
                print(f"  [OK] PDF export Tier3: Placeholder PDF generated successfully")
            
            return result  # Return dict with stats
        else:
            # Backward compatibility: old format returns string
            print(f"  [OK] PDF export Tier3: Placeholder PDF generated successfully")
            return result
    
    def export_dxf(self, page: Any, output_path: str) -> str:
        """
        Export TechDraw page to DXF.
        
        Args:
            page: TechDraw page object
            output_path: Output file path
            
        Returns:
            Path to exported DXF file
        """
        if not self.techdraw_available or page is None:
            # Fallback to DXF exporter
            from exporters.dxf_exporter import DXFExporter
            exporter = DXFExporter()
            return exporter.export(None, output_path)  # Will need document info
        
        try:
            import TechDraw
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            # Recompute page (only page, not document to avoid loops)
            page.recompute()
            doc = page.Document
            
            # Export page to DXF
            # TechDraw DXF export API varies by FreeCAD version
            try:
                # Method 1: Direct page method (FreeCAD 0.19+)
                if hasattr(page, 'exportPageAsDxf'):
                    page.exportPageAsDxf(output_path)
                # Method 2: TechDraw module function
                elif hasattr(TechDraw, 'exportPageAsDxf'):
                    TechDraw.exportPageAsDxf(page, output_path)
                # Method 3: Alternative export method
                else:
                    # Fall back to DXF exporter
                    raise AttributeError("TechDraw DXF export not available")
            except (AttributeError, RuntimeError) as e:
                # If TechDraw export fails, raise to trigger fallback
                raise RuntimeError(f"TechDraw DXF export failed: {e}") from e
            
            return output_path
            
        except Exception as e:
            print(f"  [INFO] DXF export via TechDraw failed: {e}, trying fallback exporter...")
            
            # Fallback to DXF exporter
            try:
                from exporters.dxf_exporter import DXFExporter
                exporter = DXFExporter()
                result_path = exporter.export(page, output_path)
                
                # Verify DXF was created
                if result_path and os.path.exists(result_path) and os.path.getsize(result_path) > 0:
                    print(f"  [OK] DXF export: Fallback exporter successful ({result_path})")
                    return result_path
                else:
                    raise RuntimeError("Fallback DXF exporter did not create file")
                    
            except Exception as fallback_error:
                # Both TechDraw and fallback failed
                raise RuntimeError(f"DXF export failed: TechDraw failed ({e}), fallback failed ({fallback_error})") from fallback_error
