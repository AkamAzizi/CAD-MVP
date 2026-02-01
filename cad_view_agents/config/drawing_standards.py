"""
Drawing standards configuration (ANSI/ISO projection rules).
"""
from enum import Enum


class ProjectionStandard(Enum):
    """Drawing projection standards."""
    THIRD_ANGLE = "third_angle"  # US standard
    FIRST_ANGLE = "first_angle"   # ISO standard


class DrawingStandards:
    """Drawing standards configuration."""
    
    DEFAULT_PROJECTION = ProjectionStandard.THIRD_ANGLE
    DEFAULT_LINE_WIDTH_VISIBLE = 0.5  # mm
    DEFAULT_LINE_WIDTH_HIDDEN = 0.25  # mm
    DEFAULT_LINE_WIDTH_CENTER = 0.25  # mm
    
    # Hidden line style
    HIDDEN_LINE_STYLE = "Dashed"  # FreeCAD line style
    HIDDEN_LINE_PATTERN = [5, 2]  # Dash pattern
    
    # Center line style
    CENTER_LINE_STYLE = "DashDot"
    CENTER_LINE_PATTERN = [10, 5, 2, 5]
