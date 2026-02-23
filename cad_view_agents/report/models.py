"""
Pydantic models for Engineering Report JSON schema.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class ReportMeta(BaseModel):
    """Report metadata."""
    assembly_id: str
    file_name: Optional[str] = None
    generated_at_iso: str = Field(default_factory=lambda: datetime.now().isoformat())
    version: str = "1.0"
    source_snapshot_path: str


class BBoxMM(BaseModel):
    """Bounding box in millimeters."""
    x: float
    y: float
    z: float


class ReportOverview(BaseModel):
    """Overview metrics."""
    total_parts: int
    unique_parts: int
    repeated_parts: int
    bbox_mm: Optional[BBoxMM] = None
    complexity_score_0_100: int = Field(ge=0, le=100)


class BOMItem(BaseModel):
    """BOM entry."""
    item_no: int
    part_name: str
    qty: int
    material: Optional[str] = None
    volume_mm3: Optional[float] = None
    bbox_mm: Optional[BBoxMM] = None
    category: Optional[str] = None


class Insight(BaseModel):
    """Structured insight."""
    severity: Literal["info", "warn", "risk"]
    title: str
    details: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class ManufacturingHint(BaseModel):
    """Manufacturing hint."""
    title: str
    details: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class HealthCheck(BaseModel):
    """Health check result."""
    score_0_100: int = Field(ge=0, le=100)
    warnings: List[str] = Field(default_factory=list)


class RepetitionData(BaseModel):
    """Repetition metrics."""
    top_repeated: List[Dict[str, Any]] = Field(default_factory=list)
    repeated_share_pct: float = Field(ge=0.0, le=100.0)


class ReferenceGeometryItem(BaseModel):
    """Reference geometry item (excluded from manufacturing analysis)."""
    part_name: str
    part_id: Optional[str] = None
    reason: str  # Why it's considered reference geometry


class Report(BaseModel):
    """Top-level report model."""
    meta: ReportMeta
    overview: ReportOverview
    bom: List[BOMItem] = Field(default_factory=list)
    largest_parts: List[Dict[str, Any]] = Field(default_factory=list)
    repetition: RepetitionData
    insights: List[Insight] = Field(default_factory=list)
    manufacturing_hints: List[ManufacturingHint] = Field(default_factory=list)
    health_check: HealthCheck
    next_steps: List[str] = Field(default_factory=list)
    reference_geometry: List[ReferenceGeometryItem] = Field(default_factory=list)