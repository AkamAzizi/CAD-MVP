"""
View candidate generation for CAD assemblies.
Generates standard orthographic, isometric, and section view candidates.
"""
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class ViewCandidate:
    """Represents a candidate view for the technical drawing."""
    name: str
    direction: Tuple[float, float, float]  # 3D direction vector
    type: str  # "orthographic", "isometric", "section"
    description: str = ""


class ViewCandidateGenerator:
    """Generates view candidates for CAD assemblies."""
    
    # Standard orthographic view directions (normalized)
    ORTHOGRAPHIC_VIEWS = {
        "front": (0, 0, 1),      # Looking along +Z
        "back": (0, 0, -1),      # Looking along -Z
        "top": (0, 1, 0),        # Looking along +Y
        "bottom": (0, -1, 0),     # Looking along -Y
        "right": (1, 0, 0),      # Looking along +X
        "left": (-1, 0, 0),      # Looking along -X
    }
    
    # Standard isometric view directions (normalized)
    ISOMETRIC_VIEWS = {
        "iso_top_right": (1, 1, 1),
        "iso_top_left": (-1, 1, 1),
        "iso_bottom_right": (1, -1, 1),
        "iso_bottom_left": (-1, -1, 1),
    }
    
    @staticmethod
    def generate_orthographic_views(bbox: dict = None, primary_axis: str = None) -> List[ViewCandidate]:
        """
        Generate standard orthographic view candidates.
        
        Args:
            bbox: Bounding box dict with x, y, z dimensions
            primary_axis: Primary axis ("x", "y", "z") for prioritization
            
        Returns:
            List of ViewCandidate objects
        """
        candidates = []
        
        for name, direction in ViewCandidateGenerator.ORTHOGRAPHIC_VIEWS.items():
            candidates.append(ViewCandidate(
                name=name,
                direction=direction,
                type="orthographic",
                description=f"Standard {name} view"
            ))
        
        return candidates
    
    @staticmethod
    def generate_isometric_views() -> List[ViewCandidate]:
        """
        Generate isometric view candidates.
        
        Returns:
            List of ViewCandidate objects
        """
        candidates = []
        
        for name, direction in ViewCandidateGenerator.ISOMETRIC_VIEWS.items():
            candidates.append(ViewCandidate(
                name=name,
                direction=direction,
                type="isometric",
                description=f"Isometric view: {name}"
            ))
        
        # Add standard isometric (most common)
        candidates.append(ViewCandidate(
            name="iso",
            direction=(1, 1, 1),
            type="isometric",
            description="Standard isometric view"
        ))
        
        return candidates
    
    @staticmethod
    def generate_section_views(assembly, bbox: dict = None) -> List[ViewCandidate]:
        """
        Generate section view candidates (for future use).
        MVP: Returns empty list, section views in v2.
        
        Args:
            assembly: Assembly data
            bbox: Bounding box
            
        Returns:
            List of ViewCandidate objects (empty for MVP)
        """
        # Section views will be implemented in v2
        return []
    
    @staticmethod
    def generate_all_candidates(bbox: dict = None, primary_axis: str = None) -> List[ViewCandidate]:
        """
        Generate all view candidates (orthographic + isometric).
        
        Args:
            bbox: Bounding box dict
            primary_axis: Primary axis for prioritization
            
        Returns:
            List of all ViewCandidate objects
        """
        candidates = []
        
        # Add orthographic views
        candidates.extend(ViewCandidateGenerator.generate_orthographic_views(bbox, primary_axis))
        
        # Add isometric views
        candidates.extend(ViewCandidateGenerator.generate_isometric_views())
        
        # Section views (empty for MVP)
        # candidates.extend(ViewCandidateGenerator.generate_section_views(None, bbox))
        
        return candidates
    
    @staticmethod
    def normalize_direction(direction: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        Normalize a direction vector to unit length.
        
        Args:
            direction: 3D direction vector
            
        Returns:
            Normalized direction vector
        """
        x, y, z = direction
        length = (x**2 + y**2 + z**2) ** 0.5
        if length == 0:
            return (0, 0, 1)  # Default to front view
        return (x / length, y / length, z / length)
