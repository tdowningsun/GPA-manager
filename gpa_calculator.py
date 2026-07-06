"""Pure GPA computation logic for GPA Manager v1.2.

No I/O and no global state. This module only converts scores to grade
points and computes weighted GPA from a list of courses.
"""

from typing import Optional

from data import SCORE_RANGES, TEXT_RULES, Course

ScoreInput = str | int | float


def convert_score(score: ScoreInput) -> Optional[float]:
    """Convert a raw score into its GPA grade point.

    Numeric values are matched against :data:`SCORE_RANGES`; textual
    descriptors (``及格``, ``中等``, ``良好``, ``优秀``) are matched
    against :data:`TEXT_RULES`.

    Args:
        score: Numeric value (``int``/``float``/numeric string) or a
            textual descriptor from :data:`TEXT_RULES`.

    Returns:
        The matching grade point, or ``None`` if the input cannot be
        parsed or falls outside the defined ranges.
    """
    if isinstance(score, str):
        if score in TEXT_RULES:
            return TEXT_RULES[score]
        try:
            score = float(score)
        except ValueError:
            return None

    if not isinstance(score, (int, float)) or score < 0:
        return None

    for low, high, point in SCORE_RANGES:
        if low <= score <= high:
            return point
    return None


def calculate_gpa(courses: list[Course]) -> float:
    """Compute the weighted GPA over a list of courses.

    Formula: ``sum(credit * point) / sum(credit)``.

    Args:
        courses: Course records. Each entry must provide ``credit``
            and ``point``.

    Returns:
        The weighted GPA as a float. Returns ``0.0`` when total credit
        is zero.
    """
    total_credits = sum(course["credit"] for course in courses)
    if total_credits == 0:
        return 0.0
    weighted_sum = sum(
        course["credit"] * course["point"] for course in courses
    )
    return weighted_sum / total_credits