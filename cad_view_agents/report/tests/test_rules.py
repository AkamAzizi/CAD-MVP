"""
Tests for rules engine.
"""
import pytest
from ..models import BOMItem, Report, ReportMeta, ReportOverview, RepetitionData, HealthCheck, BBoxMM
from ..rules import (
    check_high_fastener_count,
    check_fastener_variety,
    check_complexity,
    check_repetition_opportunity,
    check_size_extremes,
    generate_insights,
)


def test_check_high_fastener_count_below_threshold():
    """Test high fastener count check when below threshold."""
    bom = [
        BOMItem(item_no=1, part_name="Bolt M6", qty=5, material="Steel"),
        BOMItem(item_no=2, part_name="Screw M4", qty=10, material="Steel"),
    ]
    insight = check_high_fastener_count(bom, threshold=20)
    assert insight is None


def test_check_high_fastener_count_above_threshold():
    """Test high fastener count check when above threshold."""
    bom = [
        BOMItem(item_no=1, part_name="Bolt M6", qty=15, material="Steel"),
        BOMItem(item_no=2, part_name="Screw M4", qty=10, material="Steel"),
    ]
    insight = check_high_fastener_count(bom, threshold=20)
    assert insight is not None
    assert insight.severity == "warn"
    assert "fastener" in insight.title.lower() or "fastener" in insight.details.lower()
    assert insight.evidence["fastener_count"] == 25


def test_check_fastener_variety_below_threshold():
    """Test fastener variety check when below threshold."""
    bom = [
        BOMItem(item_no=1, part_name="Bolt M6", qty=5, material="Steel"),
        BOMItem(item_no=2, part_name="Screw M4", qty=10, material="Steel"),
    ]
    insight = check_fastener_variety(bom, threshold=5)
    assert insight is None


def test_check_fastener_variety_above_threshold():
    """Test fastener variety check when above threshold."""
    bom = [
        BOMItem(item_no=1, part_name="Bolt M6", qty=5, material="Steel"),
        BOMItem(item_no=2, part_name="Screw M4", qty=10, material="Steel"),
        BOMItem(item_no=3, part_name="Washer", qty=5, material="Steel"),
        BOMItem(item_no=4, part_name="Nut M6", qty=5, material="Steel"),
        BOMItem(item_no=5, part_name="Rivet", qty=5, material="Steel"),
        BOMItem(item_no=6, part_name="Pin", qty=5, material="Steel"),
    ]
    insight = check_fastener_variety(bom, threshold=5)
    assert insight is not None
    assert insight.severity == "warn"
    assert insight.evidence["unique_fastener_count"] == 6


def test_check_complexity_low():
    """Test complexity check with low complexity."""
    insight = check_complexity(30, threshold=70)
    assert insight is None


def test_check_complexity_medium():
    """Test complexity check with medium complexity."""
    insight = check_complexity(60, threshold=70)
    assert insight is not None
    assert insight.severity == "info"


def test_check_complexity_high():
    """Test complexity check with high complexity."""
    insight = check_complexity(80, threshold=70)
    assert insight is not None
    assert insight.severity == "risk"
    assert insight.evidence["complexity_score"] == 80


def test_check_repetition_opportunity_no_repetition():
    """Test repetition opportunity check with no repetition."""
    repetition = RepetitionData(top_repeated=[], repeated_share_pct=0.0)
    insight = check_repetition_opportunity(repetition.dict(), min_qty=3)
    assert insight is None


def test_check_repetition_opportunity_with_repetition():
    """Test repetition opportunity check with repetition."""
    repetition = RepetitionData(
        top_repeated=[
            {"part_name": "Part A", "qty": 5},
            {"part_name": "Part B", "qty": 3},
        ],
        repeated_share_pct=40.0,
    )
    insight = check_repetition_opportunity(repetition.dict(), min_qty=3)
    assert insight is not None
    assert insight.severity == "info"
    assert "Part A" in insight.details


def test_check_size_extremes_no_dominance():
    """Test size extremes check with no dominance."""
    parts = [
        {"part_name": "Part A", "volume_mm3": 1000},
        {"part_name": "Part B", "volume_mm3": 1000},
        {"part_name": "Part C", "volume_mm3": 1000},
    ]
    insight = check_size_extremes(parts, volume_threshold_ratio=0.5)
    assert insight is None or insight.severity == "warn"  # May detect small parts


def test_check_size_extremes_with_dominance():
    """Test size extremes check with volume dominance."""
    parts = [
        {"part_name": "Large Part", "volume_mm3": 1000000},
        {"part_name": "Small Part", "volume_mm3": 1000},
        {"part_name": "Tiny Part", "volume_mm3": 100},
    ]
    insight = check_size_extremes(parts, volume_threshold_ratio=0.5)
    assert insight is not None
    assert insight.severity in ["info", "warn"]
    assert "Large Part" in insight.details or "dominance" in insight.title.lower()


def test_generate_insights():
    """Test generate_insights function."""
    report = Report(
        meta=ReportMeta(
            assembly_id="test",
            file_name="test.step",
            generated_at_iso="2024-01-01T00:00:00",
            version="1.0",
            source_snapshot_path="test.json",
        ),
        overview=ReportOverview(
            total_parts=100,
            unique_parts=50,
            repeated_parts=50,
            bbox_mm=None,
            complexity_score_0_100=80,
        ),
        bom=[
            BOMItem(item_no=1, part_name="Bolt M6", qty=30, material="Steel", category="fastener"),
            BOMItem(item_no=2, part_name="Screw M4", qty=20, material="Steel", category="fastener"),
        ],
        largest_parts=[],
        repetition=RepetitionData(
            top_repeated=[{"part_name": "Part A", "qty": 10}],
            repeated_share_pct=50.0,
        ),
        insights=[],
        manufacturing_hints=[],
        health_check=HealthCheck(score_0_100=70, warnings=[]),
        next_steps=[],
    )
    
    insights = generate_insights(report)
    assert len(insights) > 0
    # Should have at least complexity insight (high complexity)
    assert any(i.severity == "risk" for i in insights)
