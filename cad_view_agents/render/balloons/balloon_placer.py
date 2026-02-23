"""
Deterministic balloon placement algorithm for technical drawings.
Handles anchor selection, slot assignment, and leader routing.
"""
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass
import math


@dataclass
class BalloonPlacement:
    """Represents a placed balloon with leader line."""
    item_number: int
    part_id: str
    balloon_center: Tuple[float, float]  # (x, y) on sheet
    anchor_point: Tuple[float, float]  # (x, y) on sheet - where leader attaches to part
    elbow_point: Tuple[float, float]  # (x, y) on sheet - elbow in leader line
    leader_segments: List[Tuple[float, float]]  # List of (x, y) points for leader line


class BalloonPlacer:
    """Deterministic balloon placement algorithm (no AI)."""
    
    # Balloon radius in mm
    BALLOON_RADIUS = 5.0
    
    # Minimum spacing between balloons (mm)
    MIN_BALLOON_SPACING = 20.0
    
    # Distance from view bbox to balloon slot ring (mm)
    SLOT_RING_OFFSET = 15.0
    
    def place(self,
              view_bbox: Tuple[float, float, float, float],  # (x, y, w, h) on sheet
              part_projections: Dict[str, Dict[str, Any]],  # part_id -> {centroid_2d, bbox_2d}
              bom_items: List[Dict[str, Any]],  # List of {item_number, part_id}
              sheet_coords: bool = True) -> List[BalloonPlacement]:
        """
        Place balloons for parts in a view.
        
        Args:
            view_bbox: View bounding box (x, y, width, height) on sheet in mm
            part_projections: Dictionary mapping part_id to projected 2D data:
                {centroid_2d: (x, y), bbox_2d: (xmin, ymin, xmax, ymax)}
            bom_items: List of BOM items with item_number and part_id
            sheet_coords: If True, coordinates are in sheet space; if False, in view space
            
        Returns:
            List of BalloonPlacement objects
        """
        x, y, w, h = view_bbox
        view_center_x = x + w / 2
        view_center_y = y + h / 2
        
        # Sort parts by item_number for determinism
        sorted_items = sorted(bom_items, key=lambda item: item.get("item_number", 0))
        
        # Create candidate balloon slots around view rectangle
        slots = self._create_slots(view_bbox)
        
        placements = []
        used_slots = set()
        
        for item in sorted_items:
            item_number = item.get("item_number", 0)
            part_id = item.get("part_id", "")
            
            if part_id not in part_projections:
                continue
            
            proj_data = part_projections[part_id]
            
            # Compute anchor point using fallback hierarchy
            anchor = self._compute_anchor(
                proj_data,
                view_bbox,
                sheet_coords
            )
            
            # Find nearest available slot
            slot = self._find_nearest_available_slot(
                anchor,
                slots,
                used_slots,
                view_bbox
            )
            
            if slot is None:
                # No slot available, skip this balloon
                continue
            
            used_slots.add(slot)
            balloon_center = slot
            
            # Compute leader elbow and segments
            elbow = self._compute_elbow(
                balloon_center,
                anchor,
                view_bbox
            )
            
            leader_segments = [balloon_center, elbow, anchor]
            
            placements.append(BalloonPlacement(
                item_number=item_number,
                part_id=part_id,
                balloon_center=balloon_center,
                anchor_point=anchor,
                elbow_point=elbow,
                leader_segments=leader_segments
            ))
        
        return placements
    
    def _compute_anchor(self,
                       proj_data: Dict[str, Any],
                       view_bbox: Tuple[float, float, float, float],
                       sheet_coords: bool) -> Tuple[float, float]:
        """
        Compute anchor point using deterministic fallback hierarchy.
        
        Hierarchy:
        1. Use projected centroid if inside view bbox
        2. Else use projected bbox center
        3. Else use nearest projected bbox corner toward view border
        """
        x, y, w, h = view_bbox
        view_xmin, view_ymin = x, y
        view_xmax, view_ymax = x + w, y + h
        
        # Get projected data
        centroid_2d = proj_data.get("centroid_2d")
        bbox_2d = proj_data.get("bbox_2d")
        
        if not sheet_coords:
            # Transform from view coords to sheet coords
            if centroid_2d:
                centroid_2d = (centroid_2d[0] + x, centroid_2d[1] + y)
            if bbox_2d:
                xmin, ymin, xmax, ymax = bbox_2d
                bbox_2d = (xmin + x, ymin + y, xmax + x, ymax + y)
        
        # Hierarchy 1: Use projected centroid if inside view bbox
        if centroid_2d:
            cx, cy = centroid_2d
            if (view_xmin <= cx <= view_xmax and view_ymin <= cy <= view_ymax):
                return (cx, cy)
        
        # Hierarchy 2: Use projected bbox center
        if bbox_2d:
            xmin, ymin, xmax, ymax = bbox_2d
            bbox_center_x = (xmin + xmax) / 2
            bbox_center_y = (ymin + ymax) / 2
            return (bbox_center_x, bbox_center_y)
        
        # Hierarchy 3: Use nearest bbox corner toward view border
        if bbox_2d:
            xmin, ymin, xmax, ymax = bbox_2d
            corners = [
                (xmin, ymin), (xmax, ymin),
                (xmin, ymax), (xmax, ymax)
            ]
            
            # Find corner closest to view center
            view_center = ((view_xmin + view_xmax) / 2, (view_ymin + view_ymax) / 2)
            nearest = min(corners, key=lambda c: math.sqrt(
                (c[0] - view_center[0])**2 + (c[1] - view_center[1])**2
            ))
            return nearest
        
        # Fallback: Use view center
        return ((view_xmin + view_xmax) / 2, (view_ymin + view_ymax) / 2)
    
    def _create_slots(self, view_bbox: Tuple[float, float, float, float]) -> List[Tuple[float, float]]:
        """
        Create candidate balloon slots around view rectangle.
        
        Slots are arranged in a ring around the view:
        - Top edge
        - Right edge
        - Bottom edge
        - Left edge
        
        Returns list of (x, y) positions.
        """
        x, y, w, h = view_bbox
        offset = self.SLOT_RING_OFFSET + self.BALLOON_RADIUS
        
        slots = []
        
        # Top edge (left to right)
        num_top = max(3, int(w / (self.MIN_BALLOON_SPACING + 2 * self.BALLOON_RADIUS)))
        for i in range(num_top):
            slot_x = x + (i + 1) * w / (num_top + 1)
            slot_y = y + h + offset
            slots.append((slot_x, slot_y))
        
        # Right edge (top to bottom)
        num_right = max(3, int(h / (self.MIN_BALLOON_SPACING + 2 * self.BALLOON_RADIUS)))
        for i in range(num_right):
            slot_x = x + w + offset
            slot_y = y + h - (i + 1) * h / (num_right + 1)
            slots.append((slot_x, slot_y))
        
        # Bottom edge (right to left)
        for i in range(num_top):
            slot_x = x + w - (i + 1) * w / (num_top + 1)
            slot_y = y - offset
            slots.append((slot_x, slot_y))
        
        # Left edge (bottom to top)
        for i in range(num_right):
            slot_x = x - offset
            slot_y = y + (i + 1) * h / (num_right + 1)
            slots.append((slot_x, slot_y))
        
        return slots
    
    def _find_nearest_available_slot(self,
                                    anchor: Tuple[float, float],
                                    slots: List[Tuple[float, float]],
                                    used_slots: set,
                                    view_bbox: Tuple[float, float, float, float]) -> Optional[Tuple[float, float]]:
        """Find nearest available slot to anchor point."""
        available_slots = [s for s in slots if s not in used_slots]
        
        if not available_slots:
            return None
        
        # Find slot with minimum distance to anchor
        nearest = min(available_slots, key=lambda s: math.sqrt(
            (s[0] - anchor[0])**2 + (s[1] - anchor[1])**2
        ))
        
        # Check collision with view bbox
        x, y, w, h = view_bbox
        if (x <= nearest[0] <= x + w and y <= nearest[1] <= y + h):
            # Slot is inside view, skip it
            return None
        
        return nearest
    
    def _compute_elbow(self,
                      balloon_center: Tuple[float, float],
                      anchor: Tuple[float, float],
                      view_bbox: Tuple[float, float, float, float]) -> Tuple[float, float]:
        """
        Compute leader elbow point using deterministic rule.
        
        Rule: Elbow = (B.x, A.y) or (A.x, B.y)
        Choose the elbow that stays outside the view bbox more.
        """
        B = balloon_center
        A = anchor
        x, y, w, h = view_bbox
        
        # Candidate elbows
        elbow1 = (B[0], A[1])  # Horizontal then vertical
        elbow2 = (A[0], B[1])  # Vertical then horizontal
        
        # Check which elbow stays outside view bbox more
        def distance_outside_bbox(point):
            """Calculate how far point is outside bbox (0 if inside)."""
            px, py = point
            dx = max(0, x - px, px - (x + w))
            dy = max(0, y - py, py - (y + h))
            return math.sqrt(dx**2 + dy**2)
        
        dist1 = distance_outside_bbox(elbow1)
        dist2 = distance_outside_bbox(elbow2)
        
        # Choose elbow that stays outside more
        return elbow1 if dist1 >= dist2 else elbow2
