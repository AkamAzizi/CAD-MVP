"""
Assembly Snapshot: machine-readable (JSON) + human-readable (Markdown) snapshot
of an assembly after STEP import and pipeline analysis. Used as RAG source.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .part_tree import PartTree, PartNode

# Type alias for selected_views: list of (ViewCandidate, score)
SelectedViewsType = List[Tuple[Any, float]]

SNAPSHOT_VERSION = "1.0"
HASH_CHUNK_SIZE = 65536  # 64 KB for source file hash


def _source_file_hash(step_path: str) -> str:
    """Compute SHA-256 of STEP file (first 64 KB or full if smaller)."""
    try:
        with open(step_path, "rb") as f:
            data = f.read(HASH_CHUNK_SIZE)
        return "sha256:" + hashlib.sha256(data).hexdigest()
    except Exception:
        return "sha256:"


def _assembly_id(step_path: str) -> str:
    """Deterministic assembly ID from source file path (filesystem-safe)."""
    base = os.path.basename(step_path) or "unknown"
    name = os.path.splitext(base)[0] or "assembly"
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:30]
    path_hash = hashlib.sha256(step_path.encode()).hexdigest()[:8]
    return f"asm_{safe_name}_{path_hash}"


def _part_bbox_volume(node: PartNode) -> Tuple[Optional[Dict[str, float]], Optional[float]]:
    """Extract bbox (x,y,z in mm) and volume (mm³) from PartNode if FreeCAD obj available."""
    bbox_mm = None
    volume_mm3 = None
    obj = getattr(node, "freecad_obj", None)
    if obj is None:
        return bbox_mm, volume_mm3
    try:
        shape = getattr(obj, "Shape", None)
        if shape is None:
            return bbox_mm, volume_mm3
        box = getattr(shape, "BoundBox", None)
        if box is not None:
            bbox_mm = {
                "x": getattr(box, "XLength", 0) or 0,
                "y": getattr(box, "YLength", 0) or 0,
                "z": getattr(box, "ZLength", 0) or 0,
            }
        try:
            volume_mm3 = float(getattr(shape, "Volume", 0) or 0)
        except (TypeError, ValueError):
            pass
    except Exception:
        pass
    return bbox_mm, volume_mm3


def _placement_array(obj: Any) -> Optional[List[float]]:
    """Get 4x4 placement as 16 floats if available."""
    try:
        pl = getattr(obj, "Placement", None)
        if pl is None:
            return None
        base = getattr(pl, "Base", None)
        rot = getattr(pl, "Rotation", None)
        if base is not None and rot is not None:
            # FreeCAD Placement: Base (x,y,z), Rotation (quat or matrix)
            x = getattr(base, "x", 0) or 0
            y = getattr(base, "y", 0) or 0
            z = getattr(base, "z", 0) or 0
            return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]
    except Exception:
        pass
    return None


def build_snapshot(
    step_path: str,
    import_result: Dict[str, Any],
    part_tree: PartTree,
    analysis: Dict[str, Any],
    bom_metadata: List[Any],
    selected_views_with_scores: SelectedViewsType,
    layout_engine: Any,
    artifacts: List[str],
    trace: List[Dict],
    qa_result: Dict[str, Any],
    export_errors: List[str],
) -> Dict[str, Any]:
    """
    Build Assembly Snapshot dict from pipeline state.

    Args:
        step_path: Path to STEP file
        import_result: From import_agent.run() (doc, parts_count, bbox)
        part_tree: PartTree after build_tree(doc)
        analysis: From assembly_analyzer_agent.run()
        bom_metadata: List of PartMetadata (from BOM generator)
        selected_views_with_scores: List of (ViewCandidate, score)
        layout_engine: LayoutEngine after place_views (sheet_size, scale)
        artifacts: List of output file paths (PDF, DXF, metadata JSON, etc.)
        trace: Pipeline trace list
        qa_result: From qa_agent.run()
        export_errors: List of export error messages

    Returns:
        Snapshot dict conforming to Assembly Snapshot spec
    """
    assembly_id = _assembly_id(step_path)
    source_hash = _source_file_hash(step_path)
    bbox = import_result.get("bbox") or {}
    parts_count_total = import_result.get("parts_count", 0)
    parts_count_unique = len(bom_metadata) if bom_metadata else parts_count_total

    # Unique parts: one row per BOM entry, with bbox/volume from part_tree
    unique_parts = []
    if bom_metadata:
        for m in bom_metadata:
            node = part_tree.get_part_by_id(m.part_id)
            if node:
                bbox_mm, volume_mm3 = _part_bbox_volume(node)
                placement = _placement_array(node.freecad_obj) if getattr(node, "freecad_obj", None) else None
                unique_parts.append({
                    "id": node.id,
                    "name": node.name,
                    "label": node.metadata.get("label", node.name),
                    "geometry_hash": node.geometry_hash,
                    "bbox_mm": bbox_mm,
                    "volume_mm3": volume_mm3,
                    "placement": placement,
                    "instances": m.quantity,
                })
    else:
        for node in part_tree.get_part_list():
            bbox_mm, volume_mm3 = _part_bbox_volume(node)
            placement = _placement_array(node.freecad_obj) if getattr(node, "freecad_obj", None) else None
            unique_parts.append({
                "id": node.id,
                "name": node.name,
                "label": node.metadata.get("label", node.name),
                "geometry_hash": node.geometry_hash,
                "bbox_mm": bbox_mm,
                "volume_mm3": volume_mm3,
                "placement": placement,
                "instances": 1,
            })

    bom_preview = []
    if bom_metadata:
        for m in bom_metadata:
            bom_preview.append({
                "item": m.item_number,
                "part_number": m.part_id,
                "description": m.name,
                "quantity": m.quantity,
                "material": getattr(m, "material", "N/A") or "N/A",
            })

    view_scores = {v[0].name: v[1] for v in selected_views_with_scores}
    view_recommendations = [
        {"view_name": name, "score": score, "reason": f"Selected view, score {score:.2f}"}
        for name, score in view_scores.items()
    ]

    pdf_path = next((a for a in artifacts if a.endswith(".pdf")), None)
    dxf_path = next((a for a in artifacts if a.endswith(".dxf")), None)
    metadata_json_path = next((a for a in artifacts if a.endswith(".json")), None)
    view_svg_paths = [a for a in artifacts if ".svg" in a or "view_" in a]

    validation_errors = list(export_errors or [])
    if qa_result.get("status") == "fail":
        validation_errors.extend(qa_result.get("issues", []))

    sheet_size_name = getattr(layout_engine.sheet_size, "name", None) or "Unknown"
    scale = getattr(layout_engine, "scale", None) or 1.0

    snapshot = {
        "snapshot_version": SNAPSHOT_VERSION,
        "assembly_id": assembly_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_file": step_path,
        "source_file_hash": source_hash,
        "overview": {
            "parts_count_total": parts_count_total,
            "parts_count_unique": parts_count_unique,
            "bbox_mm": bbox,
            "primary_axis": analysis.get("primary_axis"),
            "description": analysis.get("description", ""),
            "is_assembly": analysis.get("is_assembly", parts_count_total > 1),
        },
        "parts_tree": {"parts": unique_parts},
        "bom_preview": bom_preview,
        "orientation_heuristics": {
            "primary_axis": analysis.get("primary_axis"),
            "aspect_ratios": analysis.get("aspect_ratios") or {},
            "recommended_views": analysis.get("recommended_views") or {},
            "view_recommendations": view_recommendations,
        },
        "pipeline_artifacts": {
            "pdf_path": pdf_path,
            "dxf_path": dxf_path,
            "metadata_json_path": metadata_json_path,
            "view_svg_paths": view_svg_paths,
            "selected_views": [v[0].name for v in selected_views_with_scores],
            "sheet_size": sheet_size_name,
            "scale": scale,
            "view_scores": view_scores,
        },
        "validation_errors": validation_errors,
    }
    return snapshot


def to_markdown(snapshot: Dict[str, Any]) -> str:
    """Produce human-readable Markdown for embeddings/display."""
    lines = [
        f"# Assembly Snapshot: {snapshot.get('assembly_id', '')}",
        f"Generated: {snapshot.get('timestamp', '')} | Source: {os.path.basename(snapshot.get('source_file', ''))}",
        "",
        "## Overview",
    ]
    ov = snapshot.get("overview", {})
    lines.append(f"- Total parts: {ov.get('parts_count_total', 0)} | Unique parts: {ov.get('parts_count_unique', 0)}")
    bbox = ov.get("bbox_mm") or {}
    if bbox:
        lines.append(f"- Bounding box (mm): X={bbox.get('x', 0)}, Y={bbox.get('y', 0)}, Z={bbox.get('z', 0)}")
    lines.append(f"- Primary axis: {ov.get('primary_axis', 'N/A')}. {ov.get('description', '')}")
    lines.append("")

    lines.append("## Parts")
    lines.append("| Id | Name | Qty | Bbox (mm) | Volume (mm³) |")
    lines.append("|----|------|-----|-----------|--------------|")
    for p in snapshot.get("parts_tree", {}).get("parts", []):
        b = p.get("bbox_mm") or {}
        bstr = f"{b.get('x', 0)}×{b.get('y', 0)}×{b.get('z', 0)}" if b else "N/A"
        vol = p.get("volume_mm3")
        volstr = f"{vol:.1f}" if vol is not None else "N/A"
        lines.append(f"| {p.get('id', '')} | {p.get('name', '')} | {p.get('instances', 1)} | {bstr} | {volstr} |")
    lines.append("")

    lines.append("## BOM")
    lines.append("| Item | Part Number | Description | Qty | Material |")
    lines.append("|------|-------------|-------------|-----|----------|")
    for row in snapshot.get("bom_preview", []):
        lines.append(f"| {row.get('item', '')} | {row.get('part_number', '')} | {row.get('description', '')} | {row.get('quantity', '')} | {row.get('material', 'N/A')} |")
    lines.append("")

    lines.append("## View recommendations")
    for rec in snapshot.get("orientation_heuristics", {}).get("view_recommendations", []):
        lines.append(f"- {rec.get('view_name', '')} ({rec.get('score', 0):.2f}): {rec.get('reason', '')}")
    lines.append("")

    pa = snapshot.get("pipeline_artifacts", {})
    lines.append("## Pipeline")
    lines.append(f"- Sheet: {pa.get('sheet_size', '')}, Scale: {pa.get('scale', '')}. Views: {', '.join(pa.get('selected_views', []))}.")
    lines.append(f"- Artifacts: {pa.get('pdf_path', '') or 'N/A'}, {pa.get('dxf_path', '') or 'N/A'}.")
    lines.append("")

    errs = snapshot.get("validation_errors", [])
    lines.append("## Warnings / Errors")
    if not errs:
        lines.append("(none)")
    else:
        for e in errs:
            lines.append(f"- {e}")
    return "\n".join(lines)


def save_snapshot(snapshot: Dict[str, Any], output_dir: str) -> List[str]:
    """
    Save snapshot as JSON and Markdown to output_dir.
    Returns list of saved file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    aid = snapshot.get("assembly_id", "snapshot")
    paths = []
    json_path = os.path.join(output_dir, f"{aid}_snapshot.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    paths.append(json_path)
    md_path = os.path.join(output_dir, f"{aid}_snapshot.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(snapshot))
    paths.append(md_path)
    return paths
