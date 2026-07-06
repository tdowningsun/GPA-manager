"""Static configuration and shared domain types for GPA Manager v1.2.

This module is the single source of truth for the grading rules and
the :class:`Course` data structure. No business logic lives here.
"""

from typing import Final, TypedDict


class Course(TypedDict):
    """A single course record.

    Attributes:
        name: Course name as entered by the user.
        credit: Course credit value (positive number).
        score: Raw score input, either a numeric string or a textual
            descriptor from :data:`TEXT_RULES`.
        point: Resolved GPA grade point for the score.
    """

    name: str
    credit: float
    score: str
    point: float


# Numeric score ranges mapped to grade points.
# Each tuple is (lower_bound_inclusive, upper_bound_inclusive, grade_point).
SCORE_RANGES: Final[list[tuple[int, int, float]]] = [
    (0, 59, 0.0),
    (60, 69, 1.0),
    (70, 79, 2.0),
    (80, 89, 3.0),
    (90, 99, 4.0),
    (100, 100, 5.0),
]

# Textual score descriptors mapped to grade points.
TEXT_RULES: Final[dict[str, float]] = {
    "及格": 1.0,
    "中等": 2.0,
    "良好": 3.0,
    "优秀": 4.0,
}