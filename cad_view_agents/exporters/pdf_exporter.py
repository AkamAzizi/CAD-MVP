"""
Fallback PDF exporter using reportlab.
Used when FreeCAD TechDraw is unavailable or fails.
"""
import os
import re
import tempfile
from typing import Optional, Any, List, Tuple, Dict


class PDFExporter:
    """Fallback PDF exporter for technical drawings."""
    
    def __init__(self):
        self.reportlab_available = self._check_reportlab_available()
        self._reportlab_modules = {}  # Cache for lazy-loaded modules
    
    def _check_reportlab_available(self) -> bool:
        """Check if reportlab is available."""
        try:
            import reportlab
            return True
        except ImportError:
            return False
    
    def _get_reportlab_modules(self):
        """Lazily import reportlab modules."""
        if not self.reportlab_available:
            raise RuntimeError("reportlab not available. Install with: pip install reportlab")
        
        if not self._reportlab_modules:
            from reportlab.lib.pagesizes import A4, A3, A2, A1, A0
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
            
            self._reportlab_modules = {
                "pagesizes": {"A4": A4, "A3": A3, "A2": A2, "A1": A1, "A0": A0},
                "mm": mm,
                "canvas": canvas
            }
        
        return self._reportlab_modules
    
    def _get_page_size(self, sheet_size_name: str):
        """Get reportlab page size for sheet size name."""
        modules = self._get_reportlab_modules()
        return modules["pagesizes"].get(sheet_size_name, modules["pagesizes"]["A4"])
    
    def export(self, page: Any, output_path: str, 
               sheet_size_name: str = "A4",
               views: Optional[List[Any]] = None,
               balloons: Optional[List[Any]] = None,
               bom_table: Optional[Any] = None,
               metadata: Optional[dict] = None,
               view_svgs: Optional[List[Tuple[Optional[str], dict]]] = None) -> Dict[str, Any]:
        """
        Export drawing to PDF using reportlab.
        
        Args:
            page: TechDraw page (may be None if TechDraw unavailable)
            output_path: Output file path
            sheet_size_name: Sheet size ("A4", "A3", etc.)
            views: List of view data (if TechDraw unavailable)
            metadata: Drawing metadata
            
        Returns:
            Path to exported PDF
        """
        if not self.reportlab_available:
            raise RuntimeError("reportlab not available. Install with: pip install reportlab")
        
        try:
            # Get reportlab modules
            modules = self._get_reportlab_modules()
            mm = modules["mm"]
            canvas = modules["canvas"]
            
            # Get page size
            page_size = self._get_page_size(sheet_size_name)
            
            # Create PDF canvas
            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            c = canvas.Canvas(output_path, pagesize=page_size)
            
            # Draw title block
            self._draw_title_block(c, page_size, metadata)
            
            # Draw views (with SVG embedding if available)
            render_stats = {"rendered": 0, "total": 0, "placeholders": 0}
            if view_svgs:
                # Render SVG views embedded in PDF using reportlab + svglib
                print("  [INFO] PDF export Tier2: Rendering SVGs into PDF using svglib")
                render_stats = self._draw_view_svgs(c, page_size, view_svgs)
            elif views:
                self._draw_views(c, page_size, views)
            else:
                # Draw placeholder text if no views
                width, height = page_size
                c.drawString(50 * mm, height - 100 * mm, 
                           "TechDraw not available - view data not provided")
                c.drawString(50 * mm, height - 120 * mm, 
                           f"Use FreeCAD with TechDraw module for full functionality")
            
            # Draw balloons
            if balloons:
                self._draw_balloons(c, page_size, balloons)
            
            # Draw BOM table
            if bom_table:
                self._draw_bom_table(c, page_size, bom_table)
            else:
                self._draw_bom_placeholder(c, page_size)
            
            # Save PDF
            c.save()
            
            # Return path and render statistics
            return {
                "pdf_path": output_path,
                "rendered": render_stats.get("rendered", 0),
                "total": render_stats.get("total", 0),
                "placeholders": render_stats.get("placeholders", 0)
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to export PDF: {e}") from e
    
    def _draw_title_block(self, c: Any, page_size: Tuple[float, float], 
                         metadata: Optional[dict]):
        """Draw title block placeholder."""
        modules = self._get_reportlab_modules()
        mm = modules["mm"]
        
        width, height = page_size
        
        # Title block in bottom-right corner
        title_x = width - 180 * mm
        title_y = 10 * mm
        
        # Draw border
        c.rect(title_x, title_y, 170 * mm, 40 * mm)
        
        # Draw title
        if metadata:
            filename = metadata.get("filename", "Unknown")
            c.drawString(title_x + 5 * mm, title_y + 25 * mm, f"Drawing: {filename}")
    
    def _extract_path_bounds(self, svg_content: str) -> Optional[Tuple[float, float, float, float]]:
        """
        Extract bounding box from all path elements in SVG content.
        
        Parses path data (d attribute) to find min/max x,y coordinates.
        Handles: M (moveto), L (lineto), A (arc), and other path commands.
        
        Returns:
            Tuple (min_x, min_y, max_x, max_y) or None if no valid paths found
        """
        import re
        
        # Pattern to match all numeric values in path data (including negatives and decimals)
        # This is more robust than trying to parse individual commands
        number_pattern = re.compile(r'([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)')
        
        min_x = min_y = max_x = max_y = None
        coords_found = False
        
        # Find all path elements
        path_pattern = re.compile(r'<path[^>]*d\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
        
        for path_match in path_pattern.finditer(svg_content):
            path_data = path_match.group(1)
            
            # Extract all numbers from path data
            numbers = []
            for num_match in number_pattern.finditer(path_data):
                try:
                    num = float(num_match.group(1))
                    numbers.append(num)
                except (ValueError, TypeError):
                    continue
            
            # Process numbers in pairs (x, y coordinates)
            # Skip the first number if it's a command identifier (very unlikely to be a coordinate)
            for i in range(0, len(numbers) - 1, 2):
                if i + 1 < len(numbers):
                    x = numbers[i]
                    y = numbers[i + 1]
                    
                    if min_x is None:
                        min_x = max_x = x
                        min_y = max_y = y
                        coords_found = True
                    else:
                        min_x = min(min_x, x)
                        min_y = min(min_y, y)
                        max_x = max(max_x, x)
                        max_y = max(max_y, y)
                elif i < len(numbers):
                    # Odd number of coordinates - treat last as X (common for H command)
                    x = numbers[i]
                    # Keep previous Y or use 0
                    if min_y is not None:
                        if min_x is None:
                            min_x = max_x = x
                            min_y = max_y = 0
                            coords_found = True
                        else:
                            min_x = min(min_x, x)
                            max_x = max(max_x, x)
        
        if not coords_found:
            return None
        
        return (min_x, min_y, max_x, max_y)
    
    def _ensure_svg_has_dimensions(self, svg_path: str, default_w_pt: float, default_h_pt: float) -> str:
        """
        Ensure SVG has explicit width/height and viewBox so svglib can parse it correctly.
        
        TechDraw.exportSVGEdges() often produces SVGs without width/height, only paths.
        This patches the SVG by:
        1. Extracting actual bounding box from path coordinates
        2. Setting appropriate viewBox
        3. Setting width/height attributes
        
        Args:
            svg_path: Path to original SVG file
            default_w_pt: Default width in points (fallback if bounds extraction fails)
            default_h_pt: Default height in points (fallback if bounds extraction fails)
            
        Returns:
            Path to patched SVG file (may be same as original if no patching needed)
        """
        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
        except Exception as e:
            # If we can't read the SVG, return original path and let svglib handle the error
            return svg_path
        
        # Check if SVG already has explicit width and height attributes with non-zero values
        width_match = re.search(r'width\s*=\s*["\']([^"\']+)["\']', svg_content, re.IGNORECASE)
        height_match = re.search(r'height\s*=\s*["\']([^"\']+)["\']', svg_content, re.IGNORECASE)
        
        has_valid_width = False
        has_valid_height = False
        
        if width_match:
            width_val = width_match.group(1).strip()
            # Check if it's non-zero (handle various formats: "100", "100pt", "100px", "100mm")
            try:
                # Extract numeric value
                num_val = re.search(r'[\d.]+', width_val)
                if num_val and float(num_val.group()) > 0:
                    has_valid_width = True
            except (ValueError, AttributeError):
                pass
        
        if height_match:
            height_val = height_match.group(1).strip()
            try:
                num_val = re.search(r'[\d.]+', height_val)
                if num_val and float(num_val.group()) > 0:
                    has_valid_height = True
            except (ValueError, AttributeError):
                pass
        
        # If both width and height are valid, no patching needed
        if has_valid_width and has_valid_height:
            return svg_path
        
        # Need to patch: extract actual geometry bounds and set viewBox
        viewbox_match = re.search(r'viewBox\s*=\s*["\']([^"\']+)["\']', svg_content, re.IGNORECASE)
        
        # Standard conversion factor: mm to points
        MM_TO_PT = 2.834645669291339
        
        # Try to extract bounds from path coordinates if no viewBox exists
        bounds = None
        if not viewbox_match:
            bounds = self._extract_path_bounds(svg_content)
            if bounds:
                min_x_mm, min_y_mm, max_x_mm, max_y_mm = bounds
                # Add small padding (5% of size or 1mm, whichever is larger)
                range_x = max_x_mm - min_x_mm
                range_y = max_y_mm - min_y_mm
                padding_x = max(range_x * 0.05, 1.0) if range_x > 0 else 1.0
                padding_y = max(range_y * 0.05, 1.0) if range_y > 0 else 1.0
                min_x_mm_padded = min_x_mm - padding_x
                min_y_mm_padded = min_y_mm - padding_y
                viewbox_width_mm = (max_x_mm - min_x_mm) + 2 * padding_x
                viewbox_height_mm = (max_y_mm - min_y_mm) + 2 * padding_y
                
                # Ensure positive dimensions
                if viewbox_width_mm <= 0:
                    viewbox_width_mm = abs(max_x_mm - min_x_mm) if max_x_mm != min_x_mm else 1.0
                if viewbox_height_mm <= 0:
                    viewbox_height_mm = abs(max_y_mm - min_y_mm) if max_y_mm != min_y_mm else 1.0
                
                # CONVERT to points for viewBox:
                vb_x_pt = min_x_mm_padded * MM_TO_PT
                vb_y_pt = min_y_mm_padded * MM_TO_PT
                vb_w_pt = viewbox_width_mm * MM_TO_PT
                vb_h_pt = viewbox_height_mm * MM_TO_PT
                
                # Set viewBox in POINTS:
                viewbox_str = f"{vb_x_pt} {vb_y_pt} {vb_w_pt} {vb_h_pt}"
                
                # Calculate width/height in points that maintains aspect ratio and fits in default rectangle
                # Scale to fit in default rectangle while maintaining aspect ratio
                aspect_ratio_vb = vb_w_pt / vb_h_pt if vb_h_pt > 0 else 1.0
                aspect_ratio_default = default_w_pt / default_h_pt if default_h_pt > 0 else 1.0
                
                if aspect_ratio_vb > aspect_ratio_default:
                    # viewBox is wider - fit to width
                    width_pt = default_w_pt
                    height_pt = default_w_pt / aspect_ratio_vb
                else:
                    # viewBox is taller - fit to height
                    height_pt = default_h_pt
                    width_pt = default_h_pt * aspect_ratio_vb
                
                print(f"  [DEBUG] Extracted bounds: min=({min_x_mm:.2f},{min_y_mm:.2f}) max=({max_x_mm:.2f},{max_y_mm:.2f}) mm")
                print(f"  [DEBUG] viewBox={viewbox_str} (pt), SVG size={width_pt:.1f}x{height_pt:.1f}pt, default={default_w_pt:.1f}x{default_h_pt:.1f}pt")
        elif viewbox_match:
            # Extract dimensions from existing viewBox: "minx miny width height"
            viewbox_str_orig = viewbox_match.group(1).strip()
            viewbox_parts = re.split(r'[\s,]+', viewbox_str_orig)
            if len(viewbox_parts) >= 4:
                try:
                    vb_min_x = float(viewbox_parts[0])
                    vb_min_y = float(viewbox_parts[1])
                    vb_width = float(viewbox_parts[2])
                    vb_height = float(viewbox_parts[3])
                    if vb_width > 0 and vb_height > 0:
                        # Assume existing viewBox is in mm, convert to points
                        vb_x_pt = vb_min_x * MM_TO_PT
                        vb_y_pt = vb_min_y * MM_TO_PT
                        vb_w_pt = vb_width * MM_TO_PT
                        vb_h_pt = vb_height * MM_TO_PT
                        
                        # Set viewBox in POINTS:
                        viewbox_str = f"{vb_x_pt} {vb_y_pt} {vb_w_pt} {vb_h_pt}"
                        
                        # Width/height in points (already calculated):
                        width_pt = vb_w_pt
                        height_pt = vb_h_pt
                    else:
                        # Invalid viewBox, extract from paths instead
                        bounds = self._extract_path_bounds(svg_content)
                        if bounds:
                            min_x_mm, min_y_mm, max_x_mm, max_y_mm = bounds
                            range_x = max_x_mm - min_x_mm
                            range_y = max_y_mm - min_y_mm
                            padding_x = max(range_x * 0.05, 1.0) if range_x > 0 else 1.0
                            padding_y = max(range_y * 0.05, 1.0) if range_y > 0 else 1.0
                            min_x_mm_padded = min_x_mm - padding_x
                            min_y_mm_padded = min_y_mm - padding_y
                            viewbox_width_mm = (max_x_mm - min_x_mm) + 2 * padding_x
                            viewbox_height_mm = (max_y_mm - min_y_mm) + 2 * padding_y
                            if viewbox_width_mm <= 0:
                                viewbox_width_mm = abs(max_x_mm - min_x_mm) if max_x_mm != min_x_mm else 1.0
                            if viewbox_height_mm <= 0:
                                viewbox_height_mm = abs(max_y_mm - min_y_mm) if max_y_mm != min_y_mm else 1.0
                            
                            # CONVERT to points for viewBox:
                            vb_x_pt = min_x_mm_padded * MM_TO_PT
                            vb_y_pt = min_y_mm_padded * MM_TO_PT
                            vb_w_pt = viewbox_width_mm * MM_TO_PT
                            vb_h_pt = viewbox_height_mm * MM_TO_PT
                            
                            # Set viewBox in POINTS:
                            viewbox_str = f"{vb_x_pt} {vb_y_pt} {vb_w_pt} {vb_h_pt}"
                            
                            # Scale to fit default rectangle
                            aspect_ratio_vb = vb_w_pt / vb_h_pt if vb_h_pt > 0 else 1.0
                            aspect_ratio_default = default_w_pt / default_h_pt if default_h_pt > 0 else 1.0
                            if aspect_ratio_vb > aspect_ratio_default:
                                width_pt = default_w_pt
                                height_pt = default_w_pt / aspect_ratio_vb
                            else:
                                height_pt = default_h_pt
                                width_pt = default_h_pt * aspect_ratio_vb
                        else:
                            viewbox_str = None
                            width_pt = default_w_pt
                            height_pt = default_h_pt
                except (ValueError, IndexError):
                    viewbox_str = None
                    width_pt = default_w_pt
                    height_pt = default_h_pt
            else:
                viewbox_str = None
                width_pt = default_w_pt
                height_pt = default_h_pt
        else:
            # No viewBox and couldn't extract bounds - use defaults
            viewbox_str = None
            width_pt = default_w_pt
            height_pt = default_h_pt
        
        # Check if SVG already has an opening <svg> tag
        svg_tag_match = re.search(r'<svg[^>]*>', svg_content, re.IGNORECASE)
        
        if svg_tag_match:
            # SVG has opening tag - inject width/height and viewBox attributes
            svg_tag = svg_tag_match.group(0)
            
            # Remove existing width/height/viewBox if present (we'll add corrected ones)
            svg_tag_clean = re.sub(r'\s+width\s*=\s*["\'][^"\']+["\']', '', svg_tag, flags=re.IGNORECASE)
            svg_tag_clean = re.sub(r'\s+height\s*=\s*["\'][^"\']+["\']', '', svg_tag_clean, flags=re.IGNORECASE)
            svg_tag_clean = re.sub(r'\s+viewBox\s*=\s*["\'][^"\']+["\']', '', svg_tag_clean, flags=re.IGNORECASE)
            
            # Add viewBox, width and height attributes
            attrs = []
            if viewbox_str:
                attrs.append(f'viewBox="{viewbox_str}"')
            if not re.search(r'\s+width\s*=', svg_tag_clean, re.IGNORECASE):
                attrs.append(f'width="{width_pt}pt"')
            if not re.search(r'\s+height\s*=', svg_tag_clean, re.IGNORECASE):
                attrs.append(f'height="{height_pt}pt"')
            
            # Insert attributes before closing >
            if attrs:
                svg_tag_clean = svg_tag_clean.rstrip('>').rstrip() + ' ' + ' '.join(attrs) + '>'
            else:
                svg_tag_clean = svg_tag_clean.rstrip('>') + '>'
            
            # Replace original tag with patched tag
            patched_content = svg_content[:svg_tag_match.start()] + svg_tag_clean + svg_content[svg_tag_match.end():]
        else:
            # No <svg> tag - wrap entire content in proper SVG structure
            # This handles SVGs from TechDraw.exportSVGEdges which may output raw <path> elements
            # Add XML declaration and xmlns if not present
            if not svg_content.strip().startswith('<?xml'):
                xml_decl = '<?xml version="1.0" encoding="UTF-8"?>\n'
            else:
                xml_decl = ''
            
            xmlns = 'xmlns="http://www.w3.org/2000/svg"'
            
            # Build SVG tag with attributes
            svg_attrs = [xmlns]
            if viewbox_str:
                svg_attrs.append(f'viewBox="{viewbox_str}"')
            svg_attrs.append(f'width="{width_pt}pt"')
            svg_attrs.append(f'height="{height_pt}pt"')
            
            svg_tag = '<svg ' + ' '.join(svg_attrs) + '>'
            
            patched_content = xml_decl + svg_tag + '\n' + svg_content + '\n</svg>'
        
        # Write patched SVG to temporary file
        base_name = os.path.basename(svg_path)
        base_dir = os.path.dirname(svg_path) or "."
        name_without_ext = os.path.splitext(base_name)[0]
        patched_path = os.path.join(base_dir, f"{name_without_ext}.patched.svg")
        
        try:
            with open(patched_path, 'w', encoding='utf-8') as f:
                f.write(patched_content)
            return patched_path
        except Exception as e:
            # If patching fails, return original path
            print(f"  [WARN] Failed to create patched SVG for {os.path.basename(svg_path)}: {e}")
            return svg_path
    
    def _to_pdf_rect(self, x: float, y: float, w: float, h: float, page_height: float) -> Tuple[float, float, float, float]:
        """
        Convert FreeCAD coordinates (bottom-left origin) to PDF coordinates (bottom-left origin).
        
        Args:
            x, y: FreeCAD position (mm from bottom-left)
            w, h: Width and height in mm
            page_height: Page height in points (from reportlab)
            
        Returns:
            (pdf_x, pdf_y, w_points, h_points) in PDF coordinates
        """
        modules = self._get_reportlab_modules()
        mm = modules["mm"]
        
        # FreeCAD y is from bottom, PDF y is also from bottom
        # But FreeCAD y represents bottom-left corner, we need to account for height
        pdf_x = x * mm
        pdf_y = page_height - (y * mm + h * mm)  # Flip: y + h gives top, subtract from page height
        pdf_w = w * mm
        pdf_h = h * mm
        
        return (pdf_x, pdf_y, pdf_w, pdf_h)
    
    def _draw_view_svgs(self, c: Any, page_size: Tuple[float, float],
                       view_svgs: List[Tuple[Optional[str], dict]]) -> Dict[str, int]:
        """
        Draw views by embedding SVG files using reportlab + svglib.
        If a view SVG is missing (None), draw a placeholder box instead.
        
        Args:
            c: PDF canvas
            page_size: Page size tuple (width, height) in points
            view_svgs: List of tuples (svg_path, view_info) where view_info contains:
                {x, y, w, h, name} - position and size in mm, and view name
        
        Returns:
            Dictionary with render statistics: {"rendered": int, "total": int, "placeholders": int}
        """
        modules = self._get_reportlab_modules()
        mm = modules["mm"]
        
        width, height = page_size
        
        # Try to import svglib for SVG rendering (lazy import)
        try:
            from svglib.svglib import svg2rlg
            from reportlab.graphics import renderPDF
            svglib_available = True
        except ImportError as e:
            svglib_available = False
            print(f"  [WARN] svglib not available ({e}), falling back to placeholder boxes")
        
        rendered_count = 0
        failed_count = 0
        
        for svg_path, view_info in view_svgs:
            x = view_info.get("x", 0.0)
            y = view_info.get("y", 0.0)
            w = view_info.get("w", 100.0)
            h = view_info.get("h", 100.0)
            view_name = view_info.get("name", "View")
            
            # Convert coordinates using helper
            pdf_x, pdf_y, pdf_w, pdf_h = self._to_pdf_rect(x, y, w, h, height)
            
            # Resolve SVG path to absolute if relative
            original_svg_path = svg_path
            if svg_path:
                if not os.path.isabs(svg_path):
                    # If relative path, make it absolute relative to current working directory
                    svg_path = os.path.abspath(svg_path)
            
            if svg_path and os.path.exists(svg_path) and os.path.getsize(svg_path) > 0 and svglib_available:
                try:
                    # Patch SVG to ensure it has explicit width/height dimensions
                    patched_svg_path = self._ensure_svg_has_dimensions(svg_path, pdf_w, pdf_h)
                    was_patched = patched_svg_path != svg_path
                    
                    # Load SVG and render to PDF using patched SVG
                    drawing = svg2rlg(patched_svg_path)
                    if drawing is None:
                        raise RuntimeError("svglib failed to parse SVG - returned None")
                    
                    # Get original SVG dimensions (in points)
                    if not hasattr(drawing, 'width') or not hasattr(drawing, 'height'):
                        raise RuntimeError("SVG drawing has no width/height attributes")
                    
                    svg_width = drawing.width
                    svg_height = drawing.height
                    
                    if svg_width <= 0 or svg_height <= 0:
                        raise RuntimeError(f"Invalid SVG dimensions: {svg_width}x{svg_height}")
                    
                    # Calculate scale to fit box (maintain aspect ratio)
                    scale_x = pdf_w / svg_width if svg_width > 0 else 1.0
                    scale_y = pdf_h / svg_height if svg_height > 0 else 1.0
                    scale = min(scale_x, scale_y)  # Fit inside box, maintain aspect ratio
                    
                    # Apply scaling
                    if abs(scale - 1.0) > 0.001:  # Only scale if significantly different
                        drawing.scale(scale, scale)
                        # After scaling, update dimensions
                        svg_width = drawing.width
                        svg_height = drawing.height
                    
                    # Calculate centered position within box
                    scaled_width = svg_width
                    scaled_height = svg_height
                    
                    offset_x = (pdf_w - scaled_width) / 2.0
                    offset_y = (pdf_h - scaled_height) / 2.0
                    
                    # Render SVG to PDF at calculated position
                    render_x = pdf_x + offset_x
                    render_y = pdf_y + offset_y
                    
                    renderPDF.draw(drawing, c, render_x, render_y)
                    
                    # Draw view label (small, top-left of view box)
                    c.setFont("Helvetica", 8)
                    c.drawString(pdf_x + 5, pdf_y + pdf_h - 15, f"{view_name}")
                    
                    patched_str = f" (patched={was_patched})" if was_patched else ""
                    print(f"  [OK] Rendered SVG for view '{view_name}'{patched_str} scale={scale:.3f} dims={svg_width:.1f}x{svg_height:.1f}pt")
                    
                    rendered_count += 1
                    
                    # Clean up patched SVG file if it was created (unless debugging)
                    keep_patched = os.getenv("CAD_KEEP_PATCHED_SVG", "false").lower() == "true"
                    if not keep_patched and was_patched and os.path.exists(patched_svg_path) and patched_svg_path != svg_path:
                        try:
                            os.remove(patched_svg_path)
                        except Exception:
                            pass  # Don't fail if cleanup fails
                    elif keep_patched and was_patched:
                        print(f"  [DEBUG] Kept patched SVG: {patched_svg_path}")
                    
                except Exception as e:
                    # If SVG rendering fails, fall back to placeholder box for this view only
                    error_msg = str(e)
                    print(f"  [WARN] Failed to render SVG for view '{view_name}': {error_msg[:100]}, using placeholder")
                    self._draw_view_placeholder(c, page_size, x, y, w, h, view_name, error_msg)
                    failed_count += 1
            else:
                # Draw placeholder box if SVG is missing or svglib unavailable
                if not svglib_available:
                    error_msg = "svglib not available"
                elif not svg_path:
                    error_msg = view_info.get("error", "SVG path is None")
                elif not os.path.exists(svg_path):
                    error_msg = f"SVG file not found: {os.path.basename(svg_path)}"
                else:
                    error_msg = "SVG file is empty"
                
                self._draw_view_placeholder(c, page_size, x, y, w, h, view_name, error_msg)
                failed_count += 1
        
        # Summary logging
        total_views = len(view_svgs)
        if rendered_count > 0:
            print(f"  [OK] PDF export Tier2: Rendered {rendered_count}/{total_views} SVG views successfully into PDF")
        if failed_count > 0:
            print(f"  [WARN] PDF export Tier2: {failed_count}/{total_views} views rendered as placeholders")
        
        # Return render statistics
        return {
            "rendered": rendered_count,
            "total": total_views,
            "placeholders": failed_count
        }
    
    def _draw_view_placeholder(self, c: Any, page_size: Tuple[float, float],
                              x: float, y: float, w: float, h: float, 
                              view_name: str, error_msg: str = ""):
        """
        Draw a placeholder box for a view when SVG is not available.
        
        Args:
            c: PDF canvas
            page_size: Page size tuple (width, height) in points
            x, y: View position in mm (FreeCAD coordinates, bottom-left origin)
            w, h: View width and height in mm
            view_name: Name of the view
            error_msg: Optional error message to display
        """
        width, height = page_size
        
        # Convert to PDF coordinates using helper
        pdf_x, pdf_y, pdf_w, pdf_h = self._to_pdf_rect(x, y, w, h, height)
        
        # Draw view border
        c.rect(pdf_x, pdf_y, pdf_w, pdf_h)
        
        # Draw view label (at top-left of box)
        c.setFont("Helvetica", 8)
        c.drawString(pdf_x + 5, pdf_y + pdf_h - 15, f"{view_name} (Placeholder)")
        
        # Draw error message if available
        if error_msg:
            c.setFont("Helvetica", 6)
            c.drawString(pdf_x + 5, pdf_y + pdf_h - 25, error_msg[:40])
    
    def _draw_views(self, c: Any, page_size: Tuple[float, float], 
                   views: List[Any]):
        """Draw view placeholders with labels."""
        modules = self._get_reportlab_modules()
        mm = modules["mm"]
        
        width, height = page_size
        
        for view in views:
            if isinstance(view, dict):
                view_name = view.get("name", "View")
                x, y = view.get("position", (0, 0))
                view_width = view.get("width", 100)
                view_height = view.get("height", 100)
                scale = view.get("scale", 1.0)
            else:
                # Handle ViewPlacement objects
                view_name = view.view.name if hasattr(view, 'view') else "View"
                x, y = view.position if hasattr(view, 'position') else (0, 0)
                view_width = view.width_mm if hasattr(view, 'width_mm') else 100
                view_height = view.height_mm if hasattr(view, 'height_mm') else 100
                scale = view.scale if hasattr(view, 'scale') else 1.0
            
            # Convert from bottom-left origin (FreeCAD) to top-left origin (PDF)
            # PDF coordinates: (0,0) is bottom-left
            pdf_y = height - y - view_height
            
            # Draw view border
            c.rect(x * mm, pdf_y, view_width * mm, view_height * mm)
            
            # Draw view label
            c.setFont("Helvetica", 8)
            c.drawString((x + 5) * mm, (pdf_y + view_height - 15) * mm, 
                        f"{view_name} (Scale: {scale:.2f})")
    
    def _draw_balloons(self, c: Any, page_size: Tuple[float, float],
                      balloons: List[Any]):
        """Draw balloons with item numbers."""
        modules = self._get_reportlab_modules()
        mm = modules["mm"]
        
        width, height = page_size
        
        for balloon in balloons:
            # Extract balloon data
            if isinstance(balloon, dict):
                item_num = balloon.get("item_number", "?")
                x, y = balloon.get("position", (0, 0))
                radius = balloon.get("radius", 5)
            else:
                # Handle Balloon objects
                item_num = balloon.item_number if hasattr(balloon, 'item_number') else "?"
                x, y = balloon.position if hasattr(balloon, 'position') else (0, 0)
                radius = balloon.style.circle_radius if (hasattr(balloon, 'style') and 
                        hasattr(balloon.style, 'circle_radius')) else 5
            
            # Convert coordinates
            pdf_y = height - y
            
            # Draw balloon circle
            c.circle(x * mm, pdf_y * mm, radius * mm)
            
            # Draw item number
            c.setFont("Helvetica-Bold", 10)
            text_width = c.stringWidth(str(item_num), "Helvetica-Bold", 10)
            c.drawString((x - text_width/2) * mm, (pdf_y - 3) * mm, str(item_num))
            
            # Draw leader line if available
            if isinstance(balloon, dict) and "leader" in balloon:
                leader = balloon["leader"]
                if leader and "start_point" in leader and "end_point" in leader:
                    start = leader["start_point"]
                    end = leader["end_point"]
                    c.line(start[0] * mm, (height - start[1]) * mm,
                          end[0] * mm, (height - end[1]) * mm)
            elif hasattr(balloon, 'leader') and balloon.leader:
                leader = balloon.leader
                if hasattr(leader, 'start_point') and hasattr(leader, 'end_point'):
                    start = leader.start_point
                    end = leader.end_point
                    c.line(start[0] * mm, (height - start[1]) * mm,
                          end[0] * mm, (height - end[1]) * mm)
    
    def _draw_bom_table(self, c: Any, page_size: Tuple[float, float],
                       bom_table: Any):
        """Draw BOM table with actual data."""
        modules = self._get_reportlab_modules()
        mm = modules["mm"]
        
        width, height = page_size
        
        # BOM position (bottom-left)
        bom_x = 10 * mm
        bom_y = 10 * mm
        bom_width = 150 * mm
        bom_height = 100 * mm
        
        # Extract BOM data
        if hasattr(bom_table, 'parts'):
            parts = bom_table.parts
            columns = bom_table.columns if hasattr(bom_table, 'columns') else ["Item", "Part", "Description", "Qty"]
        elif isinstance(bom_table, dict):
            parts = bom_table.get("rows", [])
            columns = bom_table.get("columns", ["Item", "Part", "Description", "Qty"])
        else:
            # Fallback
            self._draw_bom_placeholder(c, page_size)
            return
        
        # Draw table border
        c.rect(bom_x, bom_y, bom_width, bom_height)
        
        # Draw header
        c.setFont("Helvetica-Bold", 9)
        c.drawString(bom_x + 5 * mm, bom_y + bom_height - 15 * mm, "Bill of Materials")
        
        # Draw column headers
        c.setFont("Helvetica", 7)
        col_width = bom_width / len(columns)
        for i, col in enumerate(columns):
            c.drawString(bom_x + (i * col_width + 2) * mm, 
                        bom_y + bom_height - 25 * mm, col)
        
        # Draw parts (limit to fit in table)
        max_rows = min(len(parts), int((bom_height - 30) / 8))
        c.setFont("Helvetica", 6)
        for i, part in enumerate(parts[:max_rows]):
            y_pos = bom_y + bom_height - 35 - (i * 8) * mm
            
            # Extract part data
            if isinstance(part, dict):
                item = part.get("item", part.get("item_number", ""))
                part_num = part.get("part_number", part.get("part_id", ""))
                desc = part.get("description", part.get("name", ""))
                qty = part.get("quantity", part.get("qty", ""))
            else:
                item = getattr(part, 'item_number', '')
                part_num = getattr(part, 'part_id', '')
                desc = getattr(part, 'name', '')
                qty = getattr(part, 'quantity', '')
            
            # Draw row
            c.drawString(bom_x + 2 * mm, y_pos, str(item))
            c.drawString(bom_x + col_width * mm, y_pos, str(part_num)[:15])
            c.drawString(bom_x + 2 * col_width * mm, y_pos, str(desc)[:20])
            c.drawString(bom_x + 3 * col_width * mm, y_pos, str(qty))
        
        if len(parts) > max_rows:
            c.drawString(bom_x + 2 * mm, bom_y + 5 * mm, 
                        f"... and {len(parts) - max_rows} more items")
    
    def _draw_bom_placeholder(self, c: Any, page_size: Tuple[float, float]):
        """Draw BOM table placeholder."""
        modules = self._get_reportlab_modules()
        mm = modules["mm"]
        
        width, height = page_size
        
        # BOM in bottom-left corner
        bom_x = 10 * mm
        bom_y = 10 * mm
        
        # Draw border
        c.rect(bom_x, bom_y, 150 * mm, 100 * mm)
        c.drawString(bom_x + 5 * mm, bom_y + 85 * mm, "Bill of Materials")
        c.drawString(bom_x + 5 * mm, bom_y + 70 * mm, "(Placeholder - Phase 3)")
