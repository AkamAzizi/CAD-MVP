import os

# Try to import FreeCADGui - may not be available in headless mode
try:
    import FreeCADGui
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

def run(views, out_dir, doc=None):
    """Render views. If GUI available, save PNGs. Otherwise, export STL."""
    os.makedirs(out_dir, exist_ok=True)
    
    # Try GUI mode first if available
    if GUI_AVAILABLE:
        try:
            import FreeCADGui
            if doc is not None:
                # Ensure we have an active view
                gui_doc = FreeCADGui.getDocument(doc.Name)
                if gui_doc:
                    view = gui_doc.ActiveView
                    if view:
                        outputs = []
                        for name, direction in views.items():
                            view.viewDirection(direction)
                            view.fitAll()
                            path = os.path.join(out_dir, f"{name}.png")
                            view.saveImage(path, 1920, 1080, 'White')
                            outputs.append(path)
                        
                        return {
                            "mode": "gui",
                            "artifacts": outputs
                        }
        except Exception as e:
            print(f"GUI rendering failed: {e}, falling back to headless mode")
            pass
    
    # Headless mode: export STL
    if doc is None:
        import FreeCAD
        doc = FreeCAD.ActiveDocument
    
    if doc is None:
        return {
            "mode": "headless",
            "artifacts": [],
            "error": "No document available"
        }
    
    try:
        import Mesh
        import MeshPart
        import Part
        
        # Collect all shapes
        shapes = []
        for obj in doc.Objects:
            if hasattr(obj, "Shape") and obj.Shape is not None:
                shapes.append(obj.Shape)
        
        if not shapes:
            return {
                "mode": "headless",
                "artifacts": [],
                "error": "No shapes found in document"
            }
        
        # For complex models (many parts), STL export may cause segmentation faults
        # Skip STL export if there are too many parts to avoid crashes
        if len(shapes) > 10:
            return {
                "mode": "headless",
                "artifacts": [],
                "error": f"STL export skipped: model has {len(shapes)} parts (may cause segmentation fault with FreeCAD mesh generation)"
            }
        
        # Try meshing each shape individually and combine, which is more stable
        meshes = []
        for shape in shapes:
            try:
                # Use simpler mesh parameters to avoid segfaults
                mesh = MeshPart.meshFromShape(
                    Shape=shape,
                    Fineness=1,  # Lower fineness for stability
                    SecondOrder=0,
                    Optimize=0,  # Disable optimization to avoid issues
                    AllowQuad=0
                )
                meshes.append(mesh)
            except Exception as e:
                print(f"Warning: Failed to mesh one shape: {e}")
                continue
        
        if not meshes:
            return {
                "mode": "headless",
                "artifacts": [],
                "error": "Failed to mesh any shapes"
            }
        
        # Combine meshes if multiple
        if len(meshes) == 1:
            combined_mesh = meshes[0]
        else:
            combined_mesh = meshes[0]
            for mesh in meshes[1:]:
                combined_mesh.addMesh(mesh)
        
        # Export STL
        stl_path = os.path.join(out_dir, "model.stl")
        combined_mesh.write(stl_path)
        
        return {
            "mode": "headless",
            "artifacts": [stl_path]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "mode": "headless",
            "artifacts": [],
            "error": str(e)
        }
