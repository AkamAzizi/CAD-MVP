"""
Layout engine for technical drawing sheets.
Handles sheet size selection, scale calculation, and view placement.
"""
from typing import List, Tuple, Optional
from dataclasses import dataclass
from .view_candidates import ViewCandidate


@dataclass
class SheetSize:
    """Represents a drawing sheet size."""
    name: str  # "A4", "A3", "A2", "A1"
    width_mm: float  # Width in millimeters
    height_mm: float  # Height in millimeters
    margin_mm: float  # Standard margin in millimeters


@dataclass
class ViewPlacement:
    """Represents a view placement on a sheet."""
    view: ViewCandidate
    position: Tuple[float, float]  # X, Y position on sheet (mm from bottom-left)
    scale: float
    width_mm: float  # View width on sheet
    height_mm: float  # View height on sheet


class LayoutEngine:
    """Manages sheet layout, scale calculation, and view placement."""
    
    # Standard sheet sizes (ISO A series)
    SHEET_SIZES = {
        "A4": SheetSize("A4", 210.0, 297.0, 10.0),  # Standard letter size
        "A3": SheetSize("A3", 297.0, 420.0, 15.0),
        "A2": SheetSize("A2", 420.0, 594.0, 20.0),
        "A1": SheetSize("A1", 594.0, 841.0, 25.0),
        "A0": SheetSize("A0", 841.0, 1189.0, 30.0),
    }
    
    # Standard scales (common technical drawing scales)
    STANDARD_SCALES = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
    
    # Minimum spacing between views (mm)
    MIN_VIEW_SPACING = 20.0
    
    # Title block area (bottom-right, reserved space)
    TITLE_BLOCK_WIDTH = 180.0
    TITLE_BLOCK_HEIGHT = 50.0
    
    # BOM table area (bottom-left, reserved space)
    BOM_TABLE_WIDTH = 150.0
    BOM_TABLE_HEIGHT = 100.0
    
    def __init__(self):
        self.sheet_size: Optional[SheetSize] = None
        self.scale: float = 1.0
    
    def select_sheet_size(self, bbox: Optional[dict], view_count: int, preferred_size: Optional[str] = None) -> SheetSize:
        """
        Select appropriate sheet size based on assembly bounding box and view count.
        
        Args:
            bbox: Bounding box dict with x, y, z dimensions (mm) (can be None)
            view_count: Number of views to place
            preferred_size: Optional preferred sheet size ("A4", "A3", etc.)
            
        Returns:
            Selected SheetSize
        """
        if preferred_size and preferred_size in self.SHEET_SIZES:
            self.sheet_size = self.SHEET_SIZES[preferred_size]
            return self.sheet_size
        
        if not bbox or not all(k in bbox for k in ["x", "y", "z"]):
            # Default to A4 if no bbox info
            self.sheet_size = self.SHEET_SIZES["A4"]
            return self.sheet_size
        
        # Calculate required area for views
        # Estimate: each view needs space for projection + margins
        max_dimension = max(bbox["x"], bbox["y"], bbox["z"])
        
        # Estimate view area needed (with spacing)
        # For grid layout: sqrt(view_count) x sqrt(view_count) grid
        grid_size = int(view_count ** 0.5) + (1 if view_count % int(view_count ** 0.5) != 0 else 0)
        estimated_view_area = (max_dimension * grid_size * 1.5) ** 2  # Rough estimate
        
        # Account for margins, title block, BOM
        available_width = 0
        available_height = 0
        
        for size_name, size in self.SHEET_SIZES.items():
            available_width = size.width_mm - 2 * size.margin_mm - self.TITLE_BLOCK_WIDTH
            available_height = size.height_mm - 2 * size.margin_mm - self.BOM_TABLE_HEIGHT
            
            # Check if views can fit
            if available_width * available_height >= estimated_view_area * 1.2:  # 20% safety margin
                self.sheet_size = size
                return size
        
        # Default to largest size if nothing fits
        self.sheet_size = self.SHEET_SIZES["A1"]
        return self.sheet_size
    
    def calculate_scale(self, views: List[ViewCandidate], bbox: Optional[dict], 
                       preferred_scale: Optional[float] = None) -> float:
        """
        Calculate optimal scale to fit views on selected sheet.
        
        Args:
            views: List of ViewCandidate objects
            bbox: Bounding box dict with x, y, z dimensions (mm) (can be None)
            preferred_scale: Optional preferred scale (None = auto)
            
        Returns:
            Calculated scale factor
        """
        if preferred_scale and preferred_scale > 0:
            self.scale = preferred_scale
            return self.scale
        
        if not self.sheet_size:
            # Default sheet size if not set
            self.select_sheet_size(bbox or {}, len(views))
        
        if not bbox or not all(k in bbox for k in ["x", "y", "z"]):
            # Use default scale if bbox is invalid
            self.scale = 0.1  # Small scale for large assemblies
            return self.scale
        
        # Calculate available space for views
        available_width = (self.sheet_size.width_mm - 2 * self.sheet_size.margin_mm 
                          - self.TITLE_BLOCK_WIDTH)
        available_height = (self.sheet_size.height_mm - 2 * self.sheet_size.margin_mm 
                           - self.BOM_TABLE_HEIGHT)
        
        # Estimate view dimensions (use largest bbox dimension)
        max_dimension = max(bbox["x"], bbox["y"], bbox["z"])
        
        # For grid layout: calculate how many views per row/column
        view_count = len(views)
        cols = int(view_count ** 0.5) + (1 if view_count % int(view_count ** 0.5) != 0 else 0)
        rows = (view_count + cols - 1) // cols  # Ceiling division
        
        # Calculate max view size that fits
        max_view_width = (available_width - (cols - 1) * self.MIN_VIEW_SPACING) / cols
        max_view_height = (available_height - (rows - 1) * self.MIN_VIEW_SPACING) / rows
        
        # Scale to fit
        scale_x = max_view_width / max_dimension if max_dimension > 0 else 1.0
        scale_y = max_view_height / max_dimension if max_dimension > 0 else 1.0
        
        # Use smaller scale to ensure fit
        calculated_scale = min(scale_x, scale_y) * 0.9  # 10% safety margin
        
        # Round to nearest standard scale
        self.scale = self._round_to_standard_scale(calculated_scale)
        
        return self.scale
    
    def _round_to_standard_scale(self, scale: float) -> float:
        """Round scale to nearest standard technical drawing scale."""
        if scale <= 0:
            return 1.0
        
        # Find closest standard scale
        closest = min(self.STANDARD_SCALES, key=lambda x: abs(x - scale))
        
        # If calculated scale is between standard scales, use the smaller one (safer)
        if scale < closest:
            # Find next smaller standard scale
            smaller_scales = [s for s in self.STANDARD_SCALES if s < scale]
            if smaller_scales:
                return max(smaller_scales)
        
        return closest
    
    def place_views(self, views: List[ViewCandidate], bbox: Optional[dict]) -> List[ViewPlacement]:
        """
        Place views on sheet using grid layout.
        
        Args:
            views: List of ViewCandidate objects
            bbox: Bounding box dict (can be None)
            
        Returns:
            List of ViewPlacement objects
        """
        if not self.sheet_size:
            self.select_sheet_size(bbox or {}, len(views))
        
        if not self.scale or self.scale <= 0:
            self.calculate_scale(views, bbox or {})
        
        # Calculate view dimensions
        # Use default dimensions if bbox is None or invalid
        if bbox is not None and isinstance(bbox, dict) and all(k in bbox for k in ["x", "y", "z"]):
            max_dimension = max(bbox.get("x", 100), bbox.get("y", 100), bbox.get("z", 100))
        else:
            # Default to reasonable size if bbox is invalid
            max_dimension = 100.0  # 100mm default
        
        view_width = max_dimension * self.scale
        view_height = max_dimension * self.scale
        
        # Grid layout
        view_count = len(views)
        cols = int(view_count ** 0.5) + (1 if view_count % int(view_count ** 0.5) != 0 else 0)
        rows = (view_count + cols - 1) // cols
        
        # Starting position (top-left, accounting for margins)
        start_x = self.sheet_size.margin_mm
        start_y = self.sheet_size.height_mm - self.sheet_size.margin_mm - self.BOM_TABLE_HEIGHT
        
        placements = []
        
        for idx, view in enumerate(views):
            row = idx // cols
            col = idx % cols
            
            # Calculate position
            x = start_x + col * (view_width + self.MIN_VIEW_SPACING)
            y = start_y - (row + 1) * (view_height + self.MIN_VIEW_SPACING)
            
            placements.append(ViewPlacement(
                view=view,
                position=(x, y),
                scale=self.scale,
                width_mm=view_width,
                height_mm=view_height
            ))
        
        return placements
    
    def get_available_area(self) -> Tuple[float, float]:
        """
        Get available drawing area (excluding margins, title block, BOM).
        
        Returns:
            Tuple of (width, height) in mm
        """
        if not self.sheet_size:
            return (0, 0)
        
        width = (self.sheet_size.width_mm - 2 * self.sheet_size.margin_mm 
                - self.TITLE_BLOCK_WIDTH)
        height = (self.sheet_size.height_mm - 2 * self.sheet_size.margin_mm 
                 - self.BOM_TABLE_HEIGHT)
        
        return (width, height)
    
    def get_title_block_position(self) -> Tuple[float, float]:
        """
        Get title block position (bottom-right corner).
        
        Returns:
            Tuple of (x, y) position in mm from bottom-left
        """
        if not self.sheet_size:
            return (0, 0)
        
        x = self.sheet_size.width_mm - self.sheet_size.margin_mm - self.TITLE_BLOCK_WIDTH
        y = self.sheet_size.margin_mm
        
        return (x, y)
    
    def get_bom_table_position(self) -> Tuple[float, float]:
        """
        Get BOM table position (bottom-left corner).
        
        Returns:
            Tuple of (x, y) position in mm from bottom-left
        """
        if not self.sheet_size:
            return (0, 0)
        
        x = self.sheet_size.margin_mm
        y = self.sheet_size.margin_mm
        
        return (x, y)
