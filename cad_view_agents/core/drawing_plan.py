"""
Drawing plan data structure for 2D drawing generation.
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from .layout_engine import ViewPlacement
from .bom_generator import BOMTable
from .balloon_engine import Balloon


@dataclass
class DrawingPlan:
    """Contract for drawing generation plan."""
    assembly_id: str
    sheet_size: str  # "A4", "A3", etc.
    scale: float
    view_placements: List[ViewPlacement]  # From layout_engine
    bom_table: Optional[BOMTable] = None
    balloons: Optional[List[Balloon]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert drawing plan to dictionary for JSON export."""
        return {
            "assembly_id": self.assembly_id,
            "sheet_size": self.sheet_size,
            "scale": self.scale,
            "view_count": len(self.view_placements),
            "bom_item_count": len(self.bom_table.parts) if self.bom_table else 0,
            "balloon_count": len(self.balloons) if self.balloons else 0,
            "metadata": self.metadata
        }
