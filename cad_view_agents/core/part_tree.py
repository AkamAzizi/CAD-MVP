"""
Part tree construction with stable part ID generation.
Provides deterministic part identification for ballooning and BOM generation.
"""
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class PartNode:
    """Represents a single part or subassembly in the assembly tree."""
    id: str
    name: str
    geometry_hash: str
    freecad_obj: Optional[object] = None  # Reference to FreeCAD object
    children: List['PartNode'] = field(default_factory=list)
    parent: Optional['PartNode'] = None
    metadata: Dict = field(default_factory=dict)


class PartTree:
    """Manages the assembly part tree with stable IDs."""
    
    def __init__(self):
        self.root: Optional[PartNode] = None
        self.parts: List[PartNode] = []
        self._id_map: Dict[str, PartNode] = {}  # Map stable_id -> PartNode
    
    @staticmethod
    def build_tree(doc) -> 'PartTree':
        """
        Build part tree from FreeCAD document.
        
        Args:
            doc: FreeCAD document object
            
        Returns:
            PartTree instance with all parts organized
        """
        tree = PartTree()
        
        # Get all objects with shapes
        objs = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape is not None]
        
        if not objs:
            return tree
        
        # Create root node
        tree.root = PartNode(
            id="ROOT",
            name="Assembly",
            geometry_hash="",
            freecad_obj=None
        )
        
        # Process each object
        for obj in objs:
            stable_id = PartTree.get_stable_id(obj)
            geometry_hash = PartTree.get_geometry_hash(obj)
            
            # Extract name from object
            name = obj.Label if hasattr(obj, "Label") else obj.Name if hasattr(obj, "Name") else f"Part_{len(tree.parts) + 1}"
            
            # Create part node
            part_node = PartNode(
                id=stable_id,
                name=name,
                geometry_hash=geometry_hash,
                freecad_obj=obj,
                parent=tree.root
            )
            
            # Extract metadata if available
            if hasattr(obj, "Material"):
                part_node.metadata["material"] = str(obj.Material)
            if hasattr(obj, "Label"):
                part_node.metadata["label"] = obj.Label
            
            tree.parts.append(part_node)
            tree.root.children.append(part_node)
            tree._id_map[stable_id] = part_node
        
        return tree
    
    @staticmethod
    def get_stable_id(part_obj) -> str:
        """
        Generate stable, deterministic ID for a part.
        Uses geometry hash to ensure same part gets same ID across runs.
        
        Args:
            part_obj: FreeCAD object with Shape
            
        Returns:
            Stable ID string (e.g., "PART_12345")
        """
        if not hasattr(part_obj, "Shape") or part_obj.Shape is None:
            # Fallback to object name/index
            obj_name = part_obj.Name if hasattr(part_obj, "Name") else str(id(part_obj))
            return f"PART_{abs(hash(obj_name)) % 100000}"
        
        # Use geometry hash for stability
        geometry_hash = PartTree.get_geometry_hash(part_obj)
        return f"PART_{abs(int(geometry_hash, 16)) % 100000}"
    
    @staticmethod
    def get_geometry_hash(part_obj) -> str:
        """
        Generate hash from part geometry for stable identification.
        
        Args:
            part_obj: FreeCAD object with Shape
            
        Returns:
            Hexadecimal hash string
        """
        if not hasattr(part_obj, "Shape") or part_obj.Shape is None:
            return "0"
        
        try:
            bbox = part_obj.Shape.BoundBox
            
            # Create hash from bounding box and volume
            # This is deterministic and stable for same geometry
            hash_input = f"{bbox.XMin:.6f},{bbox.YMin:.6f},{bbox.ZMin:.6f}," \
                        f"{bbox.XMax:.6f},{bbox.YMax:.6f},{bbox.ZMax:.6f}"
            
            # Add volume if available
            try:
                volume = part_obj.Shape.Volume
                hash_input += f",{volume:.6f}"
            except:
                pass
            
            # Add face count for additional uniqueness
            try:
                face_count = len(part_obj.Shape.Faces)
                hash_input += f",{face_count}"
            except:
                pass
            
            # Generate MD5 hash
            hash_obj = hashlib.md5(hash_input.encode())
            return hash_obj.hexdigest()
        except Exception as e:
            # Fallback to object name hash
            obj_name = part_obj.Name if hasattr(part_obj, "Name") else str(id(part_obj))
            hash_obj = hashlib.md5(obj_name.encode())
            return hash_obj.hexdigest()
    
    def get_part_list(self) -> List[PartNode]:
        """
        Get flat list of all parts (excluding root).
        
        Returns:
            List of PartNode objects
        """
        return self.parts.copy()
    
    def get_part_by_id(self, part_id: str) -> Optional[PartNode]:
        """
        Get part node by stable ID.
        
        Args:
            part_id: Stable part ID
            
        Returns:
            PartNode or None if not found
        """
        return self._id_map.get(part_id)
    
    def get_part_count(self) -> int:
        """Get total number of parts."""
        return len(self.parts)
