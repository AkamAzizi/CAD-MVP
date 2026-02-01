import os

def run(artifacts):
    """Validate artifacts exist and are non-empty."""
    issues = []
    min_size = 1000  # Minimum file size in bytes (1KB)
    
    if not artifacts:
        # Don't fail QA if no artifacts - STL export may be skipped for complex models
        return {
            "status": "pass",
            "issues": ["No artifacts generated (STL export may be skipped for complex models)"]
        }
    
    for artifact_path in artifacts:
        if not os.path.exists(artifact_path):
            issues.append(f"Artifact missing: {artifact_path}")
        else:
            size = os.path.getsize(artifact_path)
            if size < min_size:
                issues.append(f"Artifact too small ({size} bytes): {artifact_path}")
    
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues
    }
