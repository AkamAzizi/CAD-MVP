"""
Configuration defaults for report generation.
"""

# Complexity thresholds
COMPLEXITY_HIGH_THRESHOLD = 70
COMPLEXITY_MEDIUM_THRESHOLD = 50

# Fastener detection
FASTENER_KEYWORDS = ["bolt", "screw", "washer", "nut", "fastener", "rivet", "pin"]
FASTENER_COUNT_WARNING_THRESHOLD = 20
FASTENER_VARIETY_WARNING_THRESHOLD = 5

# Repetition
REPETITION_MIN_QTY = 3

# Size extremes
VOLUME_DOMINANCE_THRESHOLD = 0.5  # Largest part > 50% of total volume
MIN_VOLUME_THRESHOLD_MM3 = 1.0  # Very small parts threshold

# Report output
REPORT_VERSION = "1.0"
DEFAULT_SHEET_UNITS = "mm"

# Reference geometry detection
REFERENCE_GEOMETRY_KEYWORDS = [
    "axis", "plane", "origin", "datum", "sketch", "coordinate", "csys", "reference",
    "x-axis", "y-axis", "z-axis", "xy-plane", "xz-plane", "yz-plane"
]
MAX_REALISTIC_VOLUME_MM3 = 1e12  # 1 cubic meter = 1e9 mm³, so 1e12 is extremely large
