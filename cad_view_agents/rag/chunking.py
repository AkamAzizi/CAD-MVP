"""
Chunk snapshot into text + metadata for RAG retrieval.
"""
from typing import Any, Dict, List


def chunk_snapshot(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Split snapshot into chunks with text and metadata for embedding/retrieval.

    Chunk types: overview, part, bom, view_recommendations, pipeline_artifacts, validation_errors.

    Returns:
        List of {"text": str, "metadata": dict} with metadata containing
        assembly_id, chunk_type, and optional part_id, chunk_index.
    """
    chunks = []
    assembly_id = snapshot.get("assembly_id", "")

    # Overview
    ov = snapshot.get("overview", {})
    text = (
        f"Assembly overview: {ov.get('parts_count_total', 0)} total parts, "
        f"{ov.get('parts_count_unique', 0)} unique parts. "
    )
    bbox = ov.get("bbox_mm") or {}
    if bbox:
        text += f"Bounding box (mm): X={bbox.get('x', 0)}, Y={bbox.get('y', 0)}, Z={bbox.get('z', 0)}. "
    text += f"Primary axis: {ov.get('primary_axis', 'N/A')}. {ov.get('description', '')}"
    chunks.append({
        "text": text.strip(),
        "metadata": {"assembly_id": assembly_id, "chunk_type": "overview"},
    })

    # Part chunks
    for i, p in enumerate(snapshot.get("parts_tree", {}).get("parts", [])):
        b = p.get("bbox_mm") or {}
        bstr = f"{b.get('x', 0)}x{b.get('y', 0)}x{b.get('z', 0)} mm" if b else "N/A"
        vol = p.get("volume_mm3")
        volstr = f"{vol:.1f} mm³" if vol is not None else "N/A"
        text = (
            f"Part {p.get('id', '')}: name={p.get('name', '')}, "
            f"instances={p.get('instances', 1)}, bbox={bstr}, volume={volstr}."
        )
        chunks.append({
            "text": text,
            "metadata": {
                "assembly_id": assembly_id,
                "chunk_type": "part",
                "part_id": p.get("id", ""),
                "chunk_index": i,
                "instances": p.get("instances", 1),
                "volume_mm3": p.get("volume_mm3"),
            },
        })

    # BOM (one chunk)
    rows = snapshot.get("bom_preview", [])
    if rows:
        lines = ["BOM: item, part_number, description, quantity, material."]
        for r in rows:
            lines.append(
                f"  {r.get('item', '')} | {r.get('part_number', '')} | "
                f"{r.get('description', '')} | qty={r.get('quantity', 1)} | {r.get('material', 'N/A')}"
            )
        chunks.append({
            "text": "\n".join(lines),
            "metadata": {"assembly_id": assembly_id, "chunk_type": "bom"},
        })

    # View recommendations
    recs = snapshot.get("orientation_heuristics", {}).get("view_recommendations", [])
    if recs:
        lines = ["View recommendations and scores:"]
        for r in recs:
            lines.append(f"  {r.get('view_name', '')}: score={r.get('score', 0):.2f}, {r.get('reason', '')}")
        chunks.append({
            "text": "\n".join(lines),
            "metadata": {"assembly_id": assembly_id, "chunk_type": "view_recommendations"},
        })

    # Pipeline artifacts
    pa = snapshot.get("pipeline_artifacts", {})
    text = (
        f"Pipeline artifacts: sheet={pa.get('sheet_size', '')}, scale={pa.get('scale', '')}. "
        f"Selected views: {', '.join(pa.get('selected_views', []))}. "
        f"PDF: {pa.get('pdf_path', 'N/A')}, DXF: {pa.get('dxf_path', 'N/A')}."
    )
    chunks.append({
        "text": text,
        "metadata": {"assembly_id": assembly_id, "chunk_type": "pipeline_artifacts"},
    })

    # Validation errors
    errs = snapshot.get("validation_errors", [])
    if errs:
        text = "Pipeline warnings and errors: " + "; ".join(errs)
    else:
        text = "Pipeline warnings and errors: none."
    chunks.append({
        "text": text,
        "metadata": {"assembly_id": assembly_id, "chunk_type": "validation_errors"},
    })

    return chunks
