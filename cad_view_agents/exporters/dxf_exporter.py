"""
Fallback DXF exporter using ezdxf.
Used when FreeCAD TechDraw is unavailable or fails.
"""
import os
from typing import Optional, Any, List, Tuple


class DXFExporter:
    """Fallback DXF exporter for technical drawings."""
    
    def __init__(self):
        self.ezdxf_available = self._check_ezdxf_available()
    
    def _check_ezdxf_available(self) -> bool:
        """Check if ezdxf is available."""
        try:
            import ezdxf
            return True
        except ImportError:
            return False
    
    def export(self, page: Any, output_path: str,
               sheet_size_name: str = "A4",
               views: Optional[List[Any]] = None,
               metadata: Optional[dict] = None) -> str:
        """
        Export drawing to DXF using ezdxf.
        
        Args:
            page: TechDraw page (may be None if TechDraw unavailable)
            output_path: Output file path
            sheet_size_name: Sheet size ("A4", "A3", etc.)
            views: List of view data (if TechDraw unavailable)
            metadata: Drawing metadata
            
        Returns:
            Path to exported DXF
        """
        if not self.ezdxf_available:
            raise RuntimeError("ezdxf not available. Install with: pip install ezdxf")
        
        try:
            import ezdxf
            from ezdxf import units
            
            # Create new DXF document
            doc = ezdxf.new('R2010')  # AutoCAD 2010 format for compatibility
            doc.units = units.MM  # Use millimeters
            
            # Get model space
            msp = doc.modelspace()
            
            # Draw title block placeholder
            self._draw_title_block(msp, sheet_size_name, metadata)
            
            # Draw views placeholder
            if views:
                self._draw_views_placeholder(msp, views)
            else:
                # Draw placeholder text
                msp.add_text(
                    "TechDraw not available - placeholder DXF generated",
                    dxfattribs={'height': 5.0}
                ).set_placement((50, 100))
                msp.add_text(
                    "Use FreeCAD with TechDraw module for full functionality",
                    dxfattribs={'height': 3.5}
                ).set_placement((50, 95))
            
            # Draw BOM table placeholder
            self._draw_bom_placeholder(msp)
            
            # Save DXF
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            doc.saveas(output_path)
            
            return output_path
            
        except Exception as e:
            raise RuntimeError(f"Failed to export DXF: {e}") from e
    
    def _draw_title_block(self, msp, sheet_size_name: str, metadata: Optional[dict]):
        """Draw title block placeholder in DXF."""
        # Title block border (bottom-right corner)
        # For A4: 210x297mm
        if sheet_size_name == "A4":
            width, height = 210, 297
        elif sheet_size_name == "A3":
            width, height = 297, 420
        else:
            width, height = 210, 297  # Default to A4
        
        title_x = width - 180
        title_y = 10
        title_width = 170
        title_height = 40
        
        # Draw border rectangle
        msp.add_lwpolyline([
            (title_x, title_y),
            (title_x + title_width, title_y),
            (title_x + title_width, title_y + title_height),
            (title_x, title_y + title_height),
            (title_x, title_y)  # Close rectangle
        ], dxfattribs={'closed': True})
        
        # Draw title text
        if metadata:
            filename = metadata.get("filename", "Unknown")
            msp.add_text(
                f"Drawing: {filename}",
                dxfattribs={'height': 3.5}
            ).set_placement((title_x + 5, title_y + 25))
    
    def _draw_views_placeholder(self, msp, views: List[Any]):
        """Draw placeholder for views in DXF."""
        # This would be implemented to draw actual view projections
        # For MVP, we leave it as a placeholder
        pass
    
    def _draw_bom_placeholder(self, msp):
        """Draw BOM table placeholder in DXF."""
        # BOM in bottom-left corner
        bom_x = 10
        bom_y = 10
        bom_width = 150
        bom_height = 100
        
        # Draw border rectangle
        msp.add_lwpolyline([
            (bom_x, bom_y),
            (bom_x + bom_width, bom_y),
            (bom_x + bom_width, bom_y + bom_height),
            (bom_x, bom_y + bom_height),
            (bom_x, bom_y)  # Close rectangle
        ], dxfattribs={'closed': True})
        
        # Draw BOM header
        msp.add_text(
            "Bill of Materials",
            dxfattribs={'height': 4.0}
        ).set_placement((bom_x + 5, bom_y + 85))
        
        msp.add_text(
            "(Placeholder - Phase 3)",
            dxfattribs={'height': 3.0}
        ).set_placement((bom_x + 5, bom_y + 75))
