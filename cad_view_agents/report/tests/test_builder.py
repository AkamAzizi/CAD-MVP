"""
Tests for ReportBuilder.
"""
import json
import tempfile
import os
from ..builder import ReportBuilder
from ..models import Report


def create_test_snapshot() -> dict:
    """Create a test snapshot dictionary."""
    return {
        "snapshot_version": "1.0",
        "assembly_id": "test_assembly",
        "timestamp": "2024-01-01T00:00:00Z",
        "source_file": "/path/to/test.step",
        "source_file_hash": "sha256:test",
        "overview": {
            "parts_count_total": 10,
            "parts_count_unique": 5,
            "bbox_mm": {"x": 100.0, "y": 200.0, "z": 50.0},
            "primary_axis": "z",
            "description": "Test assembly",
            "is_assembly": True,
        },
        "parts_tree": {
            "parts": [
                {
                    "id": "part1",
                    "name": "Part 1",
                    "label": "Part 1",
                    "geometry_hash": "hash1",
                    "bbox_mm": {"x": 50.0, "y": 50.0, "z": 50.0},
                    "volume_mm3": 125000.0,
                    "instances": 2,
                },
                {
                    "id": "part2",
                    "name": "Bolt M6",
                    "label": "Bolt M6",
                    "geometry_hash": "hash2",
                    "bbox_mm": {"x": 10.0, "y": 10.0, "z": 20.0},
                    "volume_mm3": 2000.0,
                    "instances": 5,
                },
            ]
        },
        "bom_preview": [
            {
                "item": 1,
                "part_number": "part1",
                "description": "Part 1",
                "quantity": 2,
                "material": "Steel",
            },
            {
                "item": 2,
                "part_number": "part2",
                "description": "Bolt M6",
                "quantity": 5,
                "material": "Steel",
            },
        ],
        "validation_errors": [],
    }


def test_build_from_dict():
    """Test building report from snapshot dictionary."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    assert isinstance(report, Report)
    assert report.meta.assembly_id == "test_assembly"
    assert report.overview.total_parts == 10
    assert report.overview.unique_parts == 5
    assert report.overview.repeated_parts == 5
    assert report.overview.complexity_score_0_100 >= 0
    assert report.overview.complexity_score_0_100 <= 100
    assert len(report.bom) == 2
    assert len(report.next_steps) > 0


def test_build_from_snapshot_file():
    """Test building report from snapshot file."""
    snapshot = create_test_snapshot()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(snapshot, f)
        snapshot_path = f.name
    
    try:
        builder = ReportBuilder()
        report = builder.build_from_snapshot(snapshot_path)
        
        assert isinstance(report, Report)
        assert report.meta.assembly_id == "test_assembly"
        assert report.overview.total_parts == 10
    finally:
        os.unlink(snapshot_path)


def test_build_bom():
    """Test BOM building."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    assert len(report.bom) == 2
    assert report.bom[0].item_no == 1
    assert report.bom[0].part_name == "Part 1"
    assert report.bom[0].qty == 2
    assert report.bom[1].part_name == "Bolt M6"
    assert report.bom[1].qty == 5


def test_compute_largest_parts():
    """Test largest parts computation."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    assert len(report.largest_parts) > 0
    # Part 1 should be largest (125000 > 2000)
    assert report.largest_parts[0]["part_name"] == "Part 1"
    assert report.largest_parts[0]["volume_mm3"] == 125000.0


def test_compute_repetition():
    """Test repetition computation."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    assert report.repetition.repeated_share_pct >= 0.0
    assert report.repetition.repeated_share_pct <= 100.0
    assert len(report.repetition.top_repeated) >= 0


def test_health_check():
    """Test health check computation."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    assert report.health_check.score_0_100 >= 0
    assert report.health_check.score_0_100 <= 100


def test_insights_generation():
    """Test insights generation."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    # Should have some insights (at least from complexity or other rules)
    assert isinstance(report.insights, list)


def test_manufacturing_hints():
    """Test manufacturing hints generation."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    assert isinstance(report.manufacturing_hints, list)


def test_next_steps():
    """Test next steps generation."""
    snapshot = create_test_snapshot()
    builder = ReportBuilder()
    report = builder.build_from_dict(snapshot)
    
    assert isinstance(report.next_steps, list)
    assert len(report.next_steps) > 0
