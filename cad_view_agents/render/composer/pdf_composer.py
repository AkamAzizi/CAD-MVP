"""
PDF composer for 2D technical drawings.
Renders directly to PDF using ReportLab primitives.
"""
from typing import List, Dict, Optional, Any, Tuple
from reportlab.lib.pagesizes import A4, A3, A2, A1, A0
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from ..projection import ProjectedView
from core.layout_engine import ViewPlacement


class PDFComposer:
    """Composes 2D technical drawings into PDF using ReportLab."""
    
    # Rendering constants (deterministic)
    STROKE_WIDTH_VISIBLE = 0.5 * mm
    FONT_SIZE_BALLOON = 8
    FONT_SIZE_TITLE_BLOCK = 10
    FONT_SIZE_BOM = 9
    BALLOON_RADIUS = 5 * mm
    LEADER_LINE_WIDTH = 0.3 * mm
    
    # Sheet size mapping
    SHEET_SIZES = {
        "A4": A4,
        "A3": A3,
        "A2": A2,
        "A1": A1,
        "A0": A0,
    }
    
    def compose(self,
                pdf_path: str,
                sheet_size_name: str,
                projected_views: List[ProjectedView],
                view_placements: List[ViewPlacement],
                balloon_placements: List[Any],
                bom_table: Optional[Any],
                metadata: Optional[Dict]) -> None:
        """
        Compose and render PDF drawing.
        
        Args:
            pdf_path: Output PDF file path
            sheet_size_name: Sheet size ("A4", "A3", etc.)
            projected_views: List of ProjectedView objects
            view_placements: List of ViewPlacement objects
            balloon_placements: List of BalloonPlacement objects
            bom_table: BOMTable object (optional)
            metadata: Additional metadata dictionary
        """
        # Get page size
        page_size = self.SHEET_SIZES.get(sheet_size_name, A4)
        width, height = page_size
        
        # Create PDF canvas
        c = canvas.Canvas(pdf_path, pagesize=page_size)
        
        # Draw title block (bottom-right, 180x50mm)
        self._draw_title_block(c, width, height, metadata)
        
        # Draw BOM table (bottom-left, 150x100mm)
        if bom_table:
            self._draw_bom_table(c, width, height, bom_table)
        
        # Draw views and transform balloon anchors
        view_transforms = {}  # Store transform info per view for balloon anchors
        for i, (proj_view, placement) in enumerate(zip(projected_views, view_placements)):
            # Draw view edges and get transform info
            transform_info = self._draw_view_edges(c, proj_view, placement)
            view_transforms[i] = transform_info
        
        # Draw balloons with proper transform
        self._draw_balloons(c, balloon_placements, projected_views, view_placements, view_transforms)
        
        # Save PDF
        c.save()
    
    def _draw_title_block(self, c: canvas.Canvas, width: float, height: float, metadata: Optional[Dict]) -> None:
        """Draw title block in bottom-right corner."""
        title_block_width = 180 * mm
        title_block_height = 50 * mm
        margin = 10 * mm
        
        x = width - margin - title_block_width
        y = margin
        
        # Draw border
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5 * mm)
        c.rect(x, y, title_block_width, title_block_height, stroke=1, fill=0)
        
        # Draw title block content
        assembly_name = metadata.get("assembly_name", "Assembly") if metadata else "Assembly"
        date_str = metadata.get("date", "N/A") if metadata else "N/A"
        
        c.setFont("Helvetica-Bold", self.FONT_SIZE_TITLE_BLOCK)
        c.drawString(x + 5 * mm, y + title_block_height - 15 * mm, f"Assembly: {assembly_name}")
        
        c.setFont("Helvetica", self.FONT_SIZE_TITLE_BLOCK)
        c.drawString(x + 5 * mm, y + 5 * mm, f"Date: {date_str}")
    
    def _draw_bom_table(self, c: canvas.Canvas, width: float, height: float, bom_table: Any) -> None:
        """Draw BOM table in bottom-left corner."""
        bom_width = 150 * mm
        bom_height = 100 * mm
        margin = 10 * mm
        
        x = margin
        y = margin
        
        if not hasattr(bom_table, 'parts') or not bom_table.parts:
            return
        
        # Prepare table data
        data = [["Item", "Part", "Qty"]]  # Header
        
        # Add rows (limit to top 10 for MVP)
        for part in bom_table.parts[:10]:
            item_num = getattr(part, 'item_number', 0)
            part_id = getattr(part, 'part_id', '')
            qty = getattr(part, 'quantity', 1)
            data.append([str(item_num), part_id[:20], str(qty)])
        
        # Create table
        table = Table(data, colWidths=[20 * mm, 80 * mm, 20 * mm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), self.FONT_SIZE_BOM),
            ('FONTSIZE', (0, 1), (-1, -1), self.FONT_SIZE_BOM),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        # Draw table
        table.wrapOn(c, bom_width, bom_height)
        table.drawOn(c, x, y)
    
    def _draw_view_edges(self, c: canvas.Canvas, proj_view: ProjectedView, placement: ViewPlacement) -> Dict[str, Any]:
        """Draw 2D view edges using polyline with proper 2D→sheet transform."""
        view_x, view_y = placement.position
        view_w = placement.width_mm
        view_h = placement.height_mm
        
        # Compute projected bounds from all geometry
        all_points = []
        for polyline in proj_view.edges_2d:
            all_points.extend(polyline)
        
        if not all_points:
            # No geometry, just draw border
            self._draw_view_border(c, view_x, view_y, view_w, view_h)
            return
        
        # Compute bounds
        x_coords = [p[0] for p in all_points]
        y_coords = [p[1] for p in all_points]
        minx, maxx = min(x_coords), max(x_coords)
        miny, maxy = min(y_coords), max(y_coords)
        
        # Compute uniform scale to fit with margins (5mm margin on each side)
        margin = 5.0  # mm
        available_w = view_w - 2 * margin
        available_h = view_h - 2 * margin
        
        geom_w = maxx - minx if maxx > minx else 1.0
        geom_h = maxy - miny if maxy > miny else 1.0
        
        scale_x = available_w / geom_w if geom_w > 0 else 1.0
        scale_y = available_h / geom_h if geom_h > 0 else 1.0
        scale = min(scale_x, scale_y)  # Uniform scale
        
        # Transform function: x_mm = px + (x-minx)*scale, y_mm = py + (y-miny)*scale
        # Note: PDF Y increases upward, so we need to flip Y if needed
        def transform_point(x: float, y: float) -> Tuple[float, float]:
            # Transform to view-relative coordinates
            x_rel = (x - minx) * scale
            y_rel = (y - miny) * scale
            
            # Center in view with margin
            x_sheet = view_x + margin + x_rel
            # PDF Y increases upward, so we flip: y_sheet = view_y + view_h - (margin + y_rel)
            y_sheet = view_y + view_h - (margin + y_rel)
            
            return (x_sheet * mm, y_sheet * mm)
        
        # Draw geometry
        c.setStrokeColor(colors.black)
        c.setLineWidth(self.STROKE_WIDTH_VISIBLE)
        
        polyline_count = 0
        segment_count = 0
        
        for polyline in proj_view.edges_2d:
            if len(polyline) < 2:
                continue
            
            polyline_count += 1
            segment_count += len(polyline) - 1
            
            # Draw polyline using beginPath pattern
            path = c.beginPath()
            first_point = polyline[0]
            tx, ty = transform_point(first_point[0], first_point[1])
            path.moveTo(tx, ty)
            
            for point in polyline[1:]:
                tx, ty = transform_point(point[0], point[1])
                path.lineTo(tx, ty)
            
            c.drawPath(path)
        
        # Debug rendering: Draw view placement bbox rectangle
        c.setStrokeColor(colors.red)
        c.setLineWidth(0.2 * mm)
        c.setDash([1 * mm, 1 * mm])
        c.rect(
            view_x * mm,
            view_y * mm,
            view_w * mm,
            view_h * mm,
            stroke=1,
            fill=0
        )
        c.setDash()  # Reset dash
        
        # Debug rendering: Draw cross marker at placement position
        cross_size = 2 * mm
        c.setStrokeColor(colors.blue)
        c.setLineWidth(0.2 * mm)
        center_x = (view_x + view_w / 2) * mm
        center_y = (view_y + view_h / 2) * mm
        c.line(center_x - cross_size, center_y, center_x + cross_size, center_y)
        c.line(center_x, center_y - cross_size, center_x, center_y + cross_size)
        
        # Log geometry stats
        print(f"  [DEBUG] View '{proj_view.view_name}': {polyline_count} polylines, {segment_count} segments, bounds=({minx:.2f},{miny:.2f}) to ({maxx:.2f},{maxy:.2f}), scale={scale:.3f}")
        
        # Draw view border
        self._draw_view_border(c, view_x, view_y, view_w, view_h)
        
        # Return transform info for balloon anchors
        return {
            "view_x": view_x,
            "view_y": view_y,
            "view_w": view_w,
            "view_h": view_h,
            "minx": minx,
            "miny": miny,
            "maxx": maxx,
            "maxy": maxy,
            "scale": scale,
            "margin": margin,
            "transform_func": transform_point
        }
    
    def _draw_view_border(self, c: canvas.Canvas, view_x: float, view_y: float, view_w: float, view_h: float) -> None:
        """Draw view border (dashed rectangle)."""
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.5 * mm)
        c.setDash([2 * mm, 2 * mm])
        c.rect(
            view_x * mm,
            view_y * mm,
            view_w * mm,
            view_h * mm,
            stroke=1,
            fill=0
        )
        c.setDash()  # Reset dash
    
    def _draw_balloons(self, c: canvas.Canvas, balloon_placements: List[Any],
                      projected_views: List[ProjectedView], view_placements: List[ViewPlacement],
                      view_transforms: Dict[int, Dict[str, Any]]) -> None:
        """Draw balloons and leader lines with proper transform for anchor points."""
        c.setStrokeColor(colors.black)
        
        # Group balloons by view (match by part_id in projected_views)
        balloons_by_view = {}
        for bp in balloon_placements:
            # Find which view this balloon belongs to
            view_idx = None
            for i, proj_view in enumerate(projected_views):
                if bp.part_id in proj_view.part_projections:
                    view_idx = i
                    break
            
            if view_idx is None:
                view_idx = 0  # Default to first view
            
            if view_idx not in balloons_by_view:
                balloons_by_view[view_idx] = []
            balloons_by_view[view_idx].append(bp)
        
        # Draw balloons per view with proper transform
        for view_idx, balloons in balloons_by_view.items():
            if view_idx not in view_transforms:
                continue
            
            transform_info = view_transforms[view_idx]
            transform_func = transform_info["transform_func"]
            
            # Get view info for finding part projections
            if view_idx < len(projected_views):
                proj_view = projected_views[view_idx]
            else:
                continue
            
            for bp in balloons:
                # Get anchor in view coordinates from part projection
                # The anchor from BalloonPlacer might be in sheet coords, so we need to get the view coord version
                anchor_x, anchor_y = bp.anchor_point
                
                # Check if we have view coordinate anchor stored
                if hasattr(bp, '_view_anchor') and bp._view_anchor:
                    # Use view coordinate anchor
                    anchor_x, anchor_y = bp._view_anchor
                
                # Transform anchor from view/geometry coordinates to sheet coordinates
                anchor_sheet_x, anchor_sheet_y = transform_func(anchor_x, anchor_y)
                
                # Balloon center is in sheet coordinates (from BalloonPlacer with sheet_coords=True)
                center_x = bp.balloon_center[0] * mm
                center_y = bp.balloon_center[1] * mm
                
                # Draw leader line (from balloon center to transformed anchor)
                # Use elbow point if available for 2-segment elbow rule
                c.setLineWidth(self.LEADER_LINE_WIDTH)
                path = c.beginPath()
                path.moveTo(center_x, center_y)
                
                if hasattr(bp, 'elbow_point') and bp.elbow_point:
                    elbow_x, elbow_y = bp.elbow_point
                    # Elbow is in sheet coordinates (from BalloonPlacer)
                    path.lineTo(elbow_x * mm, elbow_y * mm)
                
                # Last segment goes to transformed anchor
                path.lineTo(anchor_sheet_x, anchor_sheet_y)
                c.drawPath(path)
                
                # Draw balloon circle (stroke-only, white fill)
                c.setLineWidth(0.5 * mm)
                c.setFillColor(colors.white)
                c.circle(center_x, center_y, self.BALLOON_RADIUS, stroke=1, fill=1)
                
                # Draw item number AFTER circle (centered)
                c.setFont("Helvetica-Bold", self.FONT_SIZE_BALLOON)
                c.setFillColor(colors.black)
                text = str(bp.item_number)
                # Use drawCentredString for proper centering
                c.drawCentredString(center_x, center_y - self.FONT_SIZE_BALLOON / 3, text)
