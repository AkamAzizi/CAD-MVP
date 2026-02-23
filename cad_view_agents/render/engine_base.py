"""
Base interface for 2D drawing render engines.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any
from pathlib import Path
from core.layout_engine import ViewPlacement


class RenderEngine(ABC):
    """Base interface for 2D drawing render engines."""
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available (dependencies installed)."""
        pass
