"""Command-line entry point for GPA Manager v2.0.

This module owns all user interaction: prompts, input validation, and
output rendering. Calculation logic is delegated to
:mod:`gpa_calculator`.

The input workflow is split into three clear steps:
    1. Collect course names.
    2. Collect credits for each course.
    3. Collect scores for each course.
"""

from data import Course
import data
from gpa_calculator import calculate_gpa, convert_score

# Load the GPA scale from disk before any conversion happens. See
# ``data.load_gpa_scale`` for the loader's contract.
data.load_gpa_scale()

EXIT_SENTINEL = "end"
AFFIRMATIVE_RESPONSES: tuple[str, ...] = ("y", "yes")
NEGATIVE_RESPONSES: tuple[str, ...] = ("n", "no")

STEP_HEADER_NAMES = "Step 1/3 - Enter Course Names"
STEP_HEADER_CREDITS = "Step 2/3 - Enter Credits"
STEP_HEADER_SCORES = "Step 3/3 - Enter Scores"


def ask_to_start() -> bool:
    """Prompt the user to confirm whether to begin GPA calculation.

    Accepts ``y``/``yes`` or ``n``/``no`` (case-insensitive). Re-prompts
    on any other input.

    Returns:
        ``True`` if the user opted in, ``False`` otherwise.
    """
    while True:
        choice = input("Do you want to calculate GPA? (y/n): ").strip().lower()
        if choice in AFFIRMATIVE_RESPONSES:
            return True
        if choice in NEGATIVE_RESPONSES:
            return False
        print("Please enter y or n.")


def _read_credit(course_name: str) -> float:
    """Read a positive credit value for a specific course.

    Re-prompts on invalid input. The course name is embedded in the
    prompt so the user always knows which course they are filling in.

    Args:
        course_name: Name of the course this credit belongs to.

    Returns:
        A positive credit value as a float.
    """
    while True:
        raw = input(f"Credit for {course_name}: ").strip()
        try:
            value = float(raw)
        except ValueError:
            print(f"Invalid credit '{raw}'. Please enter a number.")
            continue
        if value <= 0:
            print("Credit must be greater than 0.")
            continue
        return value


def _read_score(course_name: str) -> tuple[str, float]:
    """Read a score for a specific course and resolve its grade point.

    Re-prompts on invalid input. The course name is embedded in the
    prompt so the user always knows which course they are filling in.

    Args:
        course_name: Name of the course this score belongs to.

    Returns:
        A ``(score, point)`` tuple where ``score`` is the raw input
        string and ``point`` is the resolved grade point.
    """
    while True:
        score = input(
            f"Score for {course_name} (number or text: 及格/中等/良好/优秀): "
        ).strip()
        point = convert_score(score)
        if point is not None:
            return score, point
        print(f"Invalid score '{score}'. Please try again.")


def _print_step_header(title: str) -> None:
    """Print a step banner with surrounding blank lines for visual separation."""
    print()
    print(title)
    print()


def _print_courses_summary(names: list[str]) -> None:
    """Print a numbered summary of the courses entered in Step 1."""
    print()
    print("Courses Entered:")
    for index, name in enumerate(names, start=1):
        print(f"{index}. {name}")
    print()
    print(f"Total Courses: {len(names)}")


def read_course_names() -> list[str]:
    """Step 1/3: collect course names from the user.

    The user is prompted with an incrementing ``Course N:`` label.
    Typing ``end`` finishes this step. Empty names are rejected and
    re-prompted. After the user finishes, a numbered summary of all
    entered courses is printed.

    Returns:
        A list of course names in the order they were entered. Empty
        when the user types ``end`` immediately.
    """
    names: list[str] = []
    _print_step_header(STEP_HEADER_NAMES)
    while True:
        name = input(f"Course {len(names) + 1}: ").strip()
        if name.lower() == EXIT_SENTINEL:
            break
        if not name:
            print("Course name cannot be empty.")
            continue
        names.append(name)

    if names:
        _print_courses_summary(names)
    return names


def read_credits(names: list[str]) -> list[float]:
    """Step 2/3: collect credits for each previously entered name.

    For every course the user is prompted with ``Credit for <name>:``
    so they immediately know which course they are entering. Invalid
    values are re-prompted until a positive number is provided.

    Args:
        names: Course names collected in Step 1.

    Returns:
        A list of credit floats aligned by index with ``names``.
    """
    _print_step_header(STEP_HEADER_CREDITS)
    credits: list[float] = []
    for index, name in enumerate(names):
        if index > 0:
            print()
        credits.append(_read_credit(name))
    return credits


def read_scores(names: list[str]) -> list[tuple[str, float]]:
    """Step 3/3: collect scores for each previously entered name.

    For every course the user is prompted with ``Score for <name>:``
    so they immediately know which course they are entering. Invalid
    scores are re-prompted until a valid value is provided.

    Args:
        names: Course names collected in Step 1.

    Returns:
        A list of ``(raw_score, grade_point)`` tuples aligned by index
        with ``names``.
    """
    _print_step_header(STEP_HEADER_SCORES)
    scores: list[tuple[str, float]] = []
    for index, name in enumerate(names):
        if index > 0:
            print()
        scores.append(_read_score(name))
    return scores


def build_courses(
    names: list[str],
    credits: list[float],
    scores: list[tuple[str, float]],
) -> list[Course]:
    """Assemble :class:`Course` records from the three collected streams.

    Args:
        names: Course names from Step 1.
        credits: Credit values from Step 2.
        scores: ``(raw_score, grade_point)`` pairs from Step 3.

    Returns:
        A list of fully populated :class:`Course` records.
    """
    courses: list[Course] = []
    for name, credit, (raw_score, point) in zip(names, credits, scores):
        courses.append({
            "name": name,
            "credit": credit,
            "score": raw_score,
            "point": point,
        })
    return courses


def collect_courses() -> list[Course]:
    """Orchestrate the three-step interactive input flow.

    Runs Step 1 (names), then Step 2 (credits), then Step 3 (scores),
    and finally assembles the data into :class:`Course` records. If
    Step 1 yields no names, the remaining steps are skipped and an
    empty list is returned.

    Returns:
        A list of :class:`Course` records, or an empty list when the
        user provides no course names.
    """
    names = read_course_names()
    if not names:
        return []
    credits = read_credits(names)
    scores = read_scores(names)
    return build_courses(names, credits, scores)


def _compute_column_widths(courses: list[Course]) -> tuple[int, int]:
    """Compute display widths for the course table columns.

    Returns:
        A ``(name_width, numeric_width)`` tuple. ``numeric_width`` is
        shared by the credit, score, and grade-point columns so the
        table stays visually balanced.
    """
    name_width = max((len(course["name"]) for course in courses), default=0)
    name_width = max(name_width, len("Course Name"))
    numeric_width = max(len("Credit"), len("Score"), len("Grade Point"))
    return name_width, numeric_width


def print_table(courses: list[Course]) -> None:
    """Render the course list as an aligned text table.

    Args:
        courses: Course records to display. An empty list still
            produces the header row.
    """
    name_w, num_w = _compute_column_widths(courses)

    header = (
        f"{'Course Name':<{name_w}} | "
        f"{'Credit':>{num_w}} | "
        f"{'Score':<{num_w}} | "
        f"{'Grade Point':>{num_w}}"
    )
    separator = "-" * len(header)
    print(separator)
    print(header)
    print(separator)
    for course in courses:
        print(
            f"{course['name']:<{name_w}} | "
            f"{course['credit']:>{num_w}} | "
            f"{str(course['score']):<{num_w}} | "
            f"{course['point']:>{num_w}.1f}"
        )
    print(separator)


def main() -> None:
    """Run the GPA Manager CLI end-to-end."""
    if not ask_to_start():
        print("Goodbye.")
        return

    courses = collect_courses()
    if not courses:
        print("No courses entered. GPA cannot be calculated.")
        return

    gpa = calculate_gpa(courses)

    print()
    print("=== Course Results ===")
    print_table(courses)
    print()
    print(f"Overall GPA: {gpa:.2f}")


if __name__ == "__main__":
    main()
