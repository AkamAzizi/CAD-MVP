"""
FreeCAD TechDraw exporter.
Handles direct TechDraw → PDF/DXF export.
"""
import os
from typing import Optional, Any


class TechDrawExporter:
    """Exports TechDraw pages using FreeCAD TechDraw module."""
    
    def __init__(self):
        self.techdraw_available = self._check_techdraw_available()
    
    def _check_techdraw_available(self) -> bool:
        """Check if TechDraw is available."""
        try:
            import TechDraw
            return True
        except ImportError:
            return False
    
    def export_pdf(self, page: Any, output_path: str) -> str:
        """
        Export TechDraw page to PDF.
        
        Args:
            page: TechDraw page object
            output_path: Output file path
            
        Returns:
            Path to exported PDF
        """
        if not self.techdraw_available or page is None:
            raise ValueError("TechDraw not available or page is None")
        
        try:
            import TechDraw
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            page.recompute()
            page.Document.recompute()
            
            # Try multiple export methods for compatibility
            if hasattr(page, 'exportPageAsPdf'):
                page.exportPageAsPdf(output_path)
            elif hasattr(TechDraw, 'exportPageAsPdf'):
                TechDraw.exportPageAsPdf(page, output_path)
            else:
                raise AttributeError("TechDraw PDF export method not found")
            
            return output_path
            
        except Exception as e:
            raise RuntimeError(f"Failed to export PDF: {e}") from e
    
    def export_dxf(self, page: Any, output_path: str) -> str:
        """
        Export TechDraw page to DXF.
        
        Args:
            page: TechDraw page object
            output_path: Output file path
            
        Returns:
            Path to exported DXF
        """
        if not self.techdraw_available or page is None:
            raise ValueError("TechDraw not available or page is None")
        
        try:
            import TechDraw
            
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            
            page.recompute()
            page.Document.recompute()
            
            # Try multiple export methods for compatibility
            if hasattr(page, 'exportPageAsDxf'):
                page.exportPageAsDxf(output_path)
            elif hasattr(TechDraw, 'exportPageAsDxf'):
                TechDraw.exportPageAsDxf(page, output_path)
            else:
                raise AttributeError("TechDraw DXF export method not found")
            
            return output_path
            
        except Exception as e:
            raise RuntimeError(f"Failed to export DXF: {e}") from e
