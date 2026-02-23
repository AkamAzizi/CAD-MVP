"""
CADQuery-based render engine for 2D drawing generation.
Uses CADQuery for STEP import and OCCT shape access.
"""
from typing import Dict, Optional, List, Any
from pathlib import Path
import os
from ..engine_base import RenderEngine
from ..projection import (
    import_step_file, PartShape, ProjectedView,
    compute_projection_transform, project_shape_to_2d
)
from ..balloons.balloon_placer import BalloonPlacer
from core.layout_engine import ViewPlacement


class CADQueryEngine(RenderEngine):
    """CADQuery-based render engine for generating 2D drawings."""
    
    def __init__(self):
        """Initialize CADQuery engine."""
        self._available = self._check_availability()
        self.balloon_placer = BalloonPlacer()
    
    def _check_availability(self) -> bool:
        """Check if CADQuery is available."""
        try:
            import cadquery as cq
            return True
        except ImportError:
            return False
        except Exception:
            return False
    
    def is_available(self) -> bool:
        """Check if engine is available (dependencies installed)."""
        return self._available
    
    def render(self, 
               plan: Dict,
               input_step_path: str,
               output_dir: Path,
               view_placements: List[ViewPlacement],
               bom_table: Optional[Any],
               balloons: Optional[List[Any]],
               metadata: Optional[Dict]) -> Dict[str, Any]:
        """
        Render 2D drawing from 3D STEP file.
        
        Args:
            plan: Drawing plan dictionary
            input_step_path: Path to input STEP file
            output_dir: Output directory for generated files
            view_placements: List of ViewPlacement objects
            bom_table: BOMTable object (optional)
            balloons: List of Balloon objects (optional)
            metadata: Additional metadata dictionary
            
        Returns:
            {
                "pdf_path": str,
                "dxf_path": Optional[str],
                "metadata": Dict,
                "rendered_views": int,
                "errors": List[str]
            }
        """
        if not self.is_available():
            return {
                "pdf_path": "",
                "dxf_path": None,
                "metadata": {},
                "rendered_views": 0,
                "errors": ["CADQuery engine not available. Install with: pip install cadquery"]
            }
        
        errors = []
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get part_id mapping from metadata/snapshot
            part_id_mapping = metadata.get("part_id_mapping", {}) if metadata else {}
            
            # Phase 2: Import STEP and create PartShapes
            try:
                part_shapes = import_step_file(input_step_path, part_id_mapping)
            except Exception as e:
                errors.append(f"Failed to import STEP file: {e}")
                return {
                    "pdf_path": "",
                    "dxf_path": None,
                    "metadata": {},
                    "rendered_views": 0,
                    "errors": errors
                }
            
            # Phase 2: Project views (pure wireframe)
            projected_views = []
            for placement in view_placements:
                view_candidate = placement.view
                view_direction = view_candidate.direction
                
                # Compute projection transform
                transform = compute_projection_transform(view_direction)
                
                # Project each part
                part_projections = {}
                all_edges_2d = []
                
                for part_shape in part_shapes:
                    try:
                        proj_result = project_shape_to_2d(part_shape, view_direction, transform)
                        part_projections[part_shape.part_id] = {
                            "centroid_2d": proj_result["centroid_2d"],
                            "bbox_2d": proj_result["bbox_2d"]
                        }
                        all_edges_2d.extend(proj_result["edges_2d"])
                    except Exception as e:
                        errors.append(f"Projection failed for part {part_shape.part_id}: {e}")
                
                # Check total segment count for the view
                total_segments = sum(max(0, len(polyline) - 1) for polyline in all_edges_2d)
                
                # Check for degeneracy in view bounds
                if all_edges_2d:
                    all_x = []
                    all_y = []
                    for polyline in all_edges_2d:
                        for p in polyline:
                            all_x.append(p[0])
                            all_y.append(p[1])
                    
                    if all_x and all_y:
                        xmin_view, xmax_view = min(all_x), max(all_x)
                        ymin_view, ymax_view = min(all_y), max(all_y)
                        
                        if (xmax_view - xmin_view) < 1e-6 or (ymax_view - ymin_view) < 1e-6:
                            print(f"  [ERROR] View '{view_candidate.name}': Projection degeneracy detected. x_range={xmax_view-xmin_view:.2e}, y_range={ymax_view-ymin_view:.2e}")
                        else:
                            print(f"  [DEBUG] View '{view_candidate.name}': bounds=({xmin_view:.2f},{ymin_view:.2f}) to ({xmax_view:.2f},{ymax_view:.2f}), segments={total_segments}")
                
                if total_segments < 100:
                    print(f"  [WARN] View '{view_candidate.name}': Projection likely failed. Total segments: {total_segments}")
                
                projected_views.append(ProjectedView(
                    view_name=view_candidate.name,
                    edges_2d=all_edges_2d,
                    part_projections=part_projections
                ))
            
            # Phase 2.5: Compute balloon placements
            balloon_placements = []
            if bom_table and projected_views:
                # Get BOM items
                bom_items = []
                if hasattr(bom_table, 'parts'):
                    for part in bom_table.parts:
                        bom_items.append({
                            "item_number": getattr(part, 'item_number', 0),
                            "part_id": getattr(part, 'part_id', '')
                        })
                
                # Place balloons for each view
                # Note: Balloon anchors need to use the same 2D→sheet transform as geometry
                # This will be handled in PDFComposer._draw_view_edges which computes the transform
                # For now, we'll pass view coordinates and let PDFComposer transform them
                for i, proj_view in enumerate(projected_views):
                    if i < len(view_placements):
                        placement = view_placements[i]
                        view_bbox = (
                            placement.position[0],
                            placement.position[1],
                            placement.width_mm,
                            placement.height_mm
                        )
                        
                        # Transform part projections to sheet coordinates for balloon placement
                        # But keep original view coordinates for anchor transform in PDFComposer
                        sheet_projections = {}
                        view_x, view_y = placement.position
                        for part_id, proj_data in proj_view.part_projections.items():
                            centroid_2d = proj_data.get("centroid_2d")
                            bbox_2d = proj_data.get("bbox_2d")
                            
                            # For balloon placement, we need sheet coordinates
                            # But we'll store both for anchor transform
                            if centroid_2d:
                                sheet_centroid = (centroid_2d[0] + view_x, centroid_2d[1] + view_y)
                            else:
                                sheet_centroid = None
                            
                            if bbox_2d:
                                xmin, ymin, xmax, ymax = bbox_2d
                                sheet_bbox = (xmin + view_x, ymin + view_y, xmax + view_x, ymax + view_y)
                            else:
                                sheet_bbox = None
                            
                            # Store both view and sheet coordinates
                            sheet_projections[part_id] = {
                                "centroid_2d": sheet_centroid,
                                "bbox_2d": sheet_bbox,
                                # Also store view coordinates for anchor transform
                                "_view_centroid_2d": centroid_2d,
                                "_view_bbox_2d": bbox_2d
                            }
                        
                        placements = self.balloon_placer.place(
                            view_bbox,
                            sheet_projections,
                            bom_items,
                            sheet_coords=True  # Balloon centers in sheet coordinates
                        )
                        
                        # Store view coordinate info with each placement for anchor transform
                        for placement_obj in placements:
                            part_id = placement_obj.part_id
                            if part_id in sheet_projections:
                                # Store view coordinates for anchor transform
                                placement_obj._view_anchor = sheet_projections[part_id].get("_view_centroid_2d") or sheet_projections[part_id].get("_view_bbox_2d")
                        
                        balloon_placements.extend(placements)
            
            # Phase 3 & 4: Compose and export PDF
            from ..composer.pdf_composer import PDFComposer
            
            composer = PDFComposer()
            pdf_path = output_dir / "drawing.pdf"
            
            sheet_size_name = metadata.get("sheet_size", "A4") if metadata else "A4"
            
            try:
                composer.compose(
                    pdf_path=str(pdf_path),
                    sheet_size_name=sheet_size_name,
                    projected_views=projected_views,
                    view_placements=view_placements,
                    balloon_placements=balloon_placements,
                    bom_table=bom_table,
                    metadata=metadata
                )
            except Exception as e:
                errors.append(f"PDF composition failed: {e}")
                return {
                    "pdf_path": "",
                    "dxf_path": None,
                    "metadata": {},
                    "rendered_views": len(projected_views),
                    "errors": errors
                }
            
            return {
                "pdf_path": str(pdf_path),
                "dxf_path": None,  # DXF in PR2/PR3
                "metadata": {
                    "rendered_views": len(projected_views),
                    "balloon_count": len(balloon_placements)
                },
                "rendered_views": len(projected_views),
                "errors": errors
            }
            
        except Exception as e:
            errors.append(f"Render failed: {e}")
            return {
                "pdf_path": "",
                "dxf_path": None,
                "metadata": {},
                "rendered_views": 0,
                "errors": errors
            }
