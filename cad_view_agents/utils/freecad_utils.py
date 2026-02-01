"""
FreeCAD helper utilities.
"""
import FreeCAD


def is_techdraw_available() -> bool:
    """Check if TechDraw module is available."""
    try:
        import TechDraw
        return True
    except ImportError:
        return False


def get_all_shapes(doc):
    """Get all objects with shapes from a FreeCAD document."""
    if doc is None:
        return []
    return [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape is not None]


def get_assembly_bbox(doc):
    """Get combined bounding box of all shapes in document."""
    objs = get_all_shapes(doc)
    if not objs:
        return None
    
    bbox = objs[0].Shape.BoundBox
    for obj in objs[1:]:
        if hasattr(obj, "Shape") and hasattr(obj.Shape, "BoundBox"):
            bbox.add(obj.Shape.BoundBox)
    
    return bbox
