"""
Engineering Report Generator: Creates PDF and JSON reports from assembly snapshots.
"""

from .builder import ReportBuilder
from .models import Report, ReportMeta, ReportOverview, BOMItem, Insight, ManufacturingHint, HealthCheck, ReferenceGeometryItem
from .complexity import compute_complexity_score
from .rules import generate_insights

__all__ = [
    "ReportBuilder",
    "Report",
    "ReportMeta",
    "ReportOverview",
    "BOMItem",
    "Insight",
    "ManufacturingHint",
    "HealthCheck",
    "ReferenceGeometryItem",
    "compute_complexity_score",
    "generate_insights",
]
