"""Command-line entry point for GPA Manager v1.2.

This module owns all user interaction: prompts, input validation, and
output rendering. Calculation logic is delegated to
:mod:`gpa_calculator`.
"""

from data import Course
from gpa_calculator import calculate_gpa, convert_score

EXIT_SENTINEL = "end"
AFFIRMATIVE_RESPONSES: tuple[str, ...] = ("y", "yes")
NEGATIVE_RESPONSES: tuple[str, ...] = ("n", "no")


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


def _read_credit() -> float:
    """Read a positive credit value, re-prompting on invalid input.

    Returns:
        A positive credit value as a float.
    """
    while True:
        raw = input("Credit: ").strip()
        try:
            value = float(raw)
        except ValueError:
            print(f"Invalid credit '{raw}'. Please enter a number.")
            continue
        if value <= 0:
            print("Credit must be greater than 0.")
            continue
        return value


def _read_score() -> tuple[str, float]:
    """Read a score and resolve its grade point, re-prompting on invalid input.

    Returns:
        A ``(score, point)`` tuple where ``score`` is the raw input
        string and ``point`` is the resolved grade point.
    """
    while True:
        score = input("Score (number or text: 及格/中等/良好/优秀): ").strip()
        point = convert_score(score)
        if point is not None:
            return score, point
        print(f"Invalid score '{score}'. Please try again.")


def collect_courses() -> list[Course]:
    """Interactively collect course records from the user.

    The user is asked for course name, credit, and score in a loop
    until they type ``end`` as the course name. Invalid credit or
    score entries are re-prompted so the current course is never lost.

    Returns:
        A list of :class:`~data.Course` records.
    """
    courses: list[Course] = []
    print(f'Enter course details. Type "{EXIT_SENTINEL}" as the course name to finish.')
    while True:
        name = input("Course name: ").strip()
        if name.lower() == EXIT_SENTINEL:
            break
        if not name:
            print("Course name cannot be empty.")
            continue

        credit = _read_credit()
        score, point = _read_score()

        course: Course = {
            "name": name,
            "credit": credit,
            "score": score,
            "point": point,
        }
        courses.append(course)
        print(f"Added: {name} | Credit {credit} | Score {score} | Point {point}")
    return courses


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