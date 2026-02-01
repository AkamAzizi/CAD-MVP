"""
Sheet size templates and title block configurations.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.layout_engine import SheetSize, LayoutEngine


class SheetTemplate:
    """Represents a drawing sheet template."""
    
    def __init__(self, name: str, sheet_size: SheetSize):
        self.name = name
        self.sheet_size = sheet_size
        self.title_block_height = 40  # mm
        self.title_block_width = 180  # mm


# Standard templates
# Access SHEET_SIZES from LayoutEngine class
TEMPLATES = {
    "standard": SheetTemplate("standard", LayoutEngine.SHEET_SIZES["A3"]),
    "a4": SheetTemplate("a4", LayoutEngine.SHEET_SIZES["A4"]),
    "a3": SheetTemplate("a3", LayoutEngine.SHEET_SIZES["A3"]),
    "a2": SheetTemplate("a2", LayoutEngine.SHEET_SIZES["A2"]),
    "a1": SheetTemplate("a1", LayoutEngine.SHEET_SIZES["A1"]),
}
