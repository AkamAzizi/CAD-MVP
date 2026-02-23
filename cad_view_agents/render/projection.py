"""
Projection utilities for 2D drawing generation.
Handles STEP import, PartShape mapping, and 2D projection.
"""
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
import math


@dataclass
class PartShape:
    """Maps BOM part to geometry for balloon anchoring."""
    part_id: str  # Stable ID from snapshot/BOM (must match snapshot mapping, never re-infer)
    shape: Any    # OCCT TopoDS_Shape
    bbox: Tuple[float, float, float, float, float, float]  # 3D bbox: xmin, ymin, zmin, xmax, ymax, zmax
    centroid: Tuple[float, float, float]  # 3D centroid (x, y, z)


@dataclass
class ProjectedView:
    """Represents a projected 2D view."""
    view_name: str
    edges_2d: List[List[Tuple[float, float]]]  # List of polylines (each polyline is list of (x, y) points)
    part_projections: Dict[str, Dict[str, Any]]  # part_id -> {centroid_2d: (x, y), bbox_2d: (xmin, ymin, xmax, ymax)}


def normalize_vector(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Normalize a 3D vector."""
    length = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if length == 0:
        return (0, 0, 1)  # Default to +Z
    return (v[0] / length, v[1] / length, v[2] / length)


def compute_projection_transform(view_direction: Tuple[float, float, float]) -> Dict[str, Any]:
    """
    Compute orthonormal basis (u, v) for 2D projection from view direction.
    
    Builds robust orthonormal basis:
    - Choose up vector not parallel to view_dir
    - u = normalize(cross(up, dir))
    - v = cross(dir, u)
    
    Args:
        view_direction: View direction vector (will be normalized)
        
    Returns:
        Dictionary with:
        - view_direction: Normalized view direction
        - u: X-axis basis vector (normalized)
        - v: Y-axis basis vector (normalized)
    """
    # Normalize view direction
    dir_vec = normalize_vector(view_direction)
    dx, dy, dz = dir_vec
    
    # Choose up vector not parallel to view_dir
    # If |dot(dir, (0,0,1))| > 0.95, use (0,1,0) as up
    dot_with_z = abs(dz)
    if dot_with_z > 0.95:
        up_vec = (0.0, 1.0, 0.0)
    else:
        up_vec = (0.0, 0.0, 1.0)
    
    # Compute u = normalize(cross(up, dir))
    up_x, up_y, up_z = up_vec
    u_x = up_y * dz - up_z * dy
    u_y = up_z * dx - up_x * dz
    u_z = up_x * dy - up_y * dx
    u_len = math.sqrt(u_x**2 + u_y**2 + u_z**2)
    
    if u_len < 1e-6:
        # Up vector is parallel to dir, try alternative
        if dot_with_z > 0.95:
            up_vec = (1.0, 0.0, 0.0)
        else:
            up_vec = (0.0, 0.0, 1.0)
        up_x, up_y, up_z = up_vec
        u_x = up_y * dz - up_z * dy
        u_y = up_z * dx - up_x * dz
        u_z = up_x * dy - up_y * dx
        u_len = math.sqrt(u_x**2 + u_y**2 + u_z**2)
    
    if u_len < 1e-6:
        # Still degenerate, use default
        u_vec = (1.0, 0.0, 0.0)
    else:
        u_vec = (u_x / u_len, u_y / u_len, u_z / u_len)
    
    # Compute v = cross(dir, u)
    v_x = dy * u_vec[2] - dz * u_vec[1]
    v_y = dz * u_vec[0] - dx * u_vec[2]
    v_z = dx * u_vec[1] - dy * u_vec[0]
    v_len = math.sqrt(v_x**2 + v_y**2 + v_z**2)
    
    if v_len < 1e-6:
        v_vec = (0.0, 1.0, 0.0)
    else:
        v_vec = (v_x / v_len, v_y / v_len, v_z / v_len)
    
    return {
        "view_direction": dir_vec,
        "u": u_vec,
        "v": v_vec
    }


def project_shape_to_2d(part_shape: PartShape, 
                        view_direction: Tuple[float, float, float],
                        transform: Any) -> Dict[str, Any]:
    """
    Project a 3D shape to 2D using pure wireframe projection.
    
    For each edge in the OCCT shape:
    - Sample the edge into ~30 points
    - Project each point to 2D using the view transform
    - Create a polyline from the projected points
    - Add to the view geometry list
    
    Args:
        part_shape: PartShape with 3D geometry
        view_direction: View direction vector
        transform: Transformation matrix from compute_projection_transform
        
    Returns:
        Dictionary with:
        - edges_2d: List of polylines (list of (x, y) points)
        - centroid_2d: (x, y) projected centroid
        - bbox_2d: (xmin, ymin, xmax, ymax) projected bbox
    """
    try:
        import cadquery as cq
        
        # Project centroid
        centroid_3d = part_shape.centroid
        centroid_2d = _project_point_3d_to_2d(centroid_3d, view_direction, transform)
        
        # Project bbox
        bbox_3d = part_shape.bbox
        bbox_2d = _project_bbox_3d_to_2d(bbox_3d, view_direction, transform)
        
        # Pure wireframe projection: extract all edges and project them
        edges_2d = []
        shape = part_shape.shape
        
        try:
            # Get all edges from shape
            if hasattr(shape, 'Edges'):
                # OCCT shape has Edges() method
                edges = shape.Edges()
            elif hasattr(shape, 'edges'):
                # Alternative access
                edges = shape.edges()
            else:
                # Try to get edges via CADQuery wrapper
                if hasattr(shape, 'val'):
                    # Workplane case
                    edges = shape.val().Edges() if hasattr(shape.val(), 'Edges') else []
                else:
                    edges = []
            
            # Pure wireframe: Project each edge to 2D
            edge_idx = 0
            for edge in edges:
                try:
                    # Sample edge into ~30 points
                    edge_points_3d = _sample_edge_points(edge, num_points=30, transform=transform)
                    
                    # Project each point to 2D using view transform
                    edge_points_2d = [_project_point_3d_to_2d(p, view_direction, transform) for p in edge_points_3d]
                    
                    # Debug dump of first 5 points for first edge
                    if edge_idx == 0 and len(edge_points_3d) > 0:
                        print(f"  [DEBUG] First edge sample (first 5 points):")
                        for i in range(min(5, len(edge_points_3d))):
                            p3d = edge_points_3d[i]
                            p2d = edge_points_2d[i] if i < len(edge_points_2d) else (0, 0)
                            print(f"    Point {i}: 3D=({p3d[0]:.3f}, {p3d[1]:.3f}, {p3d[2]:.3f}) -> 2D=({p2d[0]:.3f}, {p2d[1]:.3f})")
                    
                    # Create polyline from projected points (must have at least 2 points)
                    if len(edge_points_2d) >= 2:
                        edges_2d.append(edge_points_2d)
                    edge_idx += 1
                except Exception as e:
                    # Skip edge if projection fails
                    continue
            
        # Count total segments
        total_segments = sum(max(0, len(polyline) - 1) for polyline in edges_2d)
        
        # Check for degeneracy in projected bounds
        if edges_2d:
            all_x = []
            all_y = []
            for polyline in edges_2d:
                for p in polyline:
                    all_x.append(p[0])
                    all_y.append(p[1])
            
            if all_x and all_y:
                xmin_proj, xmax_proj = min(all_x), max(all_x)
                ymin_proj, ymax_proj = min(all_y), max(all_y)
                
                if (xmax_proj - xmin_proj) < 1e-6 or (ymax_proj - ymin_proj) < 1e-6:
                    print(f"  [ERROR] Projection degeneracy for part {part_shape.part_id}: x_range={xmax_proj-xmin_proj:.2e}, y_range={ymax_proj-ymin_proj:.2e}")
                    # Recompute transform with alternative up vector
                    dir_vec = normalize_vector(view_direction)
                    if abs(dir_vec[2]) > 0.95:
                        up_vec = (1.0, 0.0, 0.0)
                    else:
                        up_vec = (0.0, 1.0, 0.0)
                    
                    # Recompute basis (same logic as compute_projection_transform)
                    dx, dy, dz = dir_vec
                    up_x, up_y, up_z = up_vec
                    u_x = up_y * dz - up_z * dy
                    u_y = up_z * dx - up_x * dz
                    u_z = up_x * dy - up_y * dx
                    u_len = math.sqrt(u_x**2 + u_y**2 + u_z**2)
                    if u_len > 1e-6:
                        u_vec = (u_x / u_len, u_y / u_len, u_z / u_len)
                        v_x = dy * u_vec[2] - dz * u_vec[1]
                        v_y = dz * u_vec[0] - dx * u_vec[2]
                        v_z = dx * u_vec[1] - dy * u_vec[0]
                        v_len = math.sqrt(v_x**2 + v_y**2 + v_z**2)
                        if v_len > 1e-6:
                            v_vec = (v_x / v_len, v_y / v_len, v_z / v_len)
                            transform = {"u": u_vec, "v": v_vec, "view_direction": dir_vec}
                            # Retry projection with new transform
                            edges_2d = []
                            for edge in edges:
                                try:
                                    edge_points_3d = _sample_edge_points(edge, num_points=30, transform=transform)
                                    edge_points_2d = [_project_point_3d_to_2d(p, view_direction, transform) for p in edge_points_3d]
                                    if len(edge_points_2d) >= 2:
                                        edges_2d.append(edge_points_2d)
                                except Exception:
                                    continue
                            total_segments = sum(max(0, len(polyline) - 1) for polyline in edges_2d)
        
        # Warn if segment count is too low (likely projection failure)
        if total_segments < 100:
            print(f"  [WARN] Projection likely failed: only {total_segments} segments for part {part_shape.part_id}")
                    
        except Exception as e:
            # If edge extraction fails, use bbox outline as fallback
            print(f"  [WARN] Edge extraction failed for part {part_shape.part_id}: {e}, using bbox outline")
            xmin, ymin, xmax, ymax = bbox_2d
            edges_2d = [
                [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)]
            ]
        
        return {
            "edges_2d": edges_2d,
            "centroid_2d": centroid_2d,
            "bbox_2d": bbox_2d
        }
        
    except Exception as e:
        # Fallback: use bbox outline
        print(f"  [WARN] Projection failed for part {part_shape.part_id}: {e}, using bbox outline")
        bbox_3d = part_shape.bbox
        bbox_2d = _project_bbox_3d_to_2d(bbox_3d, view_direction, transform)
        centroid_2d = _project_point_3d_to_2d(part_shape.centroid, view_direction, transform)
        
        xmin, ymin, xmax, ymax = bbox_2d
        edges_2d = [
            [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)]
        ]
        
        return {
            "edges_2d": edges_2d,
            "centroid_2d": centroid_2d,
            "bbox_2d": bbox_2d
        }


def _sample_edge_points(edge: Any, num_points: int = 20) -> List[Tuple[float, float, float]]:
    """
    Sample points along an edge.
    
    For MVP, this is a simplified version that tries to extract edge vertices.
    """
    points = []
    try:
        # Try to get start and end vertices
        if hasattr(edge, 'firstVertex'):
            v1 = edge.firstVertex()
            if hasattr(v1, 'Point'):
                p1 = v1.Point()
                points.append((p1.X(), p1.Y(), p1.Z()))
        
        if hasattr(edge, 'lastVertex'):
            v2 = edge.lastVertex()
            if hasattr(v2, 'Point'):
                p2 = v2.Point()
                points.append((p2.X(), p2.Y(), p2.Z()))
        
        # If we only got 2 points, interpolate
        if len(points) == 2:
            p1, p2 = points
            for i in range(1, num_points - 1):
                t = i / (num_points - 1)
                x = p1[0] + t * (p2[0] - p1[0])
                y = p1[1] + t * (p2[1] - p1[1])
                z = p1[2] + t * (p2[2] - p1[2])
                points.insert(-1, (x, y, z))
    except Exception:
        # Fallback: return empty list
        pass
    
    return points if points else [(0, 0, 0), (100, 0, 0)]


def _project_point_3d_to_2d(point_3d: Tuple[float, float, float], 
                            view_direction: Tuple[float, float, float],
                            transform: Optional[Dict[str, Any]] = None) -> Tuple[float, float]:
    """
    Project a 3D point to 2D plane using orthonormal basis.
    
    Uses: x = dot(p, u), y = dot(p, v)
    where u and v are the basis vectors from transform.
    
    Args:
        point_3d: 3D point (x, y, z)
        view_direction: View direction vector (for backward compatibility)
        transform: Transform dictionary with 'u' and 'v' basis vectors
        
    Returns:
        (x, y) projected 2D point
    """
    px, py, pz = point_3d
    
    # If transform provided, use orthonormal basis
    if transform and 'u' in transform and 'v' in transform:
        u = transform['u']
        v = transform['v']
        x = px * u[0] + py * u[1] + pz * u[2]
        y = px * v[0] + py * v[1] + pz * v[2]
        return (x, y)
    
    # Fallback: simple coordinate dropping (for backward compatibility)
    v = normalize_vector(view_direction)
    abs_v = (abs(v[0]), abs(v[1]), abs(v[2]))
    max_idx = abs_v.index(max(abs_v))
    
    if max_idx == 0:  # X is dominant (right/left view)
        return (py, pz)  # Drop X, use Y, Z
    elif max_idx == 1:  # Y is dominant (top/bottom view)
        return (px, pz)  # Drop Y, use X, Z
    else:  # Z is dominant (front/back view)
        return (px, py)  # Drop Z, use X, Y


def _project_bbox_3d_to_2d(bbox_3d: Tuple[float, float, float, float, float, float],
                           view_direction: Tuple[float, float, float],
                           transform: Optional[Dict[str, Any]] = None) -> Tuple[float, float, float, float]:
    """
    Project a 3D bounding box to 2D.
    
    Returns: (xmin, ymin, xmax, ymax)
    """
    xmin, ymin, zmin, xmax, ymax, zmax = bbox_3d
    
    # Project all 8 corners of the bbox
    corners_3d = [
        (xmin, ymin, zmin), (xmax, ymin, zmin),
        (xmin, ymax, zmin), (xmax, ymax, zmin),
        (xmin, ymin, zmax), (xmax, ymin, zmax),
        (xmin, ymax, zmax), (xmax, ymax, zmax),
    ]
    
    corners_2d = [_project_point_3d_to_2d(c, view_direction, transform) for c in corners_3d]
    
    # Find min/max in 2D
    x_coords = [c[0] for c in corners_2d]
    y_coords = [c[1] for c in corners_2d]
    
    xmin_2d, xmax_2d = min(x_coords), max(x_coords)
    ymin_2d, ymax_2d = min(y_coords), max(y_coords)
    
    # Check for degeneracy
    if (xmax_2d - xmin_2d) < 1e-6 or (ymax_2d - ymin_2d) < 1e-6:
        print(f"  [ERROR] Projection degeneracy detected: x_range={xmax_2d-xmin_2d:.2e}, y_range={ymax_2d-ymin_2d:.2e}")
        # Try alternative up vector
        if transform:
            # Recompute with different up vector
            dir_vec = normalize_vector(view_direction)
            if abs(dir_vec[2]) > 0.95:
                # Try (1,0,0) as up
                up_vec = (1.0, 0.0, 0.0)
            else:
                # Try (0,1,0) as up
                up_vec = (0.0, 1.0, 0.0)
            
            # Recompute basis
            dx, dy, dz = dir_vec
            up_x, up_y, up_z = up_vec
            u_x = up_y * dz - up_z * dy
            u_y = up_z * dx - up_x * dz
            u_z = up_x * dy - up_y * dx
            u_len = math.sqrt(u_x**2 + u_y**2 + u_z**2)
            if u_len > 1e-6:
                u_vec = (u_x / u_len, u_y / u_len, u_z / u_len)
                v_x = dy * u_vec[2] - dz * u_vec[1]
                v_y = dz * u_vec[0] - dx * u_vec[2]
                v_z = dx * u_vec[1] - dy * u_vec[0]
                v_len = math.sqrt(v_x**2 + v_y**2 + v_z**2)
                if v_len > 1e-6:
                    v_vec = (v_x / v_len, v_y / v_len, v_z / v_len)
                    transform = {"u": u_vec, "v": v_vec}
                    # Retry projection
                    corners_2d = [_project_point_3d_to_2d(c, view_direction, transform) for c in corners_3d]
                    x_coords = [c[0] for c in corners_2d]
                    y_coords = [c[1] for c in corners_2d]
                    xmin_2d, xmax_2d = min(x_coords), max(x_coords)
                    ymin_2d, ymax_2d = min(y_coords), max(y_coords)
    
    return (xmin_2d, ymin_2d, xmax_2d, ymax_2d)


def import_step_file(step_path: str, part_id_mapping: Dict[str, str]) -> List[PartShape]:
    """
    Import STEP file and create PartShape list with stable part_id mapping.
    
    Args:
        step_path: Path to STEP file
        part_id_mapping: Dictionary mapping part labels/names to stable part_ids from snapshot
        
    Returns:
        List of PartShape objects
    """
    try:
        import cadquery as cq
        
        # Import STEP file
        # CADQuery's importStep returns a Workplane or Compound
        imported = cq.importers.importStep(step_path)
        
        # Extract shapes from imported geometry
        # For MVP, we'll handle the case where imported is a single shape or compound
        part_shapes = []
        
        # Get the underlying OCCT shape
        if hasattr(imported, 'val'):
            # Workplane case
            shape = imported.val()
        else:
            # Direct shape case
            shape = imported
        
        # For MVP, we'll create a single PartShape for the entire assembly
        # In v2, we'll properly extract individual parts
        
        # Compute bbox and centroid
        bbox = _compute_shape_bbox(shape)
        centroid = _compute_shape_centroid(shape)
        
        # Use first part_id from mapping, or generate a default
        part_id = list(part_id_mapping.values())[0] if part_id_mapping else "PART_0"
        
        part_shapes.append(PartShape(
            part_id=part_id,
            shape=shape,
            bbox=bbox,
            centroid=centroid
        ))
        
        return part_shapes
        
    except Exception as e:
        raise RuntimeError(f"Failed to import STEP file: {e}") from e


def _compute_shape_bbox(shape: Any) -> Tuple[float, float, float, float, float, float]:
    """Compute 3D bounding box of an OCCT shape."""
    try:
        import cadquery as cq
        
        # Access OCCT Bnd_Box through CADQuery/OCCT API
        if hasattr(shape, 'BoundingBox'):
            bbox = shape.BoundingBox()
            return (bbox.xmin, bbox.ymin, bbox.zmin, bbox.xmax, bbox.ymax, bbox.zmax)
        elif hasattr(shape, 'val'):
            # Workplane case
            bbox = shape.val().BoundingBox()
            return (bbox.xmin, bbox.ymin, bbox.zmin, bbox.xmax, bbox.ymax, bbox.zmax)
        else:
            # Try OCCT directly
            try:
                from OCP.Bnd import Bnd_Box
                from OCP.BRepBndLib import BRepBndLib
                bbox = Bnd_Box()
                BRepBndLib.Add_s(shape, bbox)
                return (bbox.XMin(), bbox.YMin(), bbox.ZMin(), bbox.XMax(), bbox.YMax(), bbox.ZMax())
            except Exception:
                pass
        
        # Fallback
        return (0.0, 0.0, 0.0, 100.0, 100.0, 100.0)
    except Exception:
        return (0.0, 0.0, 0.0, 100.0, 100.0, 100.0)


def _compute_shape_centroid(shape: Any) -> Tuple[float, float, float]:
    """Compute 3D centroid of an OCCT shape."""
    try:
        import cadquery as cq
        
        # Access OCCT center of mass through CADQuery/OCCT API
        if hasattr(shape, 'Center'):
            center = shape.Center()
            return (center.x, center.y, center.z)
        elif hasattr(shape, 'val'):
            # Workplane case
            center = shape.val().Center()
            return (center.x, center.y, center.z)
        else:
            # Try OCCT directly
            try:
                from OCP.GProp import GProp_GProps
                from OCP.BRepGProp import BRepGProp
                props = GProp_GProps()
                BRepGProp.VolumeProperties_s(shape, props)
                center = props.CentreOfMass()
                return (center.X(), center.Y(), center.Z())
            except Exception:
                pass
        
        # Fallback: use center of bbox
        bbox = _compute_shape_bbox(shape)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox
        return ((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)
    except Exception:
        return (50.0, 50.0, 50.0)
