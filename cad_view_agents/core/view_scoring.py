"""
Deterministic view scoring for CAD view candidates.
Scores views based on visibility, information density, and symmetry.
"""
from typing import List
from .view_candidates import ViewCandidate


class ViewScorer:
    """Scores view candidates using deterministic metrics."""
    
    def __init__(self):
        self.weights = {
            "visibility": 0.4,
            "information_density": 0.4,
            "symmetry": 0.2
        }
    
    def score_visibility(self, view_candidate: ViewCandidate, doc) -> float:
        """
        Score view based on feature visibility.
        Higher score = more visible features.
        
        Args:
            view_candidate: ViewCandidate to score
            doc: FreeCAD document
            
        Returns:
            Score between 0.0 and 1.0
        """
        if doc is None:
            return 0.5  # Default score if no document
        
        try:
            # Get all objects with shapes
            objs = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape is not None]
            
            if not objs:
                return 0.0
            
            # Count visible features (edges, faces)
            # This is a simplified heuristic - in a full implementation,
            # we would project the geometry and count visible elements
            total_features = 0
            for obj in objs:
                try:
                    # Count edges and faces as proxy for visibility
                    edge_count = len(obj.Shape.Edges) if hasattr(obj.Shape, "Edges") else 0
                    face_count = len(obj.Shape.Faces) if hasattr(obj.Shape, "Faces") else 0
                    total_features += edge_count + face_count
                except:
                    continue
            
            # Normalize score (0-1 range)
            # Typical CAD part has 10-1000 features, so we normalize accordingly
            normalized = min(1.0, total_features / 1000.0)
            return normalized
            
        except Exception as e:
            print(f"Error scoring visibility: {e}")
            return 0.5  # Default score on error
    
    def score_information_density(self, view_candidate: ViewCandidate, doc) -> float:
        """
        Score view based on information density (unique features per view).
        Higher score = more unique information visible.
        
        Args:
            view_candidate: ViewCandidate to score
            doc: FreeCAD document
            
        Returns:
            Score between 0.0 and 1.0
        """
        if doc is None:
            return 0.5
        
        try:
            # For MVP, use a simplified heuristic based on view type
            # Orthographic views typically show more detail than isometric
            if view_candidate.type == "orthographic":
                # Front, top, right views are typically most informative
                if view_candidate.name in ["front", "top", "right"]:
                    return 0.9
                elif view_candidate.name in ["back", "bottom", "left"]:
                    return 0.7
                else:
                    return 0.6
            elif view_candidate.type == "isometric":
                # Isometric shows overall shape but less detail
                return 0.5
            else:
                return 0.4
                
        except Exception as e:
            print(f"Error scoring information density: {e}")
            return 0.5
    
    def score_symmetry(self, view_candidate: ViewCandidate, doc) -> float:
        """
        Score view based on symmetry detection.
        Higher score = view shows more symmetry (preferred for clarity).
        
        Args:
            view_candidate: ViewCandidate to score
            doc: FreeCAD document
            
        Returns:
            Score between 0.0 and 1.0
        """
        if doc is None:
            return 0.5
        
        try:
            # Simplified symmetry scoring
            # Front and top views often show symmetry better
            if view_candidate.name == "front":
                return 0.8
            elif view_candidate.name == "top":
                return 0.7
            elif view_candidate.type == "orthographic":
                return 0.6
            else:
                return 0.5
                
        except Exception as e:
            print(f"Error scoring symmetry: {e}")
            return 0.5
    
    def combined_score(self, view_candidate: ViewCandidate, doc) -> float:
        """
        Calculate combined score for a view candidate.
        
        Args:
            view_candidate: ViewCandidate to score
            doc: FreeCAD document
            
        Returns:
            Combined score between 0.0 and 1.0
        """
        visibility_score = self.score_visibility(view_candidate, doc)
        info_score = self.score_information_density(view_candidate, doc)
        symmetry_score = self.score_symmetry(view_candidate, doc)
        
        combined = (
            visibility_score * self.weights["visibility"] +
            info_score * self.weights["information_density"] +
            symmetry_score * self.weights["symmetry"]
        )
        
        return combined
    
    def score_all(self, candidates: List[ViewCandidate], doc) -> List[tuple]:
        """
        Score all candidates and return sorted list.
        
        Args:
            candidates: List of ViewCandidate objects
            doc: FreeCAD document
            
        Returns:
            List of (ViewCandidate, score) tuples, sorted by score (descending)
        """
        scored = [(c, self.combined_score(c, doc)) for c in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
