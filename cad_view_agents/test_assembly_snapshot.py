"""
Unit tests for Assembly Snapshot (no FreeCAD required).
"""
import json
import os
import tempfile
from unittest.mock import MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.assembly_snapshot import build_snapshot, save_snapshot, to_markdown


def _mock_part_node(pid, name, geometry_hash, freecad_obj=None):
    n = MagicMock()
    n.id = pid
    n.name = name
    n.geometry_hash = geometry_hash
    n.freecad_obj = freecad_obj
    n.metadata = {"label": name}
    return n


def _mock_part_tree(parts_list):
    tree = MagicMock()
    tree.get_part_list.return_value = parts_list
    tree.get_part_count.return_value = len(parts_list)
    def get_by_id(pid):
        for p in parts_list:
            if p.id == pid:
                return p
        return None
    tree.get_part_by_id.side_effect = get_by_id
    return tree


def _mock_bom_metadata(parts_list):
    class PartMeta:
        def __init__(self, part_id, item_number, name, quantity, material="N/A"):
            self.part_id = part_id
            self.item_number = item_number
            self.name = name
            self.quantity = quantity
            self.material = material
    return [PartMeta(p.id, i + 1, p.name, 1) for i, p in enumerate(parts_list)]


def test_build_snapshot_minimal():
    step_path = "/tmp/test.step"
    import_result = {"doc": None, "parts_count": 2, "bbox": {"x": 100, "y": 50, "z": 30}}
    parts = [
        _mock_part_node("PART_1", "Part1", "abc"),
        _mock_part_node("PART_2", "Part2", "def"),
    ]
    part_tree = _mock_part_tree(parts)
    bom_metadata = _mock_bom_metadata(parts)
    analysis = {
        "description": "Assembly with 2 parts",
        "primary_axis": "x",
        "aspect_ratios": {},
        "is_assembly": True,
    }
    view_candidate = MagicMock()
    view_candidate.name = "front"
    selected_views = [(view_candidate, 0.85)]
    layout_engine = MagicMock()
    layout_engine.sheet_size = MagicMock()
    layout_engine.sheet_size.name = "A4"
    layout_engine.scale = 1.0
    artifacts = ["/out/model.pdf", "/out/model.json"]
    trace = []
    qa_result = {"status": "pass", "issues": []}
    export_errors = []

    snapshot = build_snapshot(
        step_path,
        import_result,
        part_tree,
        analysis,
        bom_metadata,
        selected_views,
        layout_engine,
        artifacts,
        trace,
        qa_result,
        export_errors,
    )
    assert snapshot["snapshot_version"] == "1.0"
    assert "assembly_id" in snapshot
    assert snapshot["overview"]["parts_count_total"] == 2
    assert snapshot["overview"]["parts_count_unique"] == 2
    assert len(snapshot["parts_tree"]["parts"]) == 2
    assert len(snapshot["bom_preview"]) == 2
    assert snapshot["pipeline_artifacts"]["sheet_size"] == "A4"
    assert snapshot["validation_errors"] == []


def test_save_snapshot():
    snapshot = {
        "snapshot_version": "1.0",
        "assembly_id": "asm_test_abc12345",
        "timestamp": "2025-01-29T12:00:00Z",
        "source_file": "/tmp/x.step",
        "source_file_hash": "sha256:abc",
        "overview": {"parts_count_total": 1, "parts_count_unique": 1},
        "parts_tree": {"parts": []},
        "bom_preview": [],
        "orientation_heuristics": {"view_recommendations": []},
        "pipeline_artifacts": {},
        "validation_errors": [],
    }
    with tempfile.TemporaryDirectory() as d:
        paths = save_snapshot(snapshot, d)
        assert len(paths) == 2
        json_path = [p for p in paths if p.endswith(".json")][0]
        md_path = [p for p in paths if p.endswith(".md")][0]
        assert os.path.isfile(json_path)
        assert os.path.isfile(md_path)
        with open(json_path) as f:
            loaded = json.load(f)
        assert loaded["assembly_id"] == "asm_test_abc12345"
        md_content = open(md_path).read()
        assert "Assembly Snapshot" in md_content
        assert "asm_test_abc12345" in md_content


def test_to_markdown():
    snapshot = {
        "assembly_id": "asm_x",
        "timestamp": "2025-01-29T12:00:00Z",
        "source_file": "/path/to/file.step",
        "overview": {"parts_count_total": 2, "parts_count_unique": 2, "description": "Test"},
        "parts_tree": {"parts": [{"id": "P1", "name": "Part1", "instances": 1}]},
        "bom_preview": [{"item": 1, "part_number": "P1", "description": "Part1", "quantity": 1, "material": "N/A"}],
        "orientation_heuristics": {"view_recommendations": []},
        "pipeline_artifacts": {"sheet_size": "A4", "scale": 1.0, "selected_views": []},
        "validation_errors": [],
    }
    md = to_markdown(snapshot)
    assert "# Assembly Snapshot" in md
    assert "Total parts: 2" in md
    assert "Part1" in md


if __name__ == "__main__":
    test_build_snapshot_minimal()
    test_save_snapshot()
    test_to_markdown()
    print("All tests passed.")
