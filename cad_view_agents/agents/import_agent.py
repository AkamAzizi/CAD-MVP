import FreeCAD
import Import

def run(step_path: str):
    """Import STEP file and return document with metadata."""
    doc = FreeCAD.newDocument("Model")
    Import.insert(step_path, doc.Name)
    doc.recompute()
    
    objs = [o for o in doc.Objects if hasattr(o, "Shape")]
    parts_count = len(objs)
    
    # Calculate bounding box for all objects combined
    bbox = None
    if objs:
        # Get the first object's bbox as starting point
        bbox = objs[0].Shape.BoundBox
        # Expand to include all objects
        for obj in objs[1:]:
            if hasattr(obj, "Shape") and hasattr(obj.Shape, "BoundBox"):
                obj_bbox = obj.Shape.BoundBox
                bbox.add(obj_bbox)
    
    # Validate and extract bounding box dimensions
    bbox_dict = None
    if bbox:
        x_len = bbox.XLength
        y_len = bbox.YLength
        z_len = bbox.ZLength
        
        # Validate bounding box values are realistic (not invalid like 2e+100)
        # Typical CAD models are between 0.001mm and 1000m (1e6mm)
        MAX_REALISTIC_SIZE = 1e6  # 1000 meters in mm
        MIN_REALISTIC_SIZE = 1e-3  # 0.001 mm
        
        if (MIN_REALISTIC_SIZE <= x_len <= MAX_REALISTIC_SIZE and
            MIN_REALISTIC_SIZE <= y_len <= MAX_REALISTIC_SIZE and
            MIN_REALISTIC_SIZE <= z_len <= MAX_REALISTIC_SIZE):
            bbox_dict = {
                "x": x_len,
                "y": y_len,
                "z": z_len
            }
        else:
            # Invalid bbox - calculate from individual object bounds
            # This is a fallback for corrupted geometry
            print(f"Warning: Invalid bounding box detected ({x_len}, {y_len}, {z_len}). Recalculating from individual objects.")
            min_x = min_y = min_z = float('inf')
            max_x = max_y = max_z = float('-inf')
            
            for obj in objs:
                if hasattr(obj, "Shape") and hasattr(obj.Shape, "BoundBox"):
                    obj_bbox = obj.Shape.BoundBox
                    min_x = min(min_x, obj_bbox.XMin)
                    min_y = min(min_y, obj_bbox.YMin)
                    min_z = min(min_z, obj_bbox.ZMin)
                    max_x = max(max_x, obj_bbox.XMax)
                    max_y = max(max_y, obj_bbox.YMax)
                    max_z = max(max_z, obj_bbox.ZMax)
            
            if (min_x != float('inf') and 
                MIN_REALISTIC_SIZE <= (max_x - min_x) <= MAX_REALISTIC_SIZE and
                MIN_REALISTIC_SIZE <= (max_y - min_y) <= MAX_REALISTIC_SIZE and
                MIN_REALISTIC_SIZE <= (max_z - min_z) <= MAX_REALISTIC_SIZE):
                bbox_dict = {
                    "x": max_x - min_x,
                    "y": max_y - min_y,
                    "z": max_z - min_z
                }
            else:
                print("Warning: Could not calculate valid bounding box. Using None.")
    
    return {
        "doc": doc,
        "parts_count": parts_count,
        "bbox": bbox_dict
    }
