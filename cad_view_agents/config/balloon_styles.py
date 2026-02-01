"""
Balloon style configurations.
"""
from dataclasses import dataclass


@dataclass
class BalloonStyle:
    """Balloon appearance configuration."""
    circle_radius: float = 5.0  # mm
    line_width: float = 0.5  # mm
    text_height: float = 3.5  # mm
    leader_line_width: float = 0.35  # mm
    leader_arrow_size: float = 2.0  # mm


# Standard balloon styles
SIMPLE_BALLOON = BalloonStyle(
    circle_radius=5.0,
    line_width=0.5,
    text_height=3.5,
    leader_line_width=0.35,
    leader_arrow_size=2.0
)

STANDARD_BALLOON = BalloonStyle(
    circle_radius=6.0,
    line_width=0.5,
    text_height=4.0,
    leader_line_width=0.4,
    leader_arrow_size=2.5
)
