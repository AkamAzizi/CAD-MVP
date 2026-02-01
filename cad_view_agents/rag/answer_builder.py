"""
Build structured answer (headline, facts, sources) from question + snapshot.
Uses Intent Router for deterministic answers from snapshot data.
All responses are in English regardless of question language.
"""
from typing import Any, Dict, List, Optional
import re

from .intent_router import Intent, IntentResult, route, is_deterministic_intent


# =============================================================================
# Response data structure
# =============================================================================

def _make_response(headline: str, facts: List[str], sources: List[Dict[str, str]]) -> Dict[str, Any]:
    """Create standardized response dict."""
    return {
        "answer": headline.strip(),
        "facts": facts,
        "sources": sources,
    }


# =============================================================================
# Helper functions
# =============================================================================

MAX_REASONABLE_VOLUME_MM3 = 1e12  # ~1000 m³


def _is_reasonable_part(p: Dict) -> bool:
    """Filter out reference geometry (planes, axes) and invalid volumes."""
    name = (p.get("name") or p.get("id") or "").lower()
    if any(x in name for x in ["plane", "-plane", "axis", "-axis"]):
        return False
    v = p.get("volume_mm3")
    if v is not None and isinstance(v, (int, float)):
        if v <= 0 or v > MAX_REASONABLE_VOLUME_MM3:
            return False
    bbox = p.get("bbox_mm", {})
    for dim in ["x", "y", "z"]:
        val = bbox.get(dim, 0)
        if isinstance(val, (int, float)) and val > 1e9:
            return False
    return True


def _size_key(p: Dict, metric: str = "volume") -> float:
    """Get size value for sorting (volume or bbox volume)."""
    if metric == "volume":
        v = p.get("volume_mm3")
        if v is not None and isinstance(v, (int, float)) and 0 < v <= MAX_REASONABLE_VOLUME_MM3:
            return float(v)
    b = p.get("bbox_mm") or {}
    if b and all(isinstance(b.get(ax), (int, float)) for ax in ("x", "y", "z")):
        x, y, z = b.get("x") or 0, b.get("y") or 0, b.get("z") or 0
        if 0 < x < 1e9 and 0 < y < 1e9 and 0 < z < 1e9:
            return x * y * z
    return 0.0


def _format_volume(vol: float) -> str:
    """Format volume nicely with appropriate unit."""
    if vol >= 1e9:
        return f"{vol/1e9:.2f} m³"
    elif vol >= 1e6:
        return f"{vol/1e6:.2f} dm³"
    elif vol >= 1e3:
        return f"{vol/1e3:.1f} cm³"
    else:
        return f"{vol:.1f} mm³"


def _format_bbox(bbox: Dict) -> str:
    """Format bbox dimensions."""
    x = bbox.get("x", 0)
    y = bbox.get("y", 0)
    z = bbox.get("z", 0)
    return f"{x:.1f} × {y:.1f} × {z:.1f} mm"


def _is_fastener(name: str) -> bool:
    """Heuristic detection of fasteners (bolts, nuts, screws, washers)."""
    name_lower = name.lower()
    patterns = [
        r"\bdin\s*\d+",
        r"\biso\s*\d+",
        r"\bm\d+",
        r"\bbolt\b",
        r"\bbulong\b",
        r"\bscrew\b",
        r"\bskruv\b",
        r"\bnut\b",
        r"\bmutter\b",
        r"\bwasher\b",
        r"\bbricka\b",
        r"\bhex\b",
        r"\bsocket\b",
        r"\bfastener\b",
    ]
    return any(re.search(p, name_lower) for p in patterns)


def _metadata_is_missing(value: Any) -> bool:
    """Check if metadata value is missing or placeholder."""
    if value is None:
        return True
    if isinstance(value, str):
        v = value.strip().lower()
        return v in ("", "n/a", "none", "unknown", "-", "?")
    return False


def _is_reference_geometry(p: Dict) -> bool:
    """Check if a part is reference geometry (plane, axis, origin)."""
    name = (p.get("name") or p.get("label") or p.get("id") or "").lower()
    ref_patterns = ["plane", "axis", "origin", "datum", "csys", "coordinate"]
    if any(pat in name for pat in ref_patterns):
        return True
    bbox = p.get("bbox_mm", {})
    for dim in ["x", "y", "z"]:
        val = bbox.get(dim, 0)
        if isinstance(val, (int, float)) and val > 1e9:
            return True
    return False


# =============================================================================
# Intent Handlers - All responses in English
# =============================================================================

def handle_count_parts(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Handle COUNT_PARTS intent: unique vs total instances."""
    ov = snapshot.get("overview", {})
    unique = ov.get("parts_count_unique", 0)
    total = ov.get("parts_count_total", 0)
    
    headline = f"The assembly contains {unique} unique parts with {total} total instances."
    
    facts = [
        f"Unique parts: {unique}",
        f"Total instances: {total}",
    ]
    
    if total > unique:
        ratio = total / unique if unique > 0 else 0
        facts.append(f"Average instances per part: {ratio:.1f}")
    
    is_asm = ov.get("is_assembly", False)
    facts.append(f"Type: {'Assembly' if is_asm else 'Single part'}")
    
    sources = [
        {"path": "overview.parts_count_unique", "value": str(unique)},
        {"path": "overview.parts_count_total", "value": str(total)},
    ]
    
    return _make_response(headline, facts, sources)


def handle_largest_parts(snapshot: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle LARGEST_PARTS intent: biggest part(s) by volume/bbox."""
    parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
    top_n = params.get("top_n", 5)
    metric = params.get("metric", "volume")
    
    reasonable = [p for p in parts_tree if _is_reasonable_part(p)]
    sorted_parts = sorted(reasonable, key=lambda p: _size_key(p, metric), reverse=True)
    
    if not sorted_parts:
        return _make_response(
            "No parts with valid geometry found.",
            ["Reference geometry (planes, axes) has been filtered out."],
            [{"path": "parts_tree.parts", "note": "empty or filtered"}],
        )
    
    top1 = sorted_parts[0]
    name1 = top1.get("name") or top1.get("id", "Unknown")
    vol1 = top1.get("volume_mm3", 0)
    inst1 = top1.get("instances", 1)
    
    headline = f"The largest part is \"{name1}\" ({_format_volume(vol1)}, {inst1} instance{'s' if inst1 > 1 else ''})."
    
    facts = []
    sources = []
    
    for i, p in enumerate(sorted_parts[:top_n]):
        name = p.get("name") or p.get("id", "Unknown")
        vol = p.get("volume_mm3", 0)
        bbox = p.get("bbox_mm", {})
        instances = p.get("instances", 1)
        part_id = p.get("id", "")
        
        if vol and vol > 0:
            facts.append(f"{i+1}. {name}: {_format_volume(vol)} (×{instances})")
        elif bbox:
            facts.append(f"{i+1}. {name}: bbox {_format_bbox(bbox)} (×{instances})")
        else:
            facts.append(f"{i+1}. {name} (×{instances})")
        
        sources.append({"path": f"parts_tree.parts[{part_id}]", "field": "volume_mm3"})
    
    return _make_response(headline, facts, sources)


def handle_repetitive_parts(snapshot: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle REPETITIVE_PARTS intent: most repeated parts, fasteners."""
    parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
    top_n = params.get("top_n", 10)
    filter_fasteners = params.get("filter_fasteners", False)
    
    reasonable = [p for p in parts_tree if _is_reasonable_part(p)]
    
    if filter_fasteners:
        reasonable = [p for p in reasonable if _is_fastener(p.get("name", "") or p.get("label", ""))]
    
    sorted_parts = sorted(reasonable, key=lambda p: p.get("instances", 1), reverse=True)
    repeated = [p for p in sorted_parts if p.get("instances", 1) > 1]
    
    if not repeated:
        # Check for fasteners even if no repeated parts
        fasteners = [p for p in reasonable if _is_fastener(p.get("name", ""))]
        if fasteners and not filter_fasteners:
            headline = f"No repeated parts, but {len(fasteners)} standard fastener types identified."
            facts = []
            for i, p in enumerate(fasteners[:8]):
                name = p.get("name") or p.get("id", "Unknown")
                facts.append(f"• {name} (×{p.get('instances', 1)}) 🔩")
            return _make_response(headline, facts, [{"path": "parts_tree.parts", "filter": "fasteners"}])
        
        return _make_response(
            "No parts are repeated more than once in this assembly.",
            ["All parts are unique instances."],
            [{"path": "parts_tree.parts", "note": "no repeated parts"}],
        )
    
    top1 = repeated[0]
    name1 = top1.get("name") or top1.get("id", "Unknown")
    inst1 = top1.get("instances", 1)
    
    is_fastener_top = _is_fastener(name1)
    fastener_note = " (standard fastener)" if is_fastener_top else ""
    
    headline = f"Most repeated part is \"{name1}\" with {inst1} instances{fastener_note}."
    
    facts = []
    sources = []
    fastener_count = 0
    total_fastener_instances = 0
    
    for i, p in enumerate(repeated[:top_n]):
        name = p.get("name") or p.get("id", "Unknown")
        instances = p.get("instances", 1)
        part_id = p.get("id", "")
        
        is_fast = _is_fastener(name)
        if is_fast:
            fastener_count += 1
            total_fastener_instances += instances
            facts.append(f"{i+1}. {name}: ×{instances} 🔩")
        else:
            facts.append(f"{i+1}. {name}: ×{instances}")
        
        sources.append({"path": f"parts_tree.parts[{part_id}]", "field": "instances"})
    
    if fastener_count > 0 and not filter_fasteners:
        facts.append("—")
        facts.append(f"Identified fasteners: {fastener_count} types, {total_fastener_instances} total instances")
    
    return _make_response(headline, facts, sources)


def _generate_view_reasoning(view_name: str, score: float, aspect_ratios: Dict, primary_axis: Optional[str]) -> str:
    """Generate intelligent reasoning for why a view is recommended."""
    view_lower = view_name.lower()
    reasons = []
    
    if score >= 0.9:
        reasons.append("high information density")
    elif score >= 0.8:
        reasons.append("good balance of detail and overview")
    elif score >= 0.7:
        reasons.append("complementary perspective")
    
    if "front" in view_lower:
        reasons.append("shows main profile and connections")
        if aspect_ratios.get("xz", 0) > 1.2:
            reasons.append("wide frontal area")
    elif "top" in view_lower:
        reasons.append("shows mounting pattern and layout")
        if aspect_ratios.get("xy", 0) > 1.2:
            reasons.append("flat top surface")
    elif "right" in view_lower or "side" in view_lower:
        reasons.append("shows side profile and depth")
        if aspect_ratios.get("yz", 0) > 1.2:
            reasons.append("distinctive side profile")
    elif "iso" in view_lower:
        reasons.append("3D overview of entire geometry")
        reasons.append("good for visualization")
    
    if primary_axis:
        if primary_axis == "z" and "front" in view_lower:
            reasons.append("perpendicular to primary axis")
        elif primary_axis == "y" and "top" in view_lower:
            reasons.append("perpendicular to primary axis")
    
    return "; ".join(reasons[:3]) if reasons else "standard view"


def handle_best_views(snapshot: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle BEST_VIEWS intent: recommended views with reasoning."""
    orient = snapshot.get("orientation_heuristics", {})
    view_recs = orient.get("view_recommendations", [])
    pa = snapshot.get("pipeline_artifacts", {})
    selected = pa.get("selected_views", [])
    aspect_ratios = orient.get("aspect_ratios", {})
    primary_axis = orient.get("primary_axis")
    explain_why = params.get("explain_why", True)
    
    if not view_recs:
        return _make_response(
            "No view recommendations available for this assembly.",
            ["View analysis was not run or produced no results."],
            [{"path": "orientation_heuristics.view_recommendations", "note": "empty"}],
        )
    
    sorted_views = sorted(view_recs, key=lambda r: r.get("score", 0), reverse=True)
    best = sorted_views[0]
    best_name = best.get("view_name", "unknown")
    best_score = best.get("score", 0)
    
    best_reasoning = _generate_view_reasoning(best_name, best_score, aspect_ratios, primary_axis)
    
    headline = f"Best view for 2D drawing is \"{best_name}\" (score {best_score:.2f}) — {best_reasoning}."
    
    facts = []
    sources = []
    
    for r in sorted_views:
        name = r.get("view_name", "")
        score = r.get("score", 0)
        original_reason = r.get("reason", "")
        
        is_placeholder = not original_reason or "selected view" in original_reason.lower()
        
        if explain_why:
            if is_placeholder:
                reason = _generate_view_reasoning(name, score, aspect_ratios, primary_axis)
            else:
                reason = original_reason
            facts.append(f"{name}: {score:.2f} — {reason}")
        else:
            facts.append(f"{name}: score {score:.2f}")
        
        sources.append({"path": f"orientation_heuristics.view_recommendations[{name}]", "score": str(score)})
    
    if selected:
        facts.append("—")
        facts.append(f"Selected views in drawing: {', '.join(selected)}")
        sources.append({"path": "pipeline_artifacts.selected_views", "value": ", ".join(selected)})
    
    aspect = orient.get("aspect_ratios", {})
    if aspect:
        xy = aspect.get("xy", 0)
        xz = aspect.get("xz", 0)
        yz = aspect.get("yz", 0)
        if any([xy, xz, yz]):
            facts.append(f"Aspect ratios: XY={xy:.2f}, XZ={xz:.2f}, YZ={yz:.2f}")
    
    return _make_response(headline, facts, sources)


def handle_missing_metadata(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Handle BOM_QUESTIONS intent: find parts with missing metadata."""
    bom = snapshot.get("bom_preview", [])
    
    if not bom:
        return _make_response(
            "No BOM data available for this assembly.",
            ["BOM extraction was not run or produced no results."],
            [{"path": "bom_preview", "note": "empty"}],
        )
    
    missing_material = []
    missing_part_number = []
    missing_description = []
    
    for item in bom:
        part_num = item.get("part_number", "")
        desc = item.get("description", "")
        mat = item.get("material", "")
        item_no = item.get("item", "?")
        
        if any(x in desc.lower() for x in ["plane", "axis"]):
            continue
        
        if _metadata_is_missing(mat):
            missing_material.append(f"#{item_no} {desc or part_num}")
        if _metadata_is_missing(part_num) or (part_num.startswith("PART_") and len(part_num) > 10):
            missing_part_number.append(f"#{item_no} {desc}")
        if _metadata_is_missing(desc):
            missing_description.append(f"#{item_no} {part_num}")
    
    total_missing = len(missing_material) + len(missing_part_number) + len(missing_description)
    total_items = len(bom)
    
    if total_missing == 0:
        return _make_response(
            "All BOM entries have complete metadata.",
            [f"Total of {total_items} entries reviewed.", "No missing information found."],
            [{"path": "bom_preview", "note": "all complete"}],
        )
    
    nm, np, nd = len(missing_material), len(missing_part_number), len(missing_description)
    parts = []
    if nm:
        part_s = "part" if nm == 1 else "parts"
        parts.append(f"{nm} {part_s} missing material")
    if np:
        pn_s = "part number" if np == 1 else "part numbers"
        parts.append(f"{np} missing {pn_s}")
    if nd:
        parts.append(f"{nd} missing description")
    headline = ". ".join(parts) + "." if parts else "No missing metadata."
    
    facts = []
    sources = []
    
    if missing_material:
        facts.append(f"Missing material ({len(missing_material)}):")
        for m in missing_material[:5]:
            facts.append(f"  • {m}")
        if len(missing_material) > 5:
            facts.append(f"  • ... and {len(missing_material) - 5} more")
        sources.append({"path": "bom_preview[].material", "count": str(len(missing_material))})
    
    if missing_part_number:
        facts.append(f"Missing part number ({len(missing_part_number)}):")
        for m in missing_part_number[:5]:
            facts.append(f"  • {m}")
        if len(missing_part_number) > 5:
            facts.append(f"  • ... and {len(missing_part_number) - 5} more")
        sources.append({"path": "bom_preview[].part_number", "count": str(len(missing_part_number))})
    
    return _make_response(headline, facts, sources)


def handle_warnings(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Handle WARNINGS_ERRORS intent: validation errors and issues."""
    errors = snapshot.get("validation_errors", [])
    
    if not errors:
        return _make_response(
            "No errors or warnings reported.",
            ["Pipeline ran without validation errors.", "Geometry and metadata validated successfully."],
            [{"path": "validation_errors", "note": "empty"}],
        )
    
    headline = f"Pipeline reported {len(errors)} validation error{'s' if len(errors) > 1 else ''}/warning{'s' if len(errors) > 1 else ''}."
    
    facts = []
    sources = []
    
    for i, err in enumerate(errors[:5]):
        facts.append(f"{i+1}. {err}")
        sources.append({"path": f"validation_errors[{i}]", "error": err[:50]})
    
    if len(errors) > 5:
        facts.append(f"... and {len(errors) - 5} more errors")
    
    return _make_response(headline, facts, sources)


def handle_overview(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Handle OVERVIEW intent: general assembly description."""
    ov = snapshot.get("overview", {})
    pa = snapshot.get("pipeline_artifacts", {})
    
    unique = ov.get("parts_count_unique", 0)
    total = ov.get("parts_count_total", 0)
    desc = ov.get("description", "")
    is_asm = ov.get("is_assembly", False)
    source_file = snapshot.get("source_file", "")
    
    file_name = source_file.split("/")[-1] if source_file else "Unknown file"
    
    headline = f"{file_name} is {'an assembly' if is_asm else 'a single part'} with {unique} unique parts and {total} instances."
    
    facts = []
    sources = []
    
    facts.append(f"Source file: {file_name}")
    facts.append(f"Type: {'Assembly' if is_asm else 'Single part'}")
    facts.append(f"Unique parts: {unique}")
    facts.append(f"Total instances: {total}")
    
    if desc:
        facts.append(f"Description: {desc[:150]}{'...' if len(desc) > 150 else ''}")
    
    bbox = ov.get("bbox_mm", {})
    if bbox and all(bbox.get(ax) for ax in ["x", "y", "z"]):
        facts.append(f"Total bbox: {_format_bbox(bbox)}")
    
    selected = pa.get("selected_views", [])
    if selected:
        facts.append(f"Selected views: {', '.join(selected)}")
    
    sources.append({"path": "overview", "fields": "parts_count_unique, parts_count_total, description"})
    sources.append({"path": "source_file", "value": file_name})
    
    return _make_response(headline, facts, sources)


# =============================================================================
# Tier 3 - Geometry Analysis Handlers
# =============================================================================

def handle_geometry_analysis(snapshot: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle GEOMETRY_ANALYSIS intent: aspect ratio, extreme geometry, etc."""
    subtype = params.get("subtype", "general")
    parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
    ov = snapshot.get("overview", {})
    orient = snapshot.get("orientation_heuristics", {})
    
    reasonable_parts = [p for p in parts_tree if _is_reasonable_part(p)]
    
    all_bboxes = []
    for p in reasonable_parts:
        bbox = p.get("bbox_mm", {})
        if bbox and all(isinstance(bbox.get(ax), (int, float)) for ax in ["x", "y", "z"]):
            all_bboxes.append(bbox)
    
    asm_bbox = ov.get("bbox_mm", {})
    if not asm_bbox or not all(asm_bbox.get(ax) for ax in ["x", "y", "z"]):
        if all_bboxes:
            asm_bbox = {
                "x": max(b.get("x", 0) for b in all_bboxes),
                "y": max(b.get("y", 0) for b in all_bboxes),
                "z": max(b.get("z", 0) for b in all_bboxes),
            }
    
    x = asm_bbox.get("x", 0) or 1
    y = asm_bbox.get("y", 0) or 1
    z = asm_bbox.get("z", 0) or 1
    
    dims = sorted([(x, "X (width)"), (y, "Y (depth)"), (z, "Z (height)")], reverse=True)
    longest_dim, longest_name = dims[0]
    shortest_dim, shortest_name = dims[2]
    aspect_ratio = longest_dim / shortest_dim if shortest_dim > 0 else 1
    
    facts = []
    sources = []
    
    if subtype == "aspect_ratio":
        if aspect_ratio > 3:
            shape = "very elongated"
        elif aspect_ratio > 1.5:
            shape = "moderately elongated"
        else:
            shape = "relatively compact/cubic"
        
        headline = f"The assembly is {shape} — {longest_name} is {aspect_ratio:.1f}× longer than {shortest_name}."
        facts.append(f"Longest dimension: {longest_name} = {longest_dim:.1f} mm")
        facts.append(f"Shortest dimension: {shortest_name} = {shortest_dim:.1f} mm")
        facts.append(f"Aspect ratio: {aspect_ratio:.2f}:1")
        facts.append(f"Total bbox: {x:.1f} × {y:.1f} × {z:.1f} mm")
        
        if aspect_ratio > 2:
            facts.append(f"Recommendation: Orient drawing with {longest_name} horizontal")
        
        sources.append({"path": "overview.bbox_mm", "value": f"{x:.1f}×{y:.1f}×{z:.1f}"})
        
    elif subtype == "reference_geometry":
        ref_parts = [p for p in parts_tree if _is_reference_geometry(p)]
        
        if not ref_parts:
            headline = "No reference geometry (planes, axes) detected."
            facts.append("All parts in the assembly are actual geometry.")
        else:
            headline = f"{len(ref_parts)} reference geometry items identified (planes, axes, etc.)."
            for p in ref_parts[:8]:
                name = p.get("name") or p.get("id", "Unknown")
                inst = p.get("instances", 1)
                facts.append(f"• {name} (×{inst})")
            facts.append("—")
            facts.append("These are automatically filtered from size analyses.")
        
        sources.append({"path": "parts_tree.parts", "filter": "reference_geometry"})
        
    elif subtype == "small_parts":
        if not reasonable_parts:
            headline = "No parts with valid geometry to analyze."
            facts.append("Check that snapshot contains part data.")
        else:
            volumes = [p.get("volume_mm3", 0) for p in reasonable_parts if p.get("volume_mm3", 0) > 0]
            if volumes:
                median_vol = sorted(volumes)[len(volumes)//2]
                small_threshold = median_vol * 0.01
                small_parts = [p for p in reasonable_parts 
                              if 0 < p.get("volume_mm3", 0) < small_threshold]
                
                if small_parts:
                    headline = f"{len(small_parts)} unusually small parts may cause drawing issues at normal scale."
                    for p in sorted(small_parts, key=lambda x: x.get("volume_mm3", 0))[:5]:
                        name = p.get("name") or p.get("id", "Unknown")
                        vol = p.get("volume_mm3", 0)
                        facts.append(f"• {name}: {_format_volume(vol)}")
                    facts.append("—")
                    facts.append(f"Median volume in assembly: {_format_volume(median_vol)}")
                    facts.append("Consider detail views or sections for these.")
                else:
                    headline = "No unusually small parts detected."
                    facts.append(f"All {len(reasonable_parts)} parts have reasonable size relative to each other.")
            else:
                headline = "Could not analyze part sizes (volume data missing)."
        
        sources.append({"path": "parts_tree.parts", "analysis": "small_parts"})
        
    elif subtype == "scale_outliers":
        if not reasonable_parts:
            headline = "No parts to analyze for scale deviations."
        else:
            volumes = [(p, p.get("volume_mm3", 0)) for p in reasonable_parts if p.get("volume_mm3", 0) > 0]
            if len(volumes) >= 3:
                sorted_vols = sorted(volumes, key=lambda x: x[1])
                median_vol = sorted_vols[len(sorted_vols)//2][1]
                
                large_outliers = [(p, v) for p, v in volumes if v > median_vol * 100]
                small_outliers = [(p, v) for p, v in volumes if v < median_vol * 0.01]
                
                total_outliers = len(large_outliers) + len(small_outliers)
                if total_outliers > 0:
                    headline = f"{total_outliers} parts deviate significantly in scale from others."
                    if large_outliers:
                        facts.append(f"Unusually large ({len(large_outliers)}):")
                        for p, v in large_outliers[:3]:
                            facts.append(f"  • {p.get('name', 'Unknown')}: {_format_volume(v)}")
                    if small_outliers:
                        facts.append(f"Unusually small ({len(small_outliers)}):")
                        for p, v in small_outliers[:3]:
                            facts.append(f"  • {p.get('name', 'Unknown')}: {_format_volume(v)}")
                else:
                    headline = "All parts have consistent scale — no extreme deviations."
                    facts.append(f"Analyzed {len(volumes)} parts.")
            else:
                headline = "Too few parts for meaningful scale analysis."
        
        sources.append({"path": "parts_tree.parts", "analysis": "scale_outliers"})
        
    elif subtype == "hidden_lines":
        view_recs = orient.get("view_recommendations", [])
        
        headline = "Orientation for minimal hidden lines depends on view selection and geometry complexity."
        
        if view_recs:
            best_view = max(view_recs, key=lambda r: r.get("score", 0))
            facts.append(f"Best view by heuristics: {best_view.get('view_name', 'unknown')} (score {best_view.get('score', 0):.2f})")
        
        facts.append(f"Total bbox: {x:.1f} × {y:.1f} × {z:.1f} mm")
        
        min_dim_axis = min([(x, "X/front"), (y, "Y/side"), (z, "Z/top")], key=lambda t: t[0])
        facts.append(f"View perpendicular to {min_dim_axis[1]} (thinnest dimension) often minimizes hidden lines.")
        facts.append("For complex parts, consider section views.")
        
        sources.append({"path": "orientation_heuristics", "analysis": "hidden_lines"})
        
    else:  # general
        headline = f"Assembly bbox: {x:.1f} × {y:.1f} × {z:.1f} mm with {len(reasonable_parts)} geometric parts."
        
        ref_count = len([p for p in parts_tree if _is_reference_geometry(p)])
        if ref_count > 0:
            facts.append(f"Reference geometry (filtered): {ref_count}")
        
        facts.append(f"Geometric parts: {len(reasonable_parts)}")
        facts.append(f"Aspect ratio: {aspect_ratio:.2f}:1")
        facts.append(f"Longest dimension: {longest_name}")
        
        sources.append({"path": "parts_tree.parts", "analysis": "geometry_general"})
    
    return _make_response(headline, facts, sources)


# =============================================================================
# Tier 2 - Detail Drawings Handler
# =============================================================================

def handle_detail_drawings(snapshot: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle DETAIL_DRAWINGS intent: which parts need detail drawings."""
    parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
    
    reasonable_parts = [p for p in parts_tree if _is_reasonable_part(p)]
    facts = []
    sources = []
    
    part_metrics = []
    for p in reasonable_parts:
        name = p.get("name") or p.get("id", "Unknown")
        vol = p.get("volume_mm3", 0)
        instances = p.get("instances", 1)
        bbox = p.get("bbox_mm", {})
        is_fast = _is_fastener(name)
        
        complexity_score = 0
        if vol > 0:
            complexity_score += min(vol / 100000, 5)
        if instances == 1:
            complexity_score += 2
        if not is_fast:
            complexity_score += 3
        
        part_metrics.append({
            "part": p,
            "name": name,
            "volume": vol,
            "instances": instances,
            "is_fastener": is_fast,
            "complexity": complexity_score,
            "bbox": bbox,
        })
    
    needs_detail = sorted(
        [pm for pm in part_metrics if not pm["is_fastener"] and pm["complexity"] > 3],
        key=lambda x: x["complexity"],
        reverse=True
    )
    
    def bbox_volume(pm):
        b = pm["bbox"]
        if b:
            return b.get("x", 0) * b.get("y", 0) * b.get("z", 0)
        return 0
    
    outer_dimension_parts = sorted(part_metrics, key=bbox_volume, reverse=True)[:5]
    can_ignore = [pm for pm in part_metrics if pm["is_fastener"] or (pm["instances"] > 4 and pm["complexity"] < 2)]
    
    headline = f"{len(needs_detail)} parts likely need their own detail drawings."
    
    if needs_detail:
        facts.append("Parts likely needing detail drawings:")
        for pm in needs_detail[:5]:
            facts.append(f"  • {pm['name']} ({_format_volume(pm['volume'])})")
    
    facts.append("—")
    facts.append("Parts affecting outer dimensions most:")
    for pm in outer_dimension_parts[:3]:
        b = pm["bbox"]
        if b:
            facts.append(f"  • {pm['name']}: {b.get('x', 0):.1f} × {b.get('y', 0):.1f} × {b.get('z', 0):.1f} mm")
    
    if can_ignore:
        facts.append("—")
        facts.append(f"Can be ignored in first drawing version: {len(can_ignore)} parts (fasteners, repetitive)")
    
    sources.append({"path": "parts_tree.parts", "analysis": "detail_drawings"})
    
    return _make_response(headline, facts, sources)


# =============================================================================
# Tier 4 - Structure Analysis Handler
# =============================================================================

def handle_structure_analysis(snapshot: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle STRUCTURE_ANALYSIS intent: main axis, symmetry, nesting, sub-assemblies."""
    subtype = params.get("subtype", "general")
    parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
    orient = snapshot.get("orientation_heuristics", {})
    ov = snapshot.get("overview", {})
    
    reasonable_parts = [p for p in parts_tree if _is_reasonable_part(p)]
    facts = []
    sources = []
    
    primary_axis = orient.get("primary_axis") or ov.get("primary_axis")
    
    if subtype == "main_axis":
        headline = f"Primary axis: {primary_axis.upper() if primary_axis else 'not determined'}"
        
        if primary_axis:
            facts.append(f"The assembly is oriented along the {primary_axis.upper()}-axis.")
            
            axis_aligned = []
            axis_idx = {"x": 0, "y": 1, "z": 2}.get(primary_axis.lower(), 2)
            axes = ["x", "y", "z"]
            
            for p in reasonable_parts:
                bbox = p.get("bbox_mm", {})
                if bbox:
                    dims = [bbox.get(ax, 0) for ax in axes]
                    if dims[axis_idx] > 0:
                        ratio = dims[axis_idx] / (sum(dims) / 3) if sum(dims) > 0 else 0
                        if ratio > 1.5:
                            axis_aligned.append(p)
            
            if axis_aligned:
                facts.append(f"{len(axis_aligned)} parts are elongated along the {primary_axis.upper()}-axis:")
                for p in axis_aligned[:5]:
                    facts.append(f"  • {p.get('name', 'Unknown')}")
        else:
            facts.append("Primary axis could not be determined automatically.")
            facts.append("The assembly may be symmetric or cubic.")
        
        sources.append({"path": "orientation_heuristics.primary_axis", "value": primary_axis or "null"})
        
    elif subtype == "symmetry":
        headline = "Symmetry analysis based on part counts and placement."
        
        symmetric_indicators = [p for p in reasonable_parts if p.get("instances", 1) % 2 == 0 and p.get("instances", 1) > 1]
        
        if symmetric_indicators:
            facts.append(f"{len(symmetric_indicators)} parts have even instance counts (possible symmetry):")
            for p in symmetric_indicators[:5]:
                facts.append(f"  • {p.get('name', 'Unknown')}: ×{p.get('instances', 1)}")
        else:
            facts.append("No clear symmetry indicators based on part counts.")
        
        facts.append("—")
        facts.append("Full symmetry analysis requires placement data (not implemented).")
        
        sources.append({"path": "parts_tree.parts", "analysis": "symmetry"})
        
    elif subtype == "critical_parts":
        headline = "Critical parts for assembly identified based on size and uniqueness."
        
        critical = []
        for p in reasonable_parts:
            vol = p.get("volume_mm3", 0)
            instances = p.get("instances", 1)
            name = (p.get("name") or "").lower()
            
            is_critical = False
            reason = []
            
            if vol > 100000 and instances == 1:
                is_critical = True
                reason.append("large and unique")
            if any(kw in name for kw in ["housing", "frame", "body", "base", "chassis", "main"]):
                is_critical = True
                reason.append("structural name")
            if any(kw in name for kw in ["shaft", "axel", "rotor", "spindle"]):
                is_critical = True
                reason.append("rotating component")
            
            if is_critical:
                critical.append((p, ", ".join(reason)))
        
        if critical:
            facts.append(f"{len(critical)} critical parts identified:")
            for p, reason in critical[:6]:
                facts.append(f"  • {p.get('name', 'Unknown')}: {reason}")
        else:
            facts.append("No parts matched criticality heuristics.")
        
        sources.append({"path": "parts_tree.parts", "analysis": "critical_parts"})
        
    elif subtype == "nested_parts":
        headline = "Analysis of potentially nested parts (part inside part)."
        
        facts.append("Nesting analysis requires full placement data.")
        facts.append("Heuristic indication based on size:")
        
        if reasonable_parts:
            sorted_by_vol = sorted(reasonable_parts, key=lambda p: p.get("volume_mm3", 0), reverse=True)
            largest = sorted_by_vol[0]
            largest_vol = largest.get("volume_mm3", 0)
            
            potentially_inside = [p for p in sorted_by_vol[1:] if p.get("volume_mm3", 0) < largest_vol * 0.1]
            
            if potentially_inside:
                facts.append(f"{len(potentially_inside)} parts are <10% of largest part's volume:")
                for p in potentially_inside[:5]:
                    facts.append(f"  • {p.get('name', 'Unknown')}: {_format_volume(p.get('volume_mm3', 0))}")
        
        sources.append({"path": "parts_tree.parts", "analysis": "nesting"})
        
    elif subtype == "sub_assemblies":
        headline = "Potential sub-assemblies based on naming patterns."
        
        prefixes = {}
        for p in reasonable_parts:
            name = p.get("name") or p.get("id", "")
            prefix_match = re.match(r'^([a-zA-Z]+)', name)
            if prefix_match:
                prefix = prefix_match.group(1).lower()
                if len(prefix) >= 3:
                    prefixes.setdefault(prefix, []).append(p)
        
        sub_groups = [(prefix, parts) for prefix, parts in prefixes.items() if len(parts) >= 3]
        
        if sub_groups:
            facts.append(f"{len(sub_groups)} possible sub-assembly groups:")
            for prefix, parts in sorted(sub_groups, key=lambda x: len(x[1]), reverse=True)[:5]:
                facts.append(f"  • '{prefix}*': {len(parts)} parts")
        else:
            facts.append("No clear sub-assembly patterns based on naming.")
        
        sources.append({"path": "parts_tree.parts", "analysis": "sub_assemblies"})
        
    else:  # general
        headline = f"Structure analysis: {len(reasonable_parts)} parts, primary axis {primary_axis or 'not determined'}."
        
        total_instances = sum(p.get("instances", 1) for p in reasonable_parts)
        fastener_count = len([p for p in reasonable_parts if _is_fastener(p.get("name", ""))])
        
        facts.append(f"Total {total_instances} instances of {len(reasonable_parts)} unique parts")
        facts.append(f"Identified fasteners: {fastener_count}")
        facts.append(f"Primary axis: {primary_axis or 'not determined'}")
        
        sources.append({"path": "parts_tree.parts", "analysis": "structure_general"})
    
    return _make_response(headline, facts, sources)


# =============================================================================
# Tier 5 - Engineer Copilot Handler
# =============================================================================

def handle_engineer_copilot(snapshot: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle ENGINEER_COPILOT intent: next steps, missing views, tolerances."""
    subtype = params.get("subtype", "general")
    parts_tree = snapshot.get("parts_tree", {}).get("parts", [])
    pa = snapshot.get("pipeline_artifacts", {})
    orient = snapshot.get("orientation_heuristics", {})
    ov = snapshot.get("overview", {})
    bom = snapshot.get("bom_preview", [])
    errors = snapshot.get("validation_errors", [])
    
    reasonable_parts = [p for p in parts_tree if _is_reasonable_part(p)]
    selected_views = pa.get("selected_views", [])
    view_recs = orient.get("view_recommendations", [])
    
    facts = []
    sources = []
    
    if subtype == "next_steps":
        headline = "Recommended next steps for drawing work:"
        
        steps = []
        
        if not selected_views:
            steps.append("1. Select views for the drawing (front, top, iso recommended)")
        elif len(selected_views) < 3:
            steps.append(f"1. Consider more views — have {len(selected_views)}, recommend at least 3")
        else:
            steps.append("✓ View selection looks complete")
        
        missing_material = len([b for b in bom if _metadata_is_missing(b.get("material"))])
        if missing_material > 0:
            steps.append(f"2. Complete BOM — {missing_material} parts missing material")
        else:
            steps.append("✓ BOM metadata looks complete")
        
        large_unique = [p for p in reasonable_parts 
                       if p.get("volume_mm3", 0) > 100000 and p.get("instances", 1) == 1 
                       and not _is_fastener(p.get("name", ""))]
        if large_unique:
            n = len(large_unique)
            p = "part" if n == 1 else "parts"
            steps.append(f"3. Create detail drawings for {n} large unique {p}")
        
        if errors:
            steps.append(f"4. Address {len(errors)} validation errors")
        
        steps.append("5. Add key dimensions to main drawing")
        steps.append("6. Review tolerances for critical dimensions")
        
        facts = steps
        sources.append({"path": "pipeline_artifacts", "analysis": "workflow"})
        
    elif subtype == "missing_views":
        standard_views = {"front", "top", "right", "iso"}
        selected_set = set(v.lower() for v in selected_views)
        missing = standard_views - selected_set
        
        if missing:
            headline = f"Missing views in current proposal: {', '.join(missing)}"
            facts.append(f"Selected views: {', '.join(selected_views)}")
            facts.append(f"Missing standard views: {', '.join(missing)}")
            
            for m in missing:
                if m == "front":
                    facts.append("  • front: important for main profile")
                elif m == "top":
                    facts.append("  • top: shows layout and mounting pattern")
                elif m == "right":
                    facts.append("  • right: completes depth information")
                elif m == "iso":
                    facts.append("  • iso: provides 3D overview")
        else:
            headline = "All standard views are included in the drawing proposal."
            facts.append(f"Selected views: {', '.join(selected_views)}")
            facts.append("No obvious views are missing.")
        
        sources.append({"path": "pipeline_artifacts.selected_views", "value": ", ".join(selected_views)})
        
    elif subtype == "tolerances":
        headline = "Parts likely requiring tolerances based on function:"
        
        tolerance_candidates = []
        for p in reasonable_parts:
            name = (p.get("name") or "").lower()
            reason = None
            
            if any(kw in name for kw in ["shaft", "axel", "spindle", "rotor"]):
                reason = "rotating component — requires fit"
            elif any(kw in name for kw in ["bearing", "lager", "bushing"]):
                reason = "bearing — requires hole and shaft tolerances"
            elif any(kw in name for kw in ["seal", "o-ring", "gasket"]):
                reason = "sealing — requires surface finish"
            elif any(kw in name for kw in ["piston", "cylinder"]):
                reason = "hydraulic/pneumatic — requires fit"
            elif any(kw in name for kw in ["gear", "pinion"]):
                reason = "gear — requires profile tolerance"
            
            if reason:
                tolerance_candidates.append((p, reason))
        
        if tolerance_candidates:
            for p, reason in tolerance_candidates[:6]:
                facts.append(f"• {p.get('name', 'Unknown')}: {reason}")
        else:
            facts.append("No obvious tolerance-critical parts identified automatically.")
            facts.append("Review manually: fits, bearing seats, sealing surfaces.")
        
        sources.append({"path": "parts_tree.parts", "analysis": "tolerances"})
        
    elif subtype == "dimensioning":
        headline = "Parts and dimensions to include on main drawing:"
        
        sorted_parts = sorted(reasonable_parts, key=lambda p: p.get("volume_mm3", 0), reverse=True)
        
        facts.append("Outer dimensions (from largest parts):")
        for p in sorted_parts[:3]:
            bbox = p.get("bbox_mm", {})
            if bbox:
                facts.append(f"  • {p.get('name', 'Unknown')}: {_format_bbox(bbox)}")
        
        facts.append("—")
        facts.append("Recommended dimensions on main drawing:")
        facts.append("  • Overall length/width/height")
        facts.append("  • Mounting holes (pattern, spacing)")
        facts.append("  • Connection points (flanges, threads)")
        
        fasteners = [p for p in reasonable_parts if _is_fastener(p.get("name", ""))]
        if fasteners:
            facts.append(f"  • Bolt patterns ({len(fasteners)} fastener types identified)")
        
        sources.append({"path": "parts_tree.parts", "analysis": "dimensioning"})
        
    elif subtype == "ignore_parts":
        headline = "Parts that can be omitted from first drawing version:"
        
        ignorable = []
        for p in reasonable_parts:
            name = p.get("name") or ""
            instances = p.get("instances", 1)
            
            if _is_fastener(name):
                ignorable.append((p, "standard fastener"))
            elif instances > 4:
                ignorable.append((p, f"repetitive (×{instances})"))
        
        if ignorable:
            facts.append(f"{len(ignorable)} parts can be ignored initially:")
            for p, reason in ignorable[:8]:
                facts.append(f"  • {p.get('name', 'Unknown')}: {reason}")
            facts.append("—")
            facts.append("These typically appear in BOM but rarely need their own detail drawings.")
        else:
            facts.append("All parts appear relevant for the drawing.")
        
        sources.append({"path": "parts_tree.parts", "analysis": "ignore_parts"})
        
    else:  # general
        headline = "Engineer Copilot: summary and recommendations"
        
        facts.append(f"Assembly: {ov.get('parts_count_unique', 0)} unique parts, {ov.get('parts_count_total', 0)} instances")
        facts.append(f"Selected views: {', '.join(selected_views) if selected_views else 'none'}")
        
        if errors:
            facts.append(f"⚠️ {len(errors)} validation errors to address")
        else:
            facts.append("✓ No validation errors")
        
        missing_mat = len([b for b in bom if _metadata_is_missing(b.get("material"))])
        if missing_mat > 0:
            facts.append(f"⚠️ {missing_mat} parts missing material in BOM")
        
        facts.append("—")
        facts.append("Ask specifically about: next steps, missing views, tolerances, dimensioning")
        
        sources.append({"path": "overview", "analysis": "copilot_summary"})
    
    return _make_response(headline, facts, sources)


# =============================================================================
# Fallback Handler
# =============================================================================

def handle_fallback(
    question: str,
    snapshot: Dict[str, Any],
    retrieved_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Handle FALLBACK intent: generic structured answer using retrieval."""
    ov = snapshot.get("overview", {})
    unique = ov.get("parts_count_unique", 0)
    total = ov.get("parts_count_total", 0)
    
    facts = []
    sources = []
    
    for chunk in retrieved_chunks[:3]:
        chunk_type = chunk.get("metadata", {}).get("chunk_type", "unknown")
        content = chunk.get("document", "")[:200]
        if content:
            facts.append(f"[{chunk_type}] {content}...")
            sources.append({"path": f"chunk:{chunk_type}", "note": "from retrieval"})
    
    if not facts:
        facts.append(f"Unique parts: {unique}")
        facts.append(f"Total instances: {total}")
        sources.append({"path": "overview", "note": "fallback"})
    
    headline = f"Assembly with {unique} unique parts. See facts below for details related to your question."
    
    return _make_response(headline, facts, sources)


# =============================================================================
# Main Entry Point
# =============================================================================

def build_answer(
    question: str,
    retrieved_chunks: List[Dict[str, Any]],
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a structured answer using intent routing.
    All responses are in English regardless of question language.
    
    Returns:
        {"answer": str (headline), "facts": list[str], "sources": list[dict]}
    """
    intent_result = route(question)
    intent = intent_result.intent
    params = intent_result.params
    
    # Tier 1 - Core
    if intent == Intent.COUNT_PARTS:
        return handle_count_parts(snapshot)
    
    elif intent == Intent.LARGEST_PARTS:
        return handle_largest_parts(snapshot, params)
    
    elif intent == Intent.REPETITIVE_PARTS:
        return handle_repetitive_parts(snapshot, params)
    
    elif intent == Intent.BEST_VIEWS:
        return handle_best_views(snapshot, params)
    
    # Tier 2 - BOM & Production
    elif intent == Intent.BOM_QUESTIONS:
        return handle_missing_metadata(snapshot)
    
    elif intent == Intent.DETAIL_DRAWINGS:
        return handle_detail_drawings(snapshot, params)
    
    # Tier 3 - Geometry & Quality
    elif intent == Intent.GEOMETRY_ANALYSIS:
        return handle_geometry_analysis(snapshot, params)
    
    elif intent == Intent.WARNINGS_ERRORS:
        return handle_warnings(snapshot)
    
    # Tier 4 - Structure Analysis
    elif intent == Intent.STRUCTURE_ANALYSIS:
        return handle_structure_analysis(snapshot, params)
    
    # Tier 5 - Engineer Copilot
    elif intent == Intent.ENGINEER_COPILOT:
        return handle_engineer_copilot(snapshot, params)
    
    # Other
    elif intent == Intent.OVERVIEW:
        return handle_overview(snapshot)
    
    else:  # FALLBACK
        return handle_fallback(question, snapshot, retrieved_chunks)
