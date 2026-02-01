"""
SVG to PDF conversion utilities.
Uses lazy imports to avoid hard dependencies.
"""
import os
from typing import Optional


def svg_to_pdf(svg_path: str, pdf_path: str) -> None:
    """
    Convert SVG file to PDF using available libraries.
    
    Tries methods in order:
    1. cairosvg.svg2pdf() - Best quality, requires cairosvg
    2. svglib.svg2rlg() + reportlab - Alternative, requires svglib+reportlab
    
    Args:
        svg_path: Path to input SVG file
        pdf_path: Path to output PDF file
        
    Raises:
        FileNotFoundError: If SVG file doesn't exist
        RuntimeError: If all conversion methods fail
    """
    if not os.path.exists(svg_path):
        raise FileNotFoundError(f"SVG file not found: {svg_path}")
    
    if os.path.getsize(svg_path) == 0:
        raise RuntimeError(f"SVG file is empty: {svg_path}")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(pdf_path) if os.path.dirname(pdf_path) else ".", exist_ok=True)
    
    # Method 1: Try cairosvg (best quality)
    try:
        import cairosvg
        cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)
        
        # Verify PDF was created
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return
        
        raise RuntimeError("cairosvg created empty PDF file")
        
    except ImportError:
        pass  # cairosvg not available, try next method
    except Exception as e:
        # cairosvg failed, try next method
        error_msg = str(e)
        if "cairosvg" not in error_msg.lower():
            # Real error from cairosvg, not just import failure
            raise RuntimeError(f"cairosvg conversion failed: {e}") from e
        pass
    
    # Method 2: Try svglib + reportlab
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPDF
        
        # Convert SVG to reportlab graphics
        drawing = svg2rlg(svg_path)
        
        if drawing is None:
            raise RuntimeError("svglib failed to parse SVG")
        
        # Render to PDF
        renderPDF.drawToFile(drawing, pdf_path)
        
        # Verify PDF was created
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return
        
        raise RuntimeError("svglib+reportlab created empty PDF file")
        
    except ImportError as e:
        # Neither library available
        missing = []
        try:
            import svglib
        except ImportError:
            missing.append("svglib")
        
        try:
            import reportlab
        except ImportError:
            missing.append("reportlab")
        
        if missing:
            raise RuntimeError(
                f"SVG to PDF conversion requires one of: cairosvg or {'+'.join(missing)}. "
                f"Install with: pip install cairosvg or pip install {' '.join(missing)}"
            ) from e
        
        # reportlab is available but svglib failed
        raise RuntimeError(f"svglib import failed: {e}") from e
        
    except Exception as e:
        raise RuntimeError(f"svglib+reportlab conversion failed: {e}") from e
    
    # If we get here, all methods failed
    raise RuntimeError("All SVG to PDF conversion methods failed")