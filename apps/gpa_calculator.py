"""Pure GPA computation logic for GPA Manager.

No I/O and no global state. This module only converts scores to grade
points (using the rules loaded by :func:`data.load_gpa_scale`) and
computes weighted GPA from a list of courses.

Each loaded rule is a dict of the form::

    {
        "gpa":         <float>,         # required
        "score_range": [<min>, <max>], # optional
        "aliases":     [<str>, ...],    # optional
    }

The matching algorithm follows the spec:

* Numeric input  -> iterate the rules and pick the first whose
                    ``score_range`` contains the value.
* Text input     -> iterate the rules and pick the first whose
                    ``aliases`` list contains the value.

A rule may have only ``score_range``, only ``aliases``, or both.
Rules without the field relevant to the input are skipped.
"""

from typing import Optional

from data import _loaded_linear, _loaded_rules, Course

ScoreInput = str | int | float


def convert_score(score: ScoreInput) -> Optional[float]:
    """Convert a raw score into its GPA grade point.

    The matching algorithm follows the spec:

    1. If the input is a string, it is first matched against each
       rule's ``aliases`` list. A literal match wins immediately.
    2. If the string did not match any alias, the function tries to
       coerce it to a number and falls through to the numeric
       ``score_range`` lookup. (This preserves backward compatibility
       for callers that pass numeric strings such as ``"75"``.)
    3. If the input is already a number, it is used directly in the
       numeric ``score_range`` lookup.
    4. Anything that does not resolve returns ``None``.

    Args:
        score: Numeric value (``int`` / ``float`` / numeric string) or
            a textual descriptor listed in some rule's ``aliases``.

    Returns:
        The matching grade point, or ``None`` if the input cannot be
        parsed or no rule matches it.
    """
    # 1. Try literal string match against any rule's aliases.
    if isinstance(score, str):
        for rule in _loaded_rules:
            for alias in rule.get("aliases", ()):
                if score == alias:
                    return rule["gpa"]
        # 2. No alias match: try to coerce the string to a number and
        # fall through to the numeric score_range lookup.
        try:
            numeric = float(score)
        except (TypeError, ValueError):
            return None
    elif isinstance(score, (int, float)):
        # 3. Direct numeric input.
        numeric = float(score)
    else:
        # 4. Unrecognised type.
        return None

    if numeric < 0:
        return None

    # Numeric score_range lookup. Range rules belong to range mode -
    # in linear mode they would pre-empt the linear interpolation
    # (because the for-loop returns on the first hit), so we skip
    # them whenever ``_loaded_linear`` is active. The loader already
    # keeps range rules out of ``_loaded_rules`` when ``numeric.mode
    # == "linear"``; this guard makes the contract hold even when
    # linear is manually activated between loads (e.g. via a test
    # that loads a range-mode config first and then populates
    # ``_loaded_linear`` directly).
    if not _loaded_linear:
        for rule in _loaded_rules:
            score_range = rule.get("score_range")
            if score_range is None:
                continue
            try:
                lo, hi = float(score_range[0]), float(score_range[1])
            except (TypeError, ValueError, IndexError):
                continue
            if lo <= numeric <= hi:
                return rule["gpa"]

    # Linear mode. ``_loaded_linear`` is a separate, parallel field
    # (see :mod:`data`) populated when ``numeric.mode == "linear"``.
    # The dict is mutated in place by the loader, so its empty /
    # non-empty state reliably reflects the active mode. Linear
    # interpolation between the two anchor points covers scores
    # strictly inside ``[min_score, max_score]``; scores outside
    # that range return ``None`` (no defined GPA).
    if _loaded_linear:
        try:
            min_s = float(_loaded_linear["min_score"])
            max_s = float(_loaded_linear["max_score"])
            min_g = float(_loaded_linear["min_gpa"])
            max_g = float(_loaded_linear["max_gpa"])
        except (KeyError, TypeError, ValueError):
            return None
        if min_s <= numeric <= max_s and max_s != min_s:
            return min_g + (max_g - min_g) * (numeric - min_s) / (max_s - min_s)
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
