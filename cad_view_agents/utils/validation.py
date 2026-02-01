"""
Input/output validation utilities.
"""
import os
from typing import List


def validate_step_file(step_path: str) -> tuple[bool, str]:
    """
    Validate STEP file exists and is readable.
    
    Args:
        step_path: Path to STEP file
        
    Returns:
        (is_valid, error_message) tuple
    """
    if not step_path:
        return False, "STEP file path is empty"
    
    if not os.path.exists(step_path):
        return False, f"STEP file not found: {step_path}"
    
    if not os.path.isfile(step_path):
        return False, f"Path is not a file: {step_path}"
    
    # Check extension
    ext = os.path.splitext(step_path)[1].lower()
    if ext not in [".step", ".stp"]:
        return False, f"File does not have .step or .stp extension: {ext}"
    
    # Check file size (should be > 0)
    if os.path.getsize(step_path) == 0:
        return False, "STEP file is empty"
    
    return True, ""


def validate_output_path(output_path: str) -> tuple[bool, str]:
    """
    Validate output path is writable.
    
    Args:
        output_path: Path for output file
        
    Returns:
        (is_valid, error_message) tuple
    """
    if not output_path:
        return False, "Output path is empty"
    
    # Check parent directory exists and is writable
    parent_dir = os.path.dirname(os.path.abspath(output_path))
    if not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except Exception as e:
            return False, f"Cannot create output directory: {e}"
    
    if not os.path.isdir(parent_dir):
        return False, f"Output parent path is not a directory: {parent_dir}"
    
    # Check if we can write (by attempting to create a test file)
    test_file = os.path.join(parent_dir, ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        return False, f"Cannot write to output directory: {e}"
    
    return True, ""


def validate_artifacts(artifact_paths: List[str]) -> tuple[bool, List[str]]:
    """
    Validate that artifact files exist and are non-empty.
    
    Args:
        artifact_paths: List of artifact file paths
        
    Returns:
        (is_valid, list_of_errors) tuple
    """
    errors = []
    min_size = 1000  # 1KB minimum
    
    for path in artifact_paths:
        if not os.path.exists(path):
            errors.append(f"Artifact missing: {path}")
        else:
            size = os.path.getsize(path)
            if size < min_size:
                errors.append(f"Artifact too small ({size} bytes): {path}")
    
    return len(errors) == 0, errors
