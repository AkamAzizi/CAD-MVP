"""
Intent Router: Classifies questions into engineering-focused intents for deterministic answers.

Intents (Tier 1 - Core):
- COUNT_PARTS: how many parts, unique vs instances
- LARGEST_PARTS: biggest part, top N by volume/bbox
- REPETITIVE_PARTS: most repeated parts, fasteners, standard parts
- BEST_VIEWS: which view for 2D, why, view selection reasoning

Intents (Tier 2 - BOM & Production):
- BOM_QUESTIONS: BOM, missing part_number/material/description
- DETAIL_DRAWINGS: which parts need detail drawings, outer dimensions

Intents (Tier 3 - Geometry & Quality):
- GEOMETRY_ANALYSIS: aspect ratio, extreme geometry, reference geometry, small parts, scale outliers
- WARNINGS_ERRORS: errors, warnings, validation issues, QA

Intents (Tier 4 - Structure Analysis):
- STRUCTURE_ANALYSIS: main axis parts, symmetry, nested parts, sub-assemblies, critical parts

Intents (Tier 5 - Engineer Copilot):
- ENGINEER_COPILOT: next steps, missing views, tolerances, dimensioning recommendations

Other:
- OVERVIEW: general assembly overview
- FALLBACK: unclear → use retrieval + generic structured answer
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import re


class Intent(str, Enum):
    # Tier 1 - Core
    COUNT_PARTS = "count_parts"
    LARGEST_PARTS = "largest_parts"
    REPETITIVE_PARTS = "repetitive_parts"
    BEST_VIEWS = "best_views"
    
    # Tier 2 - BOM & Production
    BOM_QUESTIONS = "bom_questions"
    DETAIL_DRAWINGS = "detail_drawings"
    
    # Tier 3 - Geometry & Quality
    GEOMETRY_ANALYSIS = "geometry_analysis"
    WARNINGS_ERRORS = "warnings_errors"
    
    # Tier 4 - Structure Analysis
    STRUCTURE_ANALYSIS = "structure_analysis"
    
    # Tier 5 - Engineer Copilot
    ENGINEER_COPILOT = "engineer_copilot"
    
    # Other
    OVERVIEW = "overview"
    FALLBACK = "fallback"


@dataclass
class IntentResult:
    """Result of intent classification with optional parameters."""
    intent: Intent
    confidence: float = 1.0
    params: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}


# Keyword patterns for each intent (Swedish + English)
_INTENT_PATTERNS: Dict[Intent, List[str]] = {
    # =========================================================================
    # Tier 1 - Core demo questions
    # =========================================================================
    Intent.COUNT_PARTS: [
        r"\bhur\s+många\b",
        r"\bantal\b",
        r"\bmånga\s+delar\b",
        r"\bunique\b",
        r"\bunika\b",
        r"\binstans\b",
        r"\binstance\b",
        r"\btotal\s+parts?\b",
        r"\bparts?\s+count\b",
        r"\bcount\s+(of\s+)?parts?\b",
        r"\bhow\s+many\s+parts?\b",
        r"\bfinns\s+i\s+monteringen\b",
    ],
    Intent.LARGEST_PARTS: [
        r"\bstörst\b",
        r"\bstörsta\b",
        r"\bbiggest\b",
        r"\blargest\b",
        r"\btopp\s*\d*\b",
        r"\btop\s*\d*\b",
        r"\bvolym\b",
        r"\bvolume\b",
        r"\bbbox\b",
        r"\bstorlek\b",
        r"\bsize\b",
        r"\bheaviest\b",
        r"\btungst\b",
    ],
    Intent.REPETITIVE_PARTS: [
        r"\bupprepas\b",
        r"\brepeat(s|ed)?\b",  # repeat, repeats, repeated
        r"\brepetitiv\b",
        r"\brepetitive\b",
        r"\bparts?\s+repeat\s+the\s+most\b",
        r"\brepeat\s+the\s+most\b",
        r"\bmost\s+repeated\b",
        r"\bstandard\s*del(ar)?\b",
        r"\bstandard\s*part\b",
        r"\bfastener\b",
        r"\bfästelement\b",
        r"\bskruv\b",
        r"\bscrew\b",
        r"\bbolt\b",
        r"\bbulong\b",
        r"\bnut\b",
        r"\bmutter\b",
        r"\bwasher\b",
        r"\bbricka\b",
        r"\bdin\b",
        r"\biso\b",
        r"\bm\d+\b",  # M8, M10, etc.
        r"\bflest\s+(gånger|instanser)\b",
        r"\bmost\s+instances\b",
        r"\bmost\s+common\b",
        r"\bvanligast\b",
        r"\bförekommer\s+flest\b",
    ],
    Intent.BEST_VIEWS: [
        r"\bbästa\s+vy\b",
        r"\bbest\s+view\b",
        r"\brekommenderad\s+vy\b",
        r"\brecommended\s+view\b",
        r"\b2d\s*ritning\b",
        r"\b2d\s*drawing\b",
        r"\bvilken\s+vy\b",
        r"\bwhich\s+view\b",
        r"\bview\s+selection\b",
        r"\bvy\s+val\b",
        r"\bvy.*passar\b",
        r"\bvyer\s+bör\s+ingå\b",
        r"\bviews\s+should\b",
        r"\bhuvudritning\b",
        r"\bmain\s+drawing\b",
        r"\bvarför.*front\b",
        r"\bwhy.*front\b",
        r"\bdolda\s+kant\b",
        r"\bhidden\s+line\b",
        r"\bhidden\s+edge\b",
        r"\bminimera.*dolda\b",
    ],
    
    # =========================================================================
    # Tier 2 - BOM & Production
    # =========================================================================
    Intent.BOM_QUESTIONS: [
        r"\bbom\b",
        r"\bbill\s+of\s+materials?\b",
        r"\bmaterial\s*lista\b",
        r"\bsaknar.*material\b",
        r"\bmissing.*materials?\b",  # "missing material" or "missing materials"
        r"\bany.*missing.*material",  # "Are there any missing materials?"
        r"\b(any|some)\s+missing\s+material",
        r"\bpart\s*number\b",
        r"\bart\.?\s*nr\b",
        r"\bsaknar.*part\s*number\b",
        r"\bmissing.*part\s*number\b",
        r"\bsaknar\s+metadata\b",
        r"\bmissing\s+metadata\b",
        r"\bdescription\s+saknas\b",
        r"\bsaknas\s+beskrivning\b",
        r"\bsaknar.*beskrivning\b",
        r"\bn/a\b",
        r"\bmaterial\s*saknas\b",
        r"\bvilka\s+delar.*material\b",
        r"\butan\s+material\b",
    ],
    Intent.DETAIL_DRAWINGS: [
        r"\bdetaljritning(ar)?\b",
        r"\bdetail\s+drawing\b",
        r"\begna\s+(detalj)?ritningar\b",
        r"\bown\s+drawing\b",
        r"\bytterdimension\b",
        r"\bouter\s+dimension\b",
        r"\bexternal\s+dimension\b",
        r"\bpåverkar.*dimension\b",
        r"\baffect.*dimension\b",
        r"\bbör\s+dimensioneras\b",
        r"\bshould\s+be\s+dimensioned\b",
        r"\bkan\s+ignoreras\b",
        r"\bcan\s+be\s+ignored\b",
        r"\bförsta\s+ritningsversion\b",
        r"\bfirst\s+drawing\s+version\b",
        r"\bdelar\s+bör.*ritning\b",  # "vilka delar bör få ritningar"
        r"\bparts?\s+need.*drawing\b",
        r"\bpåverkar.*ytterdimension",  # "påverkar ytterdimensionen"
        r"\bytterdimension",
        r"\baffects?\s+outer\b",
    ],
    
    # =========================================================================
    # Tier 3 - Geometry & Quality
    # =========================================================================
    Intent.GEOMETRY_ANALYSIS: [
        # Aspect ratio / proportions
        r"\blång\s+(än|eller)\s+hög\b",
        r"\bhög\s+(än|eller)\s+bred\b",
        r"\bbred\s+(än|eller)\b",
        r"\blonger\s+than\b",
        r"\btaller\s+than\b",
        r"\bwider\s+than\b",
        r"\baspect\s*ratio\b",
        r"\bproportioner\b",
        r"\bproportions\b",
        r"\borientering\b",
        r"\borientation\b",
        # Extreme / suspicious geometry
        r"\bextrem(a|e)?\b",
        r"\bextreme\b",
        r"\bmisstänkt(a|e)?\b",
        r"\bsuspicious\b",
        r"\bovanlig(a|t)?\b",
        r"\bunusual\b",
        r"\bextrem.*geometri\b",
        r"\bmisstänkt.*geometri\b",
        # Reference geometry
        r"\breferensgeometri\b",
        r"\breference\s+geometry\b",
        r"\bverkar\s+vara\s+referens\b",
        # Small parts / scale issues
        r"\bsmå\s+delar\b",
        r"\bsmall\s+parts?\b",
        r"\britningsproblem\b",
        r"\bdrawing\s+problem\b",
        r"\bskala\b",
        r"\bscale\b",
        r"\bavviker.*skala\b",
        r"\bscale\s+outlier\b",
    ],
    Intent.WARNINGS_ERRORS: [
        r"\bfel\b",
        r"\berror\b",
        r"\bvarning(ar)?\b",
        r"\bwarning\b",
        r"\bproblem\b",
        r"\bissue\b",
        r"\bvarför\s+blev\b",
        r"\bwhy\s+did\b",
        r"\bwhat\s+went\s+wrong\b",
        r"\bvad\s+gick\s+fel\b",
        r"\binvalid\b",
        r"\bvalidering\b",
        r"\bvalidation\b",
        r"\bgeometry\s*error\b",
        r"\bgeometri\s*fel\b",
        r"\bqa[\s-]*issue\b",
        r"\bkvalitet\b",
        r"\bquality\b",
    ],
    
    # =========================================================================
    # Tier 4 - Structure Analysis (Advanced)
    # =========================================================================
    Intent.STRUCTURE_ANALYSIS: [
        # Main axis
        r"\bhuvudaxel\b",
        r"\bmain\s+axis\b",
        r"\blängs.*axel\b",
        r"\balong.*axis\b",
        r"\bsitter\s+längs\b",
        # Symmetry
        r"\bsymmetri(sk)?(a)?\b",
        r"\bsymmetric(al)?\b",
        r"\bär\s+symmetrisk\b",
        # Critical / mounting
        r"\bkritisk(a)?\b",
        r"\bcritical\b",
        r"\bmontering\b",
        r"\bmounting\b",
        r"\bkritiska\s+för\b",
        # Nested / inside
        r"\binuti\b",
        r"\binside\b",
        r"\bnested\b",
        r"\binnesluten\b",
        r"\benclosed\b",
        r"\bsitter\s+inuti\b",
        # Sub-assemblies
        r"\bsub[\s-]*assembl(y|ies)?\b",
        r"\bdelmontering(ar)?\b",
        r"\bsub[\s-]*group\b",
        r"\bsannolika.*sub\b",
    ],
    
    # =========================================================================
    # Tier 5 - Engineer Copilot (Killer features)
    # =========================================================================
    Intent.ENGINEER_COPILOT: [
        # Next steps
        r"\bnästa\s+(rimliga\s+)?steg\b",
        r"\bnext\s+steps?\b",  # "next step" or "next steps"
        r"\bwhat\s+are\s+the\s+next\s+steps\b",
        r"\bwhat\s+should\s+i\s+do\b",
        r"\bvad\s+bör\s+jag\b",
        r"\brekommendation\b",
        r"\brecommend(ation)?\b",
        r"\britningsarbete(t)?\b",
        # Missing views
        r"\bsaknas.*vy\b",
        r"\bmissing.*view\b",
        r"\bvilka\s+vyer\s+saknas\b",
        r"\bvyer\s+saknas\b",
        # Tolerances
        r"\btolerans(er)?\b",
        r"\btolerance\b",
        r"\bkräver\s+tolerans\b",
        r"\brequire.*tolerance\b",
        r"\bdelar\s+kräver\b",
        # Dimensioning (but not "dimensioneras" which is DETAIL_DRAWINGS)
        r"\bdimensioner(ing)?\b",
        r"\bmått\b",
        r"\bmeasure\b",
    ],
    
    # =========================================================================
    # Overview / General
    # =========================================================================
    Intent.OVERVIEW: [
        r"\bberätta\s+om\b",
        r"\btell\s+me\s+about\b",
        r"\bdescribe\b",
        r"\bbeskriv\b",
        r"\böversikt\b",
        r"\boverview\b",
        r"\bsummary\b",
        r"\bsammanfattning\b",
        r"\bwhat\s+is\s+this\b",
        r"\bvad\s+är\s+det(ta)?\b",
        r"\bgeneral\s+info\b",
        r"\ballmän\s+info\b",
    ],
}


def _extract_top_n(question: str) -> int:
    """Extract numeric N from 'top N' or 'topp N' pattern. Default 5."""
    match = re.search(r"(?:top|topp)\s*(\d+)", question, re.IGNORECASE)
    if match:
        return min(int(match.group(1)), 20)  # Cap at 20
    # Check for Swedish ordinal: "störst" alone usually means top 1
    if re.search(r"\bstörst[ae]?\b", question, re.IGNORECASE):
        if "topp" not in question.lower() and "top" not in question.lower():
            return 5
    return 5


def _detect_metric(question: str) -> str:
    """Detect size metric preference: volume or bbox."""
    q = question.lower()
    if "bbox" in q or "bounding" in q:
        return "bbox"
    return "volume"


def _detect_view_type(question: str) -> Optional[str]:
    """Detect specific view type mentioned."""
    q = question.lower()
    views = ["front", "top", "right", "left", "iso", "isometric", "back", "bottom"]
    for v in views:
        if v in q:
            return v if v != "isometric" else "iso"
    return None


def _detect_geometry_subtype(question: str) -> str:
    """Detect which geometry analysis subtype is being asked about."""
    q = question.lower()
    if any(x in q for x in ["lång", "hög", "bred", "aspect", "proportion", "longer", "taller", "wider"]):
        return "aspect_ratio"
    if any(x in q for x in ["referens", "reference", "plane", "axis"]):
        return "reference_geometry"
    if any(x in q for x in ["små", "small", "liten"]):
        return "small_parts"
    if any(x in q for x in ["avviker", "outlier", "skala", "scale"]):
        return "scale_outliers"
    if any(x in q for x in ["extrem", "misstänkt", "suspicious", "unusual", "ovanlig"]):
        return "extreme_geometry"
    if any(x in q for x in ["dolda", "hidden", "orientering", "orientation"]):
        return "hidden_lines"
    return "general"


def _detect_structure_subtype(question: str) -> str:
    """Detect which structure analysis subtype is being asked about."""
    q = question.lower()
    if any(x in q for x in ["huvudaxel", "main axis", "längs"]):
        return "main_axis"
    if any(x in q for x in ["symmetri", "symmetric"]):
        return "symmetry"
    if any(x in q for x in ["kritisk", "critical", "montering", "mounting"]):
        return "critical_parts"
    if any(x in q for x in ["inuti", "inside", "nested", "innesluten"]):
        return "nested_parts"
    if any(x in q for x in ["sub-assembl", "delmontering", "sub-group"]):
        return "sub_assemblies"
    return "general"


def _detect_copilot_subtype(question: str) -> str:
    """Detect which copilot advice subtype is being asked about."""
    q = question.lower()
    if any(x in q for x in ["nästa", "next", "steg", "step"]):
        return "next_steps"
    if any(x in q for x in ["saknas", "missing"]) and "vy" in q:
        return "missing_views"
    if any(x in q for x in ["tolerans", "tolerance"]):
        return "tolerances"
    if any(x in q for x in ["dimension", "mått"]):
        return "dimensioning"
    if any(x in q for x in ["ignorera", "ignore", "första", "first"]):
        return "ignore_parts"
    return "general"


def route(question: str) -> IntentResult:
    """
    Classify a question into an intent with confidence score.
    
    Args:
        question: Natural language question
        
    Returns:
        IntentResult with intent enum, confidence, and extracted params
    """
    if not question:
        return IntentResult(intent=Intent.FALLBACK, confidence=0.0)
    
    q_lower = question.lower().strip()
    intent_scores: Dict[Intent, float] = {i: 0.0 for i in Intent}
    
    # Score each intent based on pattern matches
    for intent, patterns in _INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q_lower, re.IGNORECASE):
                intent_scores[intent] += 1.0
    
    # Find best scoring intent
    best_intent = max(intent_scores, key=intent_scores.get)
    best_score = intent_scores[best_intent]
    
    # Normalize confidence (0-1 scale)
    total_matches = sum(intent_scores.values())
    if total_matches > 0:
        confidence = best_score / max(total_matches, 1)
    else:
        confidence = 0.0
    
    # Fallback if no patterns matched or confidence too low
    if best_score == 0 or confidence < 0.3:
        return IntentResult(intent=Intent.FALLBACK, confidence=confidence)
    
    # Extract intent-specific parameters
    params: Dict[str, Any] = {}
    
    if best_intent == Intent.LARGEST_PARTS:
        params["top_n"] = _extract_top_n(question)
        params["metric"] = _detect_metric(question)
        
    elif best_intent == Intent.REPETITIVE_PARTS:
        params["top_n"] = _extract_top_n(question)
        # Check for fastener-specific query
        fastener_patterns = [r"\bfastener\b", r"\bfästelement\b", r"\bskruv\b", r"\bscrew\b", 
                           r"\bbolt\b", r"\bbulong\b", r"\bnut\b", r"\bmutter\b", r"\bstandard"]
        params["filter_fasteners"] = any(re.search(p, q_lower) for p in fastener_patterns)
        
    elif best_intent == Intent.BEST_VIEWS:
        params["view_type"] = _detect_view_type(question)
        params["explain_why"] = True  # Always explain reasoning
        
    elif best_intent == Intent.GEOMETRY_ANALYSIS:
        params["subtype"] = _detect_geometry_subtype(question)
        
    elif best_intent == Intent.STRUCTURE_ANALYSIS:
        params["subtype"] = _detect_structure_subtype(question)
        
    elif best_intent == Intent.ENGINEER_COPILOT:
        params["subtype"] = _detect_copilot_subtype(question)
        
    elif best_intent == Intent.WARNINGS_ERRORS:
        params["max_errors"] = 5
        
    elif best_intent == Intent.DETAIL_DRAWINGS:
        params["include_reasoning"] = True
    
    return IntentResult(
        intent=best_intent,
        confidence=min(confidence + 0.3, 1.0),  # Boost confidence for matched intent
        params=params,
    )


def is_deterministic_intent(intent: Intent) -> bool:
    """
    Check if an intent can be answered deterministically from snapshot data.
    If True, no retrieval/embeddings needed.
    """
    return intent in {
        Intent.COUNT_PARTS,
        Intent.LARGEST_PARTS,
        Intent.REPETITIVE_PARTS,
        Intent.BEST_VIEWS,
        Intent.BOM_QUESTIONS,
        Intent.DETAIL_DRAWINGS,
        Intent.GEOMETRY_ANALYSIS,
        Intent.WARNINGS_ERRORS,
        Intent.STRUCTURE_ANALYSIS,
        Intent.ENGINEER_COPILOT,
        Intent.OVERVIEW,
    }
