"""
Balloon placement engine for technical drawings.
Handles item number assignment, balloon placement, and leader line routing.
"""
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from .part_tree import PartTree, PartNode
from .layout_engine import ViewPlacement, SheetSize
from config.balloon_styles import BalloonStyle, SIMPLE_BALLOON

if TYPE_CHECKING:
    from .bom_generator import PartMetadata


@dataclass
class LeaderLine:
    """Represents a leader line from balloon to part."""
    start_point: Tuple[float, float]  # Balloon position
    end_point: Tuple[float, float]     # Part attachment point
    segments: List[Tuple[float, float]] = field(default_factory=list)  # Intermediate points for routing


@dataclass
class Balloon:
    """Represents a balloon with item number and leader line."""
    item_number: int
    part_id: str
    position: Tuple[float, float]  # Balloon center position (mm from bottom-left)
    leader: LeaderLine
    style: BalloonStyle = field(default_factory=lambda: SIMPLE_BALLOON)


class BalloonEngine:
    """Manages balloon placement and leader line routing."""
    
    # Minimum distance from view boundary to balloon (mm)
    MIN_VIEW_MARGIN = 15.0
    
    # Minimum spacing between balloons (mm)
    MIN_BALLOON_SPACING = 20.0
    
    # Leader line routing parameters
    LEADER_OFFSET = 10.0  # Distance from part to first leader segment (mm)
    LEADER_ANGLE = 45.0   # Preferred leader angle (degrees)
    
    def __init__(self, style: BalloonStyle = None):
        """
        Initialize balloon engine.
        
        Args:
            style: Balloon style configuration
        """
        self.style = style or SIMPLE_BALLOON
    
    def assign_item_numbers(self, part_tree: PartTree) -> Dict[str, int]:
        """
        Assign sequential item numbers to parts (1..N).
        Numbers are deterministic based on part tree order.
        
        Args:
            part_tree: PartTree instance
            
        Returns:
            Dictionary mapping part_id -> item_number
        """
        item_numbers = {}
        parts = part_tree.get_part_list()
        
        # Sort parts by stable ID for deterministic ordering
        sorted_parts = sorted(parts, key=lambda p: p.id)
        
        for idx, part in enumerate(sorted_parts, start=1):
            item_numbers[part.id] = idx
        
        return item_numbers
    
    def place_balloons(self, view_placements: List[ViewPlacement], 
                      part_tree: PartTree, 
                      item_numbers: Dict[str, int],
                      sheet_size: SheetSize,
                      bom_metadata: Optional[List['PartMetadata']] = None) -> List[Balloon]:
        """
        Place balloons for unique parts (one balloon per BOM row).
        
        Args:
            view_placements: List of ViewPlacement objects
            part_tree: PartTree instance
            item_numbers: Dictionary mapping part_id -> item_number
            sheet_size: SheetSize for boundary calculations
            bom_metadata: Optional list of PartMetadata from BOM (unique parts only)
                         If provided, places one balloon per BOM row instead of per instance
            
        Returns:
            List of Balloon objects (one per unique part)
        """
        balloons = []
        
        if not view_placements:
            return balloons
        
        # Use first view for balloon placement (MVP approach)
        primary_view = view_placements[0]
        
        # Calculate view boundary
        view_left = primary_view.position[0]
        view_right = view_left + primary_view.width_mm
        view_bottom = primary_view.position[1]
        view_top = view_bottom + primary_view.height_mm
        
        # Place balloons to the right of the view
        balloon_x = view_right + self.MIN_VIEW_MARGIN
        balloon_y_start = view_top - self.MIN_VIEW_MARGIN
        
        # If BOM metadata provided, place balloons based on unique parts (BOM rows)
        if bom_metadata:
            # Sort by item number for consistent placement
            sorted_bom_parts = sorted(bom_metadata, key=lambda p: p.item_number)
            
            # Build lookup: part_id -> representative FreeCAD object (first match)
            # This is needed to attach balloons to actual geometry
            doc = None
            if hasattr(part_tree, 'parts') and part_tree.parts:
                # Get document from first part's freecad_obj if available
                for part in part_tree.parts:
                    if part.freecad_obj is not None:
                        doc = part.freecad_obj.Document if hasattr(part.freecad_obj, 'Document') else None
                        break
            
            # Build part_id lookup for representative objects
            part_id_to_obj = {}
            if doc:
                for part_node in part_tree.get_part_list():
                    if part_node.freecad_obj is not None:
                        part_id = part_node.id
                        # Only store first occurrence of each part_id
                        if part_id not in part_id_to_obj:
                            part_id_to_obj[part_id] = part_node.freecad_obj
            
            # Place balloons for each unique part (BOM row)
            for idx, bom_part in enumerate(sorted_bom_parts):
                item_number = bom_part.item_number
                part_id = bom_part.part_id
                
                # Calculate balloon position
                balloon_y = balloon_y_start - idx * (self.style.circle_radius * 2 + self.MIN_BALLOON_SPACING)
                
                # Ensure balloon stays within sheet bounds
                if balloon_y < self.style.circle_radius:
                    # Wrap to next column if needed
                    balloon_x += self.style.circle_radius * 2 + self.MIN_BALLOON_SPACING
                    balloon_y = balloon_y_start
                
                # Create leader line (simple straight line for MVP)
                # End point is on the right edge of the view
                leader_end_x = view_right
                leader_end_y = view_bottom + (view_top - view_bottom) * (idx + 1) / (len(sorted_bom_parts) + 1)
                
                leader = LeaderLine(
                    start_point=(balloon_x, balloon_y),
                    end_point=(leader_end_x, leader_end_y),
                    segments=[]
                )
                
                # Create balloon (one per unique part)
                balloon = Balloon(
                    item_number=item_number,
                    part_id=part_id,  # This is the unique part number
                    position=(balloon_x, balloon_y),
                    leader=leader,
                    style=self.style
                )
                
                balloons.append(balloon)
            
            return balloons
        
        # Legacy behavior: place balloons for all parts (if BOM metadata not provided)
        # This is for backward compatibility
        parts = part_tree.get_part_list()
        
        # Sort parts by item number for consistent placement
        sorted_parts = sorted(parts, key=lambda p: item_numbers.get(p.id, 999))
        
        # Place balloons vertically, top to bottom
        for idx, part in enumerate(sorted_parts):
            part_id = part.id
            item_number = item_numbers.get(part_id)
            
            if item_number is None:
                continue
            
            # Calculate balloon position
            balloon_y = balloon_y_start - idx * (self.style.circle_radius * 2 + self.MIN_BALLOON_SPACING)
            
            # Ensure balloon stays within sheet bounds
            if balloon_y < self.style.circle_radius:
                # Wrap to next column if needed
                balloon_x += self.style.circle_radius * 2 + self.MIN_BALLOON_SPACING
                balloon_y = balloon_y_start
            
            # Create leader line (simple straight line for MVP)
            # End point is on the right edge of the view
            leader_end_x = view_right
            leader_end_y = view_bottom + (view_top - view_bottom) * (idx + 1) / (len(sorted_parts) + 1)
            
            leader = LeaderLine(
                start_point=(balloon_x, balloon_y),
                end_point=(leader_end_x, leader_end_y),
                segments=[]
            )
            
            # Create balloon
            balloon = Balloon(
                item_number=item_number,
                part_id=part_id,
                position=(balloon_x, balloon_y),
                leader=leader,
                style=self.style
            )
            
            balloons.append(balloon)
        
        return balloons
    
    def route_leaders(self, balloons: List[Balloon], 
                     view_placements: List[ViewPlacement]) -> List[Balloon]:
        """
        Route leader lines to avoid overlaps and minimize crossings.
        For MVP: simple straight leaders. Advanced routing in v2.
        
        Args:
            balloons: List of Balloon objects
            view_placements: List of ViewPlacement objects
            
        Returns:
            Updated list of Balloon objects with routed leaders
        """
        # MVP: Simple straight leaders
        # v2: Implement intelligent routing with intermediate segments
        
        if not view_placements:
            return balloons
        
        primary_view = view_placements[0]
        view_left = primary_view.position[0]
        view_right = view_left + primary_view.width_mm
        view_bottom = primary_view.position[1]
        view_top = view_bottom + primary_view.height_mm
        
        # Update leader end points to be on view boundary
        for idx, balloon in enumerate(balloons):
            # Distribute attachment points along right edge
            t = (idx + 1) / (len(balloons) + 1)
            leader_end_y = view_bottom + (view_top - view_bottom) * t
            
            balloon.leader.end_point = (view_right, leader_end_y)
            
            # For MVP, use straight line (no intermediate segments)
            # In v2, we can add intermediate segments to avoid overlaps
            balloon.leader.segments = []
        
        return balloons
    
    def get_balloon_bounds(self, balloon: Balloon) -> Tuple[float, float, float, float]:
        """
        Get bounding box of balloon (including circle and leader).
        
        Args:
            balloon: Balloon object
            
        Returns:
            Tuple of (min_x, min_y, max_x, max_y)
        """
        x, y = balloon.position
        radius = balloon.style.circle_radius
        
        # Balloon circle bounds
        min_x = x - radius
        max_x = x + radius
        min_y = y - radius
        max_y = y + radius
        
        # Include leader line bounds
        leader_start = balloon.leader.start_point
        leader_end = balloon.leader.end_point
        
        min_x = min(min_x, leader_start[0], leader_end[0])
        max_x = max(max_x, leader_start[0], leader_end[0])
        min_y = min(min_y, leader_start[1], leader_end[1])
        max_y = max(max_y, leader_start[1], leader_end[1])
        
        return (min_x, min_y, max_x, max_y)
    
    def check_overlaps(self, balloons: List[Balloon]) -> List[Tuple[int, int]]:
        """
        Check for overlapping balloons.
        
        Args:
            balloons: List of Balloon objects
            
        Returns:
            List of (balloon_idx1, balloon_idx2) pairs that overlap
        """
        overlaps = []
        
        for i in range(len(balloons)):
            for j in range(i + 1, len(balloons)):
                bounds_i = self.get_balloon_bounds(balloons[i])
                bounds_j = self.get_balloon_bounds(balloons[j])
                
                # Check if bounding boxes overlap
                if not (bounds_i[2] < bounds_j[0] or bounds_j[2] < bounds_i[0] or
                       bounds_i[3] < bounds_j[1] or bounds_j[3] < bounds_i[1]):
                    overlaps.append((i, j))
        
        return overlaps
