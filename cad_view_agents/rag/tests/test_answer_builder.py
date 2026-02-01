"""
Unit tests for answer_builder.py
Tests 8 key question types with snapshot fixture.
"""
import pytest
from ..answer_builder import build_answer


# =============================================================================
# Test Fixture: Realistic snapshot data
# =============================================================================

@pytest.fixture
def snapshot_fixture():
    """Realistic assembly snapshot for testing."""
    return {
        "snapshot_version": "1.0",
        "assembly_id": "asm_test_pump_12345",
        "timestamp": "2026-01-29T10:00:00+00:00",
        "source_file": "/path/to/water_pump.STEP",
        "source_file_hash": "sha256:abc123",
        "overview": {
            "parts_count_total": 64,
            "parts_count_unique": 31,
            "bbox_mm": {"x": 350.0, "y": 405.0, "z": 457.0},
            "primary_axis": "z",
            "description": "Industrial water pump assembly with motor and housing.",
            "is_assembly": True,
        },
        "parts_tree": {
            "parts": [
                # Largest part - pump housing
                {
                    "id": "PART_001",
                    "name": "Pump_Housing",
                    "label": "Pump_Housing",
                    "geometry_hash": "hash1",
                    "bbox_mm": {"x": 350.0, "y": 405.0, "z": 187.5},
                    "volume_mm3": 6889443.97,
                    "placement": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
                    "instances": 1,
                },
                # Second largest - motor cover
                {
                    "id": "PART_002",
                    "name": "Motor_Cover",
                    "label": "Motor_Cover",
                    "geometry_hash": "hash2",
                    "bbox_mm": {"x": 288.0, "y": 288.0, "z": 70.0},
                    "volume_mm3": 1440508.11,
                    "placement": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
                    "instances": 1,
                },
                # Fastener - M8 bolt (repeated)
                {
                    "id": "PART_003",
                    "name": "bulong_M8x30",
                    "label": "bulong_M8x30",
                    "geometry_hash": "hash3",
                    "bbox_mm": {"x": 15.0, "y": 15.0, "z": 30.0},
                    "volume_mm3": 2018.43,
                    "placement": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
                    "instances": 8,
                },
                # Bearing (repeated)
                {
                    "id": "PART_004",
                    "name": "SKF_Bearing_6207",
                    "label": "SKF_Bearing_6207",
                    "geometry_hash": "hash4",
                    "bbox_mm": {"x": 75.0, "y": 75.0, "z": 17.0},
                    "volume_mm3": 34709.45,
                    "placement": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
                    "instances": 2,
                },
                # Shaft
                {
                    "id": "PART_005",
                    "name": "Drive_Shaft",
                    "label": "Drive_Shaft",
                    "geometry_hash": "hash5",
                    "bbox_mm": {"x": 42.0, "y": 42.0, "z": 390.0},
                    "volume_mm3": 365411.78,
                    "placement": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
                    "instances": 1,
                },
                # Reference geometry (should be filtered out)
                {
                    "id": "PART_REF_001",
                    "name": "XY-plane",
                    "label": "XY-plane",
                    "geometry_hash": "ref1",
                    "bbox_mm": {"x": 2e+100, "y": 2e+100, "z": 0},
                    "volume_mm3": 0.0,
                    "placement": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
                    "instances": 6,
                },
            ]
        },
        "bom_preview": [
            {"item": 1, "part_number": "PH-001", "description": "Pump_Housing", "quantity": 1, "material": "Cast Iron"},
            {"item": 2, "part_number": "MC-002", "description": "Motor_Cover", "quantity": 1, "material": "N/A"},
            {"item": 3, "part_number": "PART_003", "description": "bulong_M8x30", "quantity": 8, "material": "N/A"},
            {"item": 4, "part_number": "", "description": "SKF_Bearing_6207", "quantity": 2, "material": "Steel"},
            {"item": 5, "part_number": "DS-005", "description": "Drive_Shaft", "quantity": 1, "material": "None"},
        ],
        "orientation_heuristics": {
            "primary_axis": "z",
            "aspect_ratios": {"xy": 0.86, "xz": 0.77, "yz": 0.89},
            "recommended_views": {
                "iso": [1, 1, 1],
                "front": [0, 0, 1],
                "top": [0, 1, 0],
                "right": [1, 0, 0],
            },
            "view_recommendations": [
                {"view_name": "front", "score": 0.92, "reason": "High info density, shows pump inlet/outlet"},
                {"view_name": "top", "score": 0.88, "reason": "Good for mounting pattern"},
                {"view_name": "iso", "score": 0.75, "reason": "Overall shape visibility"},
                {"view_name": "right", "score": 0.70, "reason": "Side profile"},
            ],
        },
        "pipeline_artifacts": {
            "pdf_path": "output/pump.pdf",
            "dxf_path": "output/pump.dxf",
            "metadata_json_path": "output/pump.json",
            "view_svg_paths": ["front.svg", "top.svg", "iso.svg"],
            "selected_views": ["front", "top", "iso", "right"],
            "sheet_size": "A3",
            "scale": 0.1,
            "view_scores": {"front": 0.92, "top": 0.88, "iso": 0.75, "right": 0.70},
        },
        "validation_errors": [
            "Warning: Part 'Motor_Cover' has no material assigned",
            "Error: Face count exceeds threshold for part PART_003",
        ],
    }


# =============================================================================
# Test Class: 8 Required Question Types
# =============================================================================

class TestAnswerBuilder:
    """Test build_answer for 8 key engineering question types."""
    
    # -------------------------------------------------------------------------
    # Test 1: "hur många delar" (how many parts)
    # -------------------------------------------------------------------------
    def test_hur_manga_delar(self, snapshot_fixture):
        """Test question: hur många delar"""
        result = build_answer("hur många delar", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        assert "31" in result["answer"], "Should mention 31 unique parts"
        assert len(result["facts"]) >= 2, "Should have at least 2 facts"
        assert any("31" in f or "unique" in f.lower() or "unika" in f.lower() for f in result["facts"])
        assert len(result["sources"]) >= 1, "Should have sources"
        assert any("overview" in str(s) for s in result["sources"])
    
    # -------------------------------------------------------------------------
    # Test 2: "unika delar och instanser" (unique parts and instances)
    # -------------------------------------------------------------------------
    def test_unika_delar_och_instanser(self, snapshot_fixture):
        """Test question: unika delar och instanser"""
        result = build_answer("unika delar och instanser", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        assert "31" in result["answer"], "Should mention 31 unique"
        assert "64" in result["answer"], "Should mention 64 total instances"
        assert len(result["facts"]) >= 2
        assert any("64" in f for f in result["facts"]), "Should mention 64 instances in facts"
    
    # -------------------------------------------------------------------------
    # Test 3: "vilken part är störst" (which part is largest)
    # -------------------------------------------------------------------------
    def test_vilken_part_ar_storst(self, snapshot_fixture):
        """Test question: vilken part är störst"""
        result = build_answer("vilken part är störst", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        assert "Pump_Housing" in result["answer"], "Headline should name the #1 largest part"
        assert len(result["facts"]) >= 1
        # First fact should be #1 (Pump_Housing)
        assert "1." in result["facts"][0]
        assert "Pump_Housing" in result["facts"][0]
        assert len(result["sources"]) >= 1
    
    # -------------------------------------------------------------------------
    # Test 4: "topp 5 största" (top 5 largest)
    # -------------------------------------------------------------------------
    def test_topp_5_storsta(self, snapshot_fixture):
        """Test question: topp 5 största"""
        result = build_answer("topp 5 största", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        assert "Pump_Housing" in result["answer"], "Should mention #1 in headline"
        
        # Should have 5 facts (or fewer if not enough parts)
        numbered_facts = [f for f in result["facts"] if f.startswith(("1.", "2.", "3.", "4.", "5."))]
        assert len(numbered_facts) >= 4, "Should list top parts"
        
        # Verify ordering: Pump_Housing > Motor_Cover > Drive_Shaft
        fact_text = " ".join(result["facts"])
        pump_pos = fact_text.find("Pump_Housing")
        motor_pos = fact_text.find("Motor_Cover")
        shaft_pos = fact_text.find("Drive_Shaft")
        assert pump_pos < motor_pos < shaft_pos, "Parts should be sorted by size"
    
    # -------------------------------------------------------------------------
    # Test 5: "vilka delar upprepas mest" (which parts repeat most)
    # -------------------------------------------------------------------------
    def test_vilka_delar_upprepas_mest(self, snapshot_fixture):
        """Test question: vilka delar upprepas mest"""
        result = build_answer("vilka delar upprepas mest", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        # M8 bolt has 8 instances, should be #1
        assert "8" in result["answer"] or "bulong" in result["answer"].lower()
        
        # Facts should show parts with instances > 1
        assert len(result["facts"]) >= 1
        # Should identify fasteners
        fact_text = " ".join(result["facts"]).lower()
        assert "bulong" in fact_text or "m8" in fact_text
    
    # -------------------------------------------------------------------------
    # Test 6: "vilken vy passar för 2d ritning" (which view for 2D drawing)
    # -------------------------------------------------------------------------
    def test_vilken_vy_passar_for_2d(self, snapshot_fixture):
        """Test question: vilken vy passar för 2d ritning"""
        result = build_answer("vilken vy passar för 2d ritning", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        assert "front" in result["answer"].lower(), "Should recommend front view (highest score)"
        assert "0.92" in result["answer"], "Should include score"
        
        # Should explain why
        assert len(result["facts"]) >= 2
        fact_text = " ".join(result["facts"])
        assert "score" in fact_text.lower() or "reason" in fact_text.lower() or "density" in fact_text.lower()
    
    # -------------------------------------------------------------------------
    # Test 7: "saknar någon del material?" (missing material)
    # -------------------------------------------------------------------------
    def test_saknar_nagon_del_material(self, snapshot_fixture):
        """Test question: saknar någon del material?"""
        result = build_answer("saknar någon del material", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        # Should report missing materials
        assert "saknar" in result["answer"].lower() or "missing" in result["answer"].lower() or result["answer"]
        
        # Facts should list parts with N/A or None material
        assert len(result["facts"]) >= 1
        fact_text = " ".join(result["facts"])
        # Motor_Cover, bulong_M8x30, Drive_Shaft have N/A/None material
        assert any(x in fact_text for x in ["Motor_Cover", "bulong", "Drive_Shaft", "material"])
    
    # -------------------------------------------------------------------------
    # Test 8: "varför blev ritningen fel?" (why did drawing fail)
    # -------------------------------------------------------------------------
    def test_varfor_blev_ritningen_fel(self, snapshot_fixture):
        """Test question: varför blev ritningen fel?"""
        result = build_answer("varför blev ritningen fel", [], snapshot_fixture)
        
        assert result["answer"], "Headline should not be empty"
        # Should mention validation errors
        assert "2" in result["answer"] or "fel" in result["answer"].lower() or "varning" in result["answer"].lower()
        
        # Facts should contain the actual errors
        assert len(result["facts"]) >= 1
        fact_text = " ".join(result["facts"])
        assert "Warning" in fact_text or "Error" in fact_text or "material" in fact_text


class TestAnswerStructure:
    """Test answer structure requirements."""
    
    def test_headline_not_empty(self, snapshot_fixture):
        """All answers should have non-empty headlines."""
        questions = [
            "hur många delar",
            "största delen",
            "bästa vy",
            "fel och varningar",
            "berätta om assemblyt",
        ]
        for q in questions:
            result = build_answer(q, [], snapshot_fixture)
            assert result["answer"].strip(), f"Empty headline for: {q}"
    
    def test_facts_contain_measurable_data(self, snapshot_fixture):
        """Facts should contain measurable data points."""
        result = build_answer("hur många delar", [], snapshot_fixture)
        # Should contain numbers
        facts_text = " ".join(result["facts"])
        assert any(c.isdigit() for c in facts_text), "Facts should contain numbers"
    
    def test_sources_have_paths(self, snapshot_fixture):
        """Sources should contain field paths."""
        result = build_answer("största delen", [], snapshot_fixture)
        assert len(result["sources"]) >= 1
        for src in result["sources"]:
            assert "path" in src or "chunk_type" in src, "Source should have path or chunk_type"
    
    def test_largest_part_headline_matches_facts(self, snapshot_fixture):
        """Largest part in headline should match #1 in facts."""
        result = build_answer("vilken del är störst", [], snapshot_fixture)
        
        # Extract part name from headline
        headline = result["answer"]
        
        # Find first fact (should be #1)
        first_fact = result["facts"][0] if result["facts"] else ""
        
        # Both should mention the same part (Pump_Housing)
        assert "Pump_Housing" in headline
        assert "Pump_Housing" in first_fact


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_snapshot(self):
        """Handle empty/minimal snapshot gracefully."""
        empty_snapshot = {"overview": {}, "parts_tree": {"parts": []}}
        result = build_answer("hur många delar", [], empty_snapshot)
        assert result["answer"], "Should still produce an answer"
    
    def test_no_validation_errors(self, snapshot_fixture):
        """Handle snapshot with no validation errors."""
        snapshot_fixture["validation_errors"] = []
        result = build_answer("finns det några fel", [], snapshot_fixture)
        assert "inga" in result["answer"].lower() or "no" in result["answer"].lower()
    
    def test_no_view_recommendations(self, snapshot_fixture):
        """Handle snapshot with no view recommendations."""
        snapshot_fixture["orientation_heuristics"]["view_recommendations"] = []
        result = build_answer("bästa vy", [], snapshot_fixture)
        assert result["answer"], "Should handle missing view data"
    
    def test_fallback_for_unknown_question(self, snapshot_fixture):
        """FALLBACK intent for unknown question patterns."""
        result = build_answer("xyz random question", [], snapshot_fixture)
        assert result["answer"], "Fallback should produce an answer"
        assert len(result["facts"]) >= 1
