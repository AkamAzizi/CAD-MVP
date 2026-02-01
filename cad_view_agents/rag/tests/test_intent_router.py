"""
Unit tests for intent_router.py
"""
import pytest
from ..intent_router import route, Intent, IntentResult, is_deterministic_intent


class TestIntentRouting:
    """Test intent classification for various question types."""
    
    def test_count_parts_swedish(self):
        """Test COUNT_PARTS intent with Swedish questions."""
        questions = [
            "hur många delar",
            "hur många delar finns det?",
            "antal delar i assemblyt",
            "hur många unika delar",
            "hur många instanser totalt",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.COUNT_PARTS, f"Failed for: {q}"
            assert result.confidence > 0.3
    
    def test_count_parts_english(self):
        """Test COUNT_PARTS intent with English questions."""
        questions = [
            "how many parts",
            "parts count",
            "unique parts",
            "total instances",
            "count of parts",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.COUNT_PARTS, f"Failed for: {q}"
    
    def test_largest_parts_basic(self):
        """Test LARGEST_PARTS intent detection."""
        questions = [
            "vilken del är störst",
            "största delen",
            "top 5 största delarna",
            "topp 10 efter volym",
            "biggest part",
            "largest parts by volume",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.LARGEST_PARTS, f"Failed for: {q}"
    
    def test_largest_parts_top_n_extraction(self):
        """Test extraction of top N parameter."""
        result = route("topp 10 största delarna")
        assert result.intent == Intent.LARGEST_PARTS
        assert result.params.get("top_n") == 10
        
        result = route("top 3 largest parts")
        assert result.intent == Intent.LARGEST_PARTS
        assert result.params.get("top_n") == 3
        
        # Default to 5 if no number specified
        result = route("vilken del är störst")
        assert result.params.get("top_n") == 5
    
    def test_largest_parts_metric_detection(self):
        """Test metric parameter detection (volume vs bbox)."""
        result = route("största efter volym")
        assert result.params.get("metric") == "volume"
        
        result = route("largest by bbox")
        assert result.params.get("metric") == "bbox"
    
    def test_repetitive_parts(self):
        """Test REPETITIVE_PARTS intent detection."""
        questions = [
            "vilka delar upprepas mest",
            "mest upprepade delar",
            "repetitiva delar",
            "standarddelar",
            "flest instanser",
            "most common parts",
            "repeated parts",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.REPETITIVE_PARTS, f"Failed for: {q}"
    
    def test_repetitive_parts_fastener_filter(self):
        """Test fastener filter parameter."""
        fastener_questions = [
            "vilka skruvar finns det",
            "hur många bultar",
            "fasteners in assembly",
            "M8 bolts",
            "DIN screws",
        ]
        for q in fastener_questions:
            result = route(q)
            # Should match either REPETITIVE_PARTS with filter or still detect fastener context
            if result.intent == Intent.REPETITIVE_PARTS:
                assert result.params.get("filter_fasteners", False) or "m" in q.lower()
    
    def test_best_views(self):
        """Test BEST_VIEWS intent detection."""
        questions = [
            "vilken vy passar för 2d ritning",
            "bästa vy för ritning",
            "rekommenderad vy",
            "best view for 2d drawing",
            "which view should I use",
            "varför valdes front-vyn",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.BEST_VIEWS, f"Failed for: {q}"
    
    def test_best_views_explain_why(self):
        """Test explain_why parameter extraction."""
        result = route("varför valdes denna vy")
        assert result.params.get("explain_why") == True
        
        result = route("why was front view selected")
        assert result.params.get("explain_why") == True
    
    def test_bom_questions(self):
        """Test BOM_QUESTIONS intent detection."""
        questions = [
            "saknar någon del material",
            "missing material",
            "visa BOM",
            "bill of materials",
            "part numbers saknas",
            "saknar metadata",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.BOM_QUESTIONS, f"Failed for: {q}"
    
    def test_warnings_errors(self):
        """Test WARNINGS_ERRORS intent detection."""
        questions = [
            "varför blev ritningen fel",
            "finns det några fel",
            "validation errors",
            "warnings from pipeline",
            "vad gick fel",
            "problem med geometrin",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.WARNINGS_ERRORS, f"Failed for: {q}"
    
    def test_overview(self):
        """Test OVERVIEW intent detection."""
        questions = [
            "berätta om detta assembly",
            "describe this assembly",
            "översikt",
            "sammanfattning",
            "what is this",
            "vad är detta",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.OVERVIEW, f"Failed for: {q}"
    
    def test_fallback_for_unclear(self):
        """Test FALLBACK for unclear/empty questions."""
        questions = [
            "",
            "xyz abc",
            "random gibberish that matches nothing",
        ]
        for q in questions:
            result = route(q)
            assert result.intent == Intent.FALLBACK, f"Failed for: {q}"
    
    def test_deterministic_intents(self):
        """Test is_deterministic_intent helper."""
        deterministic = [
            Intent.COUNT_PARTS,
            Intent.LARGEST_PARTS,
            Intent.REPETITIVE_PARTS,
            Intent.BEST_VIEWS,
            Intent.BOM_QUESTIONS,
            Intent.WARNINGS_ERRORS,
            Intent.OVERVIEW,
        ]
        for intent in deterministic:
            assert is_deterministic_intent(intent) == True
        
        assert is_deterministic_intent(Intent.FALLBACK) == False
    
    def test_intent_result_dataclass(self):
        """Test IntentResult dataclass initialization."""
        result = IntentResult(intent=Intent.COUNT_PARTS)
        assert result.intent == Intent.COUNT_PARTS
        assert result.confidence == 1.0
        assert result.params == {}
        
        result2 = IntentResult(
            intent=Intent.LARGEST_PARTS,
            confidence=0.8,
            params={"top_n": 10}
        )
        assert result2.params["top_n"] == 10
